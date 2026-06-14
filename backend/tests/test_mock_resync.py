"""BUG-1 · mock price must stay on the real (Yahoo candle) scale.

Guards the bug where AAPL mock walked from a stale base (190) while the chart
showed Yahoo (~290), corrupting candles/RSI/signals.
"""
from backend.engines.providers.mock import _resync_base, MOCK_SYMBOLS


def test_first_tick_seeds_from_candle_close():
    assert _resync_base(None, 290.0, fallback=190.0) == 290.0


def test_first_tick_uses_fallback_when_no_candle():
    assert _resync_base(None, None, fallback=190.0) == 190.0


def test_resync_when_drifted_to_wrong_scale():
    # stale mock at 190 vs real candle 290 (34% off) -> snap back to 290
    assert _resync_base(190.0, 290.0, fallback=190.0) == 290.0


def test_keeps_price_when_close_to_candle():
    # within 5% -> keep walking from prev (continuity, no jitter)
    assert _resync_base(289.0, 290.0, fallback=190.0) == 289.0


def test_zero_candle_close_is_ignored():
    assert _resync_base(187.0, 0.0, fallback=190.0) == 187.0


def test_mock_covers_us_stocks_and_gold():
    for s in ("AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "XAUUSD"):
        assert s in MOCK_SYMBOLS
