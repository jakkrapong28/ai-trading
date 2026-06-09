from dotenv import load_dotenv
import os

# Load .env file explicitly from the backend directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
import json
import random
from typing import List, Dict, Any, Set, Optional
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager
from pydantic import BaseModel
import httpx
import anthropic
import ccxt
import pandas as pd

from backend.shared.events.core import EventBus, CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS, CH_AI_JOURNAL, CH_NEWS, CH_RISK_APPROVED, CH_RISK_REJECTED, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED
from backend.shared.database.core import Base, engine, SessionLocal
from backend.shared.database.models import Trade, PerformanceMetric, TradeAction, TradeStatus

from backend.engines.market_data import start_market_data_engine
from backend.engines.news_intelligence import start_news_intelligence_engine
from backend.engines.market_regime import start_market_regime_engine
from backend.engines.strategy import start_strategy_engine
from backend.engines.risk import start_risk_engine
from backend.engines.execution import start_execution_engine
from backend.engines.portfolio import start_portfolio_engine

from backend.core import (
    generate_price_history,
    get_market_indicators,
    evaluate_strategy_rules,
    check_trade_risk,
    calculate_position_size,
    calculate_performance_metrics,
    append_price,
    RISK_CONFIG,
    SYMBOLS
)
from backend.agents import generate_thai_debate, generate_thai_debate_async

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api-gateway")

# ─────────────────────────────────────────────────────────
# Global Event Bus
# ─────────────────────────────────────────────────────────
event_bus = EventBus()

# ─────────────────────────────────────────────────────────
# Singleton HTTP Client (Connection Pool)
# ─────────────────────────────────────────────────────────
http_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    if http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return http_client

# ─────────────────────────────────────────────────────────
# WebSocket Connection Manager — Race Condition Fixed
# ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WS connected: {len(self.active_connections)} active")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WS disconnected: {len(self.active_connections)} active")

    async def broadcast(self, message: dict):
        """Thread-safe broadcast — ไม่แก้ list ขณะ iterate"""
        async with self._lock:
            connections = list(self.active_connections)  # copy ก่อน iterate

        dead = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)

        # ลบ dead connections
        if dead:
            async with self._lock:
                for c in dead:
                    if c in self.active_connections:
                        self.active_connections.remove(c)

manager = ConnectionManager()

# ─────────────────────────────────────────────────────────
# Alert Thresholds
# ─────────────────────────────────────────────────────────
ALERT_CONFIG = {
    "rsi_overbought": 75,
    "rsi_oversold": 25,
    "max_drawdown_pct": 5.0,    # alert เมื่อ drawdown > 5%
    "price_spike_pct": 2.0,     # alert เมื่อราคาเปลี่ยน > 2% ใน 1 tick
}
_last_alerts: Dict[str, datetime] = {}  # cooldown tracker
ALERT_COOLDOWN_MINUTES = 30

# ─────────────────────────────────────────────────────────
# Analyze Request Queue — ป้องกัน multiple concurrent debates
# ─────────────────────────────────────────────────────────
_analyze_queue: asyncio.Queue = asyncio.Queue(maxsize=5)

# ─────────────────────────────────────────────────────────
# In-Memory Trading State
# ─────────────────────────────────────────────────────────
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
            0.1, 15.0, 1.8
        )
        self.mode = "watch"  # auto / watch
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
        self.last_update_id = 0
        self.signal_executed = False  # Track if the current signal was already executed
        self.daily_realized_pnl = 0.0
        self.circuit_breaker_triggered = False
        self.macro_trend_1h = "Bullish"
        self.partially_closed_trades = set()
        self._state_lock = asyncio.Lock()

        # API Keys — โหลดจาก environment
        self.telegram_token = os.environ.get("TELEGRAM_TOKEN", "")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.binance_key = os.environ.get("BINANCE_API_KEY", "")
        self.binance_secret = os.environ.get("BINANCE_API_SECRET", "")
        self.news_api_key = os.environ.get("NEWS_API_KEY", "")
        self.twelvedata_api_key = os.environ.get("TWELVEDATA_API_KEY", "")
        self.finnhub_api_key = os.environ.get("FINNHUB_API_KEY", "")

        self.telegram_chat_id = ""
        self.binance_client = None

        self._init_binance()

    def _init_binance(self):
        """เชื่อมต่อ Binance ถ้ามี key จริง"""
        if self.binance_key and self.binance_secret and "Binance" not in self.binance_key:
            try:
                self.binance_client = ccxt.binance({
                    "apiKey": self.binance_key,
                    "secret": self.binance_secret,
                    "enableRateLimit": True
                })
                logger.info("เชื่อมต่อ Binance Private API สำเร็จ")
            except Exception as e:
                logger.error(f"ไม่สามารถเปิดใช้งานโมดูล Binance CCXT: {e}")

    def mask_key(self, key: str) -> str:
        """Mask API key ก่อนส่งออก"""
        if not key or len(key) < 8:
            return "ยังไม่ได้ตั้งค่า"
        return key[:4] + "••••••••" + key[-4:]

    def get_total_equity(self) -> float:
        return sum(b["equity"] for b in self.balances)

state = TradingState()

# ─────────────────────────────────────────────────────────
# Journal Helper
# ─────────────────────────────────────────────────────────
def add_journal_entry(log_type: str, detail: str):
    entry = {"type": log_type, "detail": detail, "at": datetime.now().isoformat()}
    state.journal.insert(0, entry)
    if len(state.journal) > 100:
        state.journal.pop()

# ─────────────────────────────────────────────────────────
# Database Helpers (async-safe via asyncio.to_thread)
# ─────────────────────────────────────────────────────────
def _get_orders_from_db_sync():
    """Sync DB query — รัน via asyncio.to_thread"""
    db = SessionLocal()
    orders = []
    try:
        trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(30).all()
        for t in trades:
            orders.append({
                "id": t.id,
                "symbol": t.ticker,
                "action": t.action.name if t.action else "BUY",
                "volume": t.lot_size or 0.1,
                "entry_price": t.entry_price or 0.0,
                "exit_price": t.exit_price or 0.0,
                "pnl": t.realized_pnl or 0.0,
                "fee": 2.50,
                "status": t.status.name if t.status else "OPEN"
            })
    except Exception as e:
        logger.error(f"DB Query Error: {e}")
    finally:
        db.close()
    return orders

async def get_orders_from_db():
    """Async wrapper สำหรับ DB query"""
    return await asyncio.to_thread(_get_orders_from_db_sync)

def _get_metrics_sync():
    """Sync metrics calculation — รัน via asyncio.to_thread"""
    db = SessionLocal()
    try:
        trades = db.query(Trade).all()
        trade_dicts = []
        for t in trades:
            if t.status == TradeStatus.CLOSED:
                trade_dicts.append({
                    "status": "CLOSED",
                    "pnl": t.realized_pnl or 0.0
                })
        return calculate_performance_metrics(trade_dicts)
    except Exception as e:
        logger.error(f"Metrics Error: {e}")
        return {}
    finally:
        db.close()

async def get_metrics():
    return await asyncio.to_thread(_get_metrics_sync)

# ─────────────────────────────────────────────────────────
# Live Price Fetching
# ─────────────────────────────────────────────────────────
async def fetch_twelvedata_stock_price(symbol: str) -> Optional[float]:
    key = state.twelvedata_api_key
    if not key or "TwelveData" in key or len(key) < 10:
        return None
    try:
        r = await get_http_client().get(
            f"https://api.twelvedata.com/price?symbol={symbol}&apikey={key}",
            timeout=3.0
        )
        if r.status_code == 200:
            data = r.json()
            if "price" in data:
                return float(data["price"])
    except Exception as e:
        logger.error(f"TwelveData error for {symbol}: {e}")
    return None

async def fetch_finnhub_stock_price(symbol: str) -> Optional[float]:
    key = state.finnhub_api_key
    if not key or "Finnhub" in key or len(key) < 10:
        return None
    try:
        r = await get_http_client().get(
            f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={key}",
            timeout=3.0
        )
        if r.status_code == 200:
            price = r.json().get("c", 0.0)
            if price > 0:
                return float(price)
    except Exception as e:
        logger.error(f"Finnhub error for {symbol}: {e}")
    return None

async def fetch_live_binance_price(symbol: str) -> Optional[float]:
    if symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        try:
            r = await get_http_client().get(
                f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
                timeout=2.0
            )
            if r.status_code == 200:
                return float(r.json().get("price", 0))
        except Exception as e:
            logger.error(f"Binance price error for {symbol}: {e}")
    return None

async def fetch_live_stock_price(symbol: str) -> Optional[float]:
    if symbol in ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL"]:
        td_price = await fetch_twelvedata_stock_price(symbol)
        if td_price:
            return td_price
        fh_price = await fetch_finnhub_stock_price(symbol)
        if fh_price:
            return fh_price
        try:
            r = await get_http_client().get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=2.0
            )
            if r.status_code == 200:
                meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                p = float(meta.get("regularMarketPrice", 0))
                return p if p > 0 else None
        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
    return None

async def fetch_actual_market_price(symbol: str) -> Optional[float]:
    price = await fetch_live_binance_price(symbol)
    if price:
        return price
    return await fetch_live_stock_price(symbol)

async def sync_live_binance_balance():
    if state.binance_client:
        try:
            bal = await asyncio.to_thread(state.binance_client.fetch_balance)
            usdt_total = bal.get("USDT", {}).get("total", 0.0)
            usdt_free = bal.get("USDT", {}).get("free", 0.0)
            if usdt_total > 0:
                async with state._state_lock:
                    for b in state.balances:
                        if b["source"] == "BINANCE":
                            b["balance"] = round(usdt_total, 2)
                            b["equity"] = round(usdt_total, 2)
                            b["free_margin"] = round(usdt_free, 2)
        except Exception as e:
            logger.error(f"Binance balance sync error: {e}")

# ─────────────────────────────────────────────────────────
# Alert System
# ─────────────────────────────────────────────────────────
async def check_and_send_alerts(symbol: str, indicators: Dict, prev_price: Optional[float] = None):
    """ตรวจสอบ thresholds และส่ง Telegram alert"""
    if not state.telegram_token or not state.telegram_chat_id:
        return
    if "Telegram" in state.telegram_token:
        return

    rsi = indicators.get("rsi", 50)
    latest = indicators.get("latest", 0)
    now = datetime.now()

    alerts_to_send = []

    # RSI Overbought
    alert_key = f"rsi_ob_{symbol}"
    if rsi > ALERT_CONFIG["rsi_overbought"]:
        last = _last_alerts.get(alert_key)
        if not last or (now - last).total_seconds() > ALERT_COOLDOWN_MINUTES * 60:
            alerts_to_send.append(f"🔴 *RSI Overbought Alert* — {symbol}\nRSI = {rsi} (>{ALERT_CONFIG['rsi_overbought']})\nราคา: {latest}")
            _last_alerts[alert_key] = now

    # RSI Oversold
    alert_key = f"rsi_os_{symbol}"
    if rsi < ALERT_CONFIG["rsi_oversold"]:
        last = _last_alerts.get(alert_key)
        if not last or (now - last).total_seconds() > ALERT_COOLDOWN_MINUTES * 60:
            alerts_to_send.append(f"🟢 *RSI Oversold Alert* — {symbol}\nRSI = {rsi} (<{ALERT_CONFIG['rsi_oversold']})\nราคา: {latest}")
            _last_alerts[alert_key] = now

    # Price Spike
    if prev_price and prev_price > 0:
        change_pct = abs(latest - prev_price) / prev_price * 100
        alert_key = f"spike_{symbol}"
        if change_pct > ALERT_CONFIG["price_spike_pct"]:
            last = _last_alerts.get(alert_key)
            if not last or (now - last).total_seconds() > 5 * 60:  # 5 min cooldown
                direction = "📈" if latest > prev_price else "📉"
                alerts_to_send.append(
                    f"{direction} *Price Spike Alert* — {symbol}\n"
                    f"เปลี่ยนแปลง: {'+' if latest > prev_price else ''}{change_pct:.1f}%\n"
                    f"ราคา: {prev_price} → {latest}"
                )
                _last_alerts[alert_key] = now

    # ส่ง alerts
    for alert_text in alerts_to_send:
        await send_telegram_direct_message(state.telegram_chat_id, alert_text)
        add_journal_entry("alert_sent", alert_text[:80])

# ─────────────────────────────────────────────────────────
# Market Update
# ─────────────────────────────────────────────────────────
async def trigger_market_update(symbol: str = None):
    if symbol:
        async with state._state_lock:
            state.symbol = symbol

    await sync_live_binance_balance()

    prev_price = state.indicators.get("latest") if isinstance(state.indicators, dict) else None
    live_price = await fetch_actual_market_price(state.symbol)

    # Fetch 1h trend for Multi-Timeframe Confirmation
    trend_1h = await fetch_historical_candles_1h(state.symbol)
    if trend_1h:
        async with state._state_lock:
            state.macro_trend_1h = trend_1h

    async with state._state_lock:
        if live_price:
            append_price(state.symbol, live_price)

        state.prices = generate_price_history(state.symbol)

        state.indicators = get_market_indicators(state.prices, state.symbol)
        state.signal = evaluate_strategy_rules(state.indicators, state.symbol, state.macro_trend_1h)
        state.signal_executed = False

        # Dynamic lot size จาก ATR จริง
        pos_size = calculate_position_size(
            state.symbol,
            state.get_total_equity(),
            RISK_CONFIG["maxRiskPerTradePct"],
            state.indicators["atr"]
        )
        lot = pos_size["lot"]
        stop_dist = pos_size["stop_distance"]

        # Override stop distance for BTCUSDT to match user settings
        if state.symbol == "BTCUSDT":
            stop_dist = 300.0

        state.risk = check_trade_risk(
            state.symbol,
            state.signal["action"],
            state.indicators["latest"],
            lot,
            stop_dist,
            1.8,  # spread estimate
            state.circuit_breaker_triggered
        )
        # เก็บ lot size ที่คำนวณ
        state.risk["calculatedLot"] = lot
        state.risk["calculatedStopDist"] = stop_dist

    add_journal_entry("market_snapshot", f"ดึงข้อมูลราคา {state.symbol}: {state.indicators['latest']} (1h Trend: {state.macro_trend_1h})")

    # Check alerts
    await check_and_send_alerts(state.symbol, state.indicators, prev_price)

    await manager.broadcast({
        "type": "market_update",
        "symbol": state.symbol,
        "latest": state.indicators["latest"],
        "indicators": state.indicators,
        "signal": state.signal,
        "risk": state.risk,
        "mode": state.mode
    })

    # Queue debate แทนการ create task โดยตรง
    try:
        _analyze_queue.put_nowait(state.symbol)
    except asyncio.QueueFull:
        logger.warning("Analyze queue full, skipping debate")

# ─────────────────────────────────────────────────────────
# Debate Worker (Queue-based, ไม่มี race condition)
# ─────────────────────────────────────────────────────────
async def debate_worker():
    """ประมวลผล debate ทีละ 1 request จาก queue"""
    logger.info("Debate Worker started")
    while True:
        try:
            symbol = await _analyze_queue.get()

            if state.is_debating:
                _analyze_queue.task_done()
                continue

            state.is_debating = True
            state.active_debate = []

            try:
                # ใช้ Claude ถ้ามี API key, ไม่งั้น template
                has_claude = (
                    bool(state.anthropic_key)
                    and "Anthropic" not in state.anthropic_key
                    and len(state.anthropic_key) > 20
                )

                if has_claude:
                    debate_steps = await generate_thai_debate_async(
                        state.symbol, state.indicators, state.signal, state.risk,
                        state.anthropic_key
                    )
                else:
                    debate_steps = generate_thai_debate(
                        state.symbol, state.indicators, state.signal, state.risk
                    )

                # Telegram initial message
                tg_msg_id = None
                tg_text = ""
                if state.telegram_token and state.telegram_chat_id and "Telegram" not in state.telegram_token:
                    powered = "🤖 Claude AI" if has_claude else "📋 Template"
                    tg_text = f"🏛 <b>[สภา AI เริ่มประชุม]</b> — <b>{state.symbol}</b> ({powered})\n\n"
                    try:
                        r = await get_http_client().post(
                            f"https://api.telegram.org/bot{state.telegram_token}/sendMessage",
                            json={"chat_id": state.telegram_chat_id, "text": tg_text, "parse_mode": "HTML"},
                            timeout=5.0
                        )
                        if r.status_code == 200:
                            tg_msg_id = r.json().get("result", {}).get("message_id")
                    except Exception as e:
                        logger.error(f"Telegram send error: {e}")

                # Stream debate steps
                for i, step in enumerate(debate_steps):
                    state.active_debate.append(step)

                    await manager.broadcast({"type": "agent_typing", "message": step})

                    # อัปเดต Telegram message
                    if tg_msg_id:
                        msg_escaped = (
                            step["message"]
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        tg_text += (
                            f"{step['avatar']} <b>{step['agent']}</b>:\n"
                            f"{msg_escaped}\n\n"
                        )

                        is_last = (i == len(debate_steps) - 1)
                        payload = {
                            "chat_id": state.telegram_chat_id,
                            "message_id": tg_msg_id,
                            "text": tg_text,
                            "parse_mode": "HTML"
                        }

                        # ปุ่ม Approve/Reject สำหรับ step สุดท้าย
                        if is_last:
                            action = state.signal["action"]
                            passed = state.risk.get("passed", False)
                            if passed and action in ["BUY", "SELL"]:
                                payload["reply_markup"] = {
                                    "inline_keyboard": [[
                                        {"text": "✅ อนุมัติเทรด", "callback_data": f"approve_{state.symbol}"},
                                        {"text": "❌ ปฏิเสธ", "callback_data": f"reject_{state.symbol}"}
                                    ]]
                                }

                        try:
                            await get_http_client().post(
                                f"https://api.telegram.org/bot{state.telegram_token}/editMessageText",
                                json=payload, timeout=5.0
                            )
                        except Exception as e:
                            logger.error(f"Telegram edit error: {e}")

                    await asyncio.sleep(random.uniform(0.5, 1.0))

                # Auto execute (Auto 100% - even in watch mode it executes automatically)
                if state.risk.get("passed") and state.signal["action"] in ["BUY", "SELL"]:
                    logger.info(f"[Auto Execution] Risk passed — executing trade automatically (Mode: {state.mode.upper()})...")
                    await manager.broadcast({"type": "agent_typing", "message": {"agent": "system", "message": f"🤖 [AUTO EXECUTE] ระบบอนุมัติออโต้อัตโนมัติ (ในโหมด {state.mode.upper()})! กำลังส่งคำสั่งไปที่ EA...", "avatar": "⚡"}})
                    await asyncio.sleep(1.0)
                    await execute_mock_trade()

            finally:
                state.is_debating = False
                _analyze_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Debate Worker error: {e}")
            state.is_debating = False
            await asyncio.sleep(1)

# ─────────────────────────────────────────────────────────
# Trade Execution
# ─────────────────────────────────────────────────────────
async def execute_mock_trade():
    async with state._state_lock:
        if state.signal_executed:
            logger.info("Trade already executed, skipping")
            return
        state.signal_executed = True

    action = state.signal["action"]
    entry_price = state.indicators.get("latest", 2342.0) if isinstance(state.indicators, dict) else 2342.0

    trade_id = f"ord_{int(datetime.now().timestamp() * 1000)}"

    # Dynamic lot size
    lot = state.risk.get("calculatedLot", 0.1)
    stop_dist = state.risk.get("calculatedStopDist", 15.0)

    # Save to DB (via thread)
    def _save_trade():
        db = SessionLocal()
        try:
            trade = Trade(
                id=trade_id,
                ticker=state.symbol,
                action=TradeAction[action],
                status=TradeStatus.OPEN,
                lot_size=lot,
                entry_price=entry_price,
                stop_loss=round(entry_price - stop_dist, 2) if action == "BUY" else round(entry_price + stop_dist, 2),
                take_profit=round(entry_price + stop_dist * 2, 2) if action == "BUY" else round(entry_price - stop_dist * 2, 2)
            )
            db.add(trade)
            db.commit()
            logger.info(f"Saved trade {trade_id} to DB")
        except Exception as e:
            logger.error(f"DB save error: {e}")
        finally:
            db.close()

    await asyncio.to_thread(_save_trade)

    # Webhook to ERP
    try:
        await get_http_client().post(
            "http://localhost:5001/webhook/trade-event",
            json={"event": "trade.opened", "data": {
                "symbol": state.symbol, "action": action,
                "price": entry_price, "volume": lot
            }},
            timeout=2.0
        )
    except Exception as e:
        logger.error(f"ERP webhook error: {e}")

    add_journal_entry("trade_order.paper_created", f"คำสั่ง {action} {state.symbol} @ {entry_price} (lot={lot})")

    orders = await get_orders_from_db()
    current_order = next((o for o in orders if o["id"] == trade_id), {
        "id": trade_id, "symbol": state.symbol, "action": action,
        "volume": lot, "entry_price": entry_price,
        "exit_price": 0.0, "pnl": 0.0, "fee": 2.50, "status": "OPEN"
    })

    await manager.broadcast({"type": "order_opened", "order": current_order, "balances": state.balances})
    # Legacy simulated close removed - open_trades_monitor will manage closing based on actual SL/TP
    # asyncio.create_task(simulate_order_close(trade_id, action, entry_price, lot))

async def simulate_order_close(trade_id: str, action: str, entry_price: float, volume: float):
    await asyncio.sleep(5.0)

    spec = SYMBOLS.get(state.symbol, SYMBOLS["XAUUSD"])
    win = random.random() > 0.4
    multiplier = 1.0 if win else -0.8
    pnl = round(volume * spec["volatility"] * multiplier * 2.0 * 100, 2)
    fee = round(2.50 + random.random() * 2.0, 2)
    exit_price = round(entry_price + (pnl / (volume * 100 * spec["tickValue"])), spec["decimals"])

    def _close_trade():
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                trade.status = TradeStatus.CLOSED
                trade.exit_price = exit_price
                trade.realized_pnl = pnl
                trade.closed_at = datetime.utcnow()
                db.commit()
        except Exception as e:
            logger.error(f"DB close error: {e}")
        finally:
            db.close()

    await asyncio.to_thread(_close_trade)

    broker = "BINANCE" if state.symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"] else "MT5"
    async with state._state_lock:
        for bal in state.balances:
            if bal["source"] == broker:
                bal["balance"] = round(bal["balance"] + pnl - fee, 2)
                bal["equity"] = bal["balance"]

    add_journal_entry("trade_closed", f"ปิดออเดอร์ {state.symbol} PnL: {'+' if pnl >= 0 else ''}${pnl}")

    try:
        await get_http_client().post(
            "http://localhost:5001/webhook/trade-event",
            json={"event": "trade.pnl_realized", "data": {
                "symbol": state.symbol, "pnl": pnl, "fee": fee
            }},
            timeout=2.0
        )
    except Exception as e:
        logger.error(f"ERP close webhook error: {e}")

    orders = await get_orders_from_db()
    await manager.broadcast({
        "type": "order_closed",
        "order_id": trade_id,
        "orders": orders,
        "balances": state.balances
    })

# ─────────────────────────────────────────────────────────
# Telegram Bot
# ─────────────────────────────────────────────────────────
async def send_telegram_direct_message(chat_id: str, text: str, parse_mode: str = "Markdown"):
    if not state.telegram_token:
        return
    try:
        await get_http_client().post(
            f"https://api.telegram.org/bot{state.telegram_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=5.0
        )
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

async def get_claude_chat_response(message: str) -> str:
    key = state.anthropic_key
    if not key or "Anthropic" in key or len(key) < 20:
        return (
            "🤖 [CEO Agent]: ยังไม่ได้เชื่อมต่อ Anthropic API Key ครับ "
            "กรุณาตั้งค่าใน Settings เพื่อสนทนากับ Claude!"
        )
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        total_equity = state.get_total_equity()
        indicators = state.indicators if isinstance(state.indicators, dict) else {}

        system_prompt = (
            f"คุณคือ CEO Agent (JARVIS-CEO) หัวหน้าทีม AI Trading Virtual Office "
            f"ตอบภาษาไทยอย่างสุภาพ กระชับ มืออาชีพ เน้นการวิเคราะห์ตลาดและพอร์ตลงทุน\n"
            f"ข้อมูลพอร์ตปัจจุบัน:\n"
            f"- สินทรัพย์: {state.symbol}\n"
            f"- ราคา: {indicators.get('latest', 'N/A')}\n"
            f"- เทรนด์: {indicators.get('trend', 'N/A')}\n"
            f"- RSI: {indicators.get('rsi', 'N/A')}\n"
            f"- ATR: {indicators.get('atr', 'N/A')}\n"
            f"- สัญญาณ: {state.signal.get('action', 'N/A')} (conf: {state.signal.get('confidence', 0):.0%})\n"
            f"- Risk: {'✅ ผ่าน' if state.risk.get('passed') else '❌ ระงับ'}\n"
            f"- Net Worth: ${total_equity:,.2f}"
        )

        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude chat error: {e}")
        return f"🤖 [CEO Agent]: Claude API ขัดข้องชั่วคราว: {str(e)[:100]}"

async def get_claude_chat_response_streaming(message: str, ws_broadcast_fn):
    """Claude streaming chat — ส่ง chunks ผ่าน WebSocket"""
    key = state.anthropic_key
    if not key or "Anthropic" in key or len(key) < 20:
        await ws_broadcast_fn({"type": "chat_chunk", "text": "ยังไม่ได้ตั้งค่า Anthropic API Key ครับ", "done": True})
        return

    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        total_equity = state.get_total_equity()
        indicators = state.indicators if isinstance(state.indicators, dict) else {}

        system_prompt = (
            f"คุณคือ CEO Agent ตอบภาษาไทย กระชับ มืออาชีพ\n"
            f"สินทรัพย์: {state.symbol}, ราคา: {indicators.get('latest', 'N/A')}, "
            f"เทรนด์: {indicators.get('trend', 'N/A')}, RSI: {indicators.get('rsi', 'N/A')}, "
            f"Net Worth: ${total_equity:,.2f}"
        )

        full_text = ""
        async with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        ) as stream:
            async for text_chunk in stream.text_stream:
                full_text += text_chunk
                await ws_broadcast_fn({"type": "chat_chunk", "text": text_chunk, "done": False})

        await ws_broadcast_fn({"type": "chat_chunk", "text": "", "done": True, "full_text": full_text})

        if state.telegram_token and state.telegram_chat_id and "Telegram" not in state.telegram_token:
            try:
                user_text = f"👤 <b>[คำถามของคุณบน Dashboard]</b>:\n{message}"
                await send_telegram_direct_message(state.telegram_chat_id, user_text, parse_mode="HTML")
                
                ceo_text = f"💼 <b>[CEO Agent ตอบบน Dashboard]</b>:\n{full_text}"
                await send_telegram_direct_message(state.telegram_chat_id, ceo_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error sending stream chat copy to Telegram: {e}")

    except Exception as e:
        logger.error(f"Claude streaming error: {e}")
        await ws_broadcast_fn({"type": "chat_chunk", "text": f"Claude API error: {str(e)[:80]}", "done": True})

# ─────────────────────────────────────────────────────────
# Telegram Command Handler
# ─────────────────────────────────────────────────────────
async def handle_telegram_command_logic(cmd: str, user_tag: str) -> str:
    if cmd.startswith("/analyze"):
        parts = cmd.split()
        target_symbol = state.symbol
        if len(parts) > 1:
            sym_input = parts[1].upper()
            if sym_input in SYMBOLS:
                target_symbol = sym_input
            else:
                return f"❌ ไม่รู้จักสินทรัพย์ {sym_input}"
        asyncio.create_task(trigger_market_update(target_symbol))
        return f"🤖 กำลังวิเคราะห์ {target_symbol}... ติดตามผลบน Dashboard!"

    elif cmd.startswith("/price"):
        parts = cmd.split()
        sym = parts[1].upper() if len(parts) > 1 and parts[1].upper() in SYMBOLS else state.symbol
        live_price = await fetch_actual_market_price(sym)
        price_val = live_price or SYMBOLS[sym]["base"]
        indicators = get_market_indicators(generate_price_history(sym), sym)
        rsi = indicators.get("rsi", 50)
        trend = indicators.get("trend", "N/A")
        return f"📊 *[ราคาล่าสุด]* — {sym}\nราคา: *{price_val}*\nเทรนด์: {trend} | RSI: {rsi}"

    elif cmd.startswith("/wallet"):
        total_val = state.get_total_equity()
        bal_str = "\n".join([f"- *{b['source']}*: ${b['equity']:,.2f}" for b in state.balances])
        return f"💼 *[Net Worth Report]*\n{bal_str}\n\n💰 *รวม*: `${total_val:,.2f}`"

    elif cmd.startswith("/report"):
        orders = await get_orders_from_db()
        closed = [o for o in orders if o["status"] == "CLOSED"]
        total_pnl = sum(o["pnl"] for o in closed)
        total_fee = sum(o["fee"] for o in closed)
        win = len([o for o in closed if o["pnl"] > 0])
        wr = (win / len(closed) * 100) if closed else 0
        return (
            f"📋 *[Performance Report]*\n"
            f"- ดีลที่ปิด: *{len(closed)}*\n"
            f"- Win Rate: *{wr:.1f}%*\n"
            f"- Net PnL: *${total_pnl:+.2f}*\n"
            f"- ค่าธรรมเนียม: *${total_fee:.2f}*\n"
            f"- Net หลังหักค่าธรรมเนียม: *${total_pnl - total_fee:+.2f}*"
        )

    elif cmd.startswith("/risk"):
        passed_text = "ผ่าน ✅" if state.risk.get("passed") else "ระงับ 🔴"
        lot = state.risk.get("calculatedLot", 0.1)
        return (
            f"🛡️ *[Risk Status]*\n"
            f"สถานะ: *{passed_text}*\n"
            f"ความเสี่ยง/ไม้: {state.risk.get('riskPct', 0):.2f}%\n"
            f"Exposure: {state.risk.get('exposurePct', 0):.2f}%\n"
            f"Lot ที่แนะนำ (ATR-based): {lot}"
        )

    elif cmd.startswith("/alerts"):
        thresholds = ", ".join([f"{k}={v}" for k, v in ALERT_CONFIG.items()])
        return f"🚨 *[Alert Config]*\n{thresholds}\n\nระบบ Alert ทำงานปกติ ✅"

    elif cmd.startswith("/mode"):
        parts = cmd.split()
        if len(parts) > 1 and parts[1] in ["auto", "watch"]:
            async with state._state_lock:
                state.mode = parts[1]
            return f"⚙️ สลับโหมดเป็น *{state.mode.upper()}* เรียบร้อย"
        return f"⚙️ โหมดปัจจุบัน: *{state.mode.upper()}*\nใช้ `/mode auto` หรือ `/mode watch`"

    elif cmd.startswith("/reset_breaker"):
        if state.circuit_breaker_triggered:
            async with state._state_lock:
                state.circuit_breaker_triggered = False
                state.daily_realized_pnl = 0.0
            add_journal_entry("breaker_reset", "ปลดล็อกระบบ Circuit Breaker และรีเซ็ต PnL รายวันผ่าน Telegram")
            return "✅ *[Circuit Breaker Reset]*: ปลดล็อกระบบและรีเซ็ตประวัติขาดทุนรายวันเรียบร้อย บอทพร้อมเทรดอีกครั้ง!"
        else:
            return "ℹ️ ระบบความปลอดภัยปกติ ไม่ได้เปิดทำงาน Circuit Breaker อยู่"

    elif cmd.startswith("/pause"):
        add_journal_entry("system_pause", "ระงับระบบผ่าน Telegram")
        return "⏸️ ระงับระบบ Virtual Office ชั่วคราว"

    elif cmd.startswith("/close_all") or cmd.startswith("/close all"):
        def _close_all():
            db = SessionLocal()
            try:
                db.query(Trade).filter(Trade.status == TradeStatus.OPEN).update(
                    {Trade.status: TradeStatus.CLOSED}
                )
                db.commit()
            except Exception as e:
                logger.error(f"Close all error: {e}")
            finally:
                db.close()
        await asyncio.to_thread(_close_all)
        add_journal_entry("orders_cleared", "ล้างออเดอร์ทั้งหมดผ่าน Telegram")
        return "🧹 ปิดและเคลียร์ออเดอร์ทั้งหมดเรียบร้อย"

    else:
        return (
            "💬 *คำสั่งที่รองรับ:*\n"
            "- `/price [Symbol]` ราคาล่าสุด\n"
            "- `/analyze [Symbol]` วิเคราะห์ AI\n"
            "- `/wallet` Net Worth\n"
            "- `/report` Performance\n"
            "- `/risk` ความเสี่ยง\n"
            "- `/alerts` ตั้งค่า Alert\n"
            "- `/mode [auto/watch]` โหมดเทรด\n"
            "- `/close_all` ปิดออเดอร์ทั้งหมด\n"
            "- `/reset_breaker` ปลดล็อกเบรกเกอร์ขาดทุนสะสมรายวัน"
        )

# ─────────────────────────────────────────────────────────
# Telegram Poller
# ─────────────────────────────────────────────────────────
async def telegram_bot_poller():
    logger.info("Telegram Poller started")
    while True:
        token = state.telegram_token
        if not token or "Telegram" in token or len(token) < 20:
            await asyncio.sleep(4)
            continue
        try:
            r = await get_http_client().get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": state.last_update_id + 1, "timeout": 3},
                timeout=6.0
            )
            if r.status_code == 200:
                res = r.json()
                if res.get("ok"):
                    for upd in res.get("result", []):
                        state.last_update_id = max(state.last_update_id, upd["update_id"])
                        await handle_real_telegram_update(upd)
        except httpx.TimeoutException:
            logger.warning("[Telegram] Poller timeout — retrying")
        except httpx.NetworkError as e:
            logger.warning(f"[Telegram] Network error: {e}")
        except Exception as e:
            logger.error(f"Telegram poller error: {type(e).__name__}: {e}")
        await asyncio.sleep(2.0)

async def handle_real_telegram_update(upd: Dict[str, Any]):
    if "message" in upd:
        msg = upd["message"]
        chat_id = str(msg["chat"]["id"])
        state.telegram_chat_id = chat_id
        text = msg.get("text", "").strip()
        if not text:
            return

        logger.info(f"[Telegram] Received: {text[:50]}")

        await manager.broadcast({
            "type": "agent_typing",
            "message": {
                "agent": "user",
                "role": "ผู้บัญชาการพอร์ต",
                "avatar": "👤",
                "message": f"Telegram: {text}",
                "timestamp": datetime.now().isoformat()
            }
        })

        if text.startswith("/"):
            response_text = await handle_telegram_command_logic(text, f"TG_{chat_id[:6]}")
        else:
            response_text = await get_claude_chat_response(text)

        await send_telegram_direct_message(chat_id, response_text)

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

    elif "callback_query" in upd:
        cb = upd["callback_query"]
        cb_id = cb["id"]
        chat_id = str(cb["message"]["chat"]["id"])
        cb_data = cb.get("data", "")

        if cb_data.startswith("approve_"):
            if state.signal_executed:
                reply_text = "ℹ️ ออเดอร์นี้ได้รับการอนุมัติอัตโนมัติไปแล้ว"
            elif state.risk.get("passed"):
                await execute_mock_trade()
                reply_text = "🟢 อนุมัติสำเร็จ! เปิดออเดอร์และบันทึก ERP แล้ว"
            else:
                reply_text = "❌ ความเสี่ยงไม่ผ่านเกณฑ์ ไม่สามารถเทรดได้"
        elif cb_data.startswith("reject_"):
            if state.signal_executed:
                reply_text = "ℹ️ ออเดอร์นี้ได้รับการอนุมัติและเทรดไปแล้ว"
            else:
                add_journal_entry("trade_rejected", "ปฏิเสธแผนเทรดผ่าน Telegram")
                reply_text = "🔴 ยกเลิกแผนเทรดเรียบร้อย"
        else:
            reply_text = "ไม่ทราบรายการ"

        try:
            await get_http_client().post(
                f"https://api.telegram.org/bot{state.telegram_token}/answerCallbackQuery",
                json={"callback_query_id": cb_id, "text": reply_text}
            )
        except Exception as e:
            logger.error(f"Telegram callback error: {e}")

# ─────────────────────────────────────────────────────────
# Telegram Periodic Summary Reporter (runs every 5 minutes)
# ─────────────────────────────────────────────────────────
async def telegram_periodic_reporter():
    logger.info("Telegram Periodic Reporter started")
    while True:
        await asyncio.sleep(300)  # Report every 5 minutes
        if not state.telegram_token or not state.telegram_chat_id or "Telegram" in state.telegram_token:
            continue
        try:
            total_val = state.get_total_equity()
            bal_str = "\n".join([f"- *{b['source']}*: ${b['equity']:,.2f}" for b in state.balances])
            
            orders = await get_orders_from_db()
            closed = [o for o in orders if o["status"] == "CLOSED"]
            total_pnl = sum(o["pnl"] for o in closed)
            total_fee = sum(o["fee"] for o in closed)
            win = len([o for o in closed if o["pnl"] > 0])
            wr = (win / len(closed) * 100) if closed else 0
            
            report_text = (
                f"📋 *[รายงานสรุปสถานะพอร์ตอัตโนมัติ]*\n\n"
                f"💰 *มูลค่าพอร์ตรวม*: `${total_val:,.2f}`\n"
                f"{bal_str}\n\n"
                f"📈 *สถิติการเทรดล่าสุด*:\n"
                f"- ออเดอร์ที่ปิดแล้ว: *{len(closed)}* ดีล\n"
                f"- Win Rate: *{wr:.1f}%*\n"
                f"- กำไรสุทธิ (Net PnL): *${total_pnl:+.2f}*\n"
                f"- ค่าธรรมเนียมสะสม: *${total_fee:.2f}*\n\n"
                f"⚙️ *การตั้งค่าระบบ*: ทำงานปกติ | โหมด: *{state.mode.upper()}* (Auto 100% Active ✅)"
            )
            await send_telegram_direct_message(state.telegram_chat_id, report_text)
            logger.info("Sent periodic summary to Telegram")
        except Exception as e:
            logger.error(f"Error sending periodic Telegram report: {e}")

# ─────────────────────────────────────────────────────────
# Real-time Price Event Listener (Subscribes to CH_MARKET_DATA)
# ─────────────────────────────────────────────────────────
async def realtime_price_listener():
    logger.info("Real-time Price Signal Listener started")
    async for msg in event_bus.subscribe(CH_MARKET_DATA):
        if not isinstance(msg, dict):
            continue
        ticker = msg.get("ticker", "").upper()
        price = msg.get("price")
        if not ticker or price is None:
            continue
            
        active_symbol = state.symbol
        norm_ticker = ticker.replace("/", "").replace("-", "")
        norm_active = active_symbol.replace("/", "").replace("-", "")
        
        if norm_ticker == norm_active:
            new_price = float(price)
            prev_price = state.indicators.get("latest") if isinstance(state.indicators, dict) else None
            
            async with state._state_lock:
                append_price(active_symbol, new_price)
                state.prices = generate_price_history(active_symbol)
                state.indicators = get_market_indicators(state.prices, active_symbol)
                state.signal = evaluate_strategy_rules(state.indicators, active_symbol, state.macro_trend_1h)
                
                if state.signal["action"] == "HOLD":
                    state.signal_executed = False

                pos_size = calculate_position_size(
                    active_symbol,
                    state.get_total_equity(),
                    RISK_CONFIG["maxRiskPerTradePct"],
                    state.indicators["atr"]
                )
                
                lot = pos_size["lot"]
                stop_dist = pos_size["stop_distance"]
                if active_symbol == "BTCUSDT":
                    stop_dist = 300.0
                    
                state.risk = check_trade_risk(
                    active_symbol,
                    state.signal["action"],
                    state.indicators["latest"],
                    lot,
                    stop_dist,
                    1.8,
                    state.circuit_breaker_triggered
                )
                state.risk["calculatedLot"] = lot
                state.risk["calculatedStopDist"] = stop_dist

            # Broadcast real-time update to UI
            await manager.broadcast({
                "type": "price_tick",
                "symbol": active_symbol,
                "price": new_price,
                "indicators": state.indicators,
                "signal": state.signal,
                "risk": state.risk
            })

            # Check alerts
            await check_and_send_alerts(active_symbol, state.indicators, prev_price)

            # Instantly trigger debate and auto-execution on a new trading signal (BUY/SELL)
            if state.signal["action"] in ["BUY", "SELL"] and not state.signal_executed and not state.is_debating:
                try:
                    _analyze_queue.put_nowait(active_symbol)
                    logger.info(f"⚡ [REAL-TIME SIGNAL TRIGGER] Instantly triggered debate and trade for {active_symbol} due to signal: {state.signal['action']} @ {new_price}")
                except asyncio.QueueFull:
                    pass

# ─────────────────────────────────────────────────────────
# Helper: Fetch 1h trend
# ─────────────────────────────────────────────────────────
async def fetch_historical_candles_1h(symbol: str) -> Optional[str]:
    """ดึงแนวโน้มหลัก 1 ชั่วโมง เพื่อคำนวณ EMA(12) และ EMA(26) ยืนยันทิศทาง"""
    yf_symbol = symbol
    if symbol == "BTCUSDT":
        yf_symbol = "BTC-USD"
    elif symbol == "ETHUSDT":
        yf_symbol = "ETH-USD"
    elif symbol == "SOLUSDT":
        yf_symbol = "SOL-USD"
    elif symbol == "XAUUSD":
        yf_symbol = "GC=F"
    elif symbol == "EURUSD":
        yf_symbol = "EURUSD=X"

    try:
        r = await get_http_client().get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}?interval=1h&range=5d",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3.0
        )
        if r.status_code == 200:
            result = r.json().get("chart", {}).get("result", [{}])[0]
            indicators = result.get("indicators", {}).get("quote", [{}])[0]
            close_prices = indicators.get("close", [])
            close_prices = [float(c) for c in close_prices if c is not None]
            if len(close_prices) >= 26:
                s = pd.Series(close_prices)
                ema12 = s.ewm(span=12, adjust=False).mean().iloc[-1]
                ema26 = s.ewm(span=26, adjust=False).mean().iloc[-1]
                if ema12 > ema26 * 1.0005:
                    return "Bullish"
                elif ema12 < ema26 * 0.9995:
                    return "Bearish"
                else:
                    return "Sideways"
    except Exception as e:
        logger.error(f"Error fetching 1h trend for {symbol}: {e}")
    return None

def _get_orders_from_db_sync_by_db(db):
    orders = []
    try:
        trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(30).all()
        for t in trades:
            orders.append({
                "id": t.id,
                "symbol": t.ticker,
                "action": t.action.name if t.action else "BUY",
                "volume": t.lot_size or 0.1,
                "entry_price": t.entry_price or 0.0,
                "exit_price": t.exit_price or 0.0,
                "pnl": t.realized_pnl or 0.0,
                "fee": 2.50,
                "status": t.status.name if t.status else "OPEN"
            })
    except Exception as e:
        logger.error(f"DB Query Error in monitor sync: {e}")
    return orders

# ─────────────────────────────────────────────────────────
# Open Trades Monitor Task
# ─────────────────────────────────────────────────────────
async def open_trades_monitor():
    """คอยตรวจสอบและบริหารจัดการออเดอร์ที่เปิดค้างอยู่แบบเรียลไทม์ (Trailing Stop / Break-Even / Partial Close)"""
    logger.info("Open Trades Monitor task started")
    while True:
        await asyncio.sleep(2.0)  # Check every 2 seconds to be resource-friendly
        try:
            db = SessionLocal()
            open_trades = db.query(Trade).filter(Trade.status == TradeStatus.OPEN).all()
            if not open_trades:
                db.close()
                continue
                
            spec = SYMBOLS.get(state.symbol, SYMBOLS["XAUUSD"])
            current_price = state.indicators.get("latest", spec["base"]) if isinstance(state.indicators, dict) else spec["base"]
            
            for trade in open_trades:
                diff = current_price - trade.entry_price if trade.action == TradeAction.BUY else trade.entry_price - current_price
                floating_pnl = round(diff * trade.lot_size * 100 * spec["tickValue"], 2)
                
                # 1. Break-Even Logic (+150$ Target)
                has_moved_to_be = False
                if trade.action == TradeAction.BUY:
                    has_moved_to_be = bool(trade.stop_loss >= trade.entry_price)
                else:
                    has_moved_to_be = bool(trade.stop_loss <= trade.entry_price)
                    
                if floating_pnl >= 150.0 and not has_moved_to_be:
                    tick_size = 1.0 / (10 ** spec["decimals"]) if spec["decimals"] > 0 else 1.0
                    be_offset = 10 * tick_size
                    new_sl = round(trade.entry_price + be_offset if trade.action == TradeAction.BUY else trade.entry_price - be_offset, spec["decimals"])
                    
                    trade.stop_loss = new_sl
                    db.commit()
                    
                    alert_text = (
                        f"🛡️ *[Break-Even Activated]* — {trade.ticker}\n"
                        f"ออเดอร์ `{trade.id}` ทำกำไรถึง *$150.00* ล่าสุด\n"
                        f"ระบบทำการขยับ Stop Loss บังหน้าทุนไปที่ *{new_sl}* เรียบร้อยเพื่อล็อกกำไรขั้นต่ำ! 🔒"
                    )
                    await send_telegram_direct_message(state.telegram_chat_id, alert_text)
                    add_journal_entry("trade_be_activated", f"ออเดอร์ {trade.id} เปิดใช้งาน Break-Even SL @ {new_sl}")
                    
                # 2. Check Partial Take Profit (Close 50% at +$100 profit)
                if trade.id not in state.partially_closed_trades and floating_pnl >= 100.0:
                    state.partially_closed_trades.add(trade.id)
                    half_lot = round(trade.lot_size / 2, 2)
                    realized_pnl = round(floating_pnl / 2, 2)
                    fee = round(1.25 + random.random() * 1.0, 2)
                    
                    # Update lot size in DB
                    trade.lot_size = half_lot
                    db.commit()
                    
                    try:
                        await get_http_client().post(
                            "http://localhost:5001/webhook/trade-event",
                            json={"event": "trade.pnl_realized", "data": {
                                "symbol": trade.ticker, "action": trade.action.name,
                                "pnl": realized_pnl, "fee": fee
                            }},
                            timeout=2.0
                        )
                    except Exception as e:
                        logger.error(f"ERP webhook partial close error: {e}")
                        
                    alert_text = (
                        f"💰 *[Partial Take Profit]* — {trade.ticker}\n"
                        f"ออเดอร์ `{trade.id}` ทำกำไรถึงเป้าแรก +$100.00!\n"
                        f"ปิดทำกำไรสะสมแล้วครึ่งหนึ่ง (50% Close) *+${realized_pnl}* (เหลือสัญญาเปิด Lot: {half_lot}) 💵"
                    )
                    await send_telegram_direct_message(state.telegram_chat_id, alert_text)
                    add_journal_entry("trade_partial_close", f"ออเดอร์ {trade.id} ปิดสัญญาแบ่งกำไรครึ่งหนึ่ง (Lot: {half_lot})")
                    
                # 3. Check SL / TP Hits
                is_sl_hit = False
                is_tp_hit = False
                if trade.action == TradeAction.BUY:
                    if current_price <= trade.stop_loss:
                        is_sl_hit = True
                    elif current_price >= trade.take_profit:
                        is_tp_hit = True
                else: # SELL
                    if current_price >= trade.stop_loss:
                        is_sl_hit = True
                    elif current_price <= trade.take_profit:
                        is_tp_hit = True
                        
                if is_sl_hit or is_tp_hit:
                    final_diff = current_price - trade.entry_price if trade.action == TradeAction.BUY else trade.entry_price - current_price
                    final_pnl = round(final_diff * trade.lot_size * 100 * spec["tickValue"], 2)
                    fee = round(2.50 + random.random() * 2.0, 2)
                    
                    # Close in DB
                    trade.status = TradeStatus.CLOSED
                    trade.exit_price = current_price
                    trade.realized_pnl = final_pnl
                    trade.closed_at = datetime.utcnow()
                    db.commit()
                    
                    # Update daily realized PnL for Circuit Breaker
                    state.daily_realized_pnl = round(state.daily_realized_pnl + final_pnl, 2)
                    
                    # Webhook to ERP
                    try:
                        await get_http_client().post(
                            "http://localhost:5001/webhook/trade-event",
                            json={"event": "trade.pnl_realized", "data": {
                                "symbol": trade.ticker, "action": trade.action.name,
                                "pnl": final_pnl, "fee": fee
                            }},
                            timeout=2.0
                        )
                    except Exception as e:
                        logger.error(f"ERP webhook close error: {e}")
                        
                    hit_type = "🔴 *[Stop Loss Hit]*" if is_sl_hit else "🟢 *[Take Profit Hit]*"
                    alert_text = (
                        f"{hit_type} — {trade.ticker}\n"
                        f"ออเดอร์ `{trade.id}` ถูกปิดสัญญาที่ราคา *{current_price}*\n"
                        f"ผลลัพธ์: *{'+$' if final_pnl >= 0 else '-$'}{abs(final_pnl):,.2f}* PnL | ค่าธรรมเนียม: ${fee:.2f}"
                    )
                    await send_telegram_direct_message(state.telegram_chat_id, alert_text)
                    add_journal_entry("trade_closed", f"ออเดอร์ {trade.id} ปิดสัญญาที่ราคา {current_price} (PnL: {final_pnl})")
                    
                    # Clean up
                    state.partially_closed_trades.discard(trade.id)
                    
                    # Broadcast
                    orders_data = _get_orders_from_db_sync_by_db(db)
                    await manager.broadcast({"type": "order_closed", "order": next((o for o in orders_data if o["id"] == trade.id), {}), "balances": state.balances})
                    
                    # Check Circuit Breaker trigger! (Daily loss limit 3.0% of equity)
                    daily_loss_limit = - (state.get_total_equity() * RISK_CONFIG["maxDailyLossPct"] / 100)
                    if state.daily_realized_pnl <= daily_loss_limit and not state.circuit_breaker_triggered:
                        state.circuit_breaker_triggered = True
                        state.mode = "watch"
                        breaker_alert = (
                            f"🚨🚨 *[CIRCUIT BREAKER TRIGGERED]* 🚨🚨\n\n"
                            f"ยอดขาดทุนสะสมรายวัน (*${state.daily_realized_pnl}*) สูงเกินเกณฑ์ควบคุมความปลอดภัยสูงสุด "
                            f"(*${daily_loss_limit:.2f}* หรือ {RISK_CONFIG['maxDailyLossPct']}% ของพอร์ต)\n\n"
                            f"⚙️ *ระบบสั่งการฉุกเฉิน*:\n"
                            f"1. สับสวิตช์ปรับเข้าสู่โหมดเฝ้าระวัง *WATCH* เรียบร้อย\n"
                            f"2. สั่งระงับเปิดคำสั่งเทรดใหม่ทุกเหรียญถาวรชั่วคราว\n\n"
                            f"คุณสามารถพิมพ์คำสั่ง `/reset_breaker` ใน Telegram เพื่อตรวจสอบและทำการปลดล็อกระบบเบรกเกอร์ได้ด้วยตนเอง"
                        )
                        await send_telegram_direct_message(state.telegram_chat_id, breaker_alert)
                        add_journal_entry("circuit_breaker_triggered", f"ระบบความปลอดภัยหยุดบอทฉุกเฉินสะสมขาดทุน {state.daily_realized_pnl}")
            db.close()
        except Exception as e:
            logger.error(f"Error in open_trades_monitor: {e}")

# ─────────────────────────────────────────────────────────
# WebSocket Bridge (Redis → WS)
# ─────────────────────────────────────────────────────────
async def websocket_bridge():
    channels = [
        CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS,
        CH_AI_JOURNAL, CH_RISK_APPROVED, CH_RISK_REJECTED,
        CH_EXEC_OPENED, CH_PORTFOLIO_UPDATED, CH_NEWS
    ]
    async def bridge_channel(channel):
        async for msg in event_bus.subscribe(channel):
            await manager.broadcast({"type": channel, "data": msg})
    for ch in channels:
        asyncio.create_task(bridge_channel(ch))

# ─────────────────────────────────────────────────────────
# FastAPI Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client

    # Singleton HTTP Client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, connect=2.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )
    logger.info("HTTP Client (Singleton) initialized")

    # Database
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")

    # Start Engines
    logger.info("Starting AI Trading Engines...")
    start_market_data_engine(event_bus)
    start_news_intelligence_engine(event_bus)
    start_market_regime_engine(event_bus)
    start_strategy_engine(event_bus)
    start_risk_engine(event_bus)
    start_execution_engine(event_bus)
    start_portfolio_engine(event_bus)

    # WebSocket Bridge
    asyncio.create_task(websocket_bridge())

    # Initial Market Update
    await trigger_market_update()

    # Debate Worker
    asyncio.create_task(debate_worker())

    # Telegram Poller
    asyncio.create_task(telegram_bot_poller())

    # Telegram Periodic Reporter
    asyncio.create_task(telegram_periodic_reporter())

    # Real-time Price Listener
    asyncio.create_task(realtime_price_listener())

    # Open Trades Monitor
    asyncio.create_task(open_trades_monitor())

    # Price ticker (15s interval)
    async def price_ticker_sim():
        while True:
            await asyncio.sleep(60)
            spec = SYMBOLS.get(state.symbol, SYMBOLS["XAUUSD"])
            live_price = await fetch_actual_market_price(state.symbol)

            # Update 1h trend periodically
            trend_1h = await fetch_historical_candles_1h(state.symbol)
            if trend_1h:
                async with state._state_lock:
                    state.macro_trend_1h = trend_1h

            async with state._state_lock:
                if live_price:
                    new_price = live_price
                else:
                    current = state.indicators.get("latest", spec["base"]) if isinstance(state.indicators, dict) else spec["base"]
                    change = (random.random() - 0.5) * spec["volatility"] * 0.4
                    new_price = round(current + change, spec["decimals"])
                    new_price = max(new_price, spec["volatility"])

                # Update continuous price store
                append_price(state.symbol, new_price)
                state.prices = generate_price_history(state.symbol)
                state.indicators = get_market_indicators(state.prices, state.symbol)
                state.signal = evaluate_strategy_rules(state.indicators, state.symbol, state.macro_trend_1h)
                
                if state.signal["action"] == "HOLD":
                    state.signal_executed = False

                pos_size = calculate_position_size(
                    state.symbol,
                    state.get_total_equity(),
                    RISK_CONFIG["maxRiskPerTradePct"],
                    state.indicators["atr"]
                )
                
                lot = pos_size["lot"]
                stop_dist = pos_size["stop_distance"]
                if state.symbol == "BTCUSDT":
                    stop_dist = 300.0
                    
                state.risk = check_trade_risk(
                    state.symbol,
                    state.signal["action"],
                    state.indicators["latest"],
                    lot,
                    stop_dist,
                    1.8,
                    state.circuit_breaker_triggered
                )
                state.risk["calculatedLot"] = lot
                state.risk["calculatedStopDist"] = stop_dist

            await manager.broadcast({
                "type": "price_tick",
                "symbol": state.symbol,
                "price": new_price,
                "indicators": state.indicators,
                "signal": state.signal,
                "risk": state.risk
            })

            # Automatically trigger debate and execution on a new BUY/SELL trading signal
            if state.signal["action"] in ["BUY", "SELL"] and not state.signal_executed and not state.is_debating:
                try:
                    _analyze_queue.put_nowait(state.symbol)
                    logger.info(f"Automatically triggered debate for {state.symbol} due to strategy signal: {state.signal['action']}")
                except asyncio.QueueFull:
                    pass

    asyncio.create_task(price_ticker_sim())

    yield

    await event_bus.close()
    await http_client.aclose()
    logger.info("Shutdown complete")

# ─────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────
app = FastAPI(title="AI Trading Command Center", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────
# WebSocket Endpoint
# ─────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        orders = await get_orders_from_db()
        await websocket.send_json({
            "type": "init",
            "state": {
                "symbol": state.symbol,
                "latest": state.indicators.get("latest", 2342.0) if isinstance(state.indicators, dict) else 2342.0,
                "indicators": state.indicators,
                "signal": state.signal,
                "risk": state.risk,
                "mode": state.mode,
                "balances": state.balances,
                "journal": state.journal,
                "orders": orders,
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
                use_streaming = msg.get("streaming", False)

                # Notify thinking
                await manager.broadcast({
                    "type": "agent_typing",
                    "message": {
                        "agent": "CEO Agent",
                        "role": "ผู้นำบัญชาการ",
                        "avatar": "💼",
                        "message": "กำลังวิเคราะห์...",
                        "timestamp": datetime.now().isoformat()
                    }
                })

                if use_streaming:
                    await get_claude_chat_response_streaming(user_msg, manager.broadcast)
                else:
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
                    if state.telegram_token and state.telegram_chat_id and "Telegram" not in state.telegram_token:
                        try:
                            user_text = f"👤 <b>[คำถามของคุณบน Dashboard]</b>:\n{user_msg}"
                            await send_telegram_direct_message(state.telegram_chat_id, user_text, parse_mode="HTML")
                            
                            ceo_text = f"💼 <b>[CEO Agent ตอบบน Dashboard]</b>:\n{ai_reply}"
                            await send_telegram_direct_message(state.telegram_chat_id, ceo_text, parse_mode="HTML")
                        except Exception as e:
                            logger.error(f"Telegram dashboard chat copy error: {e}")

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)

# ─────────────────────────────────────────────────────────
# REST API Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/api/state")
async def get_state_endpoint():
    orders = await get_orders_from_db()
    return {
        "symbol": state.symbol,
        "latest": state.indicators.get("latest", 2342.0) if isinstance(state.indicators, dict) else 2342.0,
        "indicators": state.indicators,
        "signal": state.signal,
        "risk": state.risk,
        "mode": state.mode,
        "balances": state.balances,
        "journal": state.journal,
        "orders": orders,
        "debate": state.active_debate,
        "is_debating": state.is_debating,
        "settings": {
            # ✅ MASKED — ไม่โชว์ keys จริง
            "telegram_token": state.mask_key(state.telegram_token),
            "anthropic_key": state.mask_key(state.anthropic_key),
            "binance_key": state.mask_key(state.binance_key),
            "binance_secret": state.mask_key(state.binance_secret),
            "news_api_key": state.mask_key(state.news_api_key),
            "twelvedata_api_key": state.mask_key(state.twelvedata_api_key),
            "finnhub_api_key": state.mask_key(state.finnhub_api_key),
            "maxRiskPerTradePct": RISK_CONFIG["maxRiskPerTradePct"],
            "maxOpenExposurePct": RISK_CONFIG["maxOpenExposurePct"]
        }
    }

@app.get("/api/metrics")
async def get_metrics_endpoint():
    metrics = await get_metrics()
    return metrics

@app.get("/api/trades")
async def get_trades():
    def _query():
        db = SessionLocal()
        try:
            trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(50).all()
            return [{
                "id": t.id,
                "ticker": t.ticker,
                "action": t.action.name if t.action else "BUY",
                "status": t.status.name if t.status else "OPEN",
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "lot_size": t.lot_size,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "realized_pnl": t.realized_pnl,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None
            } for t in trades]
        finally:
            db.close()
    return await asyncio.to_thread(_query)

@app.get("/api/news")
async def get_live_news():
    news_api_key = state.news_api_key
    if news_api_key and "News" not in news_api_key and len(news_api_key) > 10:
        try:
            keyword = state.symbol.replace("USDT", "").replace("USD", " USD")
            r = await get_http_client().get(
                f"https://newsapi.org/v2/everything?q={keyword}&apiKey={news_api_key}&pageSize=5&sortBy=publishedAt&language=en",
                timeout=3.0
            )
            if r.status_code == 200:
                articles = r.json().get("articles", [])
                news = []
                for a in articles[:4]:
                    news.append({
                        "time": a.get("publishedAt", "")[:16].replace("T", " "),
                        "source": a.get("source", {}).get("name", "NewsAPI"),
                        "text": a.get("title", ""),
                        "url": a.get("url", ""),
                        "impact": "HIGH" if any(kw in (a.get("title","")).lower() for kw in ["fed", "rate", "inflation", "crash"]) else "MEDIUM"
                    })
                if news:
                    return {"success": True, "news": news, "source": "newsapi"}
        except Exception as e:
            logger.error(f"News API error: {e}")

    # Fallback
    return {
        "success": True,
        "source": "fallback",
        "news": [
            {"time": "Live", "source": "Market Monitor", "text": f"ราคา {state.symbol} เคลื่อนตัวในกรอบ — RSI: {state.indicators.get('rsi', 50) if isinstance(state.indicators, dict) else 50}", "impact": "MEDIUM"},
            {"time": "Live", "source": "FED Watch", "text": "ธนาคารกลางยังคงนโยบายการเงินตามคาดการณ์ของตลาด", "impact": "HIGH"},
            {"time": "Live", "source": "Macro View", "text": "Sentiment นักลงทุนสถาบันยังเป็นบวกต่อสินทรัพย์เสี่ยง", "impact": "MEDIUM"}
        ]
    }

# ─────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────
class SymbolRequest(BaseModel):
    symbol: str

class OrderRequest(BaseModel):
    lot: float
    stopDistance: float
    spread: float

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

class TelegramCommandRequest(BaseModel):
    command: str

class AlertConfigRequest(BaseModel):
    rsi_overbought: float = 75
    rsi_oversold: float = 25
    max_drawdown_pct: float = 5.0
    price_spike_pct: float = 2.0

# ─────────────────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────────────────
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
        state.indicators.get("latest", 2342.0) if isinstance(state.indicators, dict) else 2342.0,
        req.lot,
        req.stopDistance,
        req.spread
    )
    add_journal_entry("risk_check", f"อัปเดตความเสี่ยง Lot {req.lot} — {'ผ่าน' if state.risk['passed'] else 'ระงับ'}")
    return state.risk

@app.post("/api/approve")
async def approve_trade():
    if state.signal_executed:
        return {"status": "success", "message": "ออเดอร์นี้ได้รับการอนุมัติอัตโนมัติไปแล้ว"}
    if not state.risk.get("passed"):
        raise HTTPException(status_code=400, detail="ความเสี่ยงไม่ผ่านเกณฑ์")
    await execute_mock_trade()
    return {"status": "success", "message": "เปิดออเดอร์เรียบร้อย"}

@app.post("/api/reject")
def reject_trade():
    add_journal_entry("trade_rejected", f"ปฏิเสธแผนเทรด {state.symbol}")
    return {"status": "success", "message": "ปฏิเสธแผนเทรดเรียบร้อย"}

@app.post("/api/change-mode")
async def change_mode(req: Dict[str, str]):
    mode = req.get("mode", "watch")
    if mode in ["auto", "watch"]:
        async with state._state_lock:
            state.mode = mode
        add_journal_entry("mode_change", f"สลับโหมดเป็น: {mode.upper()}")
        return {"status": "success", "mode": state.mode}
    raise HTTPException(status_code=400, detail="โหมดไม่ถูกต้อง")

@app.post("/api/update-settings")
def update_settings(req: SettingsRequest):
    # อัปเดต state
    state.telegram_token = req.telegram_token.strip()
    state.anthropic_key = req.anthropic_key.strip()
    state.binance_key = req.binance_key.strip()
    state.binance_secret = req.binance_secret.strip()
    state.news_api_key = req.news_api_key.strip()
    state.twelvedata_api_key = req.twelvedata_api_key.strip()
    state.finnhub_api_key = req.finnhub_api_key.strip()

    # Save to .env (ใช้ pathlib แทน hardcode path)
    try:
        env_path = Path(__file__).parent / ".env"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_TOKEN={state.telegram_token}\n")
            f.write(f"ANTHROPIC_API_KEY={state.anthropic_key}\n")
            f.write(f"BINANCE_API_KEY={state.binance_key}\n")
            f.write(f"BINANCE_API_SECRET={state.binance_secret}\n")
            f.write(f"NEWS_API_KEY={state.news_api_key}\n")
            f.write(f"TWELVEDATA_API_KEY={state.twelvedata_api_key}\n")
            f.write(f"FINNHUB_API_KEY={state.finnhub_api_key}\n")
        logger.info("Settings saved to .env")
    except Exception as e:
        logger.error(f"Failed to save .env: {e}")

    # อัปเดต Binance client
    state._init_binance()

    # อัปเดต Risk Config
    RISK_CONFIG["maxRiskPerTradePct"] = req.maxRiskPerTradePct
    RISK_CONFIG["maxOpenExposurePct"] = req.maxOpenExposurePct

    add_journal_entry("settings_update", "อัปเดตการตั้งค่าระบบเรียบร้อย")
    return {
        "status": "success",
        "settings": {
            "telegram_token": state.mask_key(state.telegram_token),
            "anthropic_key": state.mask_key(state.anthropic_key),
            "binance_key": state.mask_key(state.binance_key),
            "binance_secret": state.mask_key(state.binance_secret),
            "news_api_key": state.mask_key(state.news_api_key),
            "twelvedata_api_key": state.mask_key(state.twelvedata_api_key),
            "finnhub_api_key": state.mask_key(state.finnhub_api_key),
            "maxRiskPerTradePct": RISK_CONFIG["maxRiskPerTradePct"],
            "maxOpenExposurePct": RISK_CONFIG["maxOpenExposurePct"]
        }
    }

@app.post("/api/update-alerts")
def update_alert_config(req: AlertConfigRequest):
    ALERT_CONFIG["rsi_overbought"] = req.rsi_overbought
    ALERT_CONFIG["rsi_oversold"] = req.rsi_oversold
    ALERT_CONFIG["max_drawdown_pct"] = req.max_drawdown_pct
    ALERT_CONFIG["price_spike_pct"] = req.price_spike_pct
    add_journal_entry("alert_config", f"อัปเดต Alert thresholds: RSI {req.rsi_oversold}/{req.rsi_overbought}")
    return {"status": "success", "alert_config": ALERT_CONFIG}

@app.get("/api/alert-config")
def get_alert_config():
    return {"alert_config": ALERT_CONFIG}

@app.get("/api/erp/ledger")
async def proxy_erp_ledger():
    try:
        r = await get_http_client().get("http://localhost:5001/api/ledger", timeout=3.0)
        return r.json()
    except Exception:
        return {"success": False, "ledger": []}

@app.get("/api/erp/tax-summary")
async def proxy_erp_tax():
    try:
        r = await get_http_client().get("http://localhost:5001/api/tax-summary", timeout=3.0)
        return r.json()
    except Exception:
        return {"success": False, "data": {}}

@app.get("/api/erp/summary")
async def proxy_erp_summary():
    try:
        r = await get_http_client().get("http://localhost:5001/api/summary", timeout=3.0)
        return r.json()
    except Exception:
        return {"success": False, "summary": {}}

@app.post("/api/telegram/command")
async def process_telegram_command(req: TelegramCommandRequest):
    response = await handle_telegram_command_logic(req.command.strip(), "UI_Emulator")
    return {"response": response}

@app.get("/health")
async def health_check():
    orders = await get_orders_from_db()
    return {
        "status": "ok",
        "version": "2.0.0",
        "symbol": state.symbol,
        "ws_connections": len(manager.active_connections),
        "is_debating": state.is_debating,
        "mode": state.mode,
        "open_orders": len([o for o in orders if o["status"] == "OPEN"]),
        "queue_size": _analyze_queue.qsize(),
        "has_claude": bool(state.anthropic_key and "Anthropic" not in state.anthropic_key),
        "has_telegram": bool(state.telegram_token and "Telegram" not in state.telegram_token),
        "timestamp": datetime.now().isoformat()
    }
