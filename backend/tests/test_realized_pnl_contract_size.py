"""P0 regression: realized PnL must honour contractSize, and fees must be charged.

Guards the bug where PaperBroker computed `(exit-entry)*lot` (missing contractSize),
making XAUUSD/EURUSD realized PnL 100x / 100000x too small while floating PnL was
correct — causing equity to jump on close.
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.core.base import trade_pnl, compute_fee


def test_trade_pnl_multiplies_contract_size_metal():
    # XAUUSD contractSize=100: 10 points * 0.1 lot * 100 = 100.0
    assert trade_pnl("XAUUSD", "BUY", 2000.0, 2010.0, 0.1) == pytest.approx(100.0)


def test_trade_pnl_sell_direction():
    assert trade_pnl("XAUUSD", "SELL", 2010.0, 2000.0, 0.1) == pytest.approx(100.0)


def test_trade_pnl_crypto_contract_size_one():
    # BTCUSDT contractSize=1: 100 * 0.02 * 1 = 2.0
    assert trade_pnl("BTCUSDT", "BUY", 68000.0, 68100.0, 0.02) == pytest.approx(2.0)


def test_compute_fee_positive_and_scaled_by_notional():
    # XAUUSD notional = 0.1 * 100 * 2010 = 20100; * 0.00008 = 1.608 -> 1.61
    fee = compute_fee("XAUUSD", 2010.0, 0.1)
    assert fee == pytest.approx(1.61, abs=0.01)
    # Half the lot -> half the fee
    assert compute_fee("XAUUSD", 2010.0, 0.05) == pytest.approx(fee / 2, abs=0.01)


@pytest.mark.asyncio
async def test_paper_broker_close_uses_contract_size_and_fee():
    from backend.brokers.paper import PaperBroker

    trade = MagicMock()
    trade.id = "t1"
    trade.ticker = "XAUUSD"
    trade.action = MagicMock(value="BUY")
    trade.entry_price = 2000.0
    trade.lot_size = 0.1
    trade.realized_pnl = None
    trade.fee = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = trade

    with patch("backend.brokers.paper.SessionLocal", return_value=db):
        res = await PaperBroker().close_order("t1", exit_price=2010.0)

    assert res["realized_pnl"] == pytest.approx(100.0)   # not 1.0
    assert res["fee"] > 0
    assert trade.realized_pnl == pytest.approx(100.0)
    assert trade.fee == res["fee"]
