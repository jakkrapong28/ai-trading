"""Guard the MR-as-primary per-window research knob (2026-06-21).

When BT_MR_PRIMARY is armed, run_walk_forward_backtest classifies each window from
its in-sample ADX (lookahead-free) and runs the mean-reversion engine as the sole
engine on the range-dominant windows. These tests pin the wiring deterministically:
the per-window decision honours the ADX threshold, the sim routes to MR, and the
feature is fully inert when it never triggers (so default behaviour is unchanged).
"""
import os

import numpy as np
import pandas as pd
import pytest

from backend.backtest import run_strategy_backtest, run_walk_forward_backtest

_KEYS = ["BT_MR_PRIMARY", "BT_MR_PRIMARY_ADX", "BT_IN_LEN", "BT_OOS_LEN", "BT_STEP_LEN"]


@pytest.fixture(autouse=True)
def _clean_env():
    saved = {k: os.environ.get(k) for k in _KEYS}
    for k in _KEYS:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v


def _range_df(n: int = 200, period: int = 30, amp: float = 30.0, seed: int = 3) -> pd.DataFrame:
    """A clean oscillating range (sine) — the tape MR is built to fade. Turning
    points drive RSI to extremes while price sits on the Donchian boundary."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    close = 2000.0 + amp * np.sin(2 * np.pi * t / period)
    high = close + np.abs(rng.normal(0, 1.5, n))
    low = close - np.abs(rng.normal(0, 1.5, n))
    open_ = close - rng.normal(0, 1.0, n)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": rng.uniform(80, 120, n),
    })


_MR_CFG = {"smc_strategy": True, "smc_v2": True, "ob_size_atr": 0.5, "fvg_gap_atr": 0.3,
           "mtf_strategy": True, "mr_primary": True, "mr_lookback": 20,
           "mr_rsi_buy": 35.0, "mr_rsi_sell": 65.0, "mr_band_atr": 0.5}


def _spy_mr(monkeypatch):
    """Wrap evaluate_mean_reversion to count invocations (patch the source module —
    run_strategy_backtest imports it locally each call). Proves routing regardless
    of whether a fadeable setup actually fills, so the test isn't regime-sensitive."""
    import backend.core.mean_reversion as mr
    calls = {"n": 0}
    real = mr.evaluate_mean_reversion

    def spy(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(mr, "evaluate_mean_reversion", spy)
    return calls


def test_mr_primary_routes_to_mr_engine(monkeypatch):
    calls = _spy_mr(monkeypatch)
    res = run_strategy_backtest(_range_df(), "XAUUSD", cfg=dict(_MR_CFG))
    assert calls["n"] > 0  # whole window handed to the MR engine
    # No breakout (SMC) trade may leak through the MR-primary branch.
    assert {t.get("strategy_type") for t in res["trades"]} <= {"MR_V1"}


def test_breakout_run_never_calls_mr(monkeypatch):
    calls = _spy_mr(monkeypatch)
    breakout = {k: v for k, v in _MR_CFG.items() if k != "mr_primary"}
    run_strategy_backtest(_range_df(), "XAUUSD", cfg=breakout)
    assert calls["n"] == 0  # default path stays on the breakout engine


def test_window_decision_honours_adx_threshold():
    df = _range_df(n=160)
    os.environ.update({"BT_IN_LEN": "60", "BT_OOS_LEN": "40", "BT_STEP_LEN": "40",
                       "BT_MR_PRIMARY": "1"})

    os.environ["BT_MR_PRIMARY_ADX"] = "999"  # in-sample ADX always below → all MR
    hi = run_walk_forward_backtest(df, "XAUUSD", smc_strategy=True, smc_v2=True)
    assert hi and all(w["best_config"].get("mr_primary") for w in hi)

    os.environ["BT_MR_PRIMARY_ADX"] = "0"    # ADX never below 0 → never MR
    lo = run_walk_forward_backtest(df, "XAUUSD", smc_strategy=True, smc_v2=True)
    assert lo and not any(w["best_config"].get("mr_primary") for w in lo)


def test_inert_when_never_triggered():
    """BT_MR_PRIMARY armed but threshold 0 (never fires) → identical OOS metrics to
    a plain base run, proving the feature can't change default behaviour."""
    df = _range_df(n=160)
    os.environ.update({"BT_IN_LEN": "60", "BT_OOS_LEN": "40", "BT_STEP_LEN": "40"})
    base = run_walk_forward_backtest(df, "XAUUSD", smc_strategy=True, smc_v2=True)

    os.environ.update({"BT_MR_PRIMARY": "1", "BT_MR_PRIMARY_ADX": "0"})
    armed = run_walk_forward_backtest(df, "XAUUSD", smc_strategy=True, smc_v2=True)

    assert len(base) == len(armed)
    for b, a in zip(base, armed):
        assert b["trades_count"] == a["trades_count"]
        assert b["oos_metrics"]["profit_factor"] == a["oos_metrics"]["profit_factor"]
