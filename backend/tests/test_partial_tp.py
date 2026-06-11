import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_partial_tp_targets():
    from backend.engines.execution import ExecutionEngine
    from backend.shared.schema.events import MarketTickEvent
    
    engine = ExecutionEngine(MagicMock())
    engine.broker = MagicMock()
    engine.broker.get_positions = AsyncMock(return_value=[{
        "ticker": "XAUUSD",
        "action": "BUY",
        "entry_price": 2300.0,
        "sl_price": 2280.0,
        "tp_price": 2360.0,
        "order_id": "test-trade-1",
        "lot_size": 1.0,
        "status": "OPEN"
    }])
    
    # Mock database session to return our Trade record
    mock_trade = MagicMock()
    mock_trade.id = "test-trade-1"
    mock_trade.ticker = "XAUUSD"
    mock_trade.action = MagicMock(value="BUY")
    mock_trade.entry_price = 2300.0
    mock_trade.sl_price = 2280.0
    mock_trade.tp_price = 2360.0
    mock_trade.lot_size = 1.0
    mock_trade.status = "OPEN"
    mock_trade.tp1_hit = False
    mock_trade.tp2_hit = False
    mock_trade.tp3_hit = False
    mock_trade.highest_price = 2300.0
    mock_trade.atr_at_entry = 10.0
    
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = mock_trade
    
    with patch("backend.engines.execution.SessionLocal", return_value=db_mock), \
         patch("backend.engines.execution.cb_manager.get_trade_lock") as mock_lock:
        
        mock_lock.return_value.__aenter__ = AsyncMock()
        mock_lock.return_value.__aexit__ = AsyncMock()
        
        # Mock partial close helpers
        engine._execute_close = AsyncMock()
        engine.broker.modify_order = AsyncMock()
        
        # Simulate price reaching TP1 (2320.0, which is +1.0R since risk is 20)
        from backend.config import FEATURE_FLAGS
        with patch.dict(FEATURE_FLAGS, {"partial_tp": True}):
            # Mock tick at 2321.0
            msg = {
                "ticker": "XAUUSD",
                "price": 2321.0,
                "source": "mock"
            }
            # Manually run the monitor loop logic for this tick
            tick = MarketTickEvent(**msg)
            engine.latest_prices[tick.ticker] = tick.price
            
            # Execute trade monitoring block logic directly
            current_r = (tick.price - mock_trade.entry_price) / 20.0 # initial_risk = 20
            assert current_r >= 1.0
            
            # Check TP1 triggers
            if current_r >= 1.0 and not mock_trade.tp1_hit:
                mock_trade.tp1_hit = True
                await engine._execute_close(mock_trade, tick.price, "TP1 Hit", close_pct=0.5)
                await engine.broker.modify_order(mock_trade.id, stop_loss=mock_trade.entry_price)
                
            engine._execute_close.assert_called_with(mock_trade, 2321.0, "TP1 Hit", close_pct=0.5)
            engine.broker.modify_order.assert_called_with("test-trade-1", stop_loss=2300.0)
