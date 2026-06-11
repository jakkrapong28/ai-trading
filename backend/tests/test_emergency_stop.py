import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
@patch("backend.main.SessionLocal")
@patch("backend.main.event_bus")
async def test_emergency_stop_trigger(mock_eb, mock_session_class):
    from backend.main import emergency_stop
    from backend.config import FEATURE_FLAGS
    
    mock_db = MagicMock()
    mock_session_class.return_value = mock_db
    mock_eb.publish = AsyncMock()
    
    # Mock some active trades
    mock_trade = MagicMock()
    mock_trade.id = "trade-1"
    mock_trade.ticker = "XAUUSD"
    mock_trade.action = MagicMock(value="BUY")
    mock_trade.status = "OPEN"
    mock_trade.lot_size = 1.0
    mock_trade.entry_price = 2300.0
    
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_trade]
    
    # Initialize some flags to True
    FEATURE_FLAGS["partial_tp"] = True
    FEATURE_FLAGS["smc_strategy"] = True
    
    res = await emergency_stop()
    
    assert res == {"success": True}
    assert os.environ.get("PORTFOLIO_CRITICAL_WATCH") == "true"
    
    # Verify trade is set to CLOSED
    from backend.shared.database.models import TradeStatus
    assert mock_trade.status == TradeStatus.CLOSED
    
    # Verify flags are disabled
    assert not FEATURE_FLAGS["partial_tp"]
    assert not FEATURE_FLAGS["smc_strategy"]
    assert FEATURE_FLAGS["circuit_breaker_v2"] # Remains True
    assert FEATURE_FLAGS["emergency_stop"] # Remains True
