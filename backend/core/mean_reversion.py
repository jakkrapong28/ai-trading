"""Mean-reversion strategy — the counterpart to SMC-breakout for range/chop tape.

Roadmap ข้อ 4. The walk-forward research (SYSTEM_UPGRADE §16-18) proved the
SMC-breakout edge tops out ~50% because it loses *structurally* in range
markets: every entry gets whipsawed against its stop. Filtering chop out only
buys "no trade" — the window still fails on thin sample. The remaining lever is
a SECOND strategy that WINS where breakout loses: fade the range extremes.

Direction here is the OPPOSITE of breakout — buy the bottom of the channel /
sell the top — so a regime/ADX router can hand chop windows to this engine and
trend windows to SMC. Returns the SAME dict shape as `evaluate_smc_signal`
(action/confidence/tier/score/strategy_type/sl_anchor/reason) so the backtest
harness and live engine consume it identically.

Every parameter is plumbed so a walk-forward A/B can tune it without code edits.
Nothing is wired on by default — the router knob (BT_MR_ROUTER) gates it, and
that stays off until walk-forward proves it (the "ไม่ปล่อยมั่ว" rule).
"""
import pandas as pd
from typing import Dict, Any, Optional

from backend.core.smc import calculate_adx

# Confidence floor for a fired MR setup (mirrors the SMC TIER-C confidence so the
# downstream confidence-weighting treats both engines on the same scale).
MR_CONFIDENCE = {"A": 0.78, "B": 0.68, "C": 0.60}
MR_TIER_A_MIN = 0.80
MR_TIER_B_MIN = 0.64


def evaluate_mean_reversion(
    df: pd.DataFrame,
    atr: float,
    indicators: Optional[Dict[str, Any]] = None,
    regime: Optional[str] = None,
    lookback: int = 20,
    rsi_buy: float = 35.0,
    rsi_sell: float = 65.0,
    band_atr: float = 0.5,
    min_range_atr: float = 2.0,
    max_range_atr: float = 12.0,
    max_adx: Optional[float] = None,
) -> Dict[str, Any]:
    """Fade the extremes of a Donchian range.

    Range = highest-high / lowest-low over the last ``lookback`` *closed* bars.
    A long fires when price is within ``band_atr``·ATR of the range floor AND RSI
    is oversold; a short mirrors it at the ceiling. The stop sits just beyond the
    range boundary (so a genuine breakout takes us out small), and direction is
    deliberately counter-trend — this is the engine for the windows where
    SMC-breakout gets chopped up.

    Guards:
      min_range_atr / max_range_atr — the channel must be wide enough to be worth
        fading but not so wide it's actually a trend leg (no room to revert).
      max_adx — optional belt-and-suspenders: stand aside when ADX says trend.
        The router already gates on ADX, so this defaults off.
    """
    wait = {
        "action": "WAIT", "confidence": 0.0, "tier": None, "score": 0.0,
        "strategy_type": "MR_V1", "sl_anchor": None, "reason": "[MR] no setup",
    }
    if df is None or len(df) < lookback + 2 or atr <= 0:
        return wait

    if max_adx is not None and calculate_adx(df) >= max_adx:
        return {**wait, "reason": f"[MR] stand aside — trending (ADX >= {max_adx:.0f})"}

    # Donchian channel over the prior `lookback` CLOSED bars (exclude the live bar
    # so the boundary isn't defined by the very bar we're testing against it).
    window = df.iloc[-(lookback + 1):-1]
    hi = float(window["high"].max())
    lo = float(window["low"].min())
    width = hi - lo
    if width <= 0:
        return wait
    if not (min_range_atr * atr <= width <= max_range_atr * atr):
        return {**wait, "reason": f"[MR] range {width / atr:.1f}·ATR out of band"}

    close = float(df["close"].iloc[-1])
    rsi = float((indicators or {}).get("rsi", 50.0))
    mid = (hi + lo) / 2.0
    band = band_atr * atr

    near_floor = close <= lo + band
    near_ceil = close >= hi - band

    action: Optional[str] = None
    reasons: list = []
    if near_floor and not near_ceil and rsi <= rsi_buy:
        action = "BUY"
        reasons = [f"range floor", f"RSI {rsi:.0f}"]
        sl_anchor = lo
    elif near_ceil and not near_floor and rsi >= rsi_sell:
        action = "SELL"
        reasons = [f"range ceil", f"RSI {rsi:.0f}"]
        sl_anchor = hi
    else:
        return {**wait, "reason": "[MR] not at a fadeable extreme"}

    # Never fade INTO a confirmed higher-TF trend (don't sell the top of a strong
    # uptrend's pullback range, or buy the floor of a downtrend) — the one place a
    # range fade turns into standing in front of a train.
    if regime == "BULL" and action == "SELL":
        return {**wait, "reason": "[MR] SELL blocked — regime BULL"}
    if regime == "BEAR" and action == "BUY":
        return {**wait, "reason": "[MR] BUY blocked — regime BEAR"}

    # Score: reward deeper RSI extremity and tighter proximity to the boundary —
    # the cleanest fades sit right on the edge with a stretched oscillator.
    if action == "BUY":
        rsi_extremity = max(0.0, (rsi_buy - rsi) / max(rsi_buy, 1.0))
        proximity = max(0.0, 1.0 - (close - lo) / max(band, 1e-9))
    else:
        rsi_extremity = max(0.0, (rsi - rsi_sell) / max(100.0 - rsi_sell, 1.0))
        proximity = max(0.0, 1.0 - (hi - close) / max(band, 1e-9))
    score = round(0.60 + 0.25 * rsi_extremity + 0.15 * proximity, 3)
    tier = "A" if score >= MR_TIER_A_MIN else "B" if score >= MR_TIER_B_MIN else "C"

    return {
        "action": action,
        "confidence": MR_CONFIDENCE[tier],
        "tier": tier,
        "score": score,
        "strategy_type": "MR_V1",
        "sl_anchor": sl_anchor,
        "reason": f"[MR {tier}] {action} — {', '.join(reasons)} (mid {mid:.2f})",
    }
