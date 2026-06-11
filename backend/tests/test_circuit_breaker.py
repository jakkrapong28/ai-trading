import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
from backend.engines.risk import CircuitBreakerManager

@patch("asyncio.create_task")
def test_circuit_breaker_consecutive_losses(mock_create_task):
    manager = CircuitBreakerManager()
    assert not manager.is_any_active()
    
    # Trigger consecutive loss breaker
    manager.update_breakers(0.01, 0.02, 5)
    assert manager.is_any_active()
    assert manager.breakers["consecutive_loss"]["active"]
    
    # Reset consecutive loss breaker
    manager.update_breakers(0.01, 0.02, 0)
    assert not manager.breakers["consecutive_loss"]["active"]

@patch("asyncio.create_task")
def test_circuit_breaker_drawdowns(mock_create_task):
    manager = CircuitBreakerManager()
    
    # Trigger daily drawdown (3%)
    manager.update_breakers(0.035, 0.01, 0)
    assert manager.breakers["daily_loss"]["active"]
    
    # Trigger weekly drawdown (8%)
    manager.update_breakers(0.01, 0.09, 0)
    assert manager.breakers["weekly_loss"]["active"]

def test_timezone_aware_resets():
    manager = CircuitBreakerManager()
    reset_time = manager._get_next_reset("daily_loss")
    assert reset_time is not None
    assert reset_time.tzinfo == timezone.utc
