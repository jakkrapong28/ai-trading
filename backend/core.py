import math
import random
import statistics
from typing import List, Dict, Any, Optional
from collections import deque

# ค่าคอนฟิกความเสี่ยงตามนโยบายระบบเทรดของคุณโทนี่
RISK_CONFIG = {
    "equity": 45750.00,
    "maxRiskPerTradePct": 2.0,  # กฎความเสี่ยงสูงสุดต่อไม้ 2%
    "maxDailyLossPct": 3.0,
    "maxOpenExposurePct": 20.0,
    "maxSpread": 3.0,
    "minStopDistance": 10.0
}

SYMBOLS = {
    "XAUUSD": {"base": 2342.0, "volatility": 7.5, "tickValue": 1.0, "decimals": 2},
    "EURUSD": {"base": 1.0832, "volatility": 0.0028, "tickValue": 10.0, "decimals": 5},
    "BTCUSDT": {"base": 68150.0, "volatility": 340.0, "tickValue": 0.1, "decimals": 2},
    "ETHUSDT": {"base": 3570.0, "volatility": 42.0, "tickValue": 0.1, "decimals": 2},
    "SOLUSDT": {"base": 170.0, "volatility": 5.0, "tickValue": 0.1, "decimals": 2},
    "TSLA": {"base": 180.0, "volatility": 6.0, "tickValue": 1.0, "decimals": 2},
    "AAPL": {"base": 190.0, "volatility": 3.5, "tickValue": 1.0, "decimals": 2},
    "NVDA": {"base": 120.0, "volatility": 4.5, "tickValue": 1.0, "decimals": 2},
    "MSFT": {"base": 420.0, "volatility": 8.0, "tickValue": 1.0, "decimals": 2},
    "AMZN": {"base": 185.0, "volatility": 4.0, "tickValue": 1.0, "decimals": 2}
}

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
    """Exponential Moving Average"""
    if not values or len(values) < period:
        return values or []
    multiplier = 2.0 / (period + 1)
    ema_values = [values[0]]
    for val in values[1:]:
        new_ema = val * multiplier + ema_values[-1] * (1.0 - multiplier)
        ema_values.append(new_ema)
    return ema_values

def calculate_rsi(values: List[float], period: int = 14) -> float:
    """Relative Strength Index (Wilder's smoothing)"""
    if len(values) <= period:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = values[i] - values[i-1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff

    avg_gain = gains / period
    avg_loss = losses / period

    for i in range(period + 1, len(values)):
        diff = values[i] - values[i-1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)

def calculate_macd(values: List[float]) -> Dict[str, float]:
    """MACD = EMA12 - EMA26, Signal = EMA9 of MACD"""
    if len(values) < 26:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema12 = calculate_ema(values, 12)
    ema26 = calculate_ema(values, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(len(ema26))]
    signal_line = calculate_ema(macd_line, 9)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(macd_val - signal_val, 4)
    }

def calculate_atr(prices: List[float], period: int = 14) -> float:
    """
    Average True Range — approximated from close-to-close differences
    (เนื่องจากไม่มี OHLCV ใช้ |close[i] - close[i-1]| เป็น True Range estimate)
    """
    if len(prices) < 2:
        return SYMBOLS.get("XAUUSD", {}).get("volatility", 1.0)
    # True Range estimate: max(|H-L|, |H-PC|, |L-PC|) approximated via close ranges
    ranges = []
    for i in range(1, len(prices)):
        # Estimate high/low from adjacent closes
        hi = max(prices[i], prices[i-1])
        lo = min(prices[i], prices[i-1])
        tr = hi - lo  # close-to-close range as TR proxy
        ranges.append(tr)

    last_ranges = ranges[-period:]
    return round(sum(last_ranges) / len(last_ranges), 4) if last_ranges else 1.0

def calculate_bollinger_bands(values: List[float], period: int = 20, std_mult: float = 2.0) -> Dict[str, float]:
    """Bollinger Bands"""
    if len(values) < period:
        last = values[-1] if values else 0
        return {"upper": last, "middle": last, "lower": last, "width": 0}
    recent = values[-period:]
    mean = sum(recent) / period
    std = statistics.stdev(recent)
    return {
        "upper": round(mean + std_mult * std, 4),
        "middle": round(mean, 4),
        "lower": round(mean - std_mult * std, 4),
        "width": round(std_mult * 2 * std, 4)
    }

def get_market_indicators(prices: List[float], symbol: str) -> Dict[str, Any]:
    """คำนวณอินดิเคเตอร์ภาพรวมตลาด"""
    if not prices:
        spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
        return {"latest": spec["base"], "rsi": 50.0, "atr": spec["volatility"], "trend": "Sideways", "support": spec["base"], "resistance": spec["base"]}

    fast = calculate_ema(prices, 12)
    slow = calculate_ema(prices, 26)
    latest = prices[-1]
    rsi_val = calculate_rsi(prices, 14)
    atr_val = calculate_atr(prices, 14)
    macd_data = calculate_macd(prices)
    bb_data = calculate_bollinger_bands(prices)

    # แนวรับแนวต้าน — ใช้ช่วง 22 แท่งล่าสุด
    recent_prices = prices[-22:]
    support = min(recent_prices)
    resistance = max(recent_prices)

    # EMA Trend
    if fast[-1] > slow[-1] * 1.001:
        trend = "Bullish"
    elif fast[-1] < slow[-1] * 0.999:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "latest": latest,
        "rsi": rsi_val,
        "atr": atr_val,
        "trend": trend,
        "support": support,
        "resistance": resistance,
        "ema_fast": round(fast[-1], SYMBOLS[symbol]["decimals"]),
        "ema_slow": round(slow[-1], SYMBOLS[symbol]["decimals"]),
        "macd": macd_data,
        "bollinger": bb_data
    }

# ─────────────────────────────────────────────────────────
# Strategy Rule Engine (ไม่มี Random Fallback)
# ─────────────────────────────────────────────────────────

def evaluate_strategy_rules(indicators: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """
    ประเมินสัญญาณเทรดจากกฎทางเทคนิค
    - ไม่มี random fallback อีกต่อไป
    - คืนค่า WAIT เมื่อไม่มีสัญญาณชัดเจน
    - เพิ่มการตรวจสอบ MACD confirmation
    """
    latest = indicators["latest"]
    support = indicators["support"]
    resistance = indicators["resistance"]
    atr = indicators["atr"]
    trend = indicators["trend"]
    rsi_val = indicators["rsi"]
    macd = indicators.get("macd", {"histogram": 0})
    bb = indicators.get("bollinger", {"lower": support, "upper": resistance})

    near_support = latest <= (support + atr * 1.5)
    near_resistance = latest >= (resistance - atr * 1.5)
    near_bb_lower = latest <= bb["lower"] * 1.002
    near_bb_upper = latest >= bb["upper"] * 0.998
    macd_bullish = macd["histogram"] > 0
    macd_bearish = macd["histogram"] < 0

    action = "WAIT"
    reason = "ยังไม่พบสัญญาณที่สอดคล้องกัน รอสัญญาณยืนยันจากหลายอินดิเคเตอร์"
    confidence = 0.0

    # ─── BUY Conditions ───
    buy_score = 0
    if trend == "Bullish": buy_score += 1
    if rsi_val < 65: buy_score += 1
    if near_support or near_bb_lower: buy_score += 1
    if macd_bullish: buy_score += 1

    # ─── SELL Conditions ───
    sell_score = 0
    if trend == "Bearish": sell_score += 1
    if rsi_val > 35: sell_score += 1
    if near_resistance or near_bb_upper: sell_score += 1
    if macd_bearish: sell_score += 1

    # ─── Strong BUY: ≥3 ตัวชี้วัดสอดคล้อง ───
    if buy_score >= 3 and rsi_val < 70 and sell_score < 2:
        action = "BUY"
        confidence = buy_score / 4.0
        reason = (
            f"สัญญาณ BUY ยืนยัน {buy_score}/4 ตัวชี้วัด — "
            f"เทรนด์ {trend}, RSI {rsi_val}, "
            f"{'ใกล้แนวรับ' if near_support else 'ใกล้ Bollinger Lower'}, "
            f"MACD {'Bullish' if macd_bullish else 'Neutral'}"
        )

    # ─── Strong SELL: ≥3 ตัวชี้วัดสอดคล้อง ───
    elif sell_score >= 3 and rsi_val > 30 and buy_score < 2:
        action = "SELL"
        confidence = sell_score / 4.0
        reason = (
            f"สัญญาณ SELL ยืนยัน {sell_score}/4 ตัวชี้วัด — "
            f"เทรนด์ {trend}, RSI {rsi_val}, "
            f"{'ใกล้แนวต้าน' if near_resistance else 'ใกล้ Bollinger Upper'}, "
            f"MACD {'Bearish' if macd_bearish else 'Neutral'}"
        )

    # ─── Overbought/Oversold override ───
    elif rsi_val > 78 and near_resistance:
        action = "SELL"
        confidence = 0.70
        reason = f"RSI Overbought ({rsi_val}) และราคาใกล้แนวต้าน {resistance:.2f} — สัญญาณ SELL แบบ Reversal"

    elif rsi_val < 22 and near_support:
        action = "BUY"
        confidence = 0.70
        reason = f"RSI Oversold ({rsi_val}) และราคาใกล้แนวรับ {support:.2f} — สัญญาณ BUY แบบ Reversal"

    return {
        "action": action,
        "reason": reason,
        "confidence": round(confidence, 2),
        "buy_score": buy_score,
        "sell_score": sell_score
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
    คำนวณขนาด Lot จาก ATR-based Stop Loss + Fixed Fractional Risk
    Formula: Lot = (Equity × Risk%) / (ATR × Multiplier × TickValue × 100)
    """
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    stop_distance = atr * atr_multiplier
    stop_distance = max(stop_distance, spec["volatility"] * 0.5)  # floor

    risk_dollars = equity * (risk_pct / 100)
    tick_val = spec["tickValue"]

    # Lot calculation
    lot_raw = risk_dollars / (stop_distance * tick_val * 100)
    lot = round(max(0.01, min(lot_raw, 10.0)), 2)

    return {
        "lot": lot,
        "stop_distance": round(stop_distance, spec["decimals"]),
        "risk_dollars": round(risk_dollars, 2)
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
    spread: float
) -> Dict[str, Any]:
    """ตรวจสอบกฎเหล็กบริหารความเสี่ยง 5 ประการ"""
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])

    risk_dollars = lot * stop_distance * spec["tickValue"] * 100
    risk_pct = (risk_dollars / RISK_CONFIG["equity"]) * 100

    exposure_dollars = lot * price * 100
    exposure_pct = (exposure_dollars / RISK_CONFIG["equity"]) * 100

    checks = [
        {"name": "มีสัญญาณซื้อขายหลัก (ไม่ใช่ WAIT)", "pass": action in ["BUY", "SELL"]},
        {"name": "ความเสี่ยงต่อไม้ไม่เกิน 2% (2% Rule)", "pass": risk_pct <= RISK_CONFIG["maxRiskPerTradePct"]},
        {"name": "มีจุดตัดขาดทุนขั้นต่ำ (Stop Loss > 10 pips)", "pass": stop_distance >= RISK_CONFIG["minStopDistance"]},
        {"name": "ค่าสเปรดไม่กว้างเกินเกณฑ์ (Spread Limit)", "pass": spread <= RISK_CONFIG["maxSpread"]},
        {"name": "ขนาดพอร์ตถือครองรวมไม่เกิน 20% (Exposure Limit)", "pass": exposure_pct <= RISK_CONFIG["maxOpenExposurePct"]}
    ]

    passed = all(check["pass"] for check in checks)

    return {
        "passed": passed,
        "checks": checks,
        "riskDollars": round(risk_dollars, 2),
        "riskPct": round(risk_pct, 2),
        "exposurePct": round(exposure_pct, 2)
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

    # Max Drawdown
    equity = 0.0
    peak = 0.0
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
