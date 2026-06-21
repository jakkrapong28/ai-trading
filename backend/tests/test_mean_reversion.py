"""Mean-reversion engine (Roadmap ข้อ 4) — pure logic, no network.

Guards `evaluate_mean_reversion`: the counter-trend range-fade that the per-regime
router hands chop windows to. Direction must be the OPPOSITE of breakout (buy the
floor / sell the ceiling), gated by RSI extremity, range width, and higher-TF
regime.
"""
import pandas as pd

from backend.core.mean_reversion import evaluate_mean_reversion


def _range_df(lo: float = 99.0, hi: float = 101.0, n: int = 25, last_close: float = 100.0,
              last_low: float = None, last_high: float = None) -> pd.DataFrame:
    """A horizontal channel between lo/hi over the prior bars, with the final bar
    parked at `last_close`. ATR is ~ (hi-lo)/2 from the oscillation."""
    highs = [hi if i % 2 else (lo + hi) / 2 for i in range(n - 1)]
    lows = [lo if i % 2 else (lo + hi) / 2 for i in range(n - 1)]
    closes = [(lo + hi) / 2] * (n - 1)
    highs.append(last_high if last_high is not None else last_close)
    lows.append(last_low if last_low is not None else last_close)
    closes.append(last_close)
    opens = closes
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": closes, "volume": [1.0] * n})


def test_short_df_waits():
    out = evaluate_mean_reversion(_range_df(n=5), atr=1.0)
    assert out["action"] == "WAIT"
    assert out["strategy_type"] == "MR_V1"


def test_zero_atr_waits():
    assert evaluate_mean_reversion(_range_df(), atr=0.0)["action"] == "WAIT"


def test_buys_oversold_floor():
    # Price pinned to the range floor (99) with an oversold RSI → fade long.
    df = _range_df(lo=99.0, hi=101.0, last_close=99.1)
    out = evaluate_mean_reversion(df, atr=1.0, indicators={"rsi": 28})
    assert out["action"] == "BUY"
    assert out["sl_anchor"] == 99.0          # stop just beyond the floor
    assert out["confidence"] > 0.0


def test_sells_overbought_ceiling():
    df = _range_df(lo=99.0, hi=101.0, last_close=100.9)
    out = evaluate_mean_reversion(df, atr=1.0, indicators={"rsi": 72})
    assert out["action"] == "SELL"
    assert out["sl_anchor"] == 101.0


def test_floor_without_oversold_rsi_waits():
    # At the floor but RSI not stretched → not a fadeable extreme.
    df = _range_df(lo=99.0, hi=101.0, last_close=99.1)
    out = evaluate_mean_reversion(df, atr=1.0, indicators={"rsi": 50})
    assert out["action"] == "WAIT"


def test_middle_of_range_waits():
    df = _range_df(lo=99.0, hi=101.0, last_close=100.0)
    out = evaluate_mean_reversion(df, atr=1.0, indicators={"rsi": 28})
    assert out["action"] == "WAIT"


def test_regime_blocks_counter_trend_buy():
    # Oversold floor fade, but the higher-TF regime is BEAR → don't catch the
    # falling knife.
    df = _range_df(lo=99.0, hi=101.0, last_close=99.1)
    out = evaluate_mean_reversion(df, atr=1.0, indicators={"rsi": 28}, regime="BEAR")
    assert out["action"] == "WAIT"
    assert "BEAR" in out["reason"]


def test_too_narrow_range_waits():
    # Range width (2.0) must clear min_range_atr·ATR; a huge ATR makes it too tight.
    df = _range_df(lo=99.0, hi=101.0, last_close=99.1)
    out = evaluate_mean_reversion(df, atr=5.0, indicators={"rsi": 28})
    assert out["action"] == "WAIT"
    assert "out of band" in out["reason"]
