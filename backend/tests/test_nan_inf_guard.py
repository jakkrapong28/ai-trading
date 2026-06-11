import pytest
import math
from backend.core import validate_atr, validate_price

def test_validate_atr_valid():
    assert validate_atr(1.5, "XAUUSD") == 1.5
    assert validate_atr(10.0, "BTCUSDT") == 10.0

def test_validate_atr_invalid():
    # NaN
    assert validate_atr(float('nan'), "XAUUSD") == 3.75 # fallback for XAUUSD (7.5 * 0.5)
    # Inf
    assert validate_atr(float('inf'), "BTCUSDT") == 170.0 # fallback for BTCUSDT (340.0 * 0.5)
    # Negative/Zero
    assert validate_atr(-1.0, "SOLUSDT") == 2.5 # fallback for SOLUSDT (5.0 * 0.5)

def test_validate_price_valid():
    assert validate_price(2350.0) == 2350.0

def test_validate_price_invalid():
    with pytest.raises(ValueError):
        validate_price(float('nan'))
    with pytest.raises(ValueError):
        validate_price(float('inf'))
    with pytest.raises(ValueError):
        validate_price(-5.0)
