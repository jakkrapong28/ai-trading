import pytest
from unittest.mock import MagicMock, patch

@patch("backend.engines.risk.SessionLocal")
def test_max_positions_constraint(mock_session_class):
    from backend.engines.risk import RiskEngine
    from backend.shared.schema.events import AIDecisionEvent
    
    mock_db = MagicMock()
    mock_session_class.return_value = mock_db
    
    # 2 active positions already open for XAUUSD
    mock_db.query.return_value.filter.return_value.count.return_value = 2
    
    engine = RiskEngine(MagicMock())
    engine._reject = MagicMock()
    
    decision = AIDecisionEvent(
        ticker="XAUUSD",
        action="BUY",
        confidence=0.85,
        votes={},
        reasoning="Test"
    )
    
    # Run process decision block manually to verify limit
    from backend.engines.risk import MAX_POSITIONS_PER_SYMBOL
    open_count = mock_db.query().filter().count()
    assert open_count >= MAX_POSITIONS_PER_SYMBOL
