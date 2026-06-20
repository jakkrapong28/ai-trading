import pytest
from datetime import datetime, timezone, timedelta
from backend.core.mtf import is_candle_closed

def test_d1_candle_closed_yahoo_convention():
    now = datetime.now(timezone.utc)
    # Yahoo/CandleManager convention: timestamp = start of day
    yesterday_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    assert is_candle_closed("D1", yesterday_start) == True
    assert is_candle_closed("D1", today_start) == (timedelta(days=1) <= timedelta(0))

def test_h1_candle_closed():
    now = datetime.now(timezone.utc)
    past_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    
    assert is_candle_closed("H1", past_hour) == True
    assert is_candle_closed("H1", current_hour) == ((current_hour + timedelta(hours=1)) <= now)

def test_m15_candle_closed():
    now = datetime.now(timezone.utc)
    # 30 mins ago, floored to :00 or :15 or :30 or :45
    past_15 = now - timedelta(minutes=30)
    past_15 = past_15.replace(minute=(past_15.minute // 15) * 15, second=0, microsecond=0)
    
    assert is_candle_closed("M15", past_15) == True
    assert is_candle_closed("M15", datetime.now(timezone.utc)) == False

@pytest.mark.asyncio
async def test_verify_d1_candle_timestamps(monkeypatch):
    import pandas as pd
    from backend.core.mtf import verify_d1_candle_timestamps
    
    alert_called = []
    async def mock_send_alert(level, msg):
        alert_called.append((level, msg))
    
    monkeypatch.setattr("backend.alert.send_alert", mock_send_alert)
    
    now = datetime.now(timezone.utc)
    two_days_ago = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Test when closed count is non-zero (start-of-day timestamps from CandleManager)
    df_ok = pd.DataFrame({"dummy": [1, 2]}, index=[two_days_ago, yesterday])
    count = await verify_d1_candle_timestamps(df_ok)
    assert count == 2
    assert len(alert_called) == 0
    
    # 2. Test with current candle (today, not yet closed) – still 1 closed from yesterday
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    df_partial = pd.DataFrame({"dummy": [1, 2]}, index=[yesterday, today])
    count_partial = await verify_d1_candle_timestamps(df_partial)
    expected = 2 if (today + timedelta(days=1)) <= now else 1
    assert count_partial == expected

    # 3. Production shape from CandleManager.get_ohlc(): RangeIndex + `timestamp`
    # column. This is the case that triggered the live
    # "'int' object has no attribute 'tzinfo'" crash — must not throw.
    df_prod = pd.DataFrame({
        "open": [1, 2], "high": [1, 2], "low": [1, 2], "close": [1, 2],
        "volume": [0, 0], "timestamp": [two_days_ago, yesterday],
    })
    assert await verify_d1_candle_timestamps(df_prod) == 2
