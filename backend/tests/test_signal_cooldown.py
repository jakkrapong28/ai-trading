import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

@patch("backend.engines.strategy.SessionLocal")
def test_signal_cooldown_active(mock_session_class):
    from backend.engines.strategy import StrategyEngine
    
    mock_db = MagicMock()
    mock_session_class.return_value = mock_db
    
    # Mock active cooldown in DB
    mock_cooldown = MagicMock()
    mock_cooldown.symbol = "XAUUSD"
    mock_cooldown.signal_type = "BUY"
    mock_cooldown.cooldown_until = datetime.utcnow() + timedelta(minutes=10)
    
    mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = mock_cooldown
    
    engine = StrategyEngine(MagicMock())
    
    # Cooldown should be active
    from backend.config import FEATURE_FLAGS
    with patch.dict(FEATURE_FLAGS, {"signal_cooldown": True}):
        assert engine._is_cooldown_active("XAUUSD", "BUY")
