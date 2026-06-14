import os
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

    for _ in range(3):
        if not await mock_broker.ping():
            heartbeat.reconnect_attempts += 1

    os.environ.pop("CURRENT_MODE", None)
    os.environ.pop("PORTFOLIO_CRITICAL_WATCH", None)

    if heartbeat.reconnect_attempts >= 3:
        await heartbeat.handle_disconnect()

    # P1-3: disconnect must alert CRITICAL *and* freeze trading.
    mock_send_alert.assert_awaited_once()
    level, message = mock_send_alert.await_args.args
    assert level == "CRITICAL"
    assert "MT5 disconnect after 3 attempts" in message
    assert os.environ["CURRENT_MODE"] == "watch"
    assert os.environ["PORTFOLIO_CRITICAL_WATCH"] == "true"
