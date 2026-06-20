"""Walk-forward window sizing is configurable (Roadmap ข้อ 2 — fix the measurement).

A bigger OOS window raises trades-per-window so fewer windows are THIN. These tests
lock the windowing math (arg + env override) on a tiny synthetic df — no network.
"""
import pandas as pd
from datetime import datetime, timedelta

from backend.backtest import run_walk_forward_backtest


def _synth(n: int) -> pd.DataFrame:
    base = datetime(2024, 1, 1)
    rows = []
    p = 2000.0
    for i in range(n):
        p += (1.0 if i % 7 < 4 else -1.0) * 0.5
        rows.append({"timestamp": base + timedelta(hours=i),
                     "open": p, "high": p + 1, "low": p - 1, "close": p, "volume": 100.0})
    return pd.DataFrame(rows)


def test_window_override_via_args():
    df = _synth(180)
    res = run_walk_forward_backtest(df, "XAUUSD", smc_v2=True,
                                    in_sample_len=60, oos_len=30, step_len=30)
    # start_idx in range(0, 180-60, 30) = 0,30,60,90 → 4 windows
    assert len(res) == 4
    for r in res:
        i0, i1 = r["in_sample_range"]
        o0, o1 = r["oos_range"]
        assert i1 - i0 == 60        # in-sample length honoured
        assert o0 == i1             # OOS starts where in-sample ends
        assert 0 < (o1 - o0) <= 30  # OOS length honoured (last window may clip)


def test_window_override_via_env(monkeypatch):
    monkeypatch.setenv("BT_IN_LEN", "60")
    monkeypatch.setenv("BT_OOS_LEN", "30")
    monkeypatch.setenv("BT_STEP_LEN", "30")
    df = _synth(180)
    res = run_walk_forward_backtest(df, "XAUUSD", smc_v2=True)
    assert len(res) == 4
    assert res[0]["in_sample_range"] == (0, 60)
    assert res[0]["oos_range"] == (60, 90)
