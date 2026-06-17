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


# ─────────────────────────────────────────────────────────
# SMC v2 — directional, TIER-graded signal (Stage 1→5b funnel)
# ─────────────────────────────────────────────────────────
# The v1 SMC path decided DIRECTION with a naive EMA fast/slow crossover and
# entered at the bar close regardless of structure. v2 derives direction from
# the SMC geometry itself (which carries bull/bear kind), grades the setup into
# a TIER (A/B/C, below C = WATCH = no trade), and anchors the stop to the zone.
#
# Weighted confluence — each factor adds to the side it supports. Tuned so a
# clean "BOS + retrace into demand + H1 bias + sweep" prints TIER A.
SMC_W_MSS = 0.30     # market-structure shift / BOS in our direction (strongest)
SMC_W_ZONE = 0.26    # price sitting in an aligned order block (Demand/Supply)
SMC_W_FVG = 0.14     # price in an aligned fair-value gap
SMC_W_BIAS = 0.20    # H1 macro trend aligned (Stage 5b: lock with trend)
SMC_W_SWEEP = 0.16   # liquidity sweep grabbed stops just before entry
SMC_W_SR = 0.08      # near a swing S/R level

# TIER thresholds on the winning-side confluence score.
SMC_TIER_C_MIN = 0.46   # below this → WATCH (no trade) — Stage 4 gate
SMC_TIER_B_MIN = 0.62
SMC_TIER_A_MIN = 0.80
SMC_TIER_CONFIDENCE = {"A": 0.84, "B": 0.72, "C": 0.60}


def _zone_touch(close: float, atr: float, zones, kind: str) -> bool:
    """True if `close` sits inside (or within 0.25·ATR of) an aligned zone."""
    tol = 0.25 * atr
    for z in zones:
        if z.get("kind") != kind:
            continue
        if (z["bottom"] - tol) <= close <= (z["top"] + tol):
            return True
    return False


_TIER_RANK = {"C": 0, "B": 1, "A": 2}


def evaluate_smc_signal(
    df: pd.DataFrame,
    atr: float,
    indicators: Optional[Dict[str, Any]] = None,
    macro: Optional[str] = None,
    regime: Optional[str] = None,
    ob_size_atr: float = 0.5,
    fvg_gap_atr: float = 0.3,
    min_tier: str = "C",
    require_bias: bool = False,
) -> Dict[str, Any]:
    """Directional, TIER-graded SMC signal.

    Returns {action, confidence, tier, score, strategy_type, sl_anchor, reason}.
    `action` is WAIT when the best side fails the TIER-C gate (the WATCH state).
    `sl_anchor` is a structural stop price (zone/swing extreme) or None.

    Tuning knobs (used to suppress the catastrophic out-of-sample windows):
      min_tier     — drop setups below this TIER ("C"|"B"|"A"); higher = fewer,
                     cleaner trades.
      require_bias — only trade WITH the H1 macro trend (BUY needs Bullish, SELL
                     needs Bearish); blocks the choppy counter-bias blow-ups.
    """
    wait = {
        "action": "WAIT", "confidence": 0.0, "tier": None, "score": 0.0,
        "strategy_type": "SMC_V2", "sl_anchor": None, "reason": "[SMC] no setup",
    }
    if df is None or len(df) < 20 or atr <= 0:
        return wait

    levels = detect_smc_levels(df, atr, ob_size_atr, fvg_gap_atr)
    close = float(df["close"].iloc[-1])
    high = float(df["high"].iloc[-1])
    low = float(df["low"].iloc[-1])

    swing_highs, swing_lows = detect_swing_levels(df)
    recent_highs = df["high"][swing_highs].tail(5)
    recent_lows = df["low"][swing_lows].tail(5)

    long_score = 0.0
    short_score = 0.0
    long_reasons: list = []
    short_reasons: list = []

    # 1. Market-structure shift / BOS (Stage 1 raw + Stage 3 pattern)
    mss = levels.get("mss")
    if mss:
        if mss["kind"] == "bullish_bos":
            long_score += SMC_W_MSS
            long_reasons.append("BOS↑")
        elif mss["kind"] == "bearish_bos":
            short_score += SMC_W_MSS
            short_reasons.append("BOS↓")

    # 2. Order-block context (Stage 2 zone) — retrace INTO demand=long / supply=short
    if _zone_touch(close, atr, levels.get("order_blocks", []), "bull"):
        long_score += SMC_W_ZONE
        long_reasons.append("Demand OB")
    if _zone_touch(close, atr, levels.get("order_blocks", []), "bear"):
        short_score += SMC_W_ZONE
        short_reasons.append("Supply OB")

    # 3. Fair-value-gap context
    if _zone_touch(close, atr, levels.get("fvgs", []), "bull"):
        long_score += SMC_W_FVG
        long_reasons.append("Bull FVG")
    if _zone_touch(close, atr, levels.get("fvgs", []), "bear"):
        short_score += SMC_W_FVG
        short_reasons.append("Bear FVG")

    # 4. Liquidity sweep direction (Stage 1) — grabbed sell-side stops → long
    if not recent_lows.empty and low < float(recent_lows.iloc[-1]) and close > float(recent_lows.iloc[-1]):
        long_score += SMC_W_SWEEP
        long_reasons.append("sweep low")
    if not recent_highs.empty and high > float(recent_highs.iloc[-1]) and close < float(recent_highs.iloc[-1]):
        short_score += SMC_W_SWEEP
        short_reasons.append("sweep high")

    # 5. H1 macro bias (Stage 5b: lock WITH the higher-timeframe trend)
    if macro == "Bullish":
        long_score += SMC_W_BIAS
        long_reasons.append("H1 bull")
    elif macro == "Bearish":
        short_score += SMC_W_BIAS
        short_reasons.append("H1 bear")

    # 6. Near a swing S/R level
    if not recent_lows.empty and abs(close - float(recent_lows.iloc[-1])) <= 0.5 * atr:
        long_score += SMC_W_SR
        long_reasons.append("S level")
    if not recent_highs.empty and abs(close - float(recent_highs.iloc[-1])) <= 0.5 * atr:
        short_score += SMC_W_SR
        short_reasons.append("R level")

    # Pick the dominant side
    if long_score >= short_score:
        action, score, reasons = "BUY", long_score, long_reasons
    else:
        action, score, reasons = "SELL", short_score, short_reasons

    # Regime hard-gate (Stage 5b: never fight a strong trend on the higher TF)
    if regime == "BULL" and action == "SELL":
        return {**wait, "reason": "[SMC] SELL blocked — regime BULL"}
    if regime == "BEAR" and action == "BUY":
        return {**wait, "reason": "[SMC] BUY blocked — regime BEAR"}

    # Optional: only trade WITH the H1 macro bias (kills counter-bias chop)
    if require_bias:
        if action == "BUY" and macro != "Bullish":
            return {**wait, "reason": "[SMC] BUY skipped — H1 not bullish"}
        if action == "SELL" and macro != "Bearish":
            return {**wait, "reason": "[SMC] SELL skipped — H1 not bearish"}

    # RSI sanity — don't buy what's already overbought / sell oversold
    rsi = float((indicators or {}).get("rsi", 50.0))
    if action == "BUY" and rsi >= 75:
        return {**wait, "reason": f"[SMC] BUY skipped — RSI {rsi:.0f} overbought"}
    if action == "SELL" and rsi <= 25:
        return {**wait, "reason": f"[SMC] SELL skipped — RSI {rsi:.0f} oversold"}

    # TIER gate (Stage 4/5a)
    if score < SMC_TIER_C_MIN:
        return {**wait, "score": round(score, 3), "reason": "[SMC] below TIER-C → WATCH"}
    tier = "A" if score >= SMC_TIER_A_MIN else "B" if score >= SMC_TIER_B_MIN else "C"
    if _TIER_RANK[tier] < _TIER_RANK.get(min_tier, 0):
        return {**wait, "score": round(score, 3),
                "reason": f"[SMC] TIER {tier} below floor {min_tier} → WATCH"}

    # Structural stop anchor (Stage: SL under the demand / over the supply)
    sl_anchor = None
    if action == "BUY":
        candidates = [z["bottom"] for z in levels.get("order_blocks", []) if z["kind"] == "bull"]
        if not recent_lows.empty:
            candidates.append(float(recent_lows.iloc[-1]))
        below = [c for c in candidates if c < close]
        if below:
            sl_anchor = min(below)
    else:
        candidates = [z["top"] for z in levels.get("order_blocks", []) if z["kind"] == "bear"]
        if not recent_highs.empty:
            candidates.append(float(recent_highs.iloc[-1]))
        above = [c for c in candidates if c > close]
        if above:
            sl_anchor = max(above)

    return {
        "action": action,
        "confidence": SMC_TIER_CONFIDENCE[tier],
        "tier": tier,
        "score": round(score, 3),
        "strategy_type": "SMC_V2",
        "sl_anchor": sl_anchor,
        "reason": f"[SMC {tier}] {action} — {', '.join(reasons)}",
    }
