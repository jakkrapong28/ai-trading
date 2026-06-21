"""Roadmap ข้อ 4 (รอบถัดไป) — MR-as-primary ราย WINDOW vs base breakout.

Hypothesis (§25): คอขวดสู่ 60% = window ที่เทรดพอแต่ขาดทุนสุทธิ (PF<1). MR เดี่ยว ๆ
มี edge จริงในตลาด chop (§23) แต่ router เดิม (per-bar) ยิง <1 ไม้/window พลิกไม่ได้.
รอบนี้จัด regime ราย window จาก in-sample ADX (ไม่ lookahead) → window range-dominant
ใช้ MR เป็น engine หลักทั้ง window ให้ยิงพอจะพลิก PF.

วัดบน PINNED data (reproducible) → delta = edge จริง ไม่ใช่ noise. ทุก knob default ปิด.
รัน:  PYTHONPATH=. python backend/scratch/ab_mr_primary.py
"""
import os
import asyncio
from collections import Counter

from backend.backtest import (
    fetch_backtest_data, run_walk_forward_backtest, evaluate_walk_forward,
    WALK_FORWARD_PASS_CRITERIA as PC, WALK_FORWARD_MIN_TRADES as MIN_TR,
    YAHOO_SYMBOL_MAP,
)

SYMS = ["XAUUSD", "BTCUSDT", "ETHUSDT"]
_KEYS = ["BT_IN_LEN", "BT_OOS_LEN", "BT_STEP_LEN", "BT_CB_MAX_LOSSES", "BT_MIN_ADX",
         "BT_MR_PRIMARY", "BT_MR_PRIMARY_ADX", "BT_MR_RR", "BT_MR_RSI_BUY",
         "BT_MR_RSI_SELL", "BT_MR_LOOKBACK", "BT_MR_BAND_ATR"]
_BASE = {"BT_IN_LEN": 500, "BT_OOS_LEN": 400, "BT_STEP_LEN": 400,
         "BT_CB_MAX_LOSSES": 3, "BT_MIN_ADX": 20}


def _set(env: dict):
    for k in _KEYS:
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = str(v)


def _wf(df, sym, env):
    _set(env)
    return run_walk_forward_backtest(df, sym, smc_strategy=True, smc_v2=True)


def _summary(res):
    ev = evaluate_walk_forward(res)
    blow = sum(1 for r in res if r.get("trades_count", 0) >= MIN_TR
               and r["oos_metrics"].get("risk_of_ruin", 0) >= 0.5)
    real_fail = 0
    for r in res:
        m, tc = r["oos_metrics"], r.get("trades_count", 0)
        if tc < MIN_TR:
            continue
        pf, sh, dd, ror = m["profit_factor"], m["sharpe_ratio"], m["max_drawdown"], m["risk_of_ruin"]
        if not ((pf >= PC["profit_factor"] or pf == float("inf")) and sh >= PC["sharpe_ratio"]
                and dd <= PC["max_drawdown"] and ror <= PC["risk_of_ruin"]):
            real_fail += 1
    return ev, blow, real_fail


def _flip_metric(base, variant):
    """§25 decisive check: of the windows where base breakout loses net (tc>=5, PF<1),
    how many does MR-primary turn into a PF>=1.3 pass-grade — and does anything regress?"""
    flipped = regressed = losing = 0
    for b, v in zip(base, variant):
        bm, vm = b["oos_metrics"], v["oos_metrics"]
        b_tc = b.get("trades_count", 0)
        if b_tc >= MIN_TR and bm["profit_factor"] < 1.0:
            losing += 1
            if v.get("trades_count", 0) >= MIN_TR and vm["profit_factor"] >= PC["profit_factor"]:
                flipped += 1
        # regression: base full-pass → variant fails (only meaningful where engine changed)
        b_pass = (b_tc >= MIN_TR and (bm["profit_factor"] >= PC["profit_factor"]) and bm["sharpe_ratio"] >= PC["sharpe_ratio"]
                  and bm["max_drawdown"] <= PC["max_drawdown"] and bm["risk_of_ruin"] <= PC["risk_of_ruin"])
        v_pass = (v.get("trades_count", 0) >= MIN_TR and (vm["profit_factor"] >= PC["profit_factor"]) and vm["sharpe_ratio"] >= PC["sharpe_ratio"]
                  and vm["max_drawdown"] <= PC["max_drawdown"] and vm["risk_of_ruin"] <= PC["risk_of_ruin"])
        if b_pass and not v_pass:
            regressed += 1
    return losing, flipped, regressed


def run(df, sym):
    base = _wf(df, sym, {**_BASE})
    ev_b, blow_b, rf_b = _summary(base)
    print(f"\n=== {sym} ===  bars={len(df)}  windows={ev_b['total_windows']}")
    print(f"  [base CB3+ADX20      ] pass {ev_b['passed_windows']:>2}/{ev_b['total_windows']:<2} "
          f"({ev_b['pass_ratio']:>5.1f}%)  thin={ev_b['thin_windows']:<2} real_fail={rf_b:<2} blowups={blow_b}")
    for adx in (20, 25, 30):
        var = _wf(df, sym, {**_BASE, "BT_MR_PRIMARY": 1, "BT_MR_PRIMARY_ADX": adx, "BT_MR_RR": 1.0})
        ev_v, blow_v, rf_v = _summary(var)
        losing, flipped, regressed = _flip_metric(base, var)
        d = ev_v["pass_ratio"] - ev_b["pass_ratio"]
        print(f"  [MR-primary adx<{adx:<2}     ] pass {ev_v['passed_windows']:>2}/{ev_v['total_windows']:<2} "
              f"({ev_v['pass_ratio']:>5.1f}%)  d={d:+5.1f}pp  thin={ev_v['thin_windows']:<2} "
              f"real_fail={rf_v:<2} blowups={blow_v}  |  losing->flipped {flipped}/{losing}, regressed {regressed}")


def main():
    for sym in SYMS:
        yf = YAHOO_SYMBOL_MAP.get(sym, sym)
        df = asyncio.run(fetch_backtest_data(yf, "1h", "730d"))
        if len(df) < 700:
            print(f"{sym}: insufficient ({len(df)})"); continue
        run(df, sym)
    print("\nDONE-MR-PRIMARY")


if __name__ == "__main__":
    main()
