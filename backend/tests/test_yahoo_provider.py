"""Stocks → real prices via free Yahoo feed (no API key)."""
from backend.engines.providers.yahoo import parse_chart_price, YAHOO_SYMBOLS, YahooProvider
from unittest.mock import MagicMock


def test_parse_regular_market_price():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 291.13}}]}}
    assert parse_chart_price(payload) == 291.13


def test_parse_falls_back_to_previous_close_when_market_closed():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": None, "previousClose": 288.5}}]}}
    assert parse_chart_price(payload) == 288.5


def test_parse_bad_payload_returns_none():
    assert parse_chart_price({}) is None
    assert parse_chart_price({"chart": {"result": []}}) is None


def test_provider_enabled_without_key():
    assert YahooProvider(MagicMock()).enabled is True


def test_covers_requested_stocks():
    for s in ("AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "XAUUSD"):
        assert s in YAHOO_SYMBOLS
