"""Roadmap ข้อ 3 A/B — does adaptive TP (H1) and/or a session gate (H2) lift the
pass-ratio above the current best (CB3+ADX20 = 47.1%) toward the 60% gate?

1h / 730d, OOS=400 (the valid measurement from Phase B). Every config sits on top
of the proven base (CB3 + ADX20).
  H1 = adaptive take-profit RR per regime (BULL/BEAR 2.5, SIDEWAYS 1.2, VOLATILE 1.5)
  H2 = session gate (min boost 1.0 → trade London/NY only, skip Asian/Sydney)
"""
import os
import asyncio
from backend.backtest import (
    fetch_backtest_data, run_walk_forward_backtest, evaluate_walk_forward,
)

_KEYS = ["BT_CB_MAX_LOSSES", "BT_CB_COOLDOWN", "BT_MIN_ADX", "BT_BLOCK_VOLATILE",
         "BT_MAX_ATR_EXPANSION", "BT_IN_LEN", "BT_OOS_LEN", "BT_STEP_LEN",
         "BT_RR_BULL", "BT_RR_BEAR", "BT_RR_SIDEWAYS", "BT_RR_VOLATILE", "BT_MIN_SESSION"]
_BASE = {"BT_IN_LEN": 500, "BT_OOS_LEN": 400, "BT_STEP_LEN": 400,
         "BT_CB_MAX_LOSSES": 3, "BT_MIN_ADX": 20}
_H1 = {"BT_RR_BULL": 2.5, "BT_RR_BEAR": 2.5, "BT_RR_SIDEWAYS": 1.2, "BT_RR_VOLATILE": 1.5}
_H2 = {"BT_MIN_SESSION": 1.0}


def _set(env: dict):
    for k in _KEYS:
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = str(v)


def run(df, label, env):
    _set(env)
    res = run_walk_forward_backtest(df, "XAUUSD", smc_strategy=True, smc_v2=True)
    ev = evaluate_walk_forward(res)
    blow = sum(1 for r in res if r.get("trades_count", 0) >= 5
               and r["oos_metrics"].get("risk_of_ruin", 0) >= 0.5)
    avg_tr = sum(r.get("trades_count", 0) for r in res) / max(len(res), 1)
    print(f"[{label:<18}] pass {ev['passed_windows']:>2}/{ev['total_windows']:<2} "
          f"({ev['pass_ratio']:>5.1f}%)  thin={ev['thin_windows']:<2} "
          f"avgTr/win={avg_tr:>4.1f}  blowups={blow}  gate={'PASS' if ev['gate_pass'] else 'FAIL'}",
          flush=True)


def main():
    df = asyncio.run(fetch_backtest_data("GC=F", "1h", "730d"))
    print(f"== 1h/730d OOS=400 base=CB3+ADX20 ==  bars={len(df)}", flush=True)
    run(df, "base", {**_BASE})
    run(df, "base+H1(adaptTP)", {**_BASE, **_H1})
    run(df, "base+H2(session)", {**_BASE, **_H2})
    run(df, "base+H1+H2", {**_BASE, **_H1, **_H2})
    print("DONE-AB", flush=True)


if __name__ == "__main__":
    main()
