import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import pandas as pd
from backend.core import calculate_rsi

logger = logging.getLogger("mtf")

TIMEFRAMES = {
    "M15": {"weight": 1, "bars": 96},
    "H1":  {"weight": 2, "bars": 48},
    "H4":  {"weight": 3, "bars": 30},
    "D1":  {"weight": 4, "bars": 20},
}

D1_SLOPE_THRESHOLD = 1.5  # configurable — EMA200 movement in ATR units over 20 days

def is_candle_closed(tf: str, timestamp: datetime) -> bool:
    """Check if a candle period has ended.
    
    The `timestamp` is the start of the candle period (e.g. 14:00 for H1 candle).
    A candle is closed when the current time has passed the period end.
    Works with both CandleManager (Yahoo bootstrap) and live tick data.
    """
    now = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    from datetime import timedelta
    if tf == "M15": return (timestamp + timedelta(minutes=15)) <= now
    if tf == "H1":  return (timestamp + timedelta(hours=1)) <= now
    if tf == "H4":  return (timestamp + timedelta(hours=4)) <= now
    if tf == "D1":  return (timestamp + timedelta(days=1)) <= now
    return True

def calculate_mtf_indicators(ohlc: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    results = {}
    for tf, df in ohlc.items():
        closed = df[df.apply(lambda r: is_candle_closed(tf, r.name), axis=1)]
        if len(closed) < 20:
            continue
        close_series = closed["close"]
        ema_12 = close_series.ewm(span=12, adjust=False).mean().iloc[-1]
        ema_26 = close_series.ewm(span=26, adjust=False).mean().iloc[-1]
        
        ema_200_series = close_series.ewm(span=200, adjust=False).mean()
        ema_200 = ema_200_series.iloc[-1]
        
        ema_200_20bars_ago = ema_200_series.iloc[-20] if len(closed) >= 20 else ema_200_series.iloc[0]
        ema_200_slope = (ema_200 - ema_200_20bars_ago) / abs(ema_200_20bars_ago + 0.0001)
        
        results[tf] = {
            "rsi": calculate_rsi(close_series.tolist()),
            "ema_12": round(float(ema_12), 4),
            "ema_26": round(float(ema_26), 4),
            "ema_200": round(float(ema_200), 4),
            "ema_200_history": [round(float(v), 4) for v in ema_200_series.tail(20).tolist()],
            "ema_200_slope": round(float(ema_200_slope), 6),
            "trend": "Bullish" if ema_12 > ema_26 else "Bearish",
            "candle_count": len(closed),
        }
    return results

def check_d1_bias_lock(mtf_data: Dict[str, Any], signal_action: str, d1_atr: Optional[float] = None) -> bool:
    """
    Returns True if D1 trend is opposite to signal_action (meaning the trade is locked/blocked).
    Uses ATR-normalized slope of daily EMA 200.
    """
    d1 = mtf_data.get("D1")
    if not d1 or "ema_200" not in d1 or "ema_200_history" not in d1 or not d1["ema_200_history"]:
        return False
        
    ema_200 = d1["ema_200"]
    ema_200_history = d1["ema_200_history"]
    
    # Calculate EMA200 20 days ago
    ema_200_20bars_ago = ema_200_history[0]  # ema_200_history has tail(20) items
    price_change = ema_200 - ema_200_20bars_ago

    if not d1_atr or d1_atr <= 0:
        return False  # Cannot normalize, do not lock

    normalized_slope = price_change / d1_atr
    
    if normalized_slope > D1_SLOPE_THRESHOLD:
        d1_trend = "UP"
    elif normalized_slope < -D1_SLOPE_THRESHOLD:
        d1_trend = "DOWN"
    else:
        d1_trend = "SIDEWAYS"
        
    if d1_trend == "DOWN" and signal_action == "BUY":
        return True
    if d1_trend == "UP" and signal_action == "SELL":
        return True
        
    return False

async def verify_d1_candle_timestamps(df: pd.DataFrame) -> int:
    """Checks the D1 bar timestamp convention from the data source.
    If closed_count == 0, notifies critical alert that D1 Bias Lock won't function.
    """
    from backend.alert import send_alert
    # get_ohlc() returns a RangeIndex with `timestamp` as a column, so use the
    # column when present; fall back to the index for callers that index by time.
    if "timestamp" in df.columns:
        ts_series = pd.to_datetime(df["timestamp"])
    else:
        ts_series = pd.to_datetime(pd.Series(df.index))
    closed_count = int(sum(is_candle_closed("D1", ts) for ts in ts_series))
    if closed_count == 0:
        await send_alert("CRITICAL", "❌ D1 timestamp convention mismatch — D1 Bias Lock จะไม่ทำงาน")
    logger.info(f"D1 candle pre-flight: {closed_count}/{len(df)} bars match convention")
    return closed_count
