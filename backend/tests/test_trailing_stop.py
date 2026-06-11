import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_adaptive_trailing_stop():
    from backend.engines.execution import ExecutionEngine
    
    engine = ExecutionEngine(MagicMock())
    engine.broker = MagicMock()
    engine.broker.modify_order = AsyncMock()
    
    # 1. Trailing 2 ATR at 1.8R
    # BUY entry = 2300, initial sl = 2280 (risk = 20), ATR = 10
    # Price reaches 2336 (which is +1.8R)
    price = 2336.0
    atr = 10.0
    action = "BUY"
    sl = 2280.0
    
    trailing_sl = price - 2 * atr
    assert trailing_sl == 2316.0
    assert trailing_sl > sl # More favorable, should modify
    
    # 2. Trailing 1.5 ATR at 3.0R
    # Price reaches 2360 (which is 3.0R)
    price = 2360.0
    trailing_sl_2 = price - 1.5 * atr
    assert trailing_sl_2 == 2345.0
    
    # 3. Chandelier Exit (trailing 1 ATR from peak 2380) at 4.0R
    peak = 2380.0
    trailing_sl_3 = peak - 1 * atr
    assert trailing_sl_3 == 2370.0
