import pytest
from datetime import datetime, timezone
from backend.core.mtf import is_candle_closed

def test_d1_candle_closed_with_mt5_timestamps():
    # MT5 daily bar timestamp convention (23:59 UTC)
    assert is_candle_closed("D1", datetime(2024, 1, 15, 23, 59, tzinfo=timezone.utc)) == True
    assert is_candle_closed("D1", datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)) == False

@pytest.mark.asyncio
async def test_verify_d1_candle_timestamps(monkeypatch):
    import pandas as pd
    from backend.core.mtf import verify_d1_candle_timestamps
    
    alert_called = []
    async def mock_send_alert(level, msg):
        alert_called.append((level, msg))
    
    monkeypatch.setattr("backend.alert.send_alert", mock_send_alert)
    
    # 1. Test when closed count is non-zero
    df_ok = pd.DataFrame({"dummy": [1, 2]}, index=[
        datetime(2024, 1, 15, 23, 59, tzinfo=timezone.utc),
        datetime(2024, 1, 16, 23, 59, tzinfo=timezone.utc)
    ])
    count = await verify_d1_candle_timestamps(df_ok)
    assert count == 2
    assert len(alert_called) == 0
    
    # 2. Test when closed count is zero (should alert)
    df_fail = pd.DataFrame({"dummy": [1, 2]}, index=[
        datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc)
    ])
    count_fail = await verify_d1_candle_timestamps(df_fail)
    assert count_fail == 0
    assert len(alert_called) == 1
    assert alert_called[0][0] == "CRITICAL"
