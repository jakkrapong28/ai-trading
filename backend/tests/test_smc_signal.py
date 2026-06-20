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


def _ranged_df(price: float = 100.0, n: int = 30, half_range: float = 0.5) -> pd.DataFrame:
    """A df with a known median true-range (= 2*half_range) so the ATR-expansion
    gate can be exercised deterministically."""
    return pd.DataFrame({
        "open": [price] * n, "high": [price + half_range] * n,
        "low": [price - half_range] * n, "close": [price] * n, "volume": [1.0] * n,
    })


_BULLISH_LEVELS = {
    "order_blocks": [{"top": 100.5, "bottom": 99.0, "kind": "bull"}],
    "fvgs": [], "swings": [], "mss": {"price": 99.5, "kind": "bullish_bos"},
}


def _trending_df(start: float = 100.0, n: int = 40, step: float = 1.0) -> pd.DataFrame:
    """A clean uptrend → high ADX (strong trend)."""
    closes = [start + step * i for i in range(n)]
    return pd.DataFrame({
        "open": closes, "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes], "close": closes, "volume": [1.0] * n,
    })


def _choppy_df(price: float = 100.0, n: int = 40, amp: float = 1.0) -> pd.DataFrame:
    """A tight oscillation → low ADX (range/chop, like the disaster window)."""
    closes = [price + (amp if i % 2 else -amp) for i in range(n)]
    return pd.DataFrame({
        "open": closes, "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes], "close": closes, "volume": [1.0] * n,
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


# ── volatility / regime stand-aside gates (Roadmap ข้อ 2) ──────────────────

def test_block_volatile_regime_stands_aside(monkeypatch):
    # A clean TIER-A buy, but the regime is VOLATILE and the knob is on → stand aside.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 50},
                              macro="Bullish", regime="VOLATILE",
                              block_volatile_regime=True)
    assert out["action"] == "WAIT"
    assert "VOLATILE" in out["reason"]


def test_volatile_regime_ignored_when_knob_off(monkeypatch):
    # Same VOLATILE regime, knob off (default) → trades as before (no behaviour change).
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_flat_df(100.0), atr=1.0, indicators={"rsi": 50},
                              macro="Bullish", regime="VOLATILE")
    assert out["action"] == "BUY"


def test_atr_expansion_stands_aside(monkeypatch):
    # median TR = 1.0; ATR 5.0 → 5x expansion > 2.0 threshold → stand aside.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_ranged_df(100.0, half_range=0.5), atr=5.0,
                              indicators={"rsi": 50}, macro="Bullish",
                              max_atr_expansion=2.0)
    assert out["action"] == "WAIT"
    assert "ATR expansion" in out["reason"]


def test_atr_expansion_allows_normal_vol(monkeypatch):
    # median TR = 1.0; ATR 1.0 → 1x expansion < 2.0 threshold → trades normally.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_ranged_df(100.0, half_range=0.5), atr=1.0,
                              indicators={"rsi": 50}, macro="Bullish",
                              max_atr_expansion=2.0)
    assert out["action"] == "BUY"


def test_calculate_adx_trend_vs_chop():
    # Sanity: a clean trend reads a much higher ADX than a tight oscillation.
    adx_trend = smc.calculate_adx(_trending_df())
    adx_chop = smc.calculate_adx(_choppy_df())
    assert adx_trend > 50
    assert adx_chop < 30
    assert adx_trend > adx_chop


def test_min_adx_blocks_chop(monkeypatch):
    # Choppy tape (low ADX) → stand aside, even with a bullish setup.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_choppy_df(), atr=1.0, indicators={"rsi": 50},
                              macro="Bullish", min_adx=30.0)
    assert out["action"] == "WAIT"
    assert "chop" in out["reason"]


def test_min_adx_allows_trend(monkeypatch):
    # Trending tape (high ADX) → the chop guard lets the trade through.
    monkeypatch.setattr(smc, "detect_smc_levels", lambda *a, **k: _BULLISH_LEVELS)
    out = evaluate_smc_signal(_trending_df(), atr=1.0, indicators={"rsi": 50},
                              macro="Bullish", min_adx=30.0)
    assert out["action"] == "BUY"
