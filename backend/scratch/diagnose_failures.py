"""ดัน 60% — root-cause ราย window: แต่ละ OOS window ที่ fail ตกเพราะเกณฑ์ข้อไหน
(Sharpe/PF/DD/Ruin) และตกเพราะ THIN (เทรดน้อย) หรือ edge จริง — เพื่อรู้เลเวอร์จริง
ก่อนลงมือ ไม่เดา.

รันบน base ที่ดีสุด (1h/730d OOS=400 + CB3 + ADX20) ทุก symbol.
"""
import os
import asyncio
from collections import Counter
from backend.backtest import (
    fetch_backtest_data, run_walk_forward_backtest, WALK_FORWARD_PASS_CRITERIA as PC,
    WALK_FORWARD_MIN_TRADES as MIN_TR, YAHOO_SYMBOL_MAP,
)

os.environ.update({"BT_IN_LEN": "500", "BT_OOS_LEN": "400", "BT_STEP_LEN": "400",
                   "BT_CB_MAX_LOSSES": "3", "BT_MIN_ADX": "20"})

SYMS = {"XAUUSD": "GC=F", "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD"}


def classify(sym, df):
    # with_diagnostics=False — we never read vol_stats here; computing it (a fresh
    # regime over a 200-bar window per OOS bar) was ~10x the runtime for nothing.
    res = run_walk_forward_backtest(df, sym, smc_strategy=True, smc_v2=True, with_diagnostics=False)
    n = len(res)
    passed = thin_only = real_fail = blowup = 0
    fail_reasons = Counter()
    rows = []
    for i, r in enumerate(res):
        m = r["oos_metrics"]; tc = r["trades_count"]
        thin = tc < MIN_TR
        pf, sh, dd, ror = m["profit_factor"], m["sharpe_ratio"], m["max_drawdown"], m["risk_of_ruin"]
        fails = []
        if not (pf >= PC["profit_factor"] or pf == float("inf")): fails.append("PF")
        if sh < PC["sharpe_ratio"]: fails.append("Sharpe")
        if dd > PC["max_drawdown"]: fails.append("DD")
        if ror > PC["risk_of_ruin"]: fails.append("Ruin")
        ok = (not thin) and not fails
        if ok:
            passed += 1
        elif thin and not fails:
            thin_only += 1            # would pass if it had >=5 trades (frequency problem)
        elif thin:
            thin_only += 1            # thin AND would fail anyway
        else:
            real_fail += 1
            for f in fails: fail_reasons[f] += 1
        if tc >= 5 and ror >= 0.5:
            blowup += 1
        rows.append((i + 1, tc, sh, pf, dd, ror, "THIN" if thin else ("PASS" if ok else "FAIL "+",".join(fails))))
    print(f"\n=== {sym} ===  windows={n}  pass={passed} ({passed/n*100:.1f}%)  "
          f"thin={thin_only}  real_fail={real_fail}  blowups(ruin>=50%)={blowup}")
    print(f"    real-fail breakdown (enough trades but t, ตกเกณฑ์): {dict(fail_reasons)}")
    # how many windows would pass if thin guard removed (pure-frequency-blocked)?
    pure_freq = sum(1 for r in res if r["trades_count"] < MIN_TR
                    and (r["oos_metrics"]["profit_factor"] >= PC["profit_factor"] or r["oos_metrics"]["profit_factor"] == float("inf"))
                    and r["oos_metrics"]["sharpe_ratio"] >= PC["sharpe_ratio"]
                    and r["oos_metrics"]["max_drawdown"] <= PC["max_drawdown"]
                    and r["oos_metrics"]["risk_of_ruin"] <= PC["risk_of_ruin"])
    print(f"    THIN windows that meet ALL metric criteria (blocked ONLY by <5 trades): {pure_freq}")
    print(f"    → ceiling if frequency fixed: {(passed+pure_freq)/n*100:.1f}%")
    avg_tr = sum(r["trades_count"] for r in res) / n
    print(f"    avg trades/window={avg_tr:.1f}  (need >=5 to not be thin)")
    print(f"    {'win':<4} {'tr':<3} {'Sharpe':<7} {'PF':<6} {'DD%':<6} {'Ruin%':<6} verdict")
    for w, tc, sh, pf, dd, ror, v in rows:
        print(f"    #{w:<3} {tc:<3} {sh:<7.2f} {min(pf,99):<6.2f} {dd:<6.1f} {ror*100:<6.1f} {v}")


def main():
    for sym, yf in SYMS.items():
        try:
            df = asyncio.run(fetch_backtest_data(yf, "1h", "730d"))
            if len(df) < 700:
                print(f"{sym}: insufficient ({len(df)})"); continue
            classify(sym, df)
        except Exception as e:
            print(f"{sym}: ERROR {e}")
    print("\nDONE-DIAG")


if __name__ == "__main__":
    main()
