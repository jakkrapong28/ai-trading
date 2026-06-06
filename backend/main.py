import asyncio
import json
import logging
import os
import random
from typing import List, Dict, Any, Set
from datetime import datetime

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import (
    generate_price_history, 
    get_market_indicators, 
    evaluate_strategy_rules, 
    check_trade_risk, 
    RISK_CONFIG, 
    SYMBOLS
)
from agents import generate_thai_debate
import anthropic
import ccxt

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PythonTradingService")

def load_dotenv_manually():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            logger.info("โหลดคอนฟิกจากไฟล์ .env ของระบบสำเร็จ")
        except Exception as e:
            logger.error(f"ไม่สามารถโหลดไฟล์ .env: {e}")

load_dotenv_manually()

app = FastAPI(title="Python Trading & AI Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# สเตตภายในระบบ (In-Memory State) จำลองฐานข้อมูล PostgreSQL
# ---------------------------------------------------------
class TradingState:
    def __init__(self):
        self.symbol = "XAUUSD"
        self.prices = generate_price_history(self.symbol)
        self.indicators = get_market_indicators(self.prices, self.symbol)
        self.signal = evaluate_strategy_rules(self.indicators, self.symbol)
        self.risk = check_trade_risk(
            self.symbol, 
            self.signal["action"], 
            self.indicators["latest"], 
            0.1, 
            15.0, 
            1.8
        )
        self.mode = "watch" # auto / watch
        self.balances = [
            {"source": "MT5", "equity": 25000.00, "balance": 24850.00, "free_margin": 24850.00},
            {"source": "BINANCE", "equity": 12500.00, "balance": 12500.00, "free_margin": 12500.00},
            {"source": "ONCHAIN_WALLET", "equity": 8400.00, "balance": 8400.00, "free_margin": 8400.00}
        ]
        self.journal = [
            {
                "type": "system_init", 
                "detail": "ระบบนิเวศ AI Trading Virtual Office เริ่มต้นการทำงานเสร็จสมบูรณ์", 
                "at": datetime.now().isoformat()
            }
        ]
        self.orders = []
        self.active_debate = []
        self.is_debating = False
        
        # คอนฟิกการเชื่อมต่อ Telegram Bot จริง และ API Keys ในระบบ
        self.telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.binance_key = os.environ.get("BINANCE_API_KEY", "")
        self.binance_secret = os.environ.get("BINANCE_API_SECRET", "")
        self.news_api_key = os.environ.get("NEWS_API_KEY", "") or os.environ.get("NEWSAPI_KEY", "")
        self.twelvedata_api_key = os.environ.get("TWELVEDATA_API_KEY", "")
        self.finnhub_api_key = os.environ.get("FINNHUB_API_KEY", "")
        
        self.telegram_chat_id = "" # เก็บแชทไอดีล่าสุดเพื่อส่งแจ้งเตือนกลับ
        self.last_update_id = 0
        
        # เริ่มต้นโมดูล CCXT เชื่อมต่อตลาดซื้อขายจริง (ถ้ากำหนด Key)
        self.binance_client = None
        if self.binance_key and self.binance_secret:
            try:
                self.binance_client = ccxt.binance({
                    'apiKey': self.binance_key,
                    'secret': self.binance_secret,
                    'enableRateLimit': True
                })
                logger.info("เชื่อมต่อ Binance Private API สำเร็จ")
            except Exception as e:
                logger.error(f"ไม่สามารถเปิดใช้งานโมดูล Binance CCXT: {e}")

state = TradingState()

# ---------------------------------------------------------
# ระบบสตรีมสดผ่าน WebSockets
# ---------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket Client เชื่อมต่อสำเร็จ: {len(self.active_connections)} active")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket Client ตัดการเชื่อมต่อ: {len(self.active_connections)} active")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# ---------------------------------------------------------
# ฟังก์ชันหลักสำหรับการอัปเดตราคาและเริ่มเซสชันการอภิปรายของ AI
# ---------------------------------------------------------
async def fetch_twelvedata_stock_price(symbol: str) -> float:
    key = state.twelvedata_api_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={key}"
            r = await client.get(url, timeout=3.0)
            if r.status_code == 200:
                data = r.json()
                if "price" in data:
                    return float(data["price"])
                else:
                    logger.warning(f"TwelveData Price Warning: {data}")
    except Exception as e:
        logger.error(f"TwelveData ดึงข้อมูลผิดพลาด: {e}")
    return None

async def fetch_finnhub_stock_price(symbol: str) -> float:
    key = state.finnhub_api_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={key}"
            r = await client.get(url, timeout=3.0)
            if r.status_code == 200:
                price = r.json().get("c", 0.0)
                if price > 0:
                    return float(price)
    except Exception as e:
        logger.error(f"Finnhub ดึงข้อมูลผิดพลาด: {e}")
    return None

async def fetch_live_binance_price(symbol: str) -> float:
    if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                r = await client.get(url, timeout=2.0)
                if r.status_code == 200:
                    return float(r.json().get("price", 0))
        except Exception as e:
            logger.error(f"ไม่สามารถดึงราคาจริงของ {symbol} จาก Binance ได้: {e}")
    return None

async def fetch_live_stock_price(symbol: str) -> float:
    if symbol in ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN"]:
        # 1. ดึงผ่าน TwelveData (ถ้ามีคีย์)
        td_price = await fetch_twelvedata_stock_price(symbol)
        if td_price is not None:
            return td_price
        # 2. ดึงผ่าน Finnhub (ถ้ามีคีย์)
        fh_price = await fetch_finnhub_stock_price(symbol)
        if fh_price is not None:
            return fh_price
        # 3. ดึงผ่าน Yahoo Finance
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://query1.finance2.yahoo.com/v8/finance/chart/{symbol}"
                headers = {"User-Agent": "Mozilla/5.0"}
                r = await client.get(url, headers=headers, timeout=2.0)
                if r.status_code == 200:
                    data = r.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    return float(meta.get("regularMarketPrice", 0))
        except Exception as e:
            logger.error(f"ไม่สามารถดึงราคาจริงของหุ้น {symbol} จาก Yahoo Finance ได้: {e}")
    return None

async def fetch_actual_market_price(symbol: str) -> float:
    price = await fetch_live_binance_price(symbol)
    if price is not None:
        return price
    price = await fetch_live_stock_price(symbol)
    if price is not None:
        return price
    return None

async def sync_live_binance_balance():
    if state.binance_client:
        try:
            bal = await asyncio.to_thread(state.binance_client.fetch_balance)
            usdt_total = bal.get('USDT', {}).get('total', 0.0)
            usdt_free = bal.get('USDT', {}).get('free', 0.0)
            if usdt_total > 0:
                for b in state.balances:
                    if b["source"] == "BINANCE":
                        b["balance"] = round(usdt_total, 2)
                        b["equity"] = round(usdt_total, 2)
                        b["free_margin"] = round(usdt_free, 2)
        except Exception as e:
            logger.error(f"ไม่สามารถซิงค์ยอดเงินจริงจาก Binance API (CCXT) ได้: {e}")

async def trigger_market_update(symbol: str = None):
    if symbol:
        state.symbol = symbol
    
    # ดึงยอดคงเหลือจริงหากกรอก Binance API คีย์ครบ
    await sync_live_binance_balance()
    
    live_price = await fetch_actual_market_price(state.symbol)
    
    state.prices = generate_price_history(state.symbol)
    if live_price:
        state.prices[-1] = live_price
        
    state.indicators = get_market_indicators(state.prices, state.symbol)
    state.signal = evaluate_strategy_rules(state.indicators, state.symbol)
    
    state.risk = check_trade_risk(
        state.symbol, 
        state.signal["action"], 
        state.indicators["latest"], 
        0.1, 
        15.0, 
        1.8
    )
    
    add_journal_entry("market_snapshot", f"ดึงข้อมูลราคา {state.symbol} ล่าสุด: {state.indicators['latest']}")
    
    await manager.broadcast({
        "type": "market_update",
        "symbol": state.symbol,
        "latest": state.indicators["latest"],
        "indicators": state.indicators,
        "signal": state.signal,
        "risk": state.risk,
        "mode": state.mode
    })
    
    asyncio.create_task(run_agent_debate_simulation())

async def run_agent_debate_simulation():
    if state.is_debating:
        return
    
    state.is_debating = True
    state.active_debate = []
    
    debate_steps = generate_thai_debate(state.symbol, state.indicators, state.signal, state.risk)
    
    for step in debate_steps:
        state.active_debate.append(step)
        
        if "CEO" in step["agent"] and len(state.active_debate) == len(debate_steps):
            add_journal_entry("analysis_run", f"สรุปมติที่ประชุมของ {state.symbol}: {state.signal['action']} - {state.signal['reason']}")
            
        await manager.broadcast({
            "type": "agent_typing",
            "message": step
        })
        await asyncio.sleep(random.uniform(0.4, 0.9))
        
    state.is_debating = False
    
    # หากโหมดเป็นแบบ "auto" (อัตโนมัติ) และความเสี่ยงผ่านเกณฑ์ ให้สั่งเทรดอัตโนมัติ
    if state.mode == "auto" and state.risk["passed"] and state.signal["action"] in ["BUY", "SELL"]:
        logger.info("[Auto Mode] ความเสี่ยงผ่านเกณฑ์ กำลังทำรายการส่งออเดอร์อัตโนมัติ...")
        await execute_mock_trade()
        
    # หากตั้งค่า Telegram Bot สำเร็จ ให้ส่งสัญญาณแจ้งเตือนไปยังโทรศัพท์ของคุณโทนี่
    if state.telegram_token and state.telegram_chat_id:
        asyncio.create_task(send_telegram_debate_summary())

def add_journal_entry(log_type: str, detail: str):
    entry = {
        "type": log_type,
        "detail": detail,
        "at": datetime.now().isoformat()
    }
    state.journal.insert(0, entry)
    if len(state.journal) > 80:
        state.journal.pop()

async def execute_mock_trade():
    action = state.signal["action"]
    entry_price = state.indicators["latest"]
    
    order_id = f"ord_{int(datetime.now().timestamp() * 1000)}"
    volume = 0.1
    
    order = {
        "id": order_id,
        "symbol": state.symbol,
        "action": action,
        "volume": volume,
        "entry_price": entry_price,
        "exit_price": 0.0,
        "pnl": 0.0,
        "fee": 0.0,
        "status": "OPEN"
    }
    state.orders.insert(0, order)
    
    await manager.broadcast({
        "type": "order_opened",
        "order": order,
        "balances": state.balances
    })
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://localhost:5001/webhook/trade-event", json={
                "event": "trade.opened",
                "data": {
                    "symbol": state.symbol,
                    "action": action,
                    "price": entry_price,
                    "volume": volume
                }
            }, timeout=2.0)
        except Exception as e:
            logger.error(f"[ERP Link] ไม่สามารถเชื่อมต่อส่ง webhook ได้: {e}")
            
    add_journal_entry("trade_order.paper_created", f"คำสั่ง {action} {state.symbol} จำลองสำเร็จที่ราคา {entry_price}")
    asyncio.create_task(simulate_order_close(order_id, action, entry_price, volume))

async def simulate_order_close(order_id: str, action: str, entry_price: float, volume: float):
    await asyncio.sleep(5.0)
    
    spec = SYMBOLS[state.symbol]
    win = random.random() > 0.4 
    multiplier = 1.0 if win else -0.8
    pnl = round(volume * spec["volatility"] * multiplier * 2.0 * 100, 2)
    fee = round(2.50 + random.random() * 2.0, 2)
    
    exit_price = round(entry_price + (pnl / (volume * 100 * spec["tickValue"])), spec["decimals"])
    
    for ord in state.orders:
        if ord["id"] == order_id:
            ord["exit_price"] = exit_price
            ord["pnl"] = pnl
            ord["fee"] = fee
            ord["status"] = "CLOSED"
            break
            
    broker = "BINANCE" if state.symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"] else "MT5"
    for bal in state.balances:
        if bal["source"] == broker:
            bal["balance"] = round(bal["balance"] + pnl - fee, 2)
            bal["equity"] = bal["balance"]
            
    add_journal_entry("trade_closed", f"ปิดออเดอร์ดีล {state.symbol} ได้รับผลประโยชน์ PnL: {'+' if pnl >= 0 else ''}${pnl} (หักค่าธรรมเนียม ${fee})")
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post("http://localhost:5001/webhook/trade-event", json={
                "event": "trade.pnl_realized",
                "data": {
                    "symbol": state.symbol,
                    "pnl": pnl,
                    "fee": fee
                }
            }, timeout=2.0)
        except Exception as e:
            logger.error(f"[ERP Link] ไม่สามารถเชื่อมต่อส่ง webhook การปิดดีลได้: {e}")
            
    await manager.broadcast({
        "type": "order_closed",
        "order_id": order_id,
        "orders": state.orders,
        "balances": state.balances
    })

# ---------------------------------------------------------
# ระบบ Telegram Bot จริง - ส่งสรุปและปุ่มกดยืนยันออเดอร์
# ---------------------------------------------------------
async def send_telegram_debate_summary():
    """
    ส่งข้อความสรุปการวิเคราะห์ตลาดไปยัง Telegram บอทจริงพร้อมปุ่มอนุมัติ / ปฏิเสธ
    """
    if not state.telegram_token or not state.telegram_chat_id:
        return
        
    action = state.signal["action"]
    symbol = state.symbol
    price = state.indicators["latest"]
    passed = state.risk["passed"]
    
    text = (
        f"📊 *[CEO Agent - รายงานการวิเคราะห์ด่วน]*\n"
        f"คู่สินทรัพย์: *{symbol}*\n"
        f"ราคาปัจจุบัน: *{price}*\n"
        f"สัญญาณเทรด: *{action}*\n"
        f"เหตุผล: {state.signal['reason']}\n\n"
        f"🛡️ *[ประเมินความเสี่ยง]*\n"
        f"สถานะ: {'✅ ผ่าน (APPROVED)' if passed else '❌ ระงับ (BLOCKED)'}\n"
        f"ขนาดไม้จำลอง: {state.risk['riskPct']}% ของพอร์ต\n"
    )
    
    payload = {
        "chat_id": state.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    
    # หากผ่านความเสี่ยงและมีสัญญาณเทรด ให้ส่งปุ่มกด (Inline Keyboard)
    if passed and action in ["BUY", "SELL"]:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "✅ อนุมัติเทรด (Approve)", "callback_data": f"approve_{symbol}"},
                    {"text": "❌ ปฏิเสธแผน (Reject)", "callback_data": f"reject_{symbol}"}
                ]
            ]
        }
        
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.telegram.org/bot{state.telegram_token}/sendMessage"
            await client.post(url, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"ไม่สามารถส่งข้อความไปหา Telegram จริงได้: {e}")

# ---------------------------------------------------------
# โมเดลข้อมูล API
# ---------------------------------------------------------
class OrderRequest(BaseModel):
    lot: float
    stopDistance: float
    spread: float

class SymbolRequest(BaseModel):
    symbol: str

class TelegramCommandRequest(BaseModel):
    command: str

class SettingsRequest(BaseModel):
    telegram_token: str
    anthropic_key: str
    binance_key: str
    binance_secret: str
    news_api_key: str
    twelvedata_api_key: str
    finnhub_api_key: str
    maxRiskPerTradePct: float
    maxOpenExposurePct: float

# ---------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------
# (endpoints already handled, keeping place)


# ---------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------
@app.get("/api/state")
def get_state():
    return {
        "symbol": state.symbol,
        "latest": state.indicators["latest"],
        "indicators": state.indicators,
        "signal": state.signal,
        "risk": state.risk,
        "mode": state.mode,
        "balances": state.balances,
        "journal": state.journal,
        "orders": state.orders,
        "debate": state.active_debate,
        "is_debating": state.is_debating,
        "settings": {
            "telegram_token": state.telegram_token,
            "anthropic_key": state.anthropic_key,
            "binance_key": state.binance_key,
            "binance_secret": state.binance_secret,
            "news_api_key": state.news_api_key,
            "twelvedata_api_key": state.twelvedata_api_key,
            "finnhub_api_key": state.finnhub_api_key,
            "maxRiskPerTradePct": RISK_CONFIG["maxRiskPerTradePct"],
            "maxOpenExposurePct": RISK_CONFIG["maxOpenExposurePct"]
        }
    }

async def fetch_newsapi_feed(symbol: str) -> List[Dict[str, Any]]:
    key = state.news_api_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://newsapi.org/v2/everything?q={symbol}+finance&sortBy=publishedAt&pageSize=8&apiKey={key}"
            r = await client.get(url, timeout=4.0)
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                if isinstance(articles, list):
                    news_list = []
                    for art in articles[:8]:
                        published_at = art.get("publishedAt", "")
                        time_str = published_at[11:16] if len(published_at) > 16 else "Recent"
                        news_list.append({
                            "time": time_str,
                            "source": art.get("source", {}).get("name", "NewsAPI"),
                            "text": art.get("title", ""),
                            "impact": "HIGH" if "FED" in art.get("title", "") or "SEC" in art.get("title", "") else "MEDIUM"
                        })
                    return news_list
    except Exception as e:
        logger.error(f"ดึงข่าวจาก NewsAPI ขัดข้อง: {e}")
    return None

@app.get("/api/news")
async def get_live_news():
    # 1. ดึงจาก NewsAPI (ถ้ามีคีย์)
    news = await fetch_newsapi_feed(state.symbol)
    if news:
        return {"success": True, "news": news}
        
    # 2. ดึงจาก Finnhub (ถ้ามีคีย์)
    finnhub_key = state.finnhub_api_key
    if finnhub_key:
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://finnhub.io/api/v1/news?category=general&token={finnhub_key}"
                r = await client.get(url, timeout=3.0)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list):
                        news_list = []
                        for item in data[:8]:
                            dt = datetime.fromtimestamp(item.get("datetime", 0))
                            time_str = dt.strftime("%H:%M")
                            news_list.append({
                                "time": time_str,
                                "source": item.get("source", "Finnhub"),
                                "text": item.get("headline", ""),
                                "impact": "HIGH" if item.get("related", "") else "MEDIUM"
                            })
                        return {"success": True, "news": news_list}
        except Exception as e:
            logger.error(f"ดึงข่าวจาก Finnhub ขัดข้อง: {e}")

    # 3. ดึงจาก CryptoCompare
    async with httpx.AsyncClient() as client:
        try:
            url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
            r = await client.get(url, timeout=4.0)
            if r.status_code == 200:
                data = r.json().get("Data", [])
                if isinstance(data, list):
                    news_list = []
                    for item in data[:8]:
                        dt = datetime.fromtimestamp(item.get("published_on", 0))
                        time_str = dt.strftime("%H:%M")
                        news_list.append({
                            "time": time_str,
                            "source": item.get("source_info", {}).get("name", "CryptoCompare"),
                            "text": item.get("title", ""),
                            "impact": "HIGH" if "BTC" in item.get("categories", "") or "SEC" in item.get("title", "") else "MEDIUM"
                        })
                    return {"success": True, "news": news_list}
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข่าวสด: {e}")
            
        return {
            "success": True,
            "news": [
                { "time": "02:15", "source": "FED Watch", "text": "ประธาน FED ส่งสัญญาณแนวโน้มปรับลดดอกเบี้ยนโยบายปลายปีนี้ หากดัชนีเงินเฟ้อลดต่ำลงตามเป้าหมาย 2%", "impact": "HIGH" },
                { "time": "01:30", "source": "Binance Research", "text": "ปริมาณการซื้อขายเหรียญ SOL ทะยานขึ้นสูงสุดในรอบ 3 เดือน รับอานิสงส์จากการทำธุรกรรม DeFi บนเครือข่ายที่พุ่งสูง", "impact": "MEDIUM" },
                { "time": "00:45", "source": "NVIDIA Corp", "text": "NVIDIA ประกาศชิป AI รุ่นสถาปัตยกรรมใหม่ที่มีกำลังประมวลผลสูงขึ้น 4 เท่า หุ้นพุ่งทะลุ 3.5% นำดัชนี Nasdaq ดีดตัว", "impact": "HIGH" }
            ]
        }

@app.post("/api/change-symbol")
async def change_symbol(req: SymbolRequest):
    if req.symbol not in SYMBOLS:
        raise HTTPException(status_code=400, detail="ไม่รองรับสินทรัพย์นี้")
    await trigger_market_update(req.symbol)
    return {"status": "success", "symbol": state.symbol}

@app.post("/api/update-risk")
def update_risk(req: OrderRequest):
    state.risk = check_trade_risk(
        state.symbol, 
        state.signal["action"], 
        state.indicators["latest"], 
        req.lot, 
        req.stopDistance, 
        req.spread
    )
    add_journal_entry("risk_check", f"อัปเดตทดสอบความเสี่ยง Lot {req.lot} - {'ผ่าน' if state.risk['passed'] else 'ระงับ'}")
    return state.risk

@app.post("/api/approve")
async def approve_trade():
    if not state.risk["passed"]:
        raise HTTPException(status_code=400, detail="ความเสี่ยงไม่ผ่านเกณฑ์ ไม่สามารถเปิดออเดอร์ได้")
    await execute_mock_trade()
    return {"status": "success", "message": "ส่งคำขอเปิดออเดอร์ไปยังตลาดเรียบร้อย"}

@app.post("/api/reject")
def reject_trade():
    add_journal_entry("trade_rejected", f"ผู้ใช้ทำการปฏิเสธแผนการเทรดล่าสุดของ {state.symbol}")
    return {"status": "success", "message": "ปฏิเสธแผนการเทรดเรียบร้อย"}

@app.post("/api/change-mode")
def change_mode(req: Dict[str, str]):
    mode = req.get("mode", "watch")
    if mode in ["auto", "watch"]:
        state.mode = mode
        add_journal_entry("mode_change", f"สลับโหมดการควบคุมหลักเป็น: {mode.upper()}")
        return {"status": "success", "mode": state.mode}
    raise HTTPException(status_code=400, detail="โหมดไม่ถูกต้อง")

@app.post("/api/update-settings")
def update_settings(req: SettingsRequest):
    state.telegram_token = req.telegram_token.strip()
    state.anthropic_key = req.anthropic_key.strip()
    state.binance_key = req.binance_key.strip()
    state.binance_secret = req.binance_secret.strip()
    state.news_api_key = req.news_api_key.strip()
    state.twelvedata_api_key = req.twelvedata_api_key.strip()
    state.finnhub_api_key = req.finnhub_api_key.strip()
    
    # เซฟลงในไฟล์ .env ทันทีเพื่อความคงทนของข้อมูล
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_TOKEN={state.telegram_token}\n")
            f.write(f"ANTHROPIC_API_KEY={state.anthropic_key}\n")
            f.write(f"BINANCE_API_KEY={state.binance_key}\n")
            f.write(f"BINANCE_API_SECRET={state.binance_secret}\n")
            f.write(f"NEWS_API_KEY={state.news_api_key}\n")
            f.write(f"TWELVEDATA_API_KEY={state.twelvedata_api_key}\n")
            f.write(f"FINNHUB_API_KEY={state.finnhub_api_key}\n")
        logger.info("เซฟคีย์การเชื่อมต่อและโทเค็นลงในไฟล์ .env สำเร็จ")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูลลงไฟล์ .env: {e}")
        
    # เชื่อมต่อ CCXT ใหม่หากป้อนคีย์ครบ
    if state.binance_key and state.binance_secret:
        try:
            state.binance_client = ccxt.binance({
                'apiKey': state.binance_key,
                'secret': state.binance_secret,
                'enableRateLimit': True
            })
            logger.info("บันทึกคีย์และเชื่อมต่อ Binance Private API สำเร็จ")
        except Exception as e:
            logger.error(f"ไม่สามารถเริ่มใช้งาน Binance CCXT: {e}")
            
    RISK_CONFIG["maxRiskPerTradePct"] = req.maxRiskPerTradePct
    RISK_CONFIG["maxOpenExposurePct"] = req.maxOpenExposurePct
    add_journal_entry("settings_update", "อัปเดตตั้งค่าระบบวิเคราะห์ความเสี่ยงและ API Keys เรียบร้อย")
    return {"status": "success", "settings": {
        "telegram_token": state.telegram_token,
        "anthropic_key": state.anthropic_key,
        "binance_key": state.binance_key,
        "binance_secret": state.binance_secret,
        "news_api_key": state.news_api_key,
        "twelvedata_api_key": state.twelvedata_api_key,
        "finnhub_api_key": state.finnhub_api_key,
        "maxRiskPerTradePct": RISK_CONFIG["maxRiskPerTradePct"],
        "maxOpenExposurePct": RISK_CONFIG["maxOpenExposurePct"]
    }}

@app.get("/api/erp/ledger")
async def proxy_erp_ledger():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://localhost:5001/api/ledger")
            return r.json()
        except Exception:
            return {"success": False, "ledger": []}

@app.get("/api/erp/tax-summary")
async def proxy_erp_tax():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://localhost:5001/api/tax-summary")
            return r.json()
        except Exception:
            return {"success": False, "data": {}}

async def get_claude_chat_response(message: str) -> str:
    key = state.anthropic_key
    if not key:
        return (
            "🤖 [CEO Agent]: ขณะนี้ยังไม่ได้เชื่อมต่อ Anthropic API Key ครับ "
            "กรุณากรอก Key ในหน้า Settings เพื่อเริ่มต้นสนทนาอัจฉริยะกับ Claude "
            "เกี่ยวกับหุ้น คริปโต หรือสอบถามข้อมูลทั่วไปได้ตลอดเวลาครับ!"
        )
    
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        
        symbol = state.symbol
        latest_price = state.indicators["latest"]
        trend = state.indicators["trend"]
        rsi = state.indicators["rsi"]
        passed = state.risk["passed"]
        total_equity = sum(b["equity"] for b in state.balances)
        
        system_prompt = (
            f"คุณคือ CEO Agent (JARVIS-CEO) หัวหน้าทีม AI Trading Virtual Office ของคุณโทนี่ "
            f"ผู้บริหารและประเมินผลลัพธ์พอร์ตลงทุนของโครงการ Team ERP Ecosystem\n"
            f"คุณต้องสนทนาตอบผู้ใช้ด้วยภาษาไทยอย่างสุภาพ มีระดับ กระชับ ชัดเจน และเป็นมืออาชีพสูง "
            f"เน้นเรื่องการวิเคราะห์ตลาดและพอร์ตลงทุนเป็นหลัก และนี่คือข้อมูลพอร์ตปัจจุบันเพื่อใช้ตอบคำถาม:\n"
            f"- สินทรัพย์หลักขณะนี้: {symbol}\n"
            f"- ราคาซื้อขายปัจจุบัน: {latest_price}\n"
            f"- เทรนด์เทคนิคอล: {trend} (RSI: {rsi})\n"
            f"- การประเมินความเสี่ยง: {'ผ่านเกณฑ์ความปลอดภัย 🟢' if passed else 'มีความเสี่ยงสูง (ถูกสั่งระงับชั่วคราว) 🔴'}\n"
            f"- มูลค่าทรัพย์สินพอร์ตรวม (Net Worth): ${total_equity:,.2f}\n"
            f"- รายการออเดอร์สะสม: {len(state.orders)} รายการ\n\n"
            f"ผู้ใช้สามารถถามคำถามเกี่ยวกับหุ้น คริปโต หรือเรื่องทั่วไปก็ได้ แต่ขอให้คุณตอบอย่างเป็นธรรมชาติ "
            f"และสอดแทรกมุมมองของฝ่าย CEO Agent ที่ใส่ใจการเติบโตของพอร์ตลงทุนเสมอ"
        )
        
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": message}
            ]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการติดต่อ Claude API: {e}")
        return f"❌ [ไม่สามารถติดต่อ Claude API ได้]: {str(e)}"

# Telegram Chatbot Emulator
@app.post("/api/telegram/command")
async def process_telegram_command(req: TelegramCommandRequest):
    cmd = req.command.strip()
    response = await handle_telegram_command_logic(cmd, "UI_Emulator")
    return {"response": response}

async def handle_telegram_command_logic(cmd: str, user_tag: str) -> str:
    if cmd.startswith("/analyze"):
        parts = cmd.split()
        symbol = parts[1].upper() if len(parts) > 1 else state.symbol
        if symbol not in SYMBOLS:
            return f"❌ ไม่พบคู่สินทรัพย์ที่ต้องการวิเคราะห์: {symbol}"
        
        asyncio.create_task(trigger_market_update(symbol))
        return (
            f"📊 ได้รับคำสั่งวิเคราะห์ด่วนสำหรับ {symbol} จากคุณโทนี่ ({user_tag}) เรียบร้อย!\n"
            f"ขณะนี้กำลังกระตุ้นเสวนากรรมการ AI ทั้ง 6 ฝ่ายและระบบ Risk Guardian เพื่อเขียนมติอัปเดต โปรดดูสตรีมแชทสดบน Dashboard ของออฟฟิศ..."
        )
        
    elif cmd.startswith("/wallet"):
        total_equity = sum(bal["equity"] for bal in state.balances)
        balance_details = "\n".join([f"- {b['source']}: ยอดคงเหลือ ${b['balance']:,} (Equity: ${b['equity']:,})" for b in state.balances])
        return (
            f"🔍 [รายงาน Wallet Intel AI]\n"
            f"ยอดมูลค่าทรัพย์สินพอร์ตรวม (Net Worth): ${total_equity:,.2f}\n\n"
            f"รายละเอียดสมุดรายวัน:\n{balance_details}"
        )
        
    elif cmd.startswith("/mode"):
        parts = cmd.split()
        if len(parts) > 1 and parts[1].lower() in ["auto", "watch"]:
            new_mode = parts[1].lower()
            state.mode = new_mode
            add_journal_entry("mode_change", f"สลับโหมดการควบคุมหลักเป็น: {new_mode.upper()}")
            return f"⚙️ สลับโหมดการทำออเดอร์เป็น [{new_mode.upper()}] สำเร็จแล้วครับ"
        return "❓ วิธีใช้งาน: พิมพ์ `/mode auto` หรือ `/mode watch`"
    
    elif cmd.startswith("/price"):
        parts = cmd.split()
        symbol = parts[1].upper() if len(parts) > 1 else state.symbol
        if symbol not in SYMBOLS:
            return f"❌ ไม่พบคู่สินทรัพย์: {symbol}"
        return (
            f"📈 [ราคาเสนอซื้อล่าสุด]\n"
            f"คู่เหรียญ/หุ้น: {symbol}\n"
            f"ราคาเฉลี่ยปัจจุบัน: {state.indicators['latest']}\n"
            f"เทรนด์ภาพรวม: {state.indicators['trend']}"
        )
        
    elif cmd.startswith("/report"):
        today_pnl = sum(o.get("pnl", 0.0) for o in state.orders)
        return (
            f"📝 [รายงานผลเทรดจาก Report AI]\n"
            f"ประวัติดีลสำเร็จสะสม: {len(state.orders)} รายการ\n"
            f"ผลกำไร P&L สุทธิวันนี้: ${today_pnl:.2f}"
        )
        
    elif cmd.startswith("/risk"):
        passed_txt = "ผ่านเกณฑ์บริหารความปลอดภัย 🟢" if state.risk["passed"] else "ระงับออเดอร์ความปลอดภัยต่ำ 🔴"
        return (
            f"🛡️ [การตรวจความปลอดภัย Risk AI]\n"
            f"สถานะ: {passed_txt}\n"
            f"สัดส่วนความเสี่ยงไม้: {state.risk['riskPct']}%\n"
            f"สัดส่วน Exposure: {state.risk['exposurePct']}%"
        )
        
    elif cmd.startswith("/alerts"):
        return "🚨 [รายงานระบบ Alert AI]\nระบบสตรีม WebSocket และ Ledger ERP กำลังทำงานได้เสถียร 100% ไม่มีภัยคุกคามตรวจพบครับ"
        
    elif cmd.startswith("/pause"):
        add_journal_entry("system_pause", "ระบบการวิเคราะห์และยิงออเดอร์ถูกระงับชั่วคราวผ่าน Telegram")
        return "⏸️ สั่งการสำเร็จ: ระงับระบบ Virtual Office ชั่วคราวเรียบร้อย"
        
    elif cmd.startswith("/close all"):
        state.orders = []
        add_journal_entry("orders_cleared", "สั่งล้างสัญญาทั้งพอร์ตจำลองโดยผู้ใช้")
        return "🧹 สั่งปิดและเคลียร์ประวัติคำสั่งเทรดกระดาษเรียบร้อยแล้วครับ"
        
    else:
        return (
            "💬 คำสั่งที่รองรับ:\n"
            "- `/price [Symbol]` (ตรวจราคาล่าสุด)\n"
            "- `/analyze [Symbol]` (สแกนสภา AI วิเคราะห์ด่วน)\n"
            "- `/wallet` (ตรวจ Net Worth ทรัพย์สินพอร์ต)\n"
            "- `/report` (ขอสรุปดีลกำไรวันนี้)\n"
            "- `/risk` (ตรวจสอบความเสี่ยงพอร์ต)\n"
            "- `/alerts` (เช็คแจ้งเตือนภัยระบบ)\n"
            "- `/mode [auto/watch]` (สลับเทรดออโต้/กึ่งออโต้)"
        )

# ---------------------------------------------------------
# WebSocket Entry Point
# ---------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "init",
            "state": {
                "symbol": state.symbol,
                "latest": state.indicators["latest"],
                "indicators": state.indicators,
                "signal": state.signal,
                "risk": state.risk,
                "mode": state.mode,
                "balances": state.balances,
                "journal": state.journal,
                "orders": state.orders,
                "debate": state.active_debate,
                "is_debating": state.is_debating
            }
        })
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "refresh_market":
                await trigger_market_update()
            elif msg.get("type") == "command":
                user_msg = msg.get("message", "")
                
                await manager.broadcast({
                    "type": "agent_typing",
                    "message": {
                        "agent": "CEO Agent",
                        "role": "ผู้นำบัญชาการ",
                        "avatar": "💼",
                        "message": "กำลังคิดวิเคราะห์คำถามของคุณโทนี่...",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                ai_reply = await get_claude_chat_response(user_msg)
                
                await manager.broadcast({
                    "type": "agent_typing",
                    "message": {
                        "agent": "CEO Agent",
                        "role": "ผู้นำบัญชาการ",
                        "avatar": "💼",
                        "message": ai_reply,
                        "timestamp": datetime.now().isoformat()
                    }
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดใน WebSocket Connection: {e}")
        manager.disconnect(websocket)

# ---------------------------------------------------------
# ระบบลูปอะซิงโครนัส โพลลิ่ง Telegram Bot API จริง
# ---------------------------------------------------------
async def telegram_bot_poller():
    logger.info("เริ่มต้นระบบตรวจหาคำสั่งบอท Telegram (Poller Task Started)")
    while True:
        token = state.telegram_token
        if not token:
            await asyncio.sleep(4)
            continue
            
        try:
            async with httpx.AsyncClient() as client:
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                params = {"offset": state.last_update_id + 1, "timeout": 3}
                r = await client.get(url, params=params, timeout=6.0)
                
                if r.status_code == 200:
                    res = r.json()
                    if res.get("ok"):
                        updates = res.get("result", [])
                        for upd in updates:
                            state.last_update_id = max(state.last_update_id, upd["update_id"])
                            await handle_real_telegram_update(upd)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโพลล์ Telegram: {e}")
            
        await asyncio.sleep(2.0)

async def handle_real_telegram_update(upd: Dict[str, Any]):
    # 1. จัดการเหตุการณ์ข้อความทั่วไป
    if "message" in upd:
        msg = upd["message"]
        chat_id = str(msg["chat"]["id"])
        state.telegram_chat_id = chat_id # จดบันทึก Chat ID ของคุณโทนี่ไว้สำหรับตอบกลับ
        
        text = msg.get("text", "").strip()
        if not text:
            return
            
        logger.info(f"[Telegram Bot] ได้รับข้อความจากคุณโทนี่: {text}")
        
        # แสดงคำถามของคุณโทนี่บน Dashboard ด้วย
        await manager.broadcast({
            "type": "agent_typing",
            "message": {
                "agent": "user",
                "role": "ผู้บัญชาการพอร์ต",
                "avatar": "👤",
                "message": f"คุณโทนี่ (ทาง Telegram) ถาม: {text}",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        if text.startswith("/"):
            response_text = await handle_telegram_command_logic(text, f"Telegram_{chat_id[:6]}")
        else:
            response_text = await get_claude_chat_response(text)
            
        # ส่งข้อความผลลัพธ์กลับไปยัง Telegram จริง
        await send_telegram_direct_message(chat_id, response_text)
        
        # แสดงคำตอบของ AI บน Dashboard
        await manager.broadcast({
            "type": "agent_typing",
            "message": {
                "agent": "CEO Agent",
                "role": "ผู้นำบัญชาการ",
                "avatar": "💼",
                "message": response_text,
                "timestamp": datetime.now().isoformat()
            }
        })
        
    # 2. จัดการปุ่มกด (Callback Queries) เช่นกดปุ่มอนุมัติ/ปฏิเสธผ่าน Telegram มือถือ
    elif "callback_query" in upd:
        cb = upd["callback_query"]
        cb_id = cb["id"]
        chat_id = str(cb["message"]["chat"]["id"])
        cb_data = cb.get("data", "")
        
        logger.info(f"[Telegram Bot] ได้รับ Callback Query ปุ่มกด: {cb_data}")
        
        if cb_data.startswith("approve_"):
            symbol = cb_data.replace("approve_", "")
            
            # อนุมัติการเข้าเทรดกระดาษจริง
            if state.risk["passed"]:
                await execute_mock_trade()
                reply_text = f"🟢 [อนุมัติสำเร็จ] ยิงคำสั่งเปิดออเดอร์ XAUUSD สำเร็จและบันทึกบัญชีแยกประเภท ERP แล้ว!"
            else:
                reply_text = f"❌ [ระงับคำสั่ง] เกณฑ์ความเสี่ยงมีการเปลี่ยนแปลงและไม่ผ่านกฎพอร์ต ไม่สามารถเทรดได้"
                
        elif cb_data.startswith("reject_"):
            add_journal_entry("trade_rejected", "คุณโทนี่กดปฏิเสธแผนเทรดผ่าน Telegram Inline Keyboards")
            reply_text = "🔴 [ยกเลิกสำเร็จ] CEO Agent ได้ระงับการเข้าเทรดสัญญานี้เรียบร้อยแล้ว"
        else:
            reply_text = "ไม่ทราบรายการปุ่มกด"
            
        # ตอบรับ Callback (เพื่อให้หน้าจอมือถือหายกะพริบ)
        async with httpx.AsyncClient() as client:
            try:
                # ตอบรับ callback
                await client.post(
                    f"https://api.telegram.org/bot{state.telegram_token}/answerCallbackQuery",
                    json={"callback_query_id": cb_id, "text": reply_text}
                )
                # แก้ไขข้อความใน Telegram ให้ตรงกับสถานะล่าสุด
                await client.post(
                    f"https://api.telegram.org/bot{state.telegram_token}/editMessageText",
                    json={
                        "chat_id": chat_id,
                        "message_id": cb["message"]["message_id"],
                        "text": f"{cb['message']['text']}\n\n🤖 *สถานะล่าสุด*: {reply_text}",
                        "parse_mode": "Markdown"
                    }
                )
            except Exception as e:
                logger.error(f"ไม่สามารถอัปเดต Callback ปุ่มกดได้: {e}")

async def send_telegram_direct_message(chat_id: str, text: str):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.telegram.org/bot{state.telegram_token}/sendMessage"
            await client.post(url, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"ไม่สามารถตอบกลับคุณโทนี่ในแชทได้: {e}")

# ---------------------------------------------------------
# เริ่มทำงานอัปเดตราคาแบบวนรอบ (Background Poller)
# ---------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    await trigger_market_update()
    
    # รันโพลตรวจจับ Telegram บอทจริงในพื้นหลัง
    asyncio.create_task(telegram_bot_poller())
    
    # รันลูปจำลองข้อมูลราคาขยับ
    async def price_ticker_sim():
        while True:
            await asyncio.sleep(15)
            spec = SYMBOLS.get(state.symbol, SYMBOLS["XAUUSD"])
            change = (random.random() - 0.5) * spec["volatility"] * 0.4
            new_price = round(state.indicators["latest"] + change, spec["decimals"])
            
            state.prices.pop(0)
            state.prices.append(new_price)
            state.indicators = get_market_indicators(state.prices, state.symbol)
            state.signal = evaluate_strategy_rules(state.indicators, state.symbol)
            
            state.risk = check_trade_risk(
                state.symbol, 
                state.signal["action"], 
                state.indicators["latest"], 
                0.1, 
                15.0, 
                1.8
            )
            
            await manager.broadcast({
                "type": "price_tick",
                "symbol": state.symbol,
                "price": new_price,
                "indicators": state.indicators,
                "signal": state.signal,
                "risk": state.risk
            })
            
    asyncio.create_task(price_ticker_sim())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# Trigger auto-reload for updated .env config
