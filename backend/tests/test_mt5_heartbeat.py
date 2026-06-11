import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.brokers.paper import BrokerHeartbeat

@pytest.mark.asyncio
@patch("backend.brokers.paper.send_alert")
async def test_mt5_heartbeat_disconnect(mock_send_alert):
    mock_broker = MagicMock()
    mock_broker.ping = AsyncMock(return_value=False) # simulate failure
    mock_broker.reconcile_positions = AsyncMock()
    
    heartbeat = BrokerHeartbeat(mock_broker, interval=1)
    
    # Simulate failures
    assert heartbeat.reconnect_attempts == 0
    
    # Attempt 1
    ok = await mock_broker.ping()
    if not ok:
        heartbeat.reconnect_attempts += 1
    
    # Attempt 2
    ok = await mock_broker.ping()
    if not ok:
        heartbeat.reconnect_attempts += 1
        
    # Attempt 3
    ok = await mock_broker.ping()
    if not ok:
        heartbeat.reconnect_attempts += 1
        
    if heartbeat.reconnect_attempts >= 3:
        await heartbeat.handle_disconnect()
        
    mock_send_alert.assert_called_with(
        "CRITICAL",
        f"🚨 MT5 disconnect after {heartbeat.reconnect_attempts} attempts — last heartbeat: None"
    )
