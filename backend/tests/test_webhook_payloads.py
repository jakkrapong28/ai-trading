"""P1-1: webhook payloads for break_even / trailing_activated / partial_closed
must map Core's ExecutionEvent fields (ticker, realized_pnl) to the ERP shape
(symbol, pnl) the handler reads."""
from backend.shared.webhooks import _build_payload


def test_break_even_payload_maps_symbol():
    p = _build_payload("trade.break_even", {"ticker": "XAUUSD", "price": 2300.0}, "t1")
    assert p["event"] == "trade.break_even"
    assert p["data"]["symbol"] == "XAUUSD"
    assert p["data"]["price"] == 2300.0
    assert p["data"]["trade_id"] == "t1"


def test_trailing_payload_includes_new_stop_loss():
    p = _build_payload(
        "trade.trailing_activated",
        {"ticker": "BTCUSDT", "price": 68100.0, "new_stop_loss": 68050.0},
        "t2",
    )
    assert p["data"]["symbol"] == "BTCUSDT"
    assert p["data"]["new_stop_loss"] == 68050.0


def test_partial_closed_payload_maps_pnl_and_fee():
    ev = {
        "ticker": "XAUUSD",
        "action": "BUY",
        "exit_price": 2310.0,
        "lot_size": 0.05,
        "realized_pnl": 50.0,
        "fee": 1.2,
    }
    p = _build_payload("trade.partial_closed", ev, "t3")
    assert p["event"] == "trade.partial_closed"
    assert p["data"]["symbol"] == "XAUUSD"
    assert p["data"]["pnl"] == 50.0
    assert p["data"]["fee"] == 1.2
    assert p["data"]["lot_size"] == 0.05


def test_opened_payload_has_keys_erp_reads():
    # ERP handlers.mjs trade.opened reads: data.action, data.symbol, data.price,
    # data.volume || data.lot_size, data.trade_id.
    ev = {"ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0, "lot_size": 0.1}
    d = _build_payload("trade.opened", ev, "t4")["data"]
    for key in ("trade_id", "symbol", "action", "price", "volume", "lot_size"):
        assert key in d, f"ERP expects data.{key}"
    assert d["symbol"] == "XAUUSD" and d["price"] == 2000.0 and d["volume"] == 0.1


def test_pnl_realized_payload_has_keys_erp_reads():
    # ERP handlers.mjs trade.pnl_realized reads: data.pnl, data.fee, data.symbol,
    # data.price/exit_price, data.lot_size, data.trade_id.
    ev = {
        "ticker": "XAUUSD", "action": "BUY", "entry_price": 2000.0,
        "exit_price": 2010.0, "lot_size": 0.1, "realized_pnl": 100.0, "fee": 1.61,
    }
    d = _build_payload("trade.pnl_realized", ev, "t5")["data"]
    for key in ("trade_id", "symbol", "action", "price", "exit_price", "entry_price", "lot_size", "pnl", "fee"):
        assert key in d, f"ERP expects data.{key}"
    assert d["pnl"] == 100.0 and d["fee"] == 1.61
