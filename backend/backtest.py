import sys
import os
import asyncio
import httpx
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path so we can import backend core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core import get_market_indicators, evaluate_strategy_rules, SYMBOLS

async def fetch_backtest_data(symbol: str, interval: str = "1h", range_val: str = "60d"):
    """ดึงข้อมูลราคาประวัติย้อนหลังสำหรับการทำ Backtest"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_val}"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, timeout=10.0)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to fetch data: {r.text}")
        
        result = r.json().get("chart", {}).get("result", [{}])[0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        
        df = pd.DataFrame({
            "timestamp": [datetime.fromtimestamp(t) for t in timestamps],
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", [])
        })
        # Clean data
        df = df.dropna().reset_index(drop=True)
        return df

def run_backtest(df: pd.DataFrame, symbol: str):
    """รันการทดสอบกลยุทธ์ย้อนหลัง"""
    print(f"📊 เริ่มรัน Backtest สินทรัพย์: {symbol} | ข้อมูลทั้งหมด: {len(df)} แถว")
    
    spec = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"])
    
    trades = []
    active_trade = None
    
    # ต้องการข้อมูลอย่างน้อย 50 แถวเพื่อรันอินดิเคเตอร์
    for i in range(50, len(df)):
        current_row = df.iloc[i]
        
        # เตรียมชุดข้อมูลประวัติสำหรับคำนวณอินดิเคเตอร์ย้อนหลัง
        history_prices = df["close"].iloc[i-48:i+1].tolist()
        
        # 1. จัดการออเดอร์ที่เปิดค้างอยู่
        if active_trade:
            # ตรวจสอบว่าชน SL/TP หรือยัง
            high = current_row["high"]
            low = current_row["low"]
            close = current_row["close"]
            
            is_sl_hit = False
            is_tp_hit = False
            
            if active_trade["action"] == "BUY":
                if low <= active_trade["stop_loss"]:
                    is_sl_hit = True
                elif high >= active_trade["take_profit"]:
                    is_tp_hit = True
            else: # SELL
                if high >= active_trade["stop_loss"]:
                    is_sl_hit = True
                elif low <= active_trade["take_profit"]:
                    is_tp_hit = True
                    
            if is_sl_hit or is_tp_hit:
                exit_price = active_trade["stop_loss"] if is_sl_hit else active_trade["take_profit"]
                diff = exit_price - active_trade["entry_price"] if active_trade["action"] == "BUY" else active_trade["entry_price"] - exit_price
                pnl = diff * active_trade["lot"] * 100 * spec["tickValue"]
                
                active_trade["exit_price"] = exit_price
                active_trade["exit_time"] = current_row["timestamp"]
                active_trade["pnl"] = pnl
                active_trade["status"] = "SL_HIT" if is_sl_hit else "TP_HIT"
                
                trades.append(active_trade)
                active_trade = None
        
        # 2. ค้นหาสัญญาณเข้าเทรดใหม่
        if not active_trade:
            indicators = get_market_indicators(history_prices, symbol)
            # เพื่อความเรียบง่าย ใช้คำสั่งวิเคราะห์โดยไม่มี Trend 1h เป็นฟิลเตอร์ เพื่อประเมิน Base Strategy
            signal = evaluate_strategy_rules(indicators, symbol)
            
            if signal["action"] in ["BUY", "SELL"]:
                action = signal["action"]
                entry_price = current_row["close"]
                atr = indicators["atr"]
                
                # SL/TP calculation
                stop_dist = atr * 2.0
                stop_dist = max(stop_dist, spec["volatility"] * 0.5)
                
                # ใช้ SL 300 หรือ ATR ตามการตั้งค่าปัจจุบัน
                stop_dist = 300.0 if symbol == "BTCUSDT" else stop_dist
                
                sl = entry_price - stop_dist if action == "BUY" else entry_price + stop_dist
                tp = entry_price + stop_dist * 2.0 if action == "BUY" else entry_price - stop_dist * 2.0
                
                active_trade = {
                    "action": action,
                    "entry_price": entry_price,
                    "entry_time": current_row["timestamp"],
                    "stop_loss": sl,
                    "take_profit": tp,
                    "lot": 0.1,
                    "status": "OPEN"
                }
                
    # คำนวณสรุปสถิติ
    if not trades:
        print("❌ ไม่พบรายการเปิดซื้อขายในประวัติย้อนหลังนี้")
        return
        
    df_trades = pd.DataFrame(trades)
    total_trades = len(df_trades)
    wins = len(df_trades[df_trades["pnl"] > 0])
    losses = len(df_trades[df_trades["pnl"] <= 0])
    win_rate = (wins / total_trades) * 100
    total_pnl = df_trades["pnl"].sum()
    
    gross_profit = df_trades[df_trades["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(df_trades[df_trades["pnl"] <= 0]["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    
    print("\n==============================================")
    print("📈 รายงานผลทดสอบระบบเทรดประวัติย้อนหลัง (Backtest Report)")
    print("==============================================")
    print(f"สินทรัพย์: {symbol}")
    print(f"จำนวนการเทรดทั้งหมด: {total_trades} ไม้")
    print(f"ชนะ (Wins): {wins} | แพ้ (Losses): {losses}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"กำไรสุทธิทั้งหมด (Net PnL): ${total_pnl:+.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print("==============================================")

if __name__ == "__main__":
    symbol = "BTC-USD" if len(sys.argv) < 2 else sys.argv[1]
    timeframe = "1h" if len(sys.argv) < 3 else sys.argv[2]
    range_val = "60d" if len(sys.argv) < 4 else sys.argv[3]
    
    # Mapping
    mapped_symbol = "BTCUSDT"
    if "XAU" in symbol.upper() or "GOLD" in symbol.upper():
        symbol = "GC=F"
        mapped_symbol = "XAUUSD"
        
    df = asyncio.run(fetch_backtest_data(symbol, timeframe, range_val))
    run_backtest(df, mapped_symbol)
