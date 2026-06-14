"""P4-2 · feed_status() — drives the dashboard data-source badge.

live (fresh real feed) / stale (>60s real feed) / mock (synthetic gap-filler)
/ offline (never seen).
"""
from datetime import datetime, timezone, timedelta

import backend.engines.providers.base as base
from backend.engines.providers.base import feed_status


def _set(ticker, source, age_s):
    base.latest_prices[ticker] = {
        "last_price": 100.0,
        "source": source,
        "timestamp": datetime.now(timezone.utc) - timedelta(seconds=age_s),
    }


def test_offline_when_never_seen():
    base.latest_prices.pop("ZZZ", None)
    assert feed_status("ZZZ")["status"] == "offline"


def test_live_for_fresh_real_feed():
    _set("BTCUSDT", "binance", age_s=2)
    s = feed_status("BTCUSDT")
    assert s["status"] == "live"
    assert s["source"] == "binance"
    assert s["age"] is not None and s["age"] < 60


def test_stale_for_old_real_feed():
    _set("XAUUSD", "twelvedata", age_s=120)
    assert feed_status("XAUUSD")["status"] == "stale"


def test_mock_regardless_of_age():
    _set("NVDA", "mock", age_s=1)
    assert feed_status("NVDA")["status"] == "mock"
