import math
import random
import statistics
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import deque
import pandas as pd
import numpy as np

logger = logging.getLogger("core")

NAN_DETECTION_COUNT = 0

def validate_atr(atr: float, symbol: str = "XAUUSD", context: str = "") -> float:
    """NaN/Inf guard — ถ้า ATR เสีย ใช้ historical median หรือ symbol volatility แทนค่าคงที่"""
    global NAN_DETECTION_COUNT
    if atr is None or math.isnan(atr) or math.isinf(atr) or atr <= 0:
        NAN_DETECTION_COUNT += 1
        fallback = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"]).get("volatility", 5.0) * 0.5
        logger.warning(f"⚠️ Invalid ATR ({atr}) ใน {context} — fallback เป็น {fallback:.2f} ({symbol})")
        return fallback
    return atr

def validate_price(price: float, context: str = "") -> float:
    """NaN/Inf guard สำหรับราคา"""
    global NAN_DETECTION_COUNT
    if price is None or math.isnan(price) or math.isinf(price) or price <= 0:
        NAN_DETECTION_COUNT += 1
        logger.error(f"❌ Invalid price ({price}) ใน {context}")
        raise ValueError(f"Invalid price: {price} ใน {context}")
    return price

from backend.config import STARTING_BALANCE

# ค่าคอนฟิกความเสี่ยงตามนโยบายระบบเทรดของคุณโทนี่
RISK_CONFIG = {
    "equity": STARTING_BALANCE,
    "maxRiskPerTradePct": 2.0,  # กฎความเสี่ยงสูงสุดต่อไม้ 2%
    "maxDailyLossPct": 3.0,
    "maxOpenExposurePct": 20.0,
    "maxSpread": 3.0,
    "minStopDistance": 10.0
}

# Pip size per asset class — used to express bid/ask spread in pips.
PIP_SIZE = {"metal": 0.1, "forex": 0.0001, "crypto": 1.0, "stock": 0.01, "index": 1.0}
# Deterministic typical spread (pips) used when no genuine broker spread exists
# (e.g. TwelveData/mock feeds synthesize bid/ask, so their spread is not real).
TYPICAL_SPREAD_PIPS = {"metal": 2.0, "forex": 1.0, "crypto": 2.0, "stock": 2.0, "index": 1.0}
# Feeds that report a genuine broker/exchange bid-ask spread.
_REAL_SPREAD_SOURCES = {"binance", "mt5", "finnhub"}


def current_spread_pips(symbol: str) -> float:
    """Deterministic broker spread in pips for `symbol`.

    Uses the live bid/ask only when it comes from a real exchange/broker feed;
    otherwise returns a realistic per-asset-class default. Never random.
    """
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    asset_class = spec.get("assetClass", "metal")
    typical = TYPICAL_SPREAD_PIPS.get(asset_class, 2.0)
    try:
        from backend.engines.providers.base import latest_prices
        data = latest_prices.get(symbol)
        if (
            data
            and data.get("source") in _REAL_SPREAD_SOURCES
            and data.get("ask")
            and data.get("bid")
        ):
            pip = PIP_SIZE.get(asset_class, 0.1)
            live = (data["ask"] - data["bid"]) / pip
            if live > 0:
                return round(live, 2)
    except Exception:
        pass
    return typical

SYMBOLS = {
    "XAUUSD": {"base": 2342.0, "volatility": 7.5, "tickValue": 1.0, "decimals": 2, "contractSize": 100, "assetClass": "metal"},
    "EURUSD": {"base": 1.0832, "volatility": 0.0028, "tickValue": 10.0, "decimals": 5, "contractSize": 100000, "assetClass": "forex"},
    "BTCUSDT": {"base": 68150.0, "volatility": 340.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "crypto"},
    "ETHUSDT": {"base": 3570.0, "volatility": 42.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "crypto"},
    "SOLUSDT": {"base": 170.0, "volatility": 5.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "crypto"},
    "TSLA": {"base": 180.0, "volatility": 6.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "stock"},
    "AAPL": {"base": 190.0, "volatility": 3.5, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "stock"},
    "NVDA": {"base": 120.0, "volatility": 4.5, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "stock"},
    "MSFT": {"base": 420.0, "volatility": 8.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "stock"},
    "AMZN": {"base": 185.0, "volatility": 4.0, "tickValue": 1.0, "decimals": 2, "contractSize": 1, "assetClass": "stock"}
}

# RSI thresholds per symbol — calibrate via `python backend/backtest.py optimize`
# Calibrated via: python backend/backtest.py optimize (30d Yahoo 1h)
STRATEGY_CONFIG: Dict[str, Dict[str, Any]] = {
    "XAUUSD": {
        "rsi_sell_early": 75, "rsi_sell_full": 78,
        "rsi_buy_early": 22, "rsi_buy_full": 18,
        "volume_confirm_min": 1.15,
        "trend_min_score": 3, "trend_rsi_buy_max": 65, "trend_rsi_sell_min": 35,
    },
    "BTCUSDT": {
        "rsi_sell_early": 72, "rsi_sell_full": 76,
        "rsi_buy_early": 25, "rsi_buy_full": 24,
        "volume_confirm_min": 1.20,
        "trend_min_score": 3, "trend_rsi_buy_max": 62, "trend_rsi_sell_min": 38,
    },
    "ETHUSDT": {
        "rsi_sell_early": 70, "rsi_sell_full": 74,
        "rsi_buy_early": 22, "rsi_buy_full": 20,
        "volume_confirm_min": 1.18,
        "trend_min_score": 3, "trend_rsi_buy_max": 63, "trend_rsi_sell_min": 37,
    },
}

_DEFAULT_STRATEGY = {
    "rsi_sell_early": 75, "rsi_sell_full": 78,
    "rsi_buy_early": 25, "rsi_buy_full": 22,
    "volume_confirm_min": 1.15,
    "trend_min_score": 3, "trend_rsi_buy_max": 65, "trend_rsi_sell_min": 35,
}

def get_strategy_config(symbol: str) -> Dict[str, Any]:
    return {**_DEFAULT_STRATEGY, **STRATEGY_CONFIG.get(symbol, {})}

YAHOO_SYMBOL_MAP = {
    "XAUUSD": "GC=F", "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD",
    "SOLUSDT": "SOL-USD", "EURUSD": "EURUSD=X",
}

def compute_macro_trend_from_closes(closes: List[float]) -> Optional[str]:
    """คำนวณแนวโน้ม 1h จาก close series (ใช้ใน backtest)"""
    if len(closes) < 26:
        return None
    s = pd.Series(closes, dtype="float64")
    ema12 = s.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = s.ewm(span=26, adjust=False).mean().iloc[-1]
    if ema12 > ema26 * 1.0005:
        return "Bullish"
    if ema12 < ema26 * 0.9995:
        return "Bearish"
    return "Sideways"

def trade_pnl(
    symbol: str, action: str, entry: float, exit_price: float, lot: float
) -> float:
    """คำนวณ PnL ตาม contract size จริง — single source of truth สำหรับ realized และ floating PnL"""
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    contract_size = spec.get("contractSize", 100)
    diff = exit_price - entry if action == "BUY" else entry - exit_price
    return diff * lot * contract_size


def compute_fee(symbol: str, price: float, lot: float) -> float:
    """ค่าธรรมเนียมโบรกเกอร์ตาม notional (lot × contractSize × price) × commission rate.

    Deterministic ต่อ asset class (ดู config.COMMISSION_RATE). ใช้ราคาปิดเป็นฐาน
    notional; partial close ส่ง closed_lot เข้ามาเพื่อคิดตามสัดส่วน.
    """
    from backend.config import COMMISSION_RATE
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    contract_size = spec.get("contractSize", 100)
    asset_class = spec.get("assetClass", "metal")
    rate = COMMISSION_RATE.get(asset_class, 0.00008)
    notional = abs(lot) * contract_size * abs(price or 0.0)
    return round(notional * rate, 2)

# ─────────────────────────────────────────────────────────
# Continuous Price History Store (deque-based, ไม่ reset)
# ─────────────────────────────────────────────────────────
_price_store: Dict[str, deque] = {}

def get_price_store(symbol: str, maxlen: int = 200) -> deque:
    """คืน deque ที่เก็บ price history ต่อเนื่องต่อ symbol"""
    if symbol not in _price_store:
        spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
        initial = _generate_initial_prices(symbol, 96)
        _price_store[symbol] = deque(initial, maxlen=maxlen)
    return _price_store[symbol]

def append_price(symbol: str, price: float):
    """เพิ่มราคาใหม่เข้า continuous history"""
    store = get_price_store(symbol)
    store.append(round(price, SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])["decimals"]))

def _generate_initial_prices(symbol: str, length: int = 96) -> List[float]:
    """สร้างราคาเริ่มต้น — เรียกแค่ครั้งเดียว"""
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    prices = []
    price = spec["base"] + (random.random() - 0.5) * spec["volatility"] * 5
    for i in range(length):
        drift = math.sin(i / 11.0) * spec["volatility"] * 0.22
        shock = (random.random() - 0.48) * spec["volatility"]
        price = max(price + drift + shock, spec["volatility"])
        prices.append(round(price, spec["decimals"]))
    return prices

def generate_price_history(symbol: str, length: int = 96) -> List[float]:
    """ดึง price history ปัจจุบัน (ต่อเนื่อง ไม่รีเซ็ต)"""
    store = get_price_store(symbol)
    return list(store)[-length:]

# ─────────────────────────────────────────────────────────
# Technical Indicators
# ─────────────────────────────────────────────────────────

def calculate_ema(values: List[float], period: int) -> List[float]:
    """Exponential Moving Average using Pandas"""
    if not values or len(values) < period:
        return values or []
    s = pd.Series(values)
    return s.ewm(span=period, adjust=False).mean().fillna(0).tolist()

def calculate_rsi(values: List[float], period: int = 14) -> float:
    """Relative Strength Index using Pandas"""
    if len(values) <= period:
        return 50.0
    s = pd.Series(values)
    delta = s.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(round(val, 1)) if not np.isnan(val) else 50.0

def calculate_macd(values: List[float]) -> Dict[str, float]:
    """MACD using Pandas"""
    if len(values) < 26:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0, "prev_histogram": 0.0}
    s = pd.Series(values)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = histogram.iloc[-1]
    prev_hist_val = histogram.iloc[-2] if len(histogram) >= 2 else hist_val
    return {
        "macd": float(round(macd_val, 4)),
        "signal": float(round(signal_val, 4)),
        "histogram": float(round(hist_val, 4)),
        "prev_histogram": float(round(prev_hist_val, 4))
    }

def _wilder_atr(tr: pd.Series, period: int = 14) -> float:
    """Wilder-smoothed ATR (standard definition)."""
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    val = atr.iloc[-1]
    return float(round(val, 4)) if not np.isnan(val) else 1.0

def calculate_atr(prices: List[float], period: int = 14) -> float:
    """ATR fallback from close-only series (less accurate than OHLC)."""
    if len(prices) < 2:
        return SYMBOLS.get("XAUUSD", {}).get("volatility", 1.0)
    s = pd.Series(prices, dtype="float64")
    tr = s.diff().abs()
    return _wilder_atr(tr, period)

def calculate_atr_ohlc(ohlc: Any, period: int = 14) -> float:
    """True ATR from OHLC (high-low + gaps), Wilder-smoothed."""
    if isinstance(ohlc, pd.DataFrame):
        required = {"high", "low", "close"}
        if required.issubset(set(ohlc.columns)) and len(ohlc) >= 2:
            high = pd.Series(ohlc["high"], dtype="float64")
            low = pd.Series(ohlc["low"], dtype="float64")
            close = pd.Series(ohlc["close"], dtype="float64")
            prev_close = close.shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs()
            ], axis=1).max(axis=1)
            return _wilder_atr(tr, period)
    if isinstance(ohlc, (list, tuple)):
        return calculate_atr(list(ohlc), period)
    return SYMBOLS.get("XAUUSD", {}).get("volatility", 1.0)

def ticks_to_ohlc(prices: List[float], bar_size: int = 4) -> pd.DataFrame:
    """สร้าง pseudo-OHLC จาก tick/close list เมื่อไม่มี candle จริง"""
    if len(prices) < bar_size:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rows = []
    for i in range(0, len(prices) - bar_size + 1, bar_size):
        chunk = prices[i:i + bar_size]
        rows.append({
            "open": chunk[0], "high": max(chunk), "low": min(chunk),
            "close": chunk[-1], "volume": float(len(chunk))
        })
    return pd.DataFrame(rows)

def calculate_bollinger_bands(values: List[float], period: int = 20, std_mult: float = 2.0) -> Dict[str, float]:
    """Bollinger Bands using Pandas"""
    if len(values) < period:
        last = values[-1] if values else 0
        return {"upper": last, "middle": last, "lower": last, "width": 0}
    s = pd.Series(values)
    mean = s.rolling(window=period).mean()
    std = s.rolling(window=period).std()
    val_mean = mean.iloc[-1]
    val_std = std.iloc[-1]
    if np.isnan(val_mean):
        val_mean = values[-1]
        val_std = 0
    return {
        "upper": float(round(val_mean + std_mult * val_std, 4)),
        "middle": float(round(val_mean, 4)),
        "lower": float(round(val_mean - std_mult * val_std, 4)),
        "width": float(round(std_mult * 2 * val_std, 4))
    }

def get_market_indicators(prices: Any, symbol: str) -> Dict[str, Any]:
    """คำนวณอินดิเคเตอร์ภาพรวมตลาด — ใช้ OHLC จริงเมื่อมี"""
    ohlc: Optional[pd.DataFrame] = None
    if isinstance(prices, pd.DataFrame):
        ohlc = prices.copy()
        prices = ohlc["close"].dropna().astype(float).tolist()
    elif isinstance(prices, list) and len(prices) >= 8:
        ohlc = ticks_to_ohlc(prices, bar_size=4)
        if len(ohlc) >= 2:
            prices = ohlc["close"].astype(float).tolist()

    if not prices:
        spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
        return {
            "latest": spec["base"], "rsi": 50.0, "atr": spec["volatility"],
            "trend": "Sideways", "support": spec["base"], "resistance": spec["base"],
            "volume": {"current": 0.0, "avg_20": 0.0, "ratio": 1.0}
        }

    fast = calculate_ema(prices, 12)
    slow = calculate_ema(prices, 26)
    latest = float(prices[-1])
    rsi_val = calculate_rsi(prices, 14)
    atr_val = calculate_atr_ohlc(ohlc, 14) if ohlc is not None and len(ohlc) >= 2 else calculate_atr(prices, 14)
    macd_data = calculate_macd(prices)
    bb_data = calculate_bollinger_bands(prices)

    recent_prices = prices[-22:]
    support = float(min(recent_prices))
    resistance = float(max(recent_prices))

    if fast[-1] > slow[-1] * 1.001:
        trend = "Bullish"
    elif fast[-1] < slow[-1] * 0.999:
        trend = "Bearish"
    else:
        trend = "Sideways"

    volume_info = {"current": 0.0, "avg_20": 0.0, "ratio": 1.0}
    if ohlc is not None and "volume" in ohlc.columns:
        vol = pd.Series(ohlc["volume"], dtype="float64").fillna(0)
        if len(vol) > 0:
            avg_vol = float(vol.tail(20).mean()) if len(vol) >= 2 else float(vol.iloc[-1])
            cur_vol = float(vol.iloc[-1])
            volume_info = {
                "current": round(cur_vol, 2),
                "avg_20": round(avg_vol, 2),
                "ratio": round(cur_vol / avg_vol, 2) if avg_vol > 0 else 1.0
            }

    return {
        "latest": latest,
        "rsi": rsi_val,
        "atr": atr_val,
        "trend": trend,
        "support": support,
        "resistance": resistance,
        "ema_fast": round(fast[-1], SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])["decimals"]),
        "ema_slow": round(slow[-1], SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])["decimals"]),
        "macd": macd_data,
        "bollinger": bb_data,
        "volume": volume_info,
        "atr_source": "ohlc" if ohlc is not None and len(ohlc) >= 2 else "close_proxy"
    }

# ─────────────────────────────────────────────────────────
# Strategy Rule Engine — Trend & Reversal แยกกัน
# ─────────────────────────────────────────────────────────

def _indicator_context(indicators: Dict[str, Any]) -> Dict[str, Any]:
    latest = indicators["latest"]
    support = indicators["support"]
    resistance = indicators["resistance"]
    atr = indicators["atr"]
    trend = indicators["trend"]
    rsi_val = indicators["rsi"]
    macd = indicators.get("macd", {"histogram": 0, "prev_histogram": 0})
    bb = indicators.get("bollinger", {"lower": support, "upper": resistance})
    vol = indicators.get("volume", {"ratio": 1.0})

    macd_histogram = macd["histogram"]
    macd_prev_histogram = macd.get("prev_histogram", macd_histogram)

    return {
        "latest": latest, "support": support, "resistance": resistance, "atr": atr,
        "trend": trend, "rsi_val": rsi_val, "bb": bb, "vol_ratio": vol.get("ratio", 1.0),
        "near_support": latest <= (support + atr * 1.5),
        "near_resistance": latest >= (resistance - atr * 1.5),
        "near_bb_lower": latest <= bb["lower"] * 1.002,
        "near_bb_upper": latest >= bb["upper"] * 0.998,
        "macd_bullish": macd_histogram > 0,
        "macd_bearish": macd_histogram < 0,
        "macd_weakening": macd_histogram < macd_prev_histogram,
        "macd_strengthening": macd_histogram > macd_prev_histogram,
        "macd_histogram": macd_histogram,
        "macd_prev_histogram": macd_prev_histogram,
    }

def _wait_signal() -> Dict[str, Any]:
    return {
        "action": "WAIT", "reason": "ยังไม่พบสัญญาณที่สอดคล้องกัน",
        "confidence": 0.0, "strategy_type": "WAIT",
        "buy_score": 0, "sell_score": 0, "confirmations": []
    }

def evaluate_trend_following(indicators: Dict[str, Any], symbol: str, cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """กลยุทธ์เทรดตามเทรนด์ — คะแนนแยกจาก reversal"""
    cfg = cfg or get_strategy_config(symbol)
    ctx = _indicator_context(indicators)
    min_score = cfg["trend_min_score"]

    buy_score = sum([
        ctx["trend"] == "Bullish",
        ctx["rsi_val"] < cfg["trend_rsi_buy_max"],
        ctx["near_support"] or ctx["near_bb_lower"],
        ctx["macd_bullish"],
    ])
    sell_score = sum([
        ctx["trend"] == "Bearish",
        ctx["rsi_val"] > cfg["trend_rsi_sell_min"],
        ctx["near_resistance"] or ctx["near_bb_upper"],
        ctx["macd_bearish"],
    ])

    if buy_score >= min_score and ctx["rsi_val"] < 70 and sell_score < 2:
        return {
            "action": "BUY", "strategy_type": "TREND_FOLLOWING",
            "confidence": round(buy_score / 4.0, 2),
            "buy_score": buy_score, "sell_score": sell_score,
            "confirmations": ["trend", "rsi", "location", "macd"][:buy_score],
            "reason": (
                f"[Trend] BUY {buy_score}/4 — เทรนด์ {ctx['trend']}, RSI {ctx['rsi_val']}, "
                f"{'แนวรับ/BB Lower' if ctx['near_support'] or ctx['near_bb_lower'] else 'location'}, "
                f"MACD {'Bullish' if ctx['macd_bullish'] else 'Neutral'}"
            )
        }

    if sell_score >= min_score and ctx["rsi_val"] > 30 and buy_score < 2:
        return {
            "action": "SELL", "strategy_type": "TREND_FOLLOWING",
            "confidence": round(sell_score / 4.0, 2),
            "buy_score": buy_score, "sell_score": sell_score,
            "confirmations": ["trend", "rsi", "location", "macd"][:sell_score],
            "reason": (
                f"[Trend] SELL {sell_score}/4 — เทรนด์ {ctx['trend']}, RSI {ctx['rsi_val']}, "
                f"{'แนวต้าน/BB Upper' if ctx['near_resistance'] or ctx['near_bb_upper'] else 'location'}, "
                f"MACD {'Bearish' if ctx['macd_bearish'] else 'Neutral'}"
            )
        }

    result = _wait_signal()
    result["buy_score"] = buy_score
    result["sell_score"] = sell_score
    return result

RSI_THRESHOLDS = {
    "BULL":     {"oversold": 40, "overbought": 75},
    "BEAR":     {"oversold": 25, "overbought": 60},
    "SIDEWAYS": {"oversold": 35, "overbought": 65},
    "VOLATILE": {"oversold": 20, "overbought": 80},
}

def evaluate_reversal(indicators: Dict[str, Any], symbol: str, cfg: Optional[Dict] = None, regime: Optional[str] = None) -> Dict[str, Any]:
    """กลยุทธ์ reversal — RSI extreme + location + MACD + volume confirmation"""
    cfg = cfg or get_strategy_config(symbol)
    # Crypto keeps its per-symbol CALIBRATED thresholds (the generic regime
    # override degraded BTC/ETH in backtest). Trending instruments (metals/
    # forex/stocks) get regime-adaptive RSI thresholds.
    is_crypto = SYMBOLS.get(symbol, {}).get("assetClass") == "crypto"
    if regime and regime in RSI_THRESHOLDS and not is_crypto:
        oversold = RSI_THRESHOLDS[regime]["oversold"]
        overbought = RSI_THRESHOLDS[regime]["overbought"]
        cfg = cfg.copy()
        cfg["rsi_buy_early"] = oversold
        cfg["rsi_buy_full"] = oversold - 4
        cfg["rsi_sell_early"] = overbought
        cfg["rsi_sell_full"] = overbought + 3
    ctx = _indicator_context(indicators)
    vol_ok = ctx["vol_ratio"] >= cfg["volume_confirm_min"]

    # Regime gate (asset-class aware, see is_crypto above). Counter-trend
    # mean-reversion bleeds on trending instruments (gold -$6.5k→-$0.1k when
    # gated) but is a real edge on crypto (gating BTC +$1.4k→-$3.1k). Gate
    # only non-crypto.
    block_sell = regime == "BULL" and not is_crypto
    block_buy = regime == "BEAR" and not is_crypto

    # Early SELL: RSI > threshold + BB Upper + MACD weakening (+ volume)
    if (not block_sell
            and ctx["rsi_val"] > cfg["rsi_sell_early"]
            and ctx["near_bb_upper"]
            and ctx["macd_weakening"]):
        confs = ["rsi_overbought", "bb_upper", "macd_weakening"]
        confidence = 0.68
        if vol_ok:
            confs.append("volume")
            confidence = 0.74
        return {
            "action": "SELL", "strategy_type": "EARLY_REVERSAL",
            "confidence": confidence, "buy_score": 0, "sell_score": len(confs),
            "confirmations": confs,
            "reason": (
                f"[Reversal] Early SELL — RSI {ctx['rsi_val']} > {cfg['rsi_sell_early']}, "
                f"Bollinger Upper, MACD อ่อนลง ({ctx['macd_prev_histogram']:.4f}→{ctx['macd_histogram']:.4f})"
                f"{', Volume ยืนยัน' if vol_ok else ''}"
            )
        }

    # Full SELL reversal
    if not block_sell and ctx["rsi_val"] > cfg["rsi_sell_full"] and ctx["near_resistance"]:
        confs = ["rsi_extreme", "resistance"]
        confidence = 0.70
        if vol_ok:
            confs.append("volume")
            confidence = 0.76
        return {
            "action": "SELL", "strategy_type": "REVERSAL",
            "confidence": confidence, "buy_score": 0, "sell_score": len(confs),
            "confirmations": confs,
            "reason": (
                f"[Reversal] SELL — RSI {ctx['rsi_val']} > {cfg['rsi_sell_full']}, "
                f"ใกล้แนวต้าน {ctx['resistance']:.2f}"
                f"{', Volume ยืนยัน' if vol_ok else ''}"
            )
        }

    # Early BUY reversal
    if (not block_buy
            and ctx["rsi_val"] < cfg["rsi_buy_early"]
            and ctx["near_bb_lower"]
            and ctx["macd_strengthening"]):
        confs = ["rsi_oversold", "bb_lower", "macd_strengthening"]
        confidence = 0.68
        if vol_ok:
            confs.append("volume")
            confidence = 0.74
        return {
            "action": "BUY", "strategy_type": "EARLY_REVERSAL",
            "confidence": confidence, "buy_score": len(confs), "sell_score": 0,
            "confirmations": confs,
            "reason": (
                f"[Reversal] Early BUY — RSI {ctx['rsi_val']} < {cfg['rsi_buy_early']}, "
                f"Bollinger Lower, MACD แข็งขึ้น ({ctx['macd_prev_histogram']:.4f}→{ctx['macd_histogram']:.4f})"
                f"{', Volume ยืนยัน' if vol_ok else ''}"
            )
        }

    # Full BUY reversal
    if not block_buy and ctx["rsi_val"] < cfg["rsi_buy_full"] and ctx["near_support"]:
        confs = ["rsi_extreme", "support"]
        confidence = 0.70
        if vol_ok:
            confs.append("volume")
            confidence = 0.76
        return {
            "action": "BUY", "strategy_type": "REVERSAL",
            "confidence": confidence, "buy_score": len(confs), "sell_score": 0,
            "confirmations": confs,
            "reason": (
                f"[Reversal] BUY — RSI {ctx['rsi_val']} < {cfg['rsi_buy_full']}, "
                f"ใกล้แนวรับ {ctx['support']:.2f}"
                f"{', Volume ยืนยัน' if vol_ok else ''}"
            )
        }

    return _wait_signal()

def apply_mtf_filter(
    signal: Dict[str, Any],
    macro_trend_1h: Optional[str],
) -> Dict[str, Any]:
    """MTF filter — block เฉพาะ trend-following สวนเทรนด์, ปล่อย reversal ผ่าน"""
    if not macro_trend_1h or signal["action"] == "WAIT":
        return signal

    stype = signal.get("strategy_type", "WAIT")
    if stype in ("REVERSAL", "EARLY_REVERSAL"):
        return signal

    if macro_trend_1h == "Bullish" and signal["action"] == "SELL":
        return {
            **signal,
            "action": "WAIT",
            "confidence": 0.0,
            "reason": f"[MTF Block] Trend SELL สวน 1h Bullish — {signal['reason']}",
            "mtf_blocked": True,
        }
    if macro_trend_1h == "Bearish" and signal["action"] == "BUY":
        return {
            **signal,
            "action": "WAIT",
            "confidence": 0.0,
            "reason": f"[MTF Block] Trend BUY สวน 1h Bearish — {signal['reason']}",
            "mtf_blocked": True,
        }
    return signal

def evaluate_strategy_rules(
    indicators: Dict[str, Any],
    symbol: str,
    macro_trend_1h: Optional[str] = None,
    strategy_filter: Optional[str] = None,
    cfg: Optional[Dict] = None,
    regime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ประเมินสัญญาณ — แยก trend / reversal แล้วเลือกตัวที่เหมาะสม
    strategy_filter: None | 'TREND_FOLLOWING' | 'REVERSAL' (for backtest)
    """
    cfg = cfg or get_strategy_config(symbol)
    trend_sig = evaluate_trend_following(indicators, symbol, cfg)
    reversal_sig = evaluate_reversal(indicators, symbol, cfg, regime)

    if strategy_filter == "TREND_FOLLOWING":
        primary = trend_sig
    elif strategy_filter == "REVERSAL":
        primary = reversal_sig if reversal_sig["action"] != "WAIT" else _wait_signal()
    else:
        # Reversal มี priority เมื่อ RSI extreme + confirmation ครบ
        if reversal_sig["action"] != "WAIT" and len(reversal_sig.get("confirmations", [])) >= 3:
            primary = reversal_sig
        elif trend_sig["action"] != "WAIT":
            primary = trend_sig
        elif reversal_sig["action"] != "WAIT":
            primary = reversal_sig
        else:
            primary = _wait_signal()

    primary = apply_mtf_filter(primary, macro_trend_1h)

    stat_score = len(primary.get("confirmations", []))
    if primary["action"] != "WAIT":
        stat_score = min(stat_score / 4.0, 1.0)

    return {
        "action": primary["action"],
        "reason": primary["reason"],
        "confidence": primary["confidence"],
        "strategy_type": primary.get("strategy_type", "WAIT"),
        "buy_score": primary.get("buy_score", 0),
        "sell_score": primary.get("sell_score", 0),
        "confirmations": primary.get("confirmations", []),
        "statistical_score": round(stat_score, 2),
        "trend_signal": {
            "action": trend_sig["action"],
            "confidence": trend_sig["confidence"],
            "strategy_type": trend_sig.get("strategy_type", "WAIT"),
            "buy_score": trend_sig.get("buy_score", 0),
            "sell_score": trend_sig.get("sell_score", 0),
        },
        "reversal_signal": {
            "action": reversal_sig["action"],
            "confidence": reversal_sig["confidence"],
            "strategy_type": reversal_sig.get("strategy_type", "WAIT"),
            "confirmations": reversal_sig.get("confirmations", []),
        },
        "mtf_blocked": primary.get("mtf_blocked", False),
    }

# ─────────────────────────────────────────────────────────
# Dynamic Position Sizing (ATR-based)
# ─────────────────────────────────────────────────────────

def calculate_position_size(
    symbol: str,
    equity: float,
    risk_pct: float,
    atr: float,
    atr_multiplier: float = 2.0
) -> Dict[str, Any]:
    """
    คำนวณ Lot จาก ATR stop + fixed fractional risk
    XAUUSD: lot × stop_distance × contractSize(100) = risk $
    Crypto: lot (coin qty) × stop_distance = risk $
    """
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    contract_size = spec.get("contractSize", 100)
    asset_class = spec.get("assetClass", "metal")

    atr = validate_atr(atr, symbol, "calculate_position_size")
    equity = validate_price(equity, "calculate_position_size: equity")

    stop_distance = atr * atr_multiplier
    stop_distance = max(stop_distance, spec["volatility"] * 0.5)

    risk_dollars = equity * (risk_pct / 100)
    risk_per_lot = stop_distance * contract_size
    if risk_per_lot <= 0:
        risk_per_lot = stop_distance * 100

    lot_raw = risk_dollars / risk_per_lot
    max_lot = 10.0 if asset_class in ("metal", "forex") else 5.0
    lot = round(max(0.01, min(lot_raw, max_lot)), 2)

    actual_risk = lot * risk_per_lot

    return {
        "lot": lot,
        "stop_distance": round(stop_distance, spec["decimals"]),
        "risk_dollars": round(risk_dollars, 2),
        "actual_risk_dollars": round(actual_risk, 2),
        "contract_size": contract_size,
    }

# ─────────────────────────────────────────────────────────
# Risk Engine (Rule-based Guardrails)
# ─────────────────────────────────────────────────────────

def check_trade_risk(
    symbol: str,
    action: str,
    price: float,
    lot: float,
    stop_distance: float,
    spread: float,  # Spread Limit
    circuit_breaker_triggered: bool = False,
    take_profit: float = 40.0,
    reject_threshold: float = 3.0,
    risk_pct_limit: float = 1.5,
    equity: Optional[float] = None,
    broker_spread: Optional[float] = None,
) -> Dict[str, Any]:
    """ตรวจสอบกฎเหล็กบริหารความเสี่ยง 6 ประการ

    equity / broker_spread are injected by callers for a single source of truth.
    When omitted they are derived deterministically (no random, no hardcoded balance).
    """
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])

    if equity is None:
        from backend.shared.database.core import SessionLocal
        from backend.shared.database.models import Trade, TradeStatus
        db = SessionLocal()
        try:
            closed_trades = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
            total_pnl = sum([t.realized_pnl for t in closed_trades if t.realized_pnl])
            equity = STARTING_BALANCE + total_pnl
        except Exception:
            equity = STARTING_BALANCE
        finally:
            db.close()

    contract_size = spec.get("contractSize", 100)
    risk_dollars = lot * stop_distance * contract_size
    risk_pct = (risk_dollars / equity) * 100

    exposure_dollars = lot * price * contract_size
    exposure_pct = (exposure_dollars / equity) * 100

    # Deterministic broker spread from the real feed (was random.uniform).
    if broker_spread is None:
        broker_spread = current_spread_pips(symbol)

    checks = [
        {"name": "มีสัญญาณซื้อขายหลัก (ไม่ใช่ WAIT)", "pass": bool(action in ["BUY", "SELL"])},
        {"name": f"ความเสี่ยงต่อไม้ไม่เกิน {risk_pct_limit}% (ปัจจุบัน {risk_pct:.2f}%)", "pass": bool(risk_pct <= risk_pct_limit)},
        {"name": f"มีจุดตัดขาดทุนขั้นต่ำ (Stop Loss >= 20.0 pips)", "pass": bool(stop_distance >= 20.0)},
        {"name": f"ค่าสเปรดโบรกเกอร์ ({broker_spread}) ไม่เกินเกณฑ์ Spread Limit ({spread})", "pass": bool(broker_spread <= spread)},
        {"name": f"ค่าสเปรดโบรกเกอร์ ({broker_spread}) ไม่เกินเกณฑ์ Reject เด็ดขาด ({reject_threshold})", "pass": bool(broker_spread <= reject_threshold)},
        {"name": "ขนาดพอร์ตถือครองรวมไม่เกิน 20% (Exposure Limit)", "pass": bool(exposure_pct <= RISK_CONFIG["maxOpenExposurePct"])},
        {"name": "สถานะระบบความปลอดภัย (Circuit Breaker ไม่ทำงาน)", "pass": bool(not circuit_breaker_triggered)}
    ]

    passed = bool(all(check["pass"] for check in checks))

    return {
        "passed": passed,
        "checks": checks,
        "riskDollars": round(risk_dollars, 2),
        "riskPct": round(risk_pct, 2),
        "exposurePct": round(exposure_pct, 2),
        "brokerSpread": broker_spread
    }

# ─────────────────────────────────────────────────────────
# Performance Metrics Calculator
# ─────────────────────────────────────────────────────────

def calculate_performance_metrics(trades: List[Dict]) -> Dict[str, Any]:
    """
    คำนวณตัวชี้วัดประสิทธิภาพพอร์ต:
    - Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio
    """
    closed = [t for t in trades if t.get("status") == "CLOSED" and t.get("pnl") is not None]

    if not closed:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_pnl": 0.0,
            "calmar_ratio": 0.0
        }

    pnls = [t["pnl"] for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total = len(pnls)
    win_rate = (len(wins) / total * 100) if total > 0 else 0.0

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    profit_factor = min(profit_factor, 99.9)  # cap

    # Max Drawdown (จาก equity เริ่มต้น)
    equity = float(RISK_CONFIG["equity"])
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    # Sharpe Ratio (annualized, assuming 252 trading days)
    if len(pnls) >= 2:
        mean_pnl = sum(pnls) / len(pnls)
        std_pnl = statistics.stdev(pnls)
        sharpe = (mean_pnl / std_pnl * math.sqrt(252)) if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    total_pnl = sum(pnls)

    annual_return = total_pnl / RISK_CONFIG["equity"] * 100
    calmar = (annual_return / (max_dd * 100)) if max_dd > 0 else 0.0

    return {
        "total_trades": total,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_dd * 100, 2),  # เป็น %
        "sharpe_ratio": round(sharpe, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_pnl": round(total_pnl, 2),
        "calmar_ratio": round(calmar, 2)
    }

# ─────────────────────────────────────────────────────────
# Order Duplication Guard
# ─────────────────────────────────────────────────────────

class OrderDeduplicator:
    def __init__(self, maxlen: int = 100):
        self._queue: deque = deque(maxlen=maxlen)
        self._set: set = set()  # O(1) lookup

    def make_signal_id(self, symbol: str, action: str, entry_price: float) -> str:
        rounded_ts = int(datetime.now(timezone.utc).timestamp() / 300) * 300
        raw = f"{symbol}_{action}_{entry_price:.2f}_{rounded_ts}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_duplicate(self, symbol: str, action: str, entry_price: float) -> bool:
        signal_id = self.make_signal_id(symbol, action, entry_price)
        return signal_id in self._set  # O(1)

    def mark_executed(self, symbol: str, action: str, entry_price: float):
        signal_id = self.make_signal_id(symbol, action, entry_price)
        if len(self._queue) == self._queue.maxlen:
            evicted = self._queue.popleft()
            self._set.discard(evicted)
        self._queue.append(signal_id)
        self._set.add(signal_id)

order_deduplicator = OrderDeduplicator()

def needs_confirmation(signal: dict) -> bool:
    confidence = signal.get("confidence") or signal.get("confidence_score") or 0.0
    if confidence >= 0.85:
        return False
    return True

def confirm_signal(signal: dict, ohlc: pd.DataFrame, atr: float) -> bool:
    if not needs_confirmation(signal):
        return True
    zone = signal.get("zone_price") or signal.get("price_at_signal")
    if zone is None:
        return True
    last_close = ohlc["close"].iloc[-1]
    buffer = atr * 0.1  # 10% of ATR — adaptive
    action = signal.get("action") or signal.get("signal_type")
    if action == "BUY":
        return last_close > zone + buffer
    else:
        return last_close < zone - buffer

