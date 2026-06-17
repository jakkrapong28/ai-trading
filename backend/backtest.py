"""
Backtest engine — แยกกลยุทธ์ Trend / Reversal, ใช้ OHLC ATR จริง
Usage:
  python backend/backtest.py run XAUUSD
  python backend/backtest.py optimize
  python backend/backtest.py optimize BTCUSDT
  python backend/backtest.py walkforward XAUUSD   # full report
  python backend/backtest.py validate XAUUSD      # gate; exit 0=pass / 1=fail
"""
import sys
import os
import asyncio
import copy
import httpx
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core import (
    get_market_indicators,
    evaluate_strategy_rules,
    evaluate_trend_following,
    evaluate_reversal,
    calculate_position_size,
    calculate_performance_metrics,
    compute_macro_trend_from_closes,
    trade_pnl,
    get_strategy_config,
    STRATEGY_CONFIG,
    SYMBOLS,
    RISK_CONFIG,
    YAHOO_SYMBOL_MAP,
)

BACKTEST_SYMBOLS = ["XAUUSD", "BTCUSDT", "ETHUSDT"]
EQUITY = RISK_CONFIG["equity"]
ATR_MULT = 2.0
RR_RATIO = 2.0

# Per-window OOS pass criteria for the walk-forward validation gate.
WALK_FORWARD_PASS_CRITERIA = {
    "sharpe_ratio": 1.0,
    "profit_factor": 1.3,
    "max_drawdown": 15.0,   # percent
    "risk_of_ruin": 0.05,   # 5%
}
# A symbol passes the gate when at least this share of OOS windows pass, with a
# minimum number of windows so a single lucky window can't green-light a flag.
WALK_FORWARD_MIN_PASS_RATIO = 60.0
WALK_FORWARD_MIN_WINDOWS = 3
# A window with fewer than this many OOS trades is statistically meaningless — a
# 2-trade window can post Sharpe 2600 / PF 99 on pure luck. Such "thin" windows
# can NEVER pass (they only ever make the gate stricter), so noise can't
# green-light a flag. See the walk-forward report's tiny-trade windows.
WALK_FORWARD_MIN_TRADES = 5

SPREAD_COST_DICT = {
    "XAUUSD": 25.0,
    "BTCUSDT": 10.0,
    "ETHUSDT": 8.0,
    "EURUSD": 2.0,
}
COMMISSION_PCT = {
    "XAUUSD": 0.0,
    "BTCUSDT": 0.0001,  # 0.01%
}

def apply_trade_costs(trade: dict, symbol: str) -> dict:
    spread_cost = SPREAD_COST_DICT.get(symbol, 5.0) * trade.get("lot", 0.01)
    commission = abs(trade.get("pnl", 0.0)) * COMMISSION_PCT.get(symbol, 0.0)
    trade["pnl"] = trade.get("pnl", 0.0) - spread_cost - commission
    trade["costs"] = {"spread": spread_cost, "commission": commission}
    return trade

async def fetch_backtest_data(symbol: str, interval: str = "1h", range_val: str = "60d") -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_val}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, timeout=15.0)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to fetch {symbol}: HTTP {r.status_code}")

        result = r.json().get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]

        df = pd.DataFrame({
            "timestamp": [datetime.fromtimestamp(t) for t in timestamps],
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", []),
        })
        return df.dropna().reset_index(drop=True)

def _macro_trend_at_bar(df: pd.DataFrame, i: int, lookback: int = 48) -> Optional[str]:
    start = max(0, i - lookback)
    closes = df["close"].iloc[start:i + 1].astype(float).tolist()
    return compute_macro_trend_from_closes(closes)

def calculate_risk_of_ruin(pnls: List[float], initial_equity: float = 45750.00, ruin_fraction: float = 0.3, num_paths: int = 5000, path_len: int = 50, seed: int = 12345) -> float:
    if not pnls:
        return 0.0
    pnl_array = np.array(pnls)
    if len(pnl_array) == 0:
        return 0.0
    # Seeded Monte Carlo so Risk-of-Ruin is REPRODUCIBLE — identical on any run
    # and any machine (Mac/Windows) for the same trade list. Was np.random
    # (global, unseeded) → a different number every run.
    rng = np.random.default_rng(seed)
    choices = rng.choice(pnl_array, size=(num_paths, path_len), replace=True)
    cum_pnls = np.cumsum(choices, axis=1)
    equity_paths = initial_equity + cum_pnls
    min_equity_per_path = np.min(equity_paths, axis=1)
    ruined_paths = min_equity_per_path <= initial_equity * (1 - ruin_fraction)
    return float(np.sum(ruined_paths)) / num_paths

def optimize_smc_parameters(
    df: pd.DataFrame,
    symbol: str,
    smc_v2: bool = False,
) -> Dict[str, Any]:
    best_score = -1.0
    best_cfg = {
        "smc_strategy": True,
        "smc_v2": smc_v2,
        "ob_size_atr": 0.5,
        "fvg_gap_atr": 0.3,
        "mtf_strategy": True
    }
    best_result = None

    # Sweep ob_size_atr from 0.4 to 0.7, fvg_gap_atr from 0.2 to 0.4
    ob_range = [0.4, 0.5, 0.6, 0.7]
    fvg_range = [0.2, 0.25, 0.3, 0.35, 0.4]

    for ob in ob_range:
        for fvg in fvg_range:
            cfg = {
                "smc_strategy": True,
                "smc_v2": smc_v2,
                "ob_size_atr": ob,
                "fvg_gap_atr": fvg,
                "mtf_strategy": True
            }
            result = run_strategy_backtest(df, symbol, cfg=cfg)
            m = result["metrics"]
            if m["total_trades"] < 3:
                continue
            
            pf = min(m["profit_factor"], 5.0)
            wr = m["win_rate"] / 100.0
            dd_penalty = 1.0 - min(m["max_drawdown"] / 30.0, 0.5)
            score = wr * pf * dd_penalty * (1 + m["total_trades"] / 100)
            if score > best_score:
                best_score = score
                best_cfg = cfg
                best_result = result
                
    return {
        "symbol": symbol,
        "best_config": best_cfg,
        "best_score": round(best_score, 4),
        "result": best_result
    }

def run_strategy_backtest(
    df: pd.DataFrame,
    symbol: str,
    strategy_filter: Optional[str] = None,
    cfg: Optional[Dict] = None,
    use_mtf: bool = True,
    equity: float = EQUITY,
) -> Dict[str, Any]:
    """รัน backtest ต่อกลยุทธ์ — ใช้ OHLC ATR + dynamic lot sizing"""
    cfg = cfg or get_strategy_config(symbol)
    trades: List[Dict] = []
    active_trade = None
    warmup = 50

    # Backtest circuit breaker — mirrors the live circuit_breaker_v2 so the
    # walk-forward sees realistic robustness: after `cb_max_losses` consecutive
    # losers, stop opening trades for `cb_cooldown_bars` bars. Caps the
    # catastrophic OOS windows the stateless live system would never sit through.
    cb_max_losses = cfg.get("cb_max_losses", 0)
    cb_cooldown_bars = cfg.get("cb_cooldown_bars", 24)
    consec_losses = 0
    cooldown_until = -1

    for i in range(warmup, len(df)):
        row = df.iloc[i]

        if active_trade:
            high, low = float(row["high"]), float(row["low"])
            hit_sl = hit_tp = False
            if active_trade["action"] == "BUY":
                if low <= active_trade["stop_loss"]:
                    hit_sl = True
                elif high >= active_trade["take_profit"]:
                    hit_tp = True
            else:
                if high >= active_trade["stop_loss"]:
                    hit_sl = True
                elif low <= active_trade["take_profit"]:
                    hit_tp = True

            if hit_sl or hit_tp:
                exit_price = active_trade["stop_loss"] if hit_sl else active_trade["take_profit"]
                pnl = trade_pnl(symbol, active_trade["action"], active_trade["entry_price"], exit_price, active_trade["lot"])
                active_trade.update({
                    "exit_price": exit_price,
                    "exit_time": row["timestamp"],
                    "pnl": pnl,
                    "status": "CLOSED",
                    "result": "SL" if hit_sl else "TP",
                })
                active_trade = apply_trade_costs(active_trade, symbol)
                trades.append(active_trade)
                if active_trade["pnl"] < 0:
                    consec_losses += 1
                    if cb_max_losses and consec_losses >= cb_max_losses:
                        cooldown_until = i + cb_cooldown_bars
                else:
                    consec_losses = 0
                active_trade = None

        if active_trade:
            continue

        # Circuit-breaker cooldown — skip new entries while tripped.
        if cb_max_losses and i < cooldown_until:
            continue

        ohlc_window = df.iloc[max(0, i - 48):i + 1][["open", "high", "low", "close", "volume"]].copy()
        indicators = get_market_indicators(ohlc_window, symbol)
        macro = _macro_trend_at_bar(df, i) if use_mtf else None

        # Real regime (same call the live engine uses) so the backtest exercises
        # the regime-aware reversal gate — what we test == what trades live.
        regime_at_bar = None
        regime_window = df.iloc[max(0, i - 200):i + 1][["open", "high", "low", "close", "volume"]]
        if len(regime_window) >= 50:
            from backend.engines.market_regime import calculate_regime_from_h1
            regime_at_bar, _, _, _, _ = calculate_regime_from_h1(regime_window)

        if cfg and cfg.get("smc_v2", False):
            from backend.core.smc import evaluate_smc_signal
            atr = indicators["atr"]
            ob_size = cfg.get("ob_size_atr", 0.5)
            fvg_gap = cfg.get("fvg_gap_atr", 0.3)
            sig = evaluate_smc_signal(
                ohlc_window, atr, indicators, macro, regime_at_bar,
                ob_size_atr=ob_size, fvg_gap_atr=fvg_gap,
                min_tier=cfg.get("smc_min_tier", "C"),
                require_bias=cfg.get("smc_require_bias", False),
            )
            signal = {
                "action": sig["action"],
                "strategy_type": sig["strategy_type"],
                "confidence": sig["confidence"],
                "sl_anchor": sig.get("sl_anchor"),
            }
        elif cfg and cfg.get("smc_strategy", False):
            from backend.core.smc import detect_smc_concepts, calculate_signal_confidence
            atr = indicators["atr"]
            ob_size = cfg.get("ob_size_atr", 0.5)
            fvg_gap = cfg.get("fvg_gap_atr", 0.3)
            concepts = detect_smc_concepts(ohlc_window, atr, ob_size_atr=ob_size, fvg_gap_atr=fvg_gap)
            d1_aligned = True
            if use_mtf and macro:
                d1_aligned = (macro != "Sideways")
            concepts["d1_aligned"] = d1_aligned
            
            conf = calculate_signal_confidence(concepts)
            action = "WAIT"
            if conf >= 0.55:
                action = "BUY" if indicators.get("ema_fast", 0.0) > indicators.get("ema_slow", 0.0) else "SELL"
                if action == "SELL" and macro == "Bullish":
                    action = "WAIT"
                elif action == "BUY" and macro == "Bearish":
                    action = "WAIT"
            
            signal = {
                "action": action,
                "strategy_type": "SMC",
                "confidence": conf
            }
        else:
            signal = evaluate_strategy_rules(
                indicators, symbol, macro, strategy_filter=strategy_filter, cfg=cfg, regime=regime_at_bar
            )

        if signal["action"] not in ("BUY", "SELL"):
            continue

        entry = float(row["close"])
        atr = indicators["atr"]
        pos = calculate_position_size(symbol, equity, RISK_CONFIG["maxRiskPerTradePct"], atr, ATR_MULT)
        stop_dist = pos["stop_distance"]

        action = signal["action"]
        lot = pos["lot"]
        sl = entry - stop_dist if action == "BUY" else entry + stop_dist

        # Structural stop (SMC v2): anchor SL beyond the zone/swing instead of a
        # symmetric ATR box, then keep dollar-risk constant by scaling the lot.
        # Reject anchors that are absurdly tight (<0.5·ATR) or wide (>2·ATR);
        # fall back to the ATR stop there.
        anchor = signal.get("sl_anchor")
        if anchor is not None:
            buffer = 0.25 * atr
            cand = (anchor - buffer) if action == "BUY" else (anchor + buffer)
            risk = (entry - cand) if action == "BUY" else (cand - entry)
            if 0.5 * stop_dist <= risk <= 2.0 * stop_dist:
                sl = cand
                lot = pos["lot"] * stop_dist / risk

        risk = abs(entry - sl)
        tp = entry + risk * RR_RATIO if action == "BUY" else entry - risk * RR_RATIO
        active_trade = {
            "action": action,
            "strategy_type": signal.get("strategy_type", "UNKNOWN"),
            "entry_price": entry,
            "entry_time": row["timestamp"],
            "stop_loss": sl,
            "take_profit": tp,
            "lot": lot,
            "status": "OPEN",
        }

    closed = [t for t in trades if t.get("status") == "CLOSED"]
    metrics = calculate_performance_metrics(closed)
    return {
        "symbol": symbol,
        "strategy": strategy_filter or ("SMC" if cfg.get("smc_strategy", False) else "COMBINED"),
        "trades": closed,
        "metrics": metrics,
        "config": cfg,
    }

def run_walk_forward_backtest(df: pd.DataFrame, symbol: str, smc_strategy: bool = True, smc_v2: bool = False) -> List[Dict[str, Any]]:
    """Runs a Walk-Forward backtest with 500-bar rolling in-sample and 200-bar out-of-sample windows."""
    in_sample_len = 500
    oos_len = 200
    step_len = 200
    
    results = []
    num_bars = len(df)
    
    for start_idx in range(0, num_bars - in_sample_len, step_len):
        in_sample_end = start_idx + in_sample_len
        oos_end = min(in_sample_end + oos_len, num_bars)
        
        if oos_end <= in_sample_end:
            break
            
        in_sample_df = df.iloc[start_idx:in_sample_end].reset_index(drop=True)
        oos_df = df.iloc[in_sample_end:oos_end].reset_index(drop=True)
        
        # Optimize on In-Sample
        if smc_strategy:
            opt_res = optimize_smc_parameters(in_sample_df, symbol, smc_v2=smc_v2)
        else:
            opt_res = optimize_rsi_thresholds(in_sample_df, symbol)
            
        best_cfg = opt_res["best_config"]
        
        # Validate on Out-of-Sample
        oos_res = run_strategy_backtest(oos_df, symbol, cfg=best_cfg)
        
        # Calculate Risk of Ruin for this OOS window
        trades_pnls = [t["pnl"] for t in oos_res["trades"]]
        ror = calculate_risk_of_ruin(trades_pnls, initial_equity=EQUITY)
        
        oos_metrics = oos_res["metrics"].copy()
        oos_metrics["risk_of_ruin"] = ror
        
        results.append({
            "in_sample_range": (start_idx, in_sample_end),
            "oos_range": (in_sample_end, oos_end),
            "best_config": best_cfg,
            "oos_metrics": oos_metrics,
            "trades_count": len(oos_res["trades"])
        })
        
    return results

def evaluate_walk_forward(
    results: List[Dict[str, Any]],
    pass_criteria: Optional[Dict[str, float]] = None,
    min_pass_ratio: float = WALK_FORWARD_MIN_PASS_RATIO,
    min_windows: int = WALK_FORWARD_MIN_WINDOWS,
    min_trades: int = WALK_FORWARD_MIN_TRADES,
) -> Dict[str, Any]:
    """Pure gate evaluation over walk-forward OOS windows (no I/O — testable).

    Returns pass/fail counts, the overall pass ratio, and a boolean `gate_pass`
    that is True only when enough windows exist AND the ratio clears the bar.

    A window with fewer than ``min_trades`` OOS trades can never pass — its
    Sharpe/PF are small-sample noise — so thin windows only ever tighten the
    gate. Windows that omit ``trades_count`` (synthetic/unit-test inputs) skip
    the trade-count check.
    """
    pc = pass_criteria or WALK_FORWARD_PASS_CRITERIA
    total = len(results)
    passed = 0
    thin = 0
    verdicts: List[bool] = []
    for res in results:
        m = res["oos_metrics"]
        tc = res.get("trades_count")
        enough_trades = tc is None or tc >= min_trades
        if tc is not None and tc < min_trades:
            thin += 1
        pf = m.get("profit_factor", 0.0)
        pf_pass = pf >= pc["profit_factor"] or pf == float("inf")
        sharpe_pass = m.get("sharpe_ratio", 0.0) >= pc["sharpe_ratio"]
        dd_pass = m.get("max_drawdown", 100.0) <= pc["max_drawdown"]
        ror_pass = m.get("risk_of_ruin", 1.0) <= pc["risk_of_ruin"]
        wp = bool(enough_trades and pf_pass and sharpe_pass and dd_pass and ror_pass)
        verdicts.append(wp)
        passed += wp
    ratio = (passed / total * 100) if total > 0 else 0.0
    gate_pass = total >= min_windows and ratio >= min_pass_ratio
    return {
        "total_windows": total,
        "passed_windows": passed,
        "thin_windows": thin,
        "pass_ratio": round(ratio, 1),
        "gate_pass": gate_pass,
        "window_verdicts": verdicts,
        "enough_windows": total >= min_windows,
    }


def run_validate(symbols: List[str] = None, interval: str = "1h", range_val: str = "90d", smc_v2: bool = False) -> int:
    """Pre-flag / pre-deploy gate. Runs walk-forward per symbol and returns a
    process exit code (0 = all symbols passed, 1 = any failed) so it can guard a
    deploy step or the decision to flip an intelligence FEATURE_FLAG on.
    """
    symbols = symbols or BACKTEST_SYMBOLS
    print("\n" + "=" * 80)
    print(f"  WALK-FORWARD VALIDATION GATE (pre-flag / pre-deploy)  [{'SMC v2' if smc_v2 else 'SMC v1'}]")
    print(f"  Criteria/window: Sharpe>={WALK_FORWARD_PASS_CRITERIA['sharpe_ratio']}, "
          f"PF>={WALK_FORWARD_PASS_CRITERIA['profit_factor']}, "
          f"MaxDD<={WALK_FORWARD_PASS_CRITERIA['max_drawdown']}%, "
          f"Ruin<={WALK_FORWARD_PASS_CRITERIA['risk_of_ruin']*100:.0f}%  |  "
          f"Gate: >={WALK_FORWARD_MIN_PASS_RATIO:.0f}% of >={WALK_FORWARD_MIN_WINDOWS} windows")
    print("=" * 80)

    overall_pass = True
    for sym in symbols:
        yf_sym = YAHOO_SYMBOL_MAP.get(sym, sym)
        try:
            df = asyncio.run(fetch_backtest_data(yf_sym, interval, range_val))
        except Exception as e:
            print(f"  {sym:<8} [ERROR] fetch failed: {e} → FAIL")
            overall_pass = False
            continue
        if len(df) < 700:
            print(f"  {sym:<8} [SKIP→FAIL] insufficient data ({len(df)} bars, need >=700)")
            overall_pass = False
            continue

        results = run_walk_forward_backtest(df, sym, smc_strategy=True, smc_v2=smc_v2)
        ev = evaluate_walk_forward(results)
        status = "PASS 🟢" if ev["gate_pass"] else "FAIL 🔴"
        note = "" if ev["enough_windows"] else " (too few windows)"
        if ev.get("thin_windows"):
            note += f" ({ev['thin_windows']} thin <{WALK_FORWARD_MIN_TRADES} trades)"
        print(f"  {sym:<8} {ev['passed_windows']}/{ev['total_windows']} windows "
              f"({ev['pass_ratio']:.1f}%) → {status}{note}")
        overall_pass = overall_pass and ev["gate_pass"]

    print("-" * 80)
    print(f"  GATE RESULT: {'PASS 🟢 — safe to proceed' if overall_pass else 'FAIL 🔴 — do NOT enable flag / deploy'}")
    print("=" * 80)
    return 0 if overall_pass else 1


def _precompute_bars(df: pd.DataFrame, symbol: str, use_mtf: bool = True) -> List[Dict]:
    bars = []
    warmup = 50
    for i in range(warmup, len(df)):
        ohlc_window = df.iloc[max(0, i - 48):i + 1][["open", "high", "low", "close", "volume"]].copy()
        indicators = get_market_indicators(ohlc_window, symbol)
        macro = _macro_trend_at_bar(df, i) if use_mtf else None

        # Real regime (same call the live engine uses) so the backtest exercises
        # the regime-aware reversal gate — what we test == what trades live.
        regime_at_bar = None
        regime_window = df.iloc[max(0, i - 200):i + 1][["open", "high", "low", "close", "volume"]]
        if len(regime_window) >= 50:
            from backend.engines.market_regime import calculate_regime_from_h1
            regime_at_bar, _, _, _, _ = calculate_regime_from_h1(regime_window)
        bars.append({
            "row": df.iloc[i],
            "indicators": indicators,
            "macro": macro,
            "regime": regime_at_bar,
        })
    return bars

def _simulate_from_bars(
    bars: List[Dict], symbol: str, strategy_filter: Optional[str],
    cfg: Dict, equity: float = EQUITY,
) -> Dict[str, Any]:
    trades: List[Dict] = []
    active_trade = None

    for bar in bars:
        row = bar["row"]
        if active_trade:
            high, low = float(row["high"]), float(row["low"])
            hit_sl = hit_tp = False
            if active_trade["action"] == "BUY":
                hit_sl = low <= active_trade["stop_loss"]
                hit_tp = not hit_sl and high >= active_trade["take_profit"]
            else:
                hit_sl = high >= active_trade["stop_loss"]
                hit_tp = not hit_sl and low <= active_trade["take_profit"]
            if hit_sl or hit_tp:
                exit_price = active_trade["stop_loss"] if hit_sl else active_trade["take_profit"]
                pnl = trade_pnl(symbol, active_trade["action"], active_trade["entry_price"], exit_price, active_trade["lot"])
                active_trade.update({"pnl": pnl, "status": "CLOSED"})
                active_trade = apply_trade_costs(active_trade, symbol)
                trades.append(active_trade)
                active_trade = None
            if active_trade:
                continue

        signal = evaluate_strategy_rules(
            bar["indicators"], symbol, bar["macro"],
            strategy_filter=strategy_filter, cfg=cfg, regime=bar.get("regime"),
        )
        if signal["action"] not in ("BUY", "SELL"):
            continue

        entry = float(row["close"])
        pos = calculate_position_size(symbol, equity, RISK_CONFIG["maxRiskPerTradePct"], bar["indicators"]["atr"], ATR_MULT)
        stop_dist = pos["stop_distance"]
        action = signal["action"]
        sl = entry - stop_dist if action == "BUY" else entry + stop_dist
        tp = entry + stop_dist * RR_RATIO if action == "BUY" else entry - stop_dist * RR_RATIO
        active_trade = {"action": action, "entry_price": entry, "stop_loss": sl, "take_profit": tp, "lot": pos["lot"], "status": "OPEN"}

    closed = [t for t in trades if t.get("status") == "CLOSED"]
    return {"symbol": symbol, "strategy": strategy_filter or "COMBINED", "trades": closed, "metrics": calculate_performance_metrics(closed), "config": cfg}

def optimize_rsi_thresholds(
    df: pd.DataFrame,
    symbol: str,
    strategy_filter: str = "REVERSAL",
) -> Dict[str, Any]:
    best_score = -1.0
    best_cfg = get_strategy_config(symbol)
    best_result = None
    precomputed = _precompute_bars(df, symbol, use_mtf=True)

    sell_early_range = [70, 72, 75, 78]
    sell_full_range = [74, 76, 78, 80]
    buy_early_range = [22, 25, 28]
    buy_full_range = [18, 20, 22, 24]

    for rsi_sell_early in sell_early_range:
        for rsi_sell_full in sell_full_range:
            if rsi_sell_full <= rsi_sell_early:
                continue
            for rsi_buy_early in buy_early_range:
                for rsi_buy_full in buy_full_range:
                    if rsi_buy_full >= rsi_buy_early:
                        continue
                    cfg = {
                        **get_strategy_config(symbol),
                        "rsi_sell_early": rsi_sell_early,
                        "rsi_sell_full": rsi_sell_full,
                        "rsi_buy_early": rsi_buy_early,
                        "rsi_buy_full": rsi_buy_full,
                    }
                    result = _simulate_from_bars(precomputed, symbol, strategy_filter, cfg)
                    m = result["metrics"]
                    if m["total_trades"] < 3:
                        continue
                    pf = min(m["profit_factor"], 5.0)
                    wr = m["win_rate"] / 100.0
                    dd_penalty = 1.0 - min(m["max_drawdown"] / 30.0, 0.5)
                    score = wr * pf * dd_penalty * (1 + m["total_trades"] / 100)
                    if score > best_score:
                        best_score = score
                        best_cfg = cfg
                        best_result = result

    return {"symbol": symbol, "best_config": best_cfg, "best_score": round(best_score, 4), "result": best_result}

def print_backtest_report(result: Dict[str, Any]):
    m = result["metrics"]
    label = result.get("strategy", "COMBINED")
    sym = result["symbol"]
    print(f"\n{'=' * 50}")
    print(f"  {sym} | {label}")
    print(f"{'=' * 50}")
    if m["total_trades"] == 0:
        print("  ไม่มีเทรดในช่วงทดสอบ")
        return
    print(f"  Trades:        {m['total_trades']}")
    print(f"  Win Rate:      {m['win_rate']}%")
    print(f"  Profit Factor: {m['profit_factor']}")
    print(f"  Max Drawdown:  {m['max_drawdown']}%")
    print(f"  Sharpe:        {m['sharpe_ratio']}")
    print(f"  Net PnL:       ${m['total_pnl']:+,.2f}")
    print(f"  Avg Win/Loss:  ${m['avg_win']:+.2f} / ${m['avg_loss']:+.2f}")
    cfg = result.get("config", {})
    if cfg:
        print(f"  RSI SELL:      early>{cfg.get('rsi_sell_early')} full>{cfg.get('rsi_sell_full')}")
        print(f"  RSI BUY:       early<{cfg.get('rsi_buy_early')} full<{cfg.get('rsi_buy_full')}")

def run_full_report(symbols: List[str] = None, interval: str = "1h", range_val: str = "60d"):
    symbols = symbols or BACKTEST_SYMBOLS
    all_results = {}

    for sym in symbols:
        yf_sym = YAHOO_SYMBOL_MAP.get(sym, sym)
        print(f"\n[FETCH] {sym} ({yf_sym})...")
        df = asyncio.run(fetch_backtest_data(yf_sym, interval, range_val))
        print(f"   {len(df)} bars")

        for strat in ("TREND_FOLLOWING", "REVERSAL", None):
            label = strat or "COMBINED"
            result = run_strategy_backtest(df, sym, strat, use_mtf=True)
            all_results[f"{sym}_{label}"] = result
            print_backtest_report(result)

    return all_results

def run_optimize(symbols: List[str] = None, interval: str = "1h", range_val: str = "30d"):
    symbols = symbols or BACKTEST_SYMBOLS
    optimized = {}

    print("\n[OPTIMIZE] RSI Threshold Optimization")
    print("=" * 50)

    for sym in symbols:
        yf_sym = YAHOO_SYMBOL_MAP.get(sym, sym)
        print(f"\n[FETCH] {sym} ({yf_sym})...")
        df = asyncio.run(fetch_backtest_data(yf_sym, interval, range_val))

        opt = optimize_rsi_thresholds(df, sym, "REVERSAL")
        optimized[sym] = opt

        if opt["result"]:
            print(f"\n[OK] {sym} -- best score {opt['best_score']}")
            bc = opt["best_config"]
            print(f"   rsi_sell_early={bc['rsi_sell_early']} rsi_sell_full={bc['rsi_sell_full']}")
            print(f"   rsi_buy_early={bc['rsi_buy_early']} rsi_buy_full={bc['rsi_buy_full']}")
            print_backtest_report(opt["result"])

            STRATEGY_CONFIG[sym] = {
                "rsi_sell_early": bc["rsi_sell_early"],
                "rsi_sell_full": bc["rsi_sell_full"],
                "rsi_buy_early": bc["rsi_buy_early"],
                "rsi_buy_full": bc["rsi_buy_full"],
                "volume_confirm_min": bc.get("volume_confirm_min", 1.15),
            }
        else:
            print(f"[WARN] {sym} -- insufficient trades (< 5)")

    print("\n[RESULT] Optimized STRATEGY_CONFIG:")
    for sym, cfg in STRATEGY_CONFIG.items():
        if sym in optimized:
            print(f"  {sym}: {cfg}")

    return optimized

def run_walk_forward_report(symbols: List[str] = None, interval: str = "1h", range_val: str = "90d"):
    symbols = symbols or BACKTEST_SYMBOLS
    print("\n" + "="*80)
    print("  WALK-FORWARD BACKTEST & SMC SWEEP PARAMETER OPTIMIZATION")
    print("="*80)
    
    pass_criteria = WALK_FORWARD_PASS_CRITERIA
    
    for sym in symbols:
        yf_sym = YAHOO_SYMBOL_MAP.get(sym, sym)
        print(f"\n[FETCH] {sym} ({yf_sym}) from Yahoo Finance...")
        try:
            df = asyncio.run(fetch_backtest_data(yf_sym, interval, range_val))
            print(f"   Fetched {len(df)} bars.")
            if len(df) < 700:
                print(f"   [WARN] Insufficient data ({len(df)} bars) for 500/200 walk-forward. Skipping.")
                continue
        except Exception as e:
            print(f"   [ERROR] Failed to fetch data: {e}")
            continue
            
        print(f"\n[RUN] Walk-Forward Validation (SMC Strategy Sweep)...")
        results = run_walk_forward_backtest(df, sym, smc_strategy=True)
        
        print(f"\n  Walk-Forward Windows Report for {sym}:")
        print("-"*105)
        print(f"{'Window':<8} | {'In-Sample':<10} | {'Out-Sample':<10} | {'Trades':<6} | {'Sharpe':<6} | {'PF':<5} | {'MaxDD %':<7} | {'Ruin %':<6} | {'Verdict':<7}")
        print("-"*105)
        
        passed_windows = 0
        total_windows = len(results)
        
        for idx, res in enumerate(results):
            m = res["oos_metrics"]
            is_r = f"{res['in_sample_range'][0]}-{res['in_sample_range'][1]}"
            os_r = f"{res['oos_range'][0]}-{res['oos_range'][1]}"
            
            # Check criteria
            pf = m["profit_factor"]
            sharpe = m["sharpe_ratio"]
            max_dd = m["max_drawdown"]
            ror = m["risk_of_ruin"]
            
            pf_pass = pf >= pass_criteria["profit_factor"] or pf == float('inf')
            sharpe_pass = sharpe >= pass_criteria["sharpe_ratio"]
            dd_pass = max_dd <= pass_criteria["max_drawdown"]
            ror_pass = ror <= pass_criteria["risk_of_ruin"]
            thin = res["trades_count"] < WALK_FORWARD_MIN_TRADES

            window_passed = not thin and pf_pass and sharpe_pass and dd_pass and ror_pass
            if window_passed:
                passed_windows += 1
                verdict = "PASS 🟢"
            elif thin:
                verdict = "THIN ⚪"
            else:
                verdict = "FAIL 🔴"
                
            print(f"#{idx+1:<7} | {is_r:<10} | {os_r:<10} | {res['trades_count']:<6} | {sharpe:<6.2f} | {pf:<5.2f} | {max_dd:<7.2f} | {ror*100:<5.1f}% | {verdict}")
            
            # Print best config parameters
            cfg = res["best_config"]
            print(f"          Best Config: ob_size_atr={cfg.get('ob_size_atr')}, fvg_gap_atr={cfg.get('fvg_gap_atr')}")
            
        print("-"*105)
        pass_ratio = (passed_windows / total_windows * 100) if total_windows > 0 else 0.0
        print(f"  Result: {passed_windows}/{total_windows} windows passed ({pass_ratio:.1f}%)")
        if pass_ratio >= 60.0:
            print(f"  [STATUS] Robustness check PASSED for {sym} 🟢")
        else:
            print(f"  [STATUS] Robustness check FAILED for {sym} 🔴 (Requires >=60% windows passing)")
        print("="*80)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    sym_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "optimize":
        syms = [sym_arg] if sym_arg and sym_arg in BACKTEST_SYMBOLS else BACKTEST_SYMBOLS
        run_optimize(syms)
    elif cmd == "walkforward":
        syms = [sym_arg] if sym_arg and sym_arg in BACKTEST_SYMBOLS else BACKTEST_SYMBOLS
        run_walk_forward_report(syms)
    elif cmd == "validate":
        syms = [sym_arg] if sym_arg and sym_arg in BACKTEST_SYMBOLS else BACKTEST_SYMBOLS
        sys.exit(run_validate(syms))
    elif cmd == "validate2":
        syms = [sym_arg] if sym_arg and sym_arg in BACKTEST_SYMBOLS else BACKTEST_SYMBOLS
        sys.exit(run_validate(syms, smc_v2=True))
    elif cmd == "run":
        if sym_arg and sym_arg in BACKTEST_SYMBOLS:
            yf = YAHOO_SYMBOL_MAP.get(sym_arg, sym_arg)
            df = asyncio.run(fetch_backtest_data(yf))
            for strat in ("TREND_FOLLOWING", "REVERSAL", None):
                print_backtest_report(run_strategy_backtest(df, sym_arg, strat))
        else:
            run_full_report()
    else:
        print("Usage: python backend/backtest.py [run|optimize|walkforward|validate|validate2] [XAUUSD|BTCUSDT|ETHUSDT]")
        print("  validate  → walk-forward gate, SMC v1 (legacy EMA-direction); exit 0=pass, 1=fail")
        print("  validate2 → walk-forward gate, SMC v2 (directional + TIER + structural SL — recommended)")
