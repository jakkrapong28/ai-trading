"""Knob plumbing for the walk-forward A/B (Roadmap ข้อ 2-3).

`_experiment_knobs()` turns BT_* env vars into a cfg dict so experiments run
without code edits, and stays empty (= baseline) when nothing is set.
"""
from datetime import datetime, timezone

from backend.backtest import _experiment_knobs
from backend.core.smc import get_session_boost

_ALL = ["BT_CB_MAX_LOSSES", "BT_CB_COOLDOWN", "BT_MIN_ADX", "BT_BLOCK_VOLATILE",
        "BT_MAX_ATR_EXPANSION", "BT_RR_BULL", "BT_RR_BEAR", "BT_RR_SIDEWAYS",
        "BT_RR_VOLATILE", "BT_MIN_SESSION"]


def test_knobs_default_is_baseline(monkeypatch):
    for k in _ALL:
        monkeypatch.delenv(k, raising=False)
    knobs = _experiment_knobs()
    assert knobs["cb_max_losses"] == 0
    assert knobs["smc_block_volatile"] is False
    assert "smc_min_adx" not in knobs
    assert "rr_by_regime" not in knobs        # H1 off
    assert "min_session_boost" not in knobs   # H2 off


def test_knobs_rr_map_and_session(monkeypatch):
    for k in _ALL:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("BT_RR_BULL", "2.5")
    monkeypatch.setenv("BT_RR_SIDEWAYS", "1.2")
    monkeypatch.setenv("BT_MIN_SESSION", "1.0")
    monkeypatch.setenv("BT_CB_MAX_LOSSES", "3")
    monkeypatch.setenv("BT_MIN_ADX", "20")
    knobs = _experiment_knobs()
    assert knobs["rr_by_regime"] == {"BULL": 2.5, "SIDEWAYS": 1.2}  # only set regimes
    assert knobs["min_session_boost"] == 1.0
    assert knobs["cb_max_losses"] == 3
    assert knobs["smc_min_adx"] == 20.0


def test_session_boost_ranks_sessions():
    overlap = get_session_boost(datetime(2024, 1, 1, 14, tzinfo=timezone.utc))  # 13-17
    asian = get_session_boost(datetime(2024, 1, 1, 5, tzinfo=timezone.utc))     # 2-9
    assert overlap == 1.1
    assert asian == 0.8
    assert overlap > asian
