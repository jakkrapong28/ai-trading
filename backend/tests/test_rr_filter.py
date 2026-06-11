import pytest

def test_rr_filter_by_regime():
    # Min R:R config: BULL=1.5, BEAR=2.0, SIDEWAYS=1.0, VOLATILE=2.5
    min_rr = {"BULL": 1.5, "BEAR": 2.0, "SIDEWAYS": 1.0, "VOLATILE": 2.5}
    
    # Propose SL = 10, TP = 15 (R:R = 1.5)
    sl_dist = 10.0
    tp_dist = 15.0
    rr_ratio = tp_dist / sl_dist
    
    # Valid in BULL (1.5 >= 1.5)
    assert rr_ratio >= min_rr["BULL"]
    # Invalid in BEAR (1.5 < 2.0)
    assert rr_ratio < min_rr["BEAR"]
    # Valid in SIDEWAYS (1.5 >= 1.0)
    assert rr_ratio >= min_rr["SIDEWAYS"]
    # Invalid in VOLATILE (1.5 < 2.5)
    assert rr_ratio < min_rr["VOLATILE"]
