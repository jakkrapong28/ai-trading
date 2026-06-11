import pytest
from backend.core import OrderDeduplicator

def test_order_deduplication():
    dedup = OrderDeduplicator(maxlen=10)
    
    # First time: not a duplicate
    assert not dedup.is_duplicate("XAUUSD", "BUY", 2350.0)
    
    # Mark executed
    dedup.mark_executed("XAUUSD", "BUY", 2350.0)
    
    # Second time: should be a duplicate
    assert dedup.is_duplicate("XAUUSD", "BUY", 2350.0)
    
    # Different action: not duplicate
    assert not dedup.is_duplicate("XAUUSD", "SELL", 2350.0)
    
    # Different price: not duplicate
    assert not dedup.is_duplicate("XAUUSD", "BUY", 2355.0)
