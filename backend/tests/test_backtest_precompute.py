"""Guard the backtest precompute optimization (2026-06-21).

`_precompute_smc_bars` computes the cfg-independent per-bar context (indicators /
macro / regime) once so a parameter sweep can reuse it instead of recomputing the
heavy regime call ~20x per window (measured 9x faster). This test pins the
invariant that makes the optimization safe: feeding a precomputed context produces
the EXACT same trades/metrics as letting run_strategy_backtest build its own.
"""
import numpy as np
import pandas as pd

from backend.backtest import run_strategy_backtest, _precompute_smc_bars


def _walk_df(n: int = 300, seed: int = 7) -> pd.DataFrame:
    """A seeded random-walk OHLC series long enough to clear warmup and print a
    few trades through the SMC v2 path."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 2000.0 + steps
    high = close + np.abs(rng.normal(0, 0.6, n))
    low = close - np.abs(rng.normal(0, 0.6, n))
    open_ = close - rng.normal(0, 0.4, n)
    vol = rng.uniform(80, 120, n)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_, "high": high, "low": low, "close": close, "volume": vol,
    })


_CFG = {"smc_strategy": True, "smc_v2": True, "ob_size_atr": 0.5,
        "fvg_gap_atr": 0.3, "mtf_strategy": True}


def test_precomputed_matches_self_computed():
    df = _walk_df()
    base = run_strategy_backtest(df, "XAUUSD", cfg=dict(_CFG))
    pre = _precompute_smc_bars(df, "XAUUSD", use_mtf=True)
    reused = run_strategy_backtest(df, "XAUUSD", cfg=dict(_CFG), precomputed=pre)

    assert base["metrics"]["total_trades"] == reused["metrics"]["total_trades"]
    assert base["metrics"]["total_pnl"] == reused["metrics"]["total_pnl"]
    assert base["metrics"]["profit_factor"] == reused["metrics"]["profit_factor"]
    # entry/exit prices identical trade-for-trade
    assert [t["entry_price"] for t in base["trades"]] == [t["entry_price"] for t in reused["trades"]]
    assert [t["pnl"] for t in base["trades"]] == [t["pnl"] for t in reused["trades"]]


def test_precompute_covers_post_warmup_bars():
    df = _walk_df(n=120)
    pre = _precompute_smc_bars(df, "XAUUSD", use_mtf=True)
    # warmup=50 → first context bar is index 50, last is the final bar.
    assert pre[0]["i"] == 50
    assert pre[-1]["i"] == len(df) - 1
    assert all("indicators" in b and "regime" in b for b in pre)
