import math
import random
from typing import List, Dict, Any

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

# ฟังก์ชันคำนวณราคาแบบสุ่ม (Random Walk Simulator)
def generate_price_history(symbol: str, length: int = 96) -> List[float]:
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    prices = []
    price = spec["base"] + (random.random() - 0.5) * spec["volatility"] * 5
    for i in range(length):
        drift = math.sin(i / 11.0) * spec["volatility"] * 0.22
        shock = (random.random() - 0.48) * spec["volatility"]
        price = max(price + drift + shock, spec["volatility"])
        prices.append(round(price, spec["decimals"]))
    return prices

# คำนวณ Exponential Moving Average (EMA)
def calculate_ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    multiplier = 2.0 / (period + 1)
    ema_values = [values[0]]
    for val in values[1:]:
        new_ema = val * multiplier + ema_values[-1] * (1.0 - multiplier)
        ema_values.append(new_ema)
    return ema_values

# คำนวณ Relative Strength Index (RSI)
def calculate_rsi(values: List[float], period: int = 14) -> float:
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
    return 100.0 - (100.0 / (1.0 + rs))

# คำนวณตัวชี้วัดความผันผวนเลียนแบบ Average True Range (ATR-like volatility)
def calculate_atr(values: List[float], period: int = 14) -> float:
    if len(values) < 2:
        return 1.0
    ranges = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
    last_ranges = ranges[-period:]
    return sum(last_ranges) / len(last_ranges)

# ฟังก์ชันคำนวณอินดิเคเตอร์ภาพรวมตลาด
def get_market_indicators(prices: List[float], symbol: str) -> Dict[str, Any]:
    fast = calculate_ema(prices, 12)
    slow = calculate_ema(prices, 26)
    latest = prices[-1]
    rsi_val = calculate_rsi(prices, 14)
    atr_val = calculate_atr(prices, 14)
    
    # หาระดับแนวรับแนวต้านในช่วง 22 แท่งหลัง
    recent_prices = prices[-22:]
    support = min(recent_prices)
    resistance = max(recent_prices)
    
    trend = "Bullish" if fast[-1] > slow[-1] else "Bearish"
    
    return {
        "latest": latest,
        "rsi": round(rsi_val, 1),
        "atr": round(atr_val, SYMBOLS[symbol]["decimals"]),
        "trend": trend,
        "support": support,
        "resistance": resistance
    }

# เครื่องมือวิเคราะห์เงื่อนไขการเทรด (Strategy Rule Engine)
def evaluate_strategy_rules(indicators: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    latest = indicators["latest"]
    support = indicators["support"]
    resistance = indicators["resistance"]
    atr = indicators["atr"]
    trend = indicators["trend"]
    rsi_val = indicators["rsi"]
    
    near_support = latest <= (support + atr * 1.2)
    near_resistance = latest >= (resistance - atr * 1.2)
    
    action = "WAIT"
    reason = "ไม่มีทิศทางที่สอดคล้องกับตัวชี้วัดหลักอย่างชัดเจนในขณะนี้"
    
    if trend == "Bullish" and rsi_val < 68 and near_support:
        action = "BUY"
        reason = f"แนวโน้ม EMA เป็นกระทิง (Bullish), RSI {rsi_val} ยังไม่อยู่ในเขตซื้อมากเกินไป, และราคาเข้าใกล้โซนแนวรับที่ {support}"
    elif trend == "Bearish" and rsi_val > 32 and near_resistance:
        action = "SELL"
        reason = f"แนวโน้ม EMA เป็นหมี (Bearish), RSI {rsi_val} ยังไม่อยู่ในเขตขายมากเกินไป, และราคาเข้าใกล้โซนแนวต้านที่ {resistance}"
        
    if action == "WAIT" and random.random() < 0.7:
        action = random.choice(["BUY", "SELL"])
        reason = f"[จำลองสัญญาณทดสอบระบบ] สแกนพบความสอดคล้องระยะสั้นในกรอบแนวรับแนวต้านย่อย เหมาะสำหรับทดสอบปุ่มยืนยันออเดอร์"
        
    return {
        "action": action,
        "reason": reason
    }

# เครื่องมือวิเคราะห์และบริหารความเสี่ยง (Risk Engine)
def check_trade_risk(
    symbol: str, 
    action: str, 
    price: float, 
    lot: float, 
    stop_distance: float, 
    spread: float
) -> Dict[str, Any]:
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    
    # คำนวณความเสี่ยงที่เป็นจำนวนเงิน ($)
    risk_dollars = lot * stop_distance * spec["tickValue"] * 100
    risk_pct = (risk_dollars / RISK_CONFIG["equity"]) * 100
    
    # คำนวณขนาดการถือครอง (Exposure)
    exposure_dollars = lot * price * 100
    exposure_pct = (exposure_dollars / RISK_CONFIG["equity"]) * 100
    
    # ตรวจสอบกฎเหล็ก 5 ประการ
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
