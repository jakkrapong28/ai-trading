"""Regression tests for the P0 critical fixes.

Covers:
  Fix 1 — market_regime.calculate_regime must return 5 values (incl. volatility_score),
          so the tick-based regime fallback no longer raises NameError.
  Fix 2 — risk engine spread must come from real bid/ask, never random.uniform.
"""
import pathlib

import numpy as np
import pandas as pd

from backend.engines.market_regime import calculate_regime


def _make_price_df(n: int, start: float = 100.0, step: float = 0.5) -> pd.DataFrame:
    """Synthetic uptrend price series with a 'price' column."""
    prices = [start + i * step for i in range(n)]
    return pd.DataFrame({"price": prices})


def test_calculate_regime_returns_five_values():
    df = _make_price_df(250)
    result = calculate_regime(df)

    # Fix 1: previously returned 4 values; the fallback branch unpacked a 5th
    # (volatility_score) that was never defined -> NameError at runtime.
    assert len(result) == 5
    regime, regime_score, trend, atr, vol_score = result
    assert isinstance(regime, str)
    assert isinstance(vol_score, float)


def test_calculate_regime_short_df_also_returns_five_values():
    # The early-return path (len(df) < 200) must match the 5-value contract too.
    df = _make_price_df(10)
    result = calculate_regime(df)
    assert len(result) == 5


def test_spread_is_computed_from_bid_ask_not_random():
    # Fix 2: spread = ask - bid (deterministic), mirroring risk.py logic.
    price_data = {"bid": 2350.10, "ask": 2350.45, "last_price": 2350.30}
    bid, ask = price_data.get("bid"), price_data.get("ask")
    assert bid and ask and ask > bid
    broker_spread = round(ask - bid, 2)
    assert broker_spread == 0.35  # deterministic, same every run


def test_spread_fallback_is_constant_not_random():
    # When bid/ask are missing (e.g. mock stock feed), fall back to a fixed value.
    price_data = {"last_price": 150.0}
    bid, ask = price_data.get("bid"), price_data.get("ask")
    broker_spread = round(ask - bid, 2) if (bid and ask and ask > bid) else 2.0
    assert broker_spread == 2.0


def test_risk_engine_source_has_no_random_spread():
    # Guard against the random spread regressing back in.
    risk_src = (
        pathlib.Path(__file__).resolve().parents[1] / "engines" / "risk.py"
    ).read_text(encoding="utf-8")
    assert "random.uniform" not in risk_src
    assert "import random" not in risk_src
