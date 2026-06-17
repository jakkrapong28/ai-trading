"""SMC v2 directional, TIER-graded signal (pure logic, no network).

Guards `evaluate_smc_signal` — the Stage 1→5b funnel that replaces the v1
EMA-crossover direction hack. Geometry detection (`detect_smc_levels`) is
monkeypatched so these tests isolate the scoring / direction / gating logic.
"""
import pandas as pd

import backend.core.smc as smc
from backend.core.smc import evaluate_smc_signal, _zone_touch


def _flat_df(price: float = 100.0, n: int = 30) -> pd.DataFrame:
    return pd.DataFrame({
        "open": [price] * n, "high": [price] * n, "low": [price] * n,
        "close": [price] * n, "volume": [1.0] * n,
    })


def test_short_df_waits():
    out = evaluate_smc_signal(_flat_df(n=10), atr=1.0)
    assert out["action"] == "WAIT"
    assert out["strategy_type"] == "SMC_V2"


def test_zero_atr_waits():
    out = evaluate_smc_signal(_flat_df(), atr=0.0)
    assert out["action"] == "WAIT"


def test_zone_touch_tolerance():
    zones = [{"top": 101.0, "bottom": 99.0, "kind": "bull"}]
    assert _zone_touch(100.0, 1.0, zones, "bull")          # inside
    assert _zone_touch(101.2, 1.0, zones, "bull")          # within 0.25·ATR
    assert not _zone_touch(101.5, 1.0, zones, "bull")      # outside tolerance
    assert not _zone_touch(100.0, 1.0, zones, "bear")      # wrong kind


def test_bullish_confluence_is_tier_a_buy(monkeypatch):
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: {
        "order_blocks": [{"top": 100.5, "bottom": 99.0, "kind": "bull"}],
        "fvgs": [], "swings": [], "mss": {"price": 99.5, "kind": "bullish_bos"},
    })
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 50}, macro="Bullish")
    assert out["action"] == "BUY"
    assert out["tier"] == "A"
    assert out["confidence"] == smc.SMC_TIER_CONFIDENCE["A"]
    assert out["sl_anchor"] is not None and out["sl_anchor"] < 100.0


def test_regime_blocks_counter_trend_sell(monkeypatch):
    # A clean bearish setup, but the higher-TF regime is BULL → never fight it.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: {
        "order_blocks": [{"top": 101.0, "bottom": 99.5, "kind": "bear"}],
        "fvgs": [], "swings": [], "mss": {"price": 100.5, "kind": "bearish_bos"},
    })
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 50},
                              macro="Bearish", regime="BULL")
    assert out["action"] == "WAIT"
    assert "regime BULL" in out["reason"]


def test_overbought_rsi_blocks_buy(monkeypatch):
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: {
        "order_blocks": [{"top": 100.5, "bottom": 99.0, "kind": "bull"}],
        "fvgs": [], "swings": [], "mss": {"price": 99.5, "kind": "bullish_bos"},
    })
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 80}, macro="Bullish")
    assert out["action"] == "WAIT"
    assert "overbought" in out["reason"]


def test_thin_confluence_is_watch(monkeypatch):
    # Only a weak S/R nudge, no structure → below TIER-C → WATCH (no trade).
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: {
        "order_blocks": [], "fvgs": [], "swings": [], "mss": None,
    })
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 50})
    assert out["action"] == "WAIT"
    assert out["tier"] is None
