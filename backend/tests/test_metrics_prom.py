"""P4-4 · Prometheus exposition builder (pure)."""
from backend.shared.metrics_prom import sanitize, render, core_metrics_text


def test_sanitize_names():
    assert sanitize("Signals Generated") == "signals_generated"
    assert sanitize("Win Rate %") == "win_rate"


def test_render_emits_help_type_and_labels():
    text = render([{
        "name": "x_metric", "type": "gauge", "help": "demo",
        "samples": [(None, 3), ({"symbol": "BTC"}, 5)],
    }])
    assert "# HELP x_metric demo" in text
    assert "# TYPE x_metric gauge" in text
    assert "x_metric 3" in text
    assert 'x_metric{symbol="BTC"} 5' in text
    assert text.endswith("\n")


def test_core_metrics_text_includes_globals_extras_and_feeds():
    gm = {"Signals Generated": 4, "Win Rate": 0.5, "label_str": "skip-me"}
    feeds = [
        {"symbol": "BTCUSDT", "source": "binance", "age": 1.2, "status": "live"},
        {"symbol": "AAPL", "source": "mock", "age": 3.0, "status": "mock"},
    ]
    text = core_metrics_text(gm, nan_count=2, correlation_rejections=1, active_tasks=9, feeds=feeds)

    assert "ai_trading_signals_generated 4" in text
    assert "ai_trading_win_rate 0.5" in text
    assert "label_str" not in text  # non-numeric skipped
    assert "ai_trading_nan_detection_total 2" in text
    assert "ai_trading_active_background_tasks 9" in text
    assert 'ai_trading_feed_live{symbol="BTCUSDT"} 1' in text
    assert 'ai_trading_feed_live{symbol="AAPL"} 0' in text
    assert 'ai_trading_feed_age_seconds{symbol="BTCUSDT",source="binance"} 1.2' in text
