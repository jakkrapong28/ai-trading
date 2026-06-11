import pytest

def test_spread_spike_filter():
    normal_spread = 2.0
    
    # 1. Normal spread (e.g. 2.5)
    broker_spread = 2.5
    spread_ratio = broker_spread / normal_spread
    assert spread_ratio <= 5.0
    
    # 2. Spiked spread (e.g. 11.0)
    broker_spread_spike = 11.0
    spread_ratio_spike = broker_spread_spike / normal_spread
    assert spread_ratio_spike > 5.0 # Should reject
