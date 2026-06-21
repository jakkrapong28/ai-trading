"""Roadmap ข้อ 4 A/B — does a per-regime ROUTER (hand low-ADX chop windows to the
mean-reversion engine instead of standing aside) lift the pass-ratio above the
current best (CB3+ADX20 = 47.1%) toward the 60% gate?

Same valid measurement as ข้อ 3: 1h / 730d, OOS=400, on top of the proven base
(CB3 + ADX20). The router intercepts bars where ADX < BT_MR_ADX and fades the
range; bars where ADX is high still run SMC-breakout as before.
"""
import os
import asyncio
from backend.backtest import (
    fetch_backtest_data, run_walk_forward_backtest, evaluate_walk_forward,
)

_KEYS = ["BT_CB_MAX_LOSSES", "BT_CB_COOLDOWN", "BT_MIN_ADX", "BT_IN_LEN", "BT_OOS_LEN",
         "BT_STEP_LEN", "BT_MR_ROUTER", "BT_MR_ADX", "BT_MR_RSI_BUY", "BT_MR_RSI_SELL",
         "BT_MR_LOOKBACK", "BT_MR_BAND_ATR", "BT_MR_RR"]
_BASE = {"BT_IN_LEN": 500, "BT_OOS_LEN": 400, "BT_STEP_LEN": 400,
         "BT_CB_MAX_LOSSES": 3, "BT_MIN_ADX": 20}
_MR = {"BT_MR_ROUTER": 1, "BT_MR_ADX": 20}


def _set(env: dict):
    for k in _KEYS:
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = str(v)


def run(df, sym, label, env):
    _set(env)
    res = run_walk_forward_backtest(df, sym, smc_strategy=True, smc_v2=True)
    ev = evaluate_walk_forward(res)
    blow = sum(1 for r in res if r.get("trades_count", 0) >= 5
               and r["oos_metrics"].get("risk_of_ruin", 0) >= 0.5)
    avg_tr = sum(r.get("trades_count", 0) for r in res) / max(len(res), 1)
    print(f"[{label:<22}] pass {ev['passed_windows']:>2}/{ev['total_windows']:<2} "
          f"({ev['pass_ratio']:>5.1f}%)  thin={ev['thin_windows']:<2} "
          f"avgTr/win={avg_tr:>4.1f}  blowups={blow}  gate={'PASS' if ev['gate_pass'] else 'FAIL'}",
          flush=True)


def main():
    sym, yf = "XAUUSD", "GC=F"
    df = asyncio.run(fetch_backtest_data(yf, "1h", "730d"))
    print(f"== {sym} 1h/730d OOS=400 base=CB3+ADX20 ==  bars={len(df)}", flush=True)
    # Iteration 2: MR-only isolation proved the edge lives at ADX<30 + RR=1.0
    # (PF 1.54 / WR 61% / DD 5.6%). Route the chop band to MR, trend to SMC.
    # NOTE: with the router, SMC must NOT also be gated by BT_MIN_ADX or it stands
    # aside in the very band MR now owns — drop ADX20 from the router base.
    _RB = {"BT_IN_LEN": 500, "BT_OOS_LEN": 400, "BT_STEP_LEN": 400, "BT_CB_MAX_LOSSES": 3}
    run(df, sym, "base CB3+ADX20", {**_BASE})
    run(df, sym, "router adx30 rr1.0", {**_RB, **_MR, "BT_MR_ADX": 30, "BT_MR_RR": 1.0})
    run(df, sym, "router adx25 rr1.0", {**_RB, **_MR, "BT_MR_ADX": 25, "BT_MR_RR": 1.0})
    run(df, sym, "router adx35 rr1.0", {**_RB, **_MR, "BT_MR_ADX": 35, "BT_MR_RR": 1.0})
    run(df, sym, "router adx30 rr1.0 +ADX20", {**_BASE, **_MR, "BT_MR_ADX": 30, "BT_MR_RR": 1.0})
    run(df, sym, "router adx30 rr1.2", {**_RB, **_MR, "BT_MR_ADX": 30, "BT_MR_RR": 1.2})
    print("DONE-MR-AB", flush=True)


if __name__ == "__main__":
    main()
