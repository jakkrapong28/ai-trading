import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

SESSION_BOOST = {
    "LONDON_NY_OVERLAP": {"hours": (13, 17), "boost": 1.1},
    "LONDON":            {"hours": (9, 13),  "boost": 1.0},
    "NY":                {"hours": (17, 22), "boost": 1.0},
    "ASIAN":             {"hours": (2, 9),   "boost": 0.8},
    "SYDNEY":            {"hours": (22, 24), "boost": 0.7},  # Sydney wraps around 22:00 - 02:00 UTC
    "SYDNEY_EARLY":      {"hours": (0, 2),   "boost": 0.7},
}

def get_session_boost(dt: datetime) -> float:
    """Determine the session and returns its weight boost."""
    hour = dt.hour
    if 13 <= hour < 17:
        return SESSION_BOOST["LONDON_NY_OVERLAP"]["boost"]
    elif 9 <= hour < 13:
        return SESSION_BOOST["LONDON"]["boost"]
    elif 17 <= hour < 22:
        return SESSION_BOOST["NY"]["boost"]
    elif 2 <= hour < 9:
        return SESSION_BOOST["ASIAN"]["boost"]
    elif 22 <= hour or hour < 2:
        return SESSION_BOOST["SYDNEY"]["boost"]
    return 1.0

def detect_swing_levels(df: pd.DataFrame, window: int = 5) -> Tuple[pd.Series, pd.Series]:
    """Find Swing Highs and Swing Lows."""
    highs = df['high'].rolling(window=window*2+1, center=True).max()
    lows = df['low'].rolling(window=window*2+1, center=True).min()
    
    swing_highs = df['high'] == highs
    swing_lows = df['low'] == lows
    
    return swing_highs, swing_lows

def detect_smc_concepts(df: pd.DataFrame, atr: float, ob_size_atr: float = 0.5, fvg_gap_atr: float = 0.3) -> Dict[str, Any]:
    """Detects SMC concepts: OB, FVG, MSS, Liquidity Sweep."""
    if len(df) < 20:
        return {"mss": False, "ob": False, "fvg": False, "sweep": False, "sr_level": False}
        
    close = df['close'].iloc[-1]
    high = df['high'].iloc[-1]
    low = df['low'].iloc[-1]
    vol = df['volume'] if 'volume' in df else df.get('tick_volume', pd.Series([1.0]*len(df)))
    
    # Swing Highs & Lows detection
    swing_highs, swing_lows = detect_swing_levels(df)
    
    # 1. Liquidity Sweep
    # Current high/low breaks a recent swing high/low but close returns inside
    sweep = False
    recent_highs = df['high'][swing_highs].tail(5)
    recent_lows = df['low'][swing_lows].tail(5)
    
    if not recent_highs.empty:
        last_sh = recent_highs.iloc[-1]
        if high > last_sh and close < last_sh:
            sweep = True
    if not recent_lows.empty:
        last_sl = recent_lows.iloc[-1]
        if low < last_sl and close > last_sl:
            sweep = True

    # 2. Order Block (OB)
    # Candle body size >= ob_size_atr ATR and Volume >= 1.5x rolling 20 average
    ob = False
    body_size = abs(df['close'].iloc[-2] - df['open'].iloc[-2])
    avg_vol = vol.tail(20).mean()
    ob_vol = vol.iloc[-2]
    
    if body_size >= ob_size_atr * atr and ob_vol >= 1.5 * avg_vol:
        ob = True

    # 3. Fair Value Gap (FVG)
    # 3 candle gap size >= FVG gap size ATR
    fvg = False
    if len(df) >= 3:
        # Bullish FVG
        gap_bull = df['low'].iloc[-1] - df['high'].iloc[-3]
        # Bearish FVG
        gap_bear = df['low'].iloc[-3] - df['high'].iloc[-1]
        
        if gap_bull >= fvg_gap_atr * atr or gap_bear >= fvg_gap_atr * atr:
            fvg = True

    # 4. Market Structure Shift (MSS) / BOS
    mss = False
    # If price breaks the most recent swing high/low
    if not recent_highs.empty and close > recent_highs.max():
        mss = True
    if not recent_lows.empty and close < recent_lows.min():
        mss = True
        
    # Support & Resistance level proximity (within 0.5 ATR)
    sr_level = False
    if not recent_highs.empty:
        if abs(close - recent_highs.iloc[-1]) <= 0.5 * atr:
            sr_level = True
    if not recent_lows.empty:
        if abs(close - recent_lows.iloc[-1]) <= 0.5 * atr:
            sr_level = True

    return {
        "mss": mss,
        "ob": ob,
        "fvg": fvg,
        "sweep": sweep,
        "sr_level": sr_level
    }

def detect_smc_levels(
    df: pd.DataFrame,
    atr: float,
    ob_size_atr: float = 0.5,
    fvg_gap_atr: float = 0.3,
    swing_window: int = 5,
) -> Dict[str, Any]:
    """Geometry version of detect_smc_concepts — returns drawable PRICE levels
    (not just booleans) so the dashboard can overlay them on the candle chart.

    Returns: {order_blocks:[{top,bottom,kind}], fvgs:[{top,bottom,kind}],
              swings:[{price,kind}], mss:{price,kind}|None}
    """
    out: Dict[str, Any] = {"order_blocks": [], "fvgs": [], "swings": [], "mss": None}
    if df is None or len(df) < 20 or atr <= 0:
        return out

    close = float(df["close"].iloc[-1])
    vol = df["volume"] if "volume" in df else pd.Series([1.0] * len(df), index=df.index)

    swing_highs, swing_lows = detect_swing_levels(df, swing_window)
    recent_highs = df["high"][swing_highs].tail(5)
    recent_lows = df["low"][swing_lows].tail(5)

    for p in recent_highs.tolist():
        out["swings"].append({"price": float(p), "kind": "swing_high"})
    for p in recent_lows.tolist():
        out["swings"].append({"price": float(p), "kind": "swing_low"})

    # Order Block — the impulsive candle at -2 (body >= ob_size_atr·ATR, high volume)
    o2, c2 = float(df["open"].iloc[-2]), float(df["close"].iloc[-2])
    body = abs(c2 - o2)
    avg_vol = float(vol.tail(20).mean()) if len(vol) else 0.0
    ob_vol = float(vol.iloc[-2])
    if body >= ob_size_atr * atr and avg_vol > 0 and ob_vol >= 1.5 * avg_vol:
        out["order_blocks"].append({
            "top": float(df["high"].iloc[-2]),
            "bottom": float(df["low"].iloc[-2]),
            "kind": "bull" if c2 >= o2 else "bear",
        })

    # Fair Value Gap — 3-candle imbalance
    if len(df) >= 3:
        gap_bull = float(df["low"].iloc[-1] - df["high"].iloc[-3])
        gap_bear = float(df["low"].iloc[-3] - df["high"].iloc[-1])
        if gap_bull >= fvg_gap_atr * atr:
            out["fvgs"].append({
                "top": float(df["low"].iloc[-1]),
                "bottom": float(df["high"].iloc[-3]),
                "kind": "bull",
            })
        elif gap_bear >= fvg_gap_atr * atr:
            out["fvgs"].append({
                "top": float(df["low"].iloc[-3]),
                "bottom": float(df["high"].iloc[-1]),
                "kind": "bear",
            })

    # Market Structure Shift / BOS — close breaks the most recent swing extreme
    if not recent_highs.empty and close > float(recent_highs.max()):
        out["mss"] = {"price": float(recent_highs.max()), "kind": "bullish_bos"}
    elif not recent_lows.empty and close < float(recent_lows.min()):
        out["mss"] = {"price": float(recent_lows.min()), "kind": "bearish_bos"}

    return out


def calculate_signal_confidence(concepts: Dict[str, Any]) -> float:
    """Return confidence score based on combination-weighted logic.
    FVG-alone returns 0.0 (not tradeable).
    """
    if concepts.get("mss") and concepts.get("ob") and concepts.get("fvg") and concepts.get("d1_aligned"):
        return 0.85
    if concepts.get("ob") and concepts.get("fvg") and concepts.get("sr_level"):
        return 0.70
    if concepts.get("ob"):
        return 0.55
    return 0.0
