"""
Backtest engine — แยกกลยุทธ์ Trend / Reversal, ใช้ OHLC ATR จริง
Usage:
  python backend/backtest.py run XAUUSD
  python backend/backtest.py optimize
  python backend/backtest.py optimize BTCUSDT
"""
import sys
import os
import asyncio
import copy
import httpx
import pandas as pd
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


def run_strategy_backtest(
    df: pd.DataFrame,
    symbol: str,
    strategy_filter: Optional[str] = None,
    cfg: Optional[Dict] = None,
    use_mtf: bool = True,
    equity: float = EQUITY,
) -> Dict[str, Any]:
    """รัน backtest ต่อกลยุทธ์ — ใช้ OHLC ATR + dynamic lot sizing"""
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    cfg = cfg or get_strategy_config(symbol)
    trades: List[Dict] = []
    active_trade = None
    warmup = 50

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
                trades.append(active_trade)
                active_trade = None

        if active_trade:
            continue

        ohlc_window = df.iloc[max(0, i - 48):i + 1][["open", "high", "low", "close", "volume"]].copy()
        indicators = get_market_indicators(ohlc_window, symbol)
        macro = _macro_trend_at_bar(df, i) if use_mtf else None

        signal = evaluate_strategy_rules(
            indicators, symbol, macro, strategy_filter=strategy_filter, cfg=cfg
        )

        if signal["action"] not in ("BUY", "SELL"):
            continue

        entry = float(row["close"])
        atr = indicators["atr"]
        pos = calculate_position_size(symbol, equity, RISK_CONFIG["maxRiskPerTradePct"], atr, ATR_MULT)
        stop_dist = pos["stop_distance"]

        action = signal["action"]
        sl = entry - stop_dist if action == "BUY" else entry + stop_dist
        tp = entry + stop_dist * RR_RATIO if action == "BUY" else entry - stop_dist * RR_RATIO
        active_trade = {
            "action": action,
                "strategy_type": signal.get("strategy_type", "UNKNOWN"),
                "entry_price": entry,
                "entry_time": row["timestamp"],
                "stop_loss": sl,
                "take_profit": tp,
                "lot": pos["lot"],
            "status": "OPEN",
        }

    closed = [t for t in trades if t.get("status") == "CLOSED"]
    metrics = calculate_performance_metrics(closed)
    return {
        "symbol": symbol,
        "strategy": strategy_filter or "COMBINED",
        "trades": closed,
        "metrics": metrics,
        "config": cfg,
    }


def _precompute_bars(df: pd.DataFrame, symbol: str, use_mtf: bool = True) -> List[Dict]:
    """Pre-compute indicators + macro trend per bar (speed up optimization)"""
    bars = []
    warmup = 50
    for i in range(warmup, len(df)):
        ohlc_window = df.iloc[max(0, i - 48):i + 1][["open", "high", "low", "close", "volume"]].copy()
        indicators = get_market_indicators(ohlc_window, symbol)
        macro = _macro_trend_at_bar(df, i) if use_mtf else None
        bars.append({
            "row": df.iloc[i],
            "indicators": indicators,
            "macro": macro,
        })
    return bars


def _simulate_from_bars(
    bars: List[Dict], symbol: str, strategy_filter: Optional[str],
    cfg: Dict, equity: float = EQUITY,
) -> Dict[str, Any]:
    """Fast simulation using pre-computed indicator bars"""
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
                trades.append(active_trade)
                active_trade = None
            if active_trade:
                continue

        signal = evaluate_strategy_rules(
            bar["indicators"], symbol, bar["macro"],
            strategy_filter=strategy_filter, cfg=cfg,
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
    """Grid search RSI thresholds — maximize win rate x profit factor (penalize drawdown)"""
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    sym_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "optimize":
        syms = [sym_arg] if sym_arg and sym_arg in BACKTEST_SYMBOLS else BACKTEST_SYMBOLS
        run_optimize(syms)
    elif cmd == "run":
        if sym_arg and sym_arg in BACKTEST_SYMBOLS:
            yf = YAHOO_SYMBOL_MAP.get(sym_arg, sym_arg)
            df = asyncio.run(fetch_backtest_data(yf))
            for strat in ("TREND_FOLLOWING", "REVERSAL", None):
                print_backtest_report(run_strategy_backtest(df, sym_arg, strat))
        else:
            run_full_report()
    else:
        print("Usage: python backend/backtest.py [run|optimize] [XAUUSD|BTCUSDT|ETHUSDT]")
