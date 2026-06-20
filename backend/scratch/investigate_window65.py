"""One-off: dump the trades + entry context of the catastrophic low-vol window
(#65 in the 730d XAUUSD v1 walk-forward: 8 straight losers, Ruin 100%, %Volat 0%).

Reproduces the exact OOS window and logs, per trade, the direction / macro / regime
/ RSI / result so we can see WHY it lost — volatility was ~0 so the cause must be
directional/structural, not a vol shock.
"""
import asyncio
from backend.backtest import (
    fetch_backtest_data, optimize_smc_parameters, _macro_trend_at_bar,
    ATR_MULT, RR_RATIO,
)
from backend.core import (
    get_market_indicators, calculate_position_size, trade_pnl, RISK_CONFIG,
)
from backend.engines.market_regime import calculate_regime_from_h1
from backend.core.smc import (
    evaluate_smc_signal, detect_smc_concepts, calculate_signal_confidence,
)

IN_START = 12800      # in-sample 12800-13300, OOS 13300-13500  → window #65
IN_LEN = 500
OOS_LEN = 200
EQUITY = RISK_CONFIG["equity"]


def sim_and_dump(df, symbol, cfg, smc_v2):
    """Mirror run_strategy_backtest's OOS loop but log per-trade context."""
    warmup = 50
    active = None
    n_win = n_loss = 0
    print(f"\n{'='*100}\n  {symbol}  window OOS={IN_START+IN_LEN}-{IN_START+IN_LEN+OOS_LEN}  "
          f"strategy={'SMC v2' if smc_v2 else 'SMC v1'}  cfg={cfg}\n{'='*100}")
    print(f"{'#':<3} {'dir':<4} {'entry_time':<17} {'entry':>9} {'sl':>9} {'tp':>9} "
          f"{'exit':>9} {'res':<4} {'pnl':>9}  {'macro':<8} {'regime':<9} {'rsi':>5} {'tier/conf':<10}")

    idx = 0
    for i in range(warmup, len(df)):
        row = df.iloc[i]
        if active:
            high, low = float(row["high"]), float(row["low"])
            hit_sl = hit_tp = False
            if active["action"] == "BUY":
                hit_sl = low <= active["stop_loss"]
                hit_tp = not hit_sl and high >= active["take_profit"]
            else:
                hit_sl = high >= active["stop_loss"]
                hit_tp = not hit_sl and low <= active["take_profit"]
            if hit_sl or hit_tp:
                exit_price = active["stop_loss"] if hit_sl else active["take_profit"]
                pnl = trade_pnl(symbol, active["action"], active["entry_price"], exit_price, active["lot"])
                res = "SL" if hit_sl else "TP"
                if pnl >= 0: n_win += 1
                else: n_loss += 1
                idx += 1
                print(f"{idx:<3} {active['action']:<4} {str(active['entry_time'])[:16]:<17} "
                      f"{active['entry_price']:>9.2f} {active['stop_loss']:>9.2f} {active['take_profit']:>9.2f} "
                      f"{exit_price:>9.2f} {res:<4} {pnl:>9.2f}  {active['macro'] or '-':<8} "
                      f"{active['regime'] or '-':<9} {active['rsi']:>5.0f} {active['ctx']:<10}")
                active = None
        if active:
            continue

        ohlc_window = df.iloc[max(0, i - 48):i + 1][["open", "high", "low", "close", "volume"]].copy()
        indicators = get_market_indicators(ohlc_window, symbol)
        macro = _macro_trend_at_bar(df, i)
        regime = None
        regime_window = df.iloc[max(0, i - 200):i + 1][["open", "high", "low", "close", "volume"]]
        if len(regime_window) >= 50:
            regime, _, _, _, _ = calculate_regime_from_h1(regime_window)

        atr = indicators["atr"]
        ctx = ""
        if smc_v2:
            sig = evaluate_smc_signal(ohlc_window, atr, indicators, macro, regime,
                                      ob_size_atr=cfg.get("ob_size_atr", 0.5),
                                      fvg_gap_atr=cfg.get("fvg_gap_atr", 0.3))
            action = sig["action"]
            ctx = f"{sig.get('tier') or '-'}/{sig.get('confidence', 0):.2f}"
            sl_anchor = sig.get("sl_anchor")
        else:
            concepts = detect_smc_concepts(ohlc_window, atr, cfg.get("ob_size_atr", 0.5), cfg.get("fvg_gap_atr", 0.3))
            concepts["d1_aligned"] = (macro != "Sideways") if macro else True
            conf = calculate_signal_confidence(concepts)
            action = "WAIT"
            if conf >= 0.55:
                action = "BUY" if indicators.get("ema_fast", 0.0) > indicators.get("ema_slow", 0.0) else "SELL"
                if action == "SELL" and macro == "Bullish": action = "WAIT"
                elif action == "BUY" and macro == "Bearish": action = "WAIT"
            ctx = f"conf{conf:.2f}"
            sl_anchor = None

        if action not in ("BUY", "SELL"):
            continue

        entry = float(row["close"])
        pos = calculate_position_size(symbol, EQUITY, RISK_CONFIG["maxRiskPerTradePct"], atr, ATR_MULT)
        stop_dist = pos["stop_distance"]
        lot = pos["lot"]
        sl = entry - stop_dist if action == "BUY" else entry + stop_dist
        if sl_anchor is not None:
            buf = 0.25 * atr
            cand = (sl_anchor - buf) if action == "BUY" else (sl_anchor + buf)
            risk = (entry - cand) if action == "BUY" else (cand - entry)
            if 0.5 * stop_dist <= risk <= 2.0 * stop_dist:
                sl = cand
                lot = pos["lot"] * stop_dist / risk
        risk = abs(entry - sl)
        tp = entry + risk * RR_RATIO if action == "BUY" else entry - risk * RR_RATIO
        active = {"action": action, "entry_price": entry, "entry_time": row["timestamp"],
                  "stop_loss": sl, "take_profit": tp, "lot": lot,
                  "macro": macro, "regime": regime, "rsi": indicators.get("rsi", 50.0), "ctx": ctx}

    print(f"  → trades={n_win+n_loss}  wins={n_win}  losses={n_loss}")


def main():
    df = asyncio.run(fetch_backtest_data("GC=F", "1h", "730d"))
    print(f"Fetched {len(df)} bars")
    in_df = df.iloc[IN_START:IN_START + IN_LEN].reset_index(drop=True)
    oos_df = df.iloc[IN_START + IN_LEN:IN_START + IN_LEN + OOS_LEN].reset_index(drop=True)

    for smc_v2 in (False, True):
        opt = optimize_smc_parameters(in_df, "XAUUSD", smc_v2=smc_v2)
        sim_and_dump(oos_df, "XAUUSD", opt["best_config"], smc_v2=smc_v2)


if __name__ == "__main__":
    main()
