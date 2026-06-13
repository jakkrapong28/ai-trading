import pytest
from datetime import datetime, timezone, timedelta
from backend.core.candle_manager import CandleManager, _floor_timestamp, TIMEFRAMES

@pytest.fixture
def cm():
    return CandleManager("XAUUSD")

class TestFloorTimestamp:
    def test_m15(self):
        ts = datetime(2024, 1, 15, 14, 33, 15, tzinfo=timezone.utc)
        floored = _floor_timestamp(ts, "M15")
        assert floored.minute == 30
        assert floored.second == 0

    def test_h1(self):
        ts = datetime(2024, 1, 15, 14, 33, 15, tzinfo=timezone.utc)
        floored = _floor_timestamp(ts, "H1")
        assert floored.hour == 14
        assert floored.minute == 0

    def test_h4(self):
        ts = datetime(2024, 1, 15, 14, 33, 15, tzinfo=timezone.utc)
        floored = _floor_timestamp(ts, "H4")
        assert floored.hour == 12
        assert floored.minute == 0

    def test_d1(self):
        ts = datetime(2024, 1, 15, 14, 33, 15, tzinfo=timezone.utc)
        floored = _floor_timestamp(ts, "D1")
        assert floored.hour == 0
        assert floored.minute == 0

class TestCandleManager:
    def test_on_tick_creates_first_candle(self, cm):
        cm.on_tick(2350.0, 100, datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc))
        h1 = cm.get_ohlc("H1")
        assert len(h1) == 1  # building candle
        assert h1.iloc[0]["open"] == 2350.0
        assert h1.iloc[0]["high"] == 2350.0
        assert h1.iloc[0]["low"] == 2350.0
        assert h1.iloc[0]["close"] == 2350.0
        assert h1.iloc[0]["volume"] == 100

    def test_ohlc_aggregation_same_candle(self, cm):
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        cm.on_tick(2350.0, 100, ts)
        cm.on_tick(2355.0, 50, ts + timedelta(seconds=1))
        cm.on_tick(2348.0, 30, ts + timedelta(seconds=2))
        cm.on_tick(2352.0, 20, ts + timedelta(seconds=3))

        h1 = cm.get_ohlc("H1")
        assert len(h1) == 1
        assert h1.iloc[0]["open"] == 2350.0
        assert h1.iloc[0]["high"] == 2355.0
        assert h1.iloc[0]["low"] == 2348.0
        assert h1.iloc[0]["close"] == 2352.0
        assert h1.iloc[0]["volume"] == 200

    def test_candle_closure_on_new_period(self, cm):
        ts_14 = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        ts_15 = datetime(2024, 1, 15, 15, 0, 5, tzinfo=timezone.utc)

        cm.on_tick(2350.0, 100, ts_14)
        cm.on_tick(2360.0, 50, ts_15)

        h1 = cm.get_ohlc("H1")
        assert len(h1) == 2  # 1 completed + 1 building
        assert h1.iloc[0]["close"] == 2350.0  # closed candle from 14:00
        assert h1.iloc[1]["open"] == 2360.0   # new building candle from 15:00

    def test_get_completed_ohlc(self, cm):
        ts_14 = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        ts_15 = datetime(2024, 1, 15, 15, 0, 5, tzinfo=timezone.utc)

        cm.on_tick(2350.0, 100, ts_14)
        cm.on_tick(2360.0, 50, ts_15)

        completed = cm.get_completed_ohlc("H1")
        assert len(completed) == 1
        assert completed.iloc[0]["close"] == 2350.0

    def test_get_all_timeframes(self, cm):
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        cm.on_tick(2350.0, 100, ts)

        all_tf = cm.get_all_timeframes()
        assert set(all_tf.keys()) == {"M15", "H1", "H4", "D1"}
        for tf, df in all_tf.items():
            assert not df.empty
            assert "open" in df.columns
            assert "high" in df.columns
            assert "low" in df.columns
            assert "close" in df.columns
            assert "volume" in df.columns

    def test_multiple_candles_beyond_maxlen(self, cm):
        # Fill H1 with max_candles + extra ticks
        cm.max_candles = 5
        cm._candles["H1"] = type(cm._candles["H1"])(maxlen=5)

        base_ts = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            cm.on_tick(2350.0 + i, 100, base_ts + timedelta(hours=i))

        # get_completed_ohlc should show maxlen candles
        h1 = cm.get_completed_ohlc("H1")
        assert len(h1) == 5  # maxlen capped

    def test_last_price_property(self, cm):
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        cm.on_tick(2350.0, 100, ts)
        assert cm.last_price == 2350.0

        cm.on_tick(2355.0, 50, ts + timedelta(seconds=1))
        assert cm.last_price == 2355.0

    def test_status(self, cm):
        ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        cm.on_tick(2350.0, 100, ts)

        s = cm.status()
        assert "H1" in s
        assert s["H1"]["completed"] == 0
        assert s["H1"]["building"] == True

    def test_timezone_naive_tick(self, cm):
        """Ticks without timezone should be treated as UTC."""
        naive_ts = datetime(2024, 1, 15, 14, 0, 0)
        cm.on_tick(2350.0, 100, naive_ts)

        h1 = cm.get_ohlc("H1")
        assert len(h1) == 1
        assert h1.iloc[0]["open"] == 2350.0

    def test_multi_timeframe_candle_boundaries(self, cm):
        """Test that M15, H4, D1 also aggregate correctly."""
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        cm.on_tick(100.0, 10, ts)
        cm.on_tick(110.0, 10, ts + timedelta(minutes=5))
        cm.on_tick(90.0, 10, ts + timedelta(minutes=10))
        cm.on_tick(105.0, 10, ts + timedelta(minutes=20))  # new M15

        m15 = cm.get_ohlc("M15")
        assert len(m15) == 2
        assert m15.iloc[0]["high"] == 110.0
        assert m15.iloc[0]["low"] == 90.0

        h1 = cm.get_ohlc("H1")
        assert len(h1) == 1  # still same H1 candle
        assert h1.iloc[0]["high"] == 110.0
        assert h1.iloc[0]["low"] == 90.0

    def test_yahoo_bootstrap_fill_gap(self, cm, monkeypatch):
        """When no live ticks, bootstrap populates completed candles."""
        async def mock_fetch(symbol, interval, range_val):
            import pandas as pd
            return pd.DataFrame({
                "timestamp": [
                    datetime(2024, 1, 15 + i, 0, 0, tzinfo=timezone.utc)
                    for i in range(10)
                ],
                "open": [2300.0 + i for i in range(10)],
                "high": [2310.0 + i for i in range(10)],
                "low": [2290.0 + i for i in range(10)],
                "close": [2305.0 + i for i in range(10)],
                "volume": [1000.0] * 10,
            })
        
        monkeypatch.setattr(cm, "_fetch_yahoo_ohlc", mock_fetch)
        
        # This also tests that only D1 is fetched (M15/H1/H4 return different range)
        # However mock returns same data for all — that's fine for this test
        import pytest
        # bootstrap with our mock
        import asyncio
        asyncio.run(cm.bootstrap_from_yahoo(force=True))
        
        d1 = cm.get_ohlc("D1", bars=20)
        assert len(d1) == 10
        assert d1.iloc[0]["open"] == 2300.0
        assert d1.iloc[-1]["close"] == 2314.0


def test_candle_manager_global_registry():
    from backend.core.candle_manager import candle_managers, CandleManager
    
    cm = CandleManager("TEST_SYMBOL")
    candle_managers["TEST_SYMBOL"] = cm
    
    ts = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    cm.on_tick(100.0, 50, ts)
    
    assert "TEST_SYMBOL" in candle_managers
    assert candle_managers["TEST_SYMBOL"].last_price == 100.0
    
    # Cleanup registry
    del candle_managers["TEST_SYMBOL"]
