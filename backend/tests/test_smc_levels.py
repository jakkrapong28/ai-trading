"""P4-2 · detect_smc_levels() — drawable SMC geometry for the chart overlay."""
import pandas as pd

from backend.core.smc import detect_smc_levels


def _base_df(n=40, start=100.0):
    rows = []
    p = start
    for i in range(n):
        o = p
        c = p + (0.5 if i % 2 == 0 else -0.4)
        rows.append({"open": o, "high": max(o, c) + 0.3, "low": min(o, c) - 0.3,
                     "close": c, "volume": 100.0})
        p = c
    return pd.DataFrame(rows)


def test_too_short_returns_empty():
    out = detect_smc_levels(_base_df(10), atr=1.0)
    assert out == {"order_blocks": [], "fvgs": [], "swings": [], "mss": None}


def test_returns_structure_and_swings():
    out = detect_smc_levels(_base_df(40), atr=1.0)
    assert set(out.keys()) == {"order_blocks", "fvgs", "swings", "mss"}
    assert isinstance(out["swings"], list)


def test_detects_bullish_fvg():
    df = _base_df(40)
    # Force a 3-candle bullish gap at the tail: low[-1] far above high[-3]
    df.loc[df.index[-3], ["open", "high", "low", "close"]] = [100, 100.5, 99.5, 100]
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [110, 111, 110, 110.5]
    out = detect_smc_levels(df, atr=1.0)
    assert any(f["kind"] == "bull" for f in out["fvgs"])
    fvg = out["fvgs"][0]
    assert fvg["top"] > fvg["bottom"]


def test_detects_order_block_on_high_volume_impulse():
    df = _base_df(40)
    # Big body + high volume on the -2 candle
    df.loc[df.index[-2], ["open", "high", "low", "close", "volume"]] = [100, 106, 99.5, 105, 1000]
    out = detect_smc_levels(df, atr=1.0)
    assert len(out["order_blocks"]) == 1
    ob = out["order_blocks"][0]
    assert ob["kind"] == "bull" and ob["top"] >= ob["bottom"]


def test_bearish_bos_when_close_breaks_below_swing_low():
    df = _base_df(40)
    # A clear swing low at the centre (deep dip vs neighbours so it is detected)
    df.loc[df.index[20], ["open", "high", "low", "close"]] = [101, 101.5, 95, 101]
    # Final candle closes below that swing low → bearish break of structure
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [96, 96, 90, 92]
    out = detect_smc_levels(df, atr=1.0)
    assert out["mss"] is not None and out["mss"]["kind"] == "bearish_bos"
