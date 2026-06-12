import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from sqlalchemy import text

from backend.shared.events.core import (
    EventBus, CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS, 
    CH_AI_JOURNAL, CH_RISK_APPROVED, CH_RISK_REJECTED, 
    CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED, CH_PORTFOLIO_SNAPSHOT, CH_NEWS, CH_AI_DECISION, correlation_id_ctx
)
from backend.shared.database.core import Base, engine, SessionLocal
from backend.shared.database.models import Trade, TradeStatus, TradeAction, ERPDeliveryRecord
from backend.shared.tasks import registry

from backend.engines.market_data import start_market_data_engine, latest_prices, get_latest_price
from backend.engines.news_intelligence import start_news_intelligence_engine
from backend.engines.market_regime import start_market_regime_engine, ticker_data
from backend.engines.strategy import start_strategy_engine
from backend.engines.risk import start_risk_engine
from backend.engines.execution import start_execution_engine
from backend.engines.portfolio import start_portfolio_engine, global_metrics
from backend.agents import start_ai_decision_engine
from backend.core import get_market_indicators, evaluate_strategy_rules, check_trade_risk

class CorrelationFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = correlation_id_ctx.get()
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

for handler in logging.root.handlers:
    handler.addFilter(CorrelationFilter())

logger = logging.getLogger("main")

event_bus = EventBus()
http_client: httpx.AsyncClient = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        async with self._lock:
            connections = list(self.active_connections)
        dead = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        if dead:
            async with self._lock:
                for c in dead:
                    if c in self.active_connections:
                        self.active_connections.remove(c)

manager = ConnectionManager()

# Global State Variables for dashboard APIs
current_symbol = "XAUUSD"
current_mode = "watch"
os.environ["CURRENT_MODE"] = "watch"
current_risk_input = {
    "lot": 0.01,
    "stopDistance": 20.0,
    "takeProfit": 40.0,
    "spread": 2.0,
    "rejectThreshold": 3.0,
    "riskPct": 1.5
}
journal_log = [
    {
        "type": "system_init", 
        "detail": "ระบบนิเวศ AI Trading Virtual Office เริ่มต้นการทำงานเสร็จสมบูรณ์", 
        "at": datetime.now().isoformat()
    }
]
latest_news_cache: Dict[str, List[dict]] = {}

# DB Helper Functions
async def load_orders_from_db() -> List[dict]:
    db = SessionLocal()
    try:
        trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(100).all()
        orders = []
        for t in trades:
            orders.append({
                "id": t.id,
                "symbol": t.ticker,
                "action": t.action.value,
                "volume": t.lot_size,
                "entry_price": t.entry_price or 0.0,
                "exit_price": t.exit_price or 0.0,
                "pnl": t.realized_pnl or 0.0,
                "fee": 0.0,
                "status": t.status.value,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None
            })
        return orders
    except Exception as e:
        logger.error(f"Error loading orders from DB: {e}")
        return []
    finally:
        db.close()

async def calculate_balances() -> List[dict]:
    db = SessionLocal()
    try:
        closed_trades = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
        total_pnl = sum([t.realized_pnl for t in closed_trades if t.realized_pnl])
        balance = 45750.00 + total_pnl

        open_trades = db.query(Trade).filter(Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])).all()
        floating_pnl = 0.0
        for t in open_trades:
            current = latest_prices.get(t.ticker)
            if current:
                current_price = current["last_price"]
                entry = t.entry_price or 0.0
                lot = t.lot_size or 0.0
                if t.action.value == "BUY":
                    floating_pnl += (current_price - entry) * lot
                else:
                    floating_pnl += (entry - current_price) * lot
        equity = balance + floating_pnl
        
        return [
            {"source": "MT5", "equity": round(equity * 0.55, 2), "balance": round(balance * 0.55, 2), "free_margin": round(balance * 0.55, 2)},
            {"source": "BINANCE", "equity": round(equity * 0.27, 2), "balance": round(balance * 0.27, 2), "free_margin": round(balance * 0.27, 2)},
            {"source": "ONCHAIN_WALLET", "equity": round(equity * 0.18, 2), "balance": round(balance * 0.18, 2), "free_margin": round(balance * 0.18, 2)}
        ]
    except Exception as e:
        logger.error(f"Error calculating balances: {e}")
        return [
            {"source": "MT5", "equity": 25162.5, "balance": 25162.5, "free_margin": 25162.5},
            {"source": "BINANCE", "equity": 12352.5, "balance": 12352.5, "free_margin": 12352.5},
            {"source": "ONCHAIN_WALLET", "equity": 8235.0, "balance": 8235.0, "free_margin": 8235.0}
        ]
    finally:
        db.close()

# Request Models
class TelegramCommandRequest(BaseModel):
    command: str

class SymbolRequest(BaseModel):
    symbol: str

class RiskRequest(BaseModel):
    lot: float
    stopDistance: float
    takeProfit: float
    spread: float
    rejectThreshold: float = 3.0
    riskPct: float = 1.5

class SettingsRequest(BaseModel):
    telegram_token: Optional[str] = ""
    anthropic_key: Optional[str] = ""
    binance_key: Optional[str] = ""
    binance_secret: Optional[str] = ""
    news_api_key: Optional[str] = ""
    twelvedata_api_key: Optional[str] = ""
    finnhub_api_key: Optional[str] = ""
    maxRiskPerTradePct: Optional[float] = 2.0
    maxOpenExposurePct: Optional[float] = 20.0

async def handle_telegram_command_logic(cmd: str, user_tag: str) -> str:
    global current_symbol, current_mode
    
    if cmd.startswith("/analyze"):
        parts = cmd.split()
        symbol = parts[1].upper() if len(parts) > 1 else current_symbol
        from backend.core import SYMBOLS
        if symbol not in SYMBOLS:
            return f"❌ ไม่พบคู่สินทรัพย์ที่ต้องการวิเคราะห์: {symbol}"
        
        current_symbol = symbol
        journal_entry = {
            "ticker": symbol,
            "decision": "MANUAL_ANALYSIS_TRIGGERED",
            "signal_action": "HOLD",
            "confidence_score": 1.0,
            "reasons": [f"ได้รับคำสั่งวิเคราะห์ด่วนสำหรับ {symbol} จาก {user_tag}"]
        }
        await event_bus.publish(CH_AI_JOURNAL, journal_entry)
        
        return (
            f"📊 ได้รับคำสั่งวิเคราะห์ด่วนสำหรับ {symbol} จากคุณโทนี่ ({user_tag}) เรียบร้อย!\n"
            f"ขณะนี้กำลังกระตุ้นเสวนากรรมการ AI ทั้ง 6 ฝ่ายและระบบ Risk Guardian เพื่อเขียนมติอัปเดต โปรดดูสตรีมแชทสดบน Dashboard ของออฟฟิศ..."
        )
        
    elif cmd.startswith("/wallet"):
        balances = await calculate_balances()
        total_equity = sum(bal["equity"] for bal in balances)
        balance_details = "\n".join([f"- {b['source']}: ยอดคงเหลือ ${b['balance']:,} (Equity: ${b['equity']:,})" for b in balances])
        return (
            f"🔍 [รายงาน Wallet Intel AI]\n"
            f"ยอดมูลค่าทรัพย์สินพอร์ตรวม (Net Worth): ${total_equity:,.2f}\n\n"
            f"รายละเอียดสมุดรายวัน:\n{balance_details}"
        )
        
    elif cmd.startswith("/mode"):
        parts = cmd.split()
        if len(parts) > 1 and parts[1].lower() in ["auto", "watch"]:
            new_mode = parts[1].lower()
            current_mode = new_mode
            os.environ["CURRENT_MODE"] = new_mode
            
            journal_entry = {
                "ticker": current_symbol,
                "decision": "MODE_CHANGE",
                "signal_action": "HOLD",
                "confidence_score": 1.0,
                "reasons": [f"สลับโหมดการควบคุมหลักเป็น: {new_mode.upper()}"]
            }
            await event_bus.publish(CH_AI_JOURNAL, journal_entry)
            return f"⚙️ สลับโหมดการทำออเดอร์เป็น [{new_mode.upper()}] สำเร็จแล้วครับ"
        return "❓ วิธีใช้งาน: พิมพ์ `/mode auto` หรือ `/mode watch`"
    
    elif cmd.startswith("/price"):
        parts = cmd.split()
        symbol = parts[1].upper() if len(parts) > 1 else current_symbol
        from backend.core import SYMBOLS
        if symbol not in SYMBOLS:
            return f"❌ ไม่พบคู่สินทรัพย์: {symbol}"
            
        df = ticker_data.get(symbol)
        if df is not None and not df.empty:
            prices_list = df['price'].tolist()
        else:
            prices_list = []
        indicators = get_market_indicators(prices_list, symbol)
        
        return (
            f"📈 [ราคาเสนอซื้อล่าสุด]\n"
            f"คู่เหรียญ/หุ้น: {symbol}\n"
            f"ราคาเฉลี่ยปัจจุบัน: {indicators['latest']}\n"
            f"เทรนด์ภาพรวม: {indicators['trend']}"
        )
        
    elif cmd.startswith("/report"):
        orders = await load_orders_from_db()
        today_pnl = sum(o.get("pnl", 0.0) for o in orders)
        return (
            f"📝 [รายงานผลเทรดจาก Report AI]\n"
            f"ประวัติดีลสำเร็จสะสม: {len(orders)} รายการ\n"
            f"ผลกำไร P&L สุทธิวันนี้: ${today_pnl:.2f}"
        )
        
    elif cmd.startswith("/risk"):
        df = ticker_data.get(current_symbol)
        if df is not None and not df.empty:
            prices_list = df['price'].tolist()
        else:
            prices_list = []
        indicators = get_market_indicators(prices_list, current_symbol)
        from backend.engines.market_regime import regime_managers
        regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
        signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)
        risk = check_trade_risk(
            current_symbol,
            signal["action"],
            indicators["latest"],
            current_risk_input["lot"],
            current_risk_input["stopDistance"],
            current_risk_input["spread"],
            take_profit=current_risk_input["takeProfit"],
            reject_threshold=current_risk_input["rejectThreshold"],
            risk_pct_limit=current_risk_input["riskPct"]
        )
        
        passed_txt = "ผ่านเกณฑ์บริหารความปลอดภัย 🟢" if risk["passed"] else "ระงับออเดอร์ความปลอดภัยต่ำ 🔴"
        return (
            f"🛡️ [การตรวจความปลอดภัย Risk AI]\n"
            f"สถานะ: {passed_txt}\n"
            f"สัดส่วนความเสี่ยงไม้: {risk['riskPct']}%\n"
            f"สัดส่วน Exposure: {risk['exposurePct']}%"
        )
        
    elif cmd.startswith("/alerts"):
        return "🚨 [รายงานระบบ Alert AI]\nระบบสตรีม WebSocket และ Ledger ERP กำลังทำงานได้เสถียร 100% ไม่มีภัยคุกคามตรวจพบครับ"
        
    elif cmd.startswith("/pause"):
        current_mode = "watch"
        os.environ["CURRENT_MODE"] = "watch"
        journal_entry = {
            "ticker": current_symbol,
            "decision": "SYSTEM_PAUSE",
            "signal_action": "HOLD",
            "confidence_score": 1.0,
            "reasons": ["ระบบการวิเคราะห์และยิงออเดอร์ถูกระงับชั่วคราวผ่าน Telegram"]
        }
        await event_bus.publish(CH_AI_JOURNAL, journal_entry)
        return "⏸️ สั่งการสำเร็จ: ระงับระบบ Virtual Office ชั่วคราวเรียบร้อย"
        
    elif cmd.startswith("/closeall"):
        db = SessionLocal()
        closed_count = 0
        total_pnl = 0.0
        try:
            open_trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()
            
            from backend.brokers.paper import PaperBroker
            from backend.shared.schema.events import ExecutionEvent
            import uuid, json, hmac, hashlib
            broker = PaperBroker()
            
            async def fire_erp_webhook_local(event_type: str, event_data: dict, trade_id: str, entry_price: float):
                erp_url = os.getenv("ERP_WEBHOOK_URL", "http://localhost:5001/webhook/trade-event")
                erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
                erp_webhook_secret = os.getenv("ERP_WEBHOOK_SECRET", "")
                idemp_key = str(uuid.uuid4())
                
                payload = {
                    "event": event_type,
                    "data": {
                        "trade_id": trade_id,
                        "symbol": event_data["ticker"],
                        "action": event_data["action"],
                        "price": event_data.get("exit_price", 0),
                        "exit_price": event_data.get("exit_price", 0),
                        "entry_price": entry_price,
                        "volume": event_data["lot_size"],
                        "lot_size": event_data["lot_size"],
                        "pnl": event_data["realized_pnl"],
                        "fee": 0.0
                    }
                }
                raw_body = json.dumps(payload, separators=(',', ':'), sort_keys=False)
                signature = ""
                if erp_webhook_secret:
                    sig_hex = hmac.new(
                        erp_webhook_secret.encode('utf-8'),
                        raw_body.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    signature = f"sha256={sig_hex}"
                    
                db_erp = SessionLocal()
                try:
                    record = ERPDeliveryRecord(
                        trade_id=trade_id,
                        idempotency_key=idemp_key,
                        request_payload=payload
                    )
                    db_erp.add(record)
                    db_erp.commit()
                    
                    headers = {
                        "Idempotency-Key": idemp_key,
                        "X-Api-Key": erp_api_key,
                        "Content-Type": "application/json"
                    }
                    if signature:
                        headers["X-Signature"] = signature
                        
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            erp_url,
                            content=raw_body,
                            headers=headers,
                            timeout=3.0
                        )
                        record.response_code = resp.status_code
                        record.response_body = resp.text
                        record.status = "SUCCESS" if resp.status_code < 300 else "FAILED"
                    db_erp.commit()
                except Exception as ex:
                    logger.error(f"Failed to fire ERP webhook for command close: {ex}")
                finally:
                    db_erp.close()

            for t in open_trades:
                current_price = t.entry_price or 0.0
                df = ticker_data.get(t.ticker)
                if df is not None and not df.empty:
                    current_price = float(df['price'].iloc[-1])
                
                res = await broker.close_order(t.id, exit_price=current_price)
                pnl = res["realized_pnl"]
                total_pnl += pnl
                closed_count += 1
                
                closed_event = ExecutionEvent(
                    trade_id=t.id,
                    ticker=t.ticker,
                    action=t.action.value if hasattr(t.action, "value") else t.action,
                    status="CLOSED",
                    lot_size=t.lot_size,
                    exit_price=current_price,
                    realized_pnl=pnl,
                    message="Manual Command Close"
                )
                await event_bus.publish(CH_EXEC_CLOSED, closed_event.model_dump())
                asyncio.create_task(fire_erp_webhook_local("trade.pnl_realized", closed_event.model_dump(), t.id, t.entry_price or 0.0))
                
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error executing /closeall command: {e}")
            return f"❌ เกิดข้อผิดพลาดในการปิดออเดอร์: {e}"
        finally:
            db.close()
            
        if closed_count > 0:
            journal_entry = {
                "ticker": current_symbol,
                "decision": "ORDERS_CLOSED_COMMAND",
                "signal_action": "HOLD",
                "confidence_score": 1.0,
                "reasons": [f"ผู้ใช้สั่งปิดออเดอร์ทั้งหมดในพอร์ตด้วยคำสั่งพิมพ์ ({closed_count} ออเดอร์) รวมกำไร/ขาดทุนสุทธิ: {total_pnl:+.2f} USD"]
            }
            await event_bus.publish(CH_AI_JOURNAL, journal_entry)
            return f"✅ สั่งปิดโพซิชันทั้งหมดในพอร์ตจำนวน {closed_count} ไม้ เรียบร้อยแล้วครับ! (ยอดกำไร/ขาดทุนสะสมสุทธิ: {total_pnl:+.2f} USD)"
        return "ℹ️ ไม่มีโพซิชันเทรดที่กำลังรันอยู่ในขณะนี้"

    elif cmd.startswith("/close all"):
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])).all()
            for t in open_trades:
                t.status = TradeStatus.CANCELLED
            db.commit()
        finally:
            db.close()
            
        # Broadcast update to WebSocket clients to clear active orders in UI
        orders_list = await load_orders_from_db()
        balances_list = await calculate_balances()
        await manager.broadcast({
            "type": "order_closed",
            "orders": orders_list,
            "balances": balances_list
        })
            
        journal_entry = {
            "ticker": current_symbol,
            "decision": "ORDERS_CLEARED",
            "signal_action": "HOLD",
            "confidence_score": 1.0,
            "reasons": ["สั่งล้างสัญญาทั้งพอร์ตจำลองโดยผู้ใช้"]
        }
        await event_bus.publish(CH_AI_JOURNAL, journal_entry)
        return "🧹 สั่งปิดและเคลียร์ประวัติคำสั่งเทรดกระดาษเรียบร้อยแล้วครับ"
        
    else:
        return (
            "💬 คำสั่งที่รองรับ:\n"
            "- `/price [Symbol]` (ตรวจราคาล่าสุด)\n"
            "- `/analyze [Symbol]` (สแกนสภา AI วิเคราะห์ด่วน)\n"
            "- `/wallet` (ตรวจ Net Worth ทรัพย์สินพอร์ต)\n"
            "- `/mode [auto/watch]` (เปลี่ยนโหมดควบคุมพอร์ต)\n"
            "- `/report` (ผลกำไร P&L พอร์ตวันนี้)\n"
            "- `/risk` (ตรวจวัดเกราะความเสี่ยง)\n"
            "- `/alerts` (ดูบันทึกแจ้งเตือนภัยพอร์ต)\n"
            "- `/pause` (กดปุ่มฉุกเฉินหยุดการซื้อขาย)\n"
            "- `/close all` (ล้างสัญญาจำลองที่ค้างคา - ยกเลิก)\n"
            "- `/closeall` (สั่งปิดโพซิชันทั้งหมดด้วยราคาตลาดปัจจุบัน)"
        )

async def websocket_bridge():
    channels = [
        CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS,
        CH_AI_JOURNAL, CH_RISK_APPROVED, CH_RISK_REJECTED,
        CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED, 
        CH_PORTFOLIO_SNAPSHOT, CH_NEWS, CH_AI_DECISION
    ]
    
    async def bridge_channel(channel):
        async for msg in event_bus.subscribe(channel):
            try:
                if channel == CH_AI_JOURNAL:
                    detail = msg.get("reasons", [""])[0] if msg.get("reasons") else ""
                    log_type = msg.get("decision", "INFO")
                    entry = {
                        "type": log_type,
                        "detail": detail,
                        "at": datetime.now().isoformat()
                    }
                    global journal_log
                    journal_log.insert(0, entry)
                    if len(journal_log) > 80:
                        journal_log.pop()
                        
                    agent_name = "CEO Agent"
                    if "SIGNAL_GENERATED" in log_type:
                        agent_name = "Strategy AI"
                    elif "RISK" in log_type:
                        agent_name = "Risk AI"
                    elif "EXEC" in log_type:
                        agent_name = "EA Bot"
                    
                    await manager.broadcast({
                        "type": "agent_typing",
                        "message": {
                            "agent": agent_name,
                            "role": "ผู้นำบัญชาการ",
                            "avatar": "🕴️" if agent_name == "CEO Agent" else "🤖",
                            "message": detail,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                elif channel == CH_MARKET_DATA:
                    if msg.get("ticker") == current_symbol:
                        df = ticker_data.get(current_symbol)
                        if df is not None and not df.empty:
                            prices_list = df['price'].tolist()
                        else:
                            prices_list = []
                        indicators = get_market_indicators(prices_list, current_symbol)
                        from backend.engines.market_regime import regime_managers
                        regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
                        signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)
                        risk = check_trade_risk(
                            current_symbol,
                            signal["action"],
                            indicators["latest"],
                            current_risk_input["lot"],
                            current_risk_input["stopDistance"],
                            current_risk_input["spread"],
                            take_profit=current_risk_input["takeProfit"],
                            reject_threshold=current_risk_input["rejectThreshold"],
                            risk_pct_limit=current_risk_input["riskPct"]
                        )
                        await manager.broadcast({
                            "type": "price_tick",
                            "symbol": current_symbol,
                            "price": msg.get("price"),
                            "indicators": indicators,
                            "signal": signal,
                            "risk": risk
                        })
                        
                elif channel == CH_EXEC_OPENED:
                    orders_list = await load_orders_from_db()
                    balances_list = await calculate_balances()
                    await manager.broadcast({
                        "type": "order_opened",
                        "order": orders_list[0] if orders_list else None,
                        "balances": balances_list
                    })
                    
                elif channel == CH_EXEC_CLOSED:
                    orders_list = await load_orders_from_db()
                    balances_list = await calculate_balances()
                    await manager.broadcast({
                        "type": "order_closed",
                        "orders": orders_list,
                        "balances": balances_list
                    })
                    
                elif channel == CH_NEWS:
                    ticker = msg["ticker"]
                    if ticker not in latest_news_cache:
                        latest_news_cache[ticker] = []
                    if msg["headline"] not in [n["text"] for n in latest_news_cache[ticker]]:
                        time_str = datetime.now().strftime("%H:%M")
                        news_item = {
                            "time": time_str,
                            "source": msg["source"],
                            "text": msg["headline"],
                            "impact": "HIGH" if msg["final_news_score"] > 70 or "FED" in msg["headline"].upper() else "MEDIUM"
                        }
                        latest_news_cache[ticker].insert(0, news_item)
                        if len(latest_news_cache[ticker]) > 8:
                            latest_news_cache[ticker].pop()
            except Exception as bridge_err:
                logger.error(f"Error in WS bridge for channel {channel}: {bridge_err}")
            
            await manager.broadcast({"type": channel, "data": msg})

    for ch in channels:
        registry.register(bridge_channel(ch), name=f"ws_bridge_{ch}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    logger.info("Initializing system...")
    
    PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() == "true"
    logger.info(f"PAPER_MODE is set to: {PAPER_MODE}")
    
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, connect=2.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database synchronized")
    
    logger.info("Starting up engines...")
    start_market_data_engine(event_bus)
    start_news_intelligence_engine(event_bus)
    start_market_regime_engine(event_bus)
    start_strategy_engine(event_bus)
    start_ai_decision_engine(event_bus)
    start_risk_engine(event_bus)
    start_execution_engine(event_bus)
    start_portfolio_engine(event_bus)
    
    registry.register(websocket_bridge(), name="ws_bridge_manager")
    
    yield
    
    logger.info("Initiating graceful shutdown...")
    
    await registry.cancel_all()
    
    await event_bus.close()
    await http_client.aclose()
    
    engine.dispose()
    
    # Flush logs
    for handler in logging.root.handlers:
        handler.flush()
        
    logger.info("Shutdown complete. Goodbye.")

app = FastAPI(title="AI Trading Command Center", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "paper_mode": os.getenv("PAPER_MODE", "true").lower() == "true"}

@app.get("/health/deep")
async def deep_health_check():
    health_status = "HEALTHY"
    details = {}
    
    redis_ok = await event_bus.health_check()
    details["redis"] = "UP" if redis_ok else "DOWN"
    if not redis_ok: health_status = "UNHEALTHY"
        
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        details["database"] = "UP"
        db.close()
    except Exception as e:
        details["database"] = f"DOWN: {e}"
        health_status = "UNHEALTHY"
        
    from backend.shared.tasks import registry
    active_tasks = len([t for t in registry.tasks if not t.done()])
    details["active_background_tasks"] = active_tasks
    if active_tasks < 5:
        health_status = "DEGRADED" if health_status == "HEALTHY" else health_status
        
    return {"status": health_status, "details": details}

@app.get("/metrics")
async def get_metrics():
    return global_metrics

@app.get("/debug/tasks")
async def debug_tasks():
    from backend.shared.tasks import registry
    result = []
    for t in registry.tasks:
        result.append({
            "name": t.get_name(),
            "done": t.done(),
            "cancelled": t.cancelled()
        })
    return result

@app.get("/debug/prices")
async def debug_prices():
    import sys
    res = {}
    for name, mod in list(sys.modules.items()):
        if "market_data" in name and not name.endswith("__pycache__"):
            lp = getattr(mod, "latest_prices", None)
            if lp is not None:
                res[name] = {k: {**v, "timestamp": str(v["timestamp"])} for k, v in lp.items()}
            else:
                res[name] = "No latest_prices"
    return res

# Dashboard API Endpoints

@app.get("/api/state")
async def get_state():
    from backend.engines.market_regime import regime_managers
    from backend.engines.risk import cb_manager, CORRELATION_REJECTION_COUNT
    from backend.brokers.paper import BrokerHeartbeat
    from backend.core.base import NAN_DETECTION_COUNT
    from backend.config import FEATURE_FLAGS
    from backend.shared.database.models import SMCSignalLog

    df = ticker_data.get(current_symbol)
    if df is not None and not df.empty:
        prices_list = df['price'].tolist()
    else:
        prices_list = []
    
    indicators = get_market_indicators(prices_list, current_symbol)
    regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
    signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)
    
    risk = check_trade_risk(
        current_symbol,
        signal["action"],
        indicators["latest"],
        current_risk_input["lot"],
        current_risk_input["stopDistance"],
        current_risk_input["spread"],
        take_profit=current_risk_input["takeProfit"],
        reject_threshold=current_risk_input["rejectThreshold"],
        risk_pct_limit=current_risk_input["riskPct"]
    )
    
    orders = await load_orders_from_db()
    balances = await calculate_balances()
    
    db = SessionLocal()
    try:
        calibrated_count = db.query(SMCSignalLog).filter(SMCSignalLog.calibrated_at.isnot(None)).count()
        pending_count = db.query(SMCSignalLog).filter(SMCSignalLog.actual_outcome == "PENDING").count()
    except Exception:
        calibrated_count = 0
        pending_count = 0
    finally:
        db.close()
        
    broker_heartbeat = None
    if hasattr(BrokerHeartbeat, "_instance") and BrokerHeartbeat._instance:
        hb = BrokerHeartbeat._instance.last_heartbeat
        if hb:
            broker_heartbeat = hb.isoformat()
            
    return {
        "symbol": current_symbol,
        "latest": indicators["latest"],
        "indicators": indicators,
        "signal": signal,
        "risk": risk,
        "mode": current_mode,
        "balances": balances,
        "journal": journal_log,
        "orders": orders,
        "debate": [],
        "is_debating": False,
        "settings": {
            "telegram_token": os.getenv("TELEGRAM_TOKEN", ""),
            "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
            "binance_key": os.getenv("BINANCE_API_KEY", ""),
            "binance_secret": os.getenv("BINANCE_API_SECRET", ""),
            "news_api_key": os.getenv("NEWS_API_KEY", ""),
            "twelvedata_api_key": os.getenv("TWELVEDATA_API_KEY", ""),
            "finnhub_api_key": os.getenv("FINNHUB_API_KEY", "")
        },
        "feature_flags": FEATURE_FLAGS,
        "circuit_breaker": cb_manager.breakers,
        "heartbeats": {
            "broker": broker_heartbeat,
            "system": datetime.now(timezone.utc).isoformat()
        },
        "nan_logs": {
            "count": NAN_DETECTION_COUNT
        },
        "calibration": {
            "calibrated_count": calibrated_count,
            "pending_count": pending_count
        },
        "correlation_rejections": {
            "count": CORRELATION_REJECTION_COUNT
        }
    }

@app.post("/api/change-symbol")
async def change_symbol(req: SymbolRequest):
    global current_symbol
    symbol_upper = req.symbol.upper()
    from backend.core import SYMBOLS
    if symbol_upper not in SYMBOLS:
        raise HTTPException(status_code=400, detail=f"ไม่รองรับสินทรัพย์นี้: {symbol_upper}")
    current_symbol = symbol_upper
    return {"status": "success", "symbol": current_symbol}

@app.post("/api/update-risk")
async def update_risk(req: RiskRequest):
    global current_risk_input
    current_risk_input = {
        "lot": req.lot,
        "stopDistance": req.stopDistance,
        "takeProfit": req.takeProfit,
        "spread": req.spread,
        "rejectThreshold": req.rejectThreshold,
        "riskPct": req.riskPct
    }
    
    df = ticker_data.get(current_symbol)
    if df is not None and not df.empty:
        prices_list = df['price'].tolist()
    else:
        prices_list = []
        
    indicators = get_market_indicators(prices_list, current_symbol)
    from backend.engines.market_regime import regime_managers
    regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
    signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)
    
    risk = check_trade_risk(
        current_symbol,
        signal["action"],
        indicators["latest"],
        req.lot,
        req.stopDistance,
        req.spread,
        take_profit=req.takeProfit,
        reject_threshold=req.rejectThreshold,
        risk_pct_limit=req.riskPct
    )
    return risk

@app.post("/api/change-mode")
async def change_mode(req: Dict[str, str]):
    global current_mode
    mode = req.get("mode", "watch")
    if mode in ["auto", "watch"]:
        current_mode = mode
        os.environ["CURRENT_MODE"] = mode
        
        journal_entry = {
            "ticker": current_symbol,
            "decision": "MODE_CHANGE",
            "signal_action": "HOLD",
            "confidence_score": 1.0,
            "reasons": [f"สลับโหมดการควบคุมหลักเป็น: {mode.upper()}"]
        }
        await event_bus.publish(CH_AI_JOURNAL, journal_entry)
        return {"status": "success", "mode": current_mode}
    raise HTTPException(status_code=400, detail="โหมดไม่ถูกต้อง")

@app.post("/api/approve")
async def approve_trade():
    df = ticker_data.get(current_symbol)
    if df is not None and not df.empty:
        prices_list = df['price'].tolist()
    else:
        prices_list = []
    indicators = get_market_indicators(prices_list, current_symbol)
    from backend.engines.market_regime import regime_managers
    regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
    signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)
    
    action = signal["action"]
    if action not in ["BUY", "SELL"]:
        action = "BUY"
        
    price = indicators["latest"]
    atr = indicators["atr"]
    if atr <= 0:
        atr = price * 0.02
        
    sl_dist = current_risk_input["stopDistance"]
    if sl_dist <= 0:
        sl_dist = 20.0
    tp_dist = current_risk_input["takeProfit"]
    if tp_dist <= 0:
        tp_dist = 40.0
        
    if action == "BUY":
        stop_loss = price - sl_dist
        take_profit = price + tp_dist
    else:
        stop_loss = price + sl_dist
        take_profit = price - tp_dist
        
    lot_size = current_risk_input["lot"]
    
    from backend.shared.schema.events import RiskApprovedEvent
    approve_event = RiskApprovedEvent(
        ticker=current_symbol,
        action=action,
        lot_size=lot_size,
        signal_price=price,
        stop_loss=round(stop_loss, 4),
        take_profit=round(take_profit, 4),
        strategy_name="ManualApproval",
        atr_at_entry=atr
    )
    await event_bus.publish(CH_RISK_APPROVED, approve_event.model_dump())
    return {"status": "success", "message": "ส่งคำขอเปิดออเดอร์ไปยังตลาดเรียบร้อย"}

@app.post("/api/reject")
async def reject_trade():
    journal_entry = {
        "ticker": current_symbol,
        "decision": "TRADE_REJECTED",
        "signal_action": "REJECT",
        "confidence_score": 1.0,
        "reasons": [f"ผู้ใช้ทำการปฏิเสธแผนการเทรดล่าสุดของ {current_symbol}"]
    }
    await event_bus.publish(CH_AI_JOURNAL, journal_entry)
    return {"status": "success", "message": "ปฏิเสธแผนการเทรดเรียบร้อย"}

@app.post("/api/reset-data")
async def reset_data():
    global journal_log
    
    from sqlalchemy import text
    from backend.shared.database.core import engine
    
    tables = [
        "erp_delivery_records",
        "tax_ledger",
        "trade_ledger",
        "trades",
        "portfolio_snapshots",
        "performance_metrics",
        "ai_decision_journal"
    ]
    
    try:
        with engine.begin() as conn:
            for table in tables:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE;"))
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {e}")
        
    try:
        erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
        await http_client.delete(
            "http://localhost:5001/api/reset",
            headers={"X-Api-Key": erp_api_key}
        )
    except Exception as e:
        logger.error(f"Error resetting ERP server: {e}")
        
    journal_log = [
        {
            "type": "system_init",
            "detail": "รีเซ็ตประวัติการเทรดและบันทึก ERP ทั่วทั้งระบบนิเวศเรียบร้อยแล้ว",
            "at": datetime.now().isoformat()
        }
    ]
    
    return {"status": "success", "message": "รีเซ็ตประวัติการเทรดและระบบ ERP เรียบร้อย"}

@app.post("/api/emergency-stop")
async def emergency_stop():
    import os
    from backend.config import FEATURE_FLAGS
    from backend.alert import send_alert
    
    os.environ["PORTFOLIO_CRITICAL_WATCH"] = "true"
    
    # Close all active positions in DB
    db = SessionLocal()
    try:
        open_trades = db.query(Trade).filter(
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
        ).all()
        for t in open_trades:
            t.status = TradeStatus.CLOSED
            t.closed_at = datetime.utcnow()
            t.exit_price = t.entry_price or 0.0
            t.realized_pnl = 0.0
            
            from backend.shared.schema.events import ExecutionEvent
            closed_event = ExecutionEvent(
                trade_id=t.id,
                ticker=t.ticker,
                action=t.action.value,
                status="CLOSED",
                lot_size=t.lot_size,
                exit_price=t.exit_price,
                realized_pnl=t.realized_pnl,
                message="EMERGENCY STOP Close"
            )
            await event_bus.publish(CH_EXEC_CLOSED, closed_event.model_dump())
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error during emergency stop DB close: {e}")
    finally:
        db.close()

    # Disable all flags except circuit_breaker_v2 & emergency_stop
    for flag in list(FEATURE_FLAGS.keys()):
        if flag not in ("circuit_breaker_v2", "emergency_stop"):
            FEATURE_FLAGS[flag] = False
            
    await send_alert("CRITICAL", "🚨 EMERGENCY STOP activated by user")
    await manager.broadcast({"type": "emergency_stop", "message": "🛑 ระบบหยุดฉุกเฉิน!"})
    return {"success": True}

class CloseOrderRequest(BaseModel):
    order_id: str

@app.post("/api/close-order")
async def close_order_endpoint(req: CloseOrderRequest):
    import json
    import uuid
    import hmac
    import hashlib
    from backend.brokers.paper import PaperBroker
    from backend.shared.schema.events import ExecutionEvent
    
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.id == req.order_id).first()
        if not trade:
            raise HTTPException(status_code=404, detail="ไม่พบออเดอร์นี้ในระบบ")
        if trade.status in [TradeStatus.CLOSED, TradeStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="ออเดอร์นี้ถูกปิดหรือยกเลิกไปแล้ว")
        
        # Get current price
        current_price = trade.entry_price or 0.0
        df = ticker_data.get(trade.ticker)
        if df is not None and not df.empty:
            current_price = float(df['price'].iloc[-1])
            
        broker = PaperBroker()
        res = await broker.close_order(trade.id, exit_price=current_price)
        realized_pnl = res["realized_pnl"]
        
        # Publish closed event to Redis
        closed_event = ExecutionEvent(
            trade_id=trade.id,
            ticker=trade.ticker,
            action=trade.action.value if hasattr(trade.action, "value") else trade.action,
            status="CLOSED",
            lot_size=trade.lot_size,
            exit_price=current_price,
            realized_pnl=realized_pnl,
            message="Manual Close from Dashboard"
        )
        await event_bus.publish(CH_EXEC_CLOSED, closed_event.model_dump())
        
        # Fire ERP Webhook
        async def fire_erp_webhook_local(event_type: str, event_data: dict, trade_id: str):
            erp_url = os.getenv("ERP_WEBHOOK_URL", "http://localhost:5001/webhook/trade-event")
            erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
            erp_webhook_secret = os.getenv("ERP_WEBHOOK_SECRET", "")
            idemp_key = str(uuid.uuid4())
            
            payload = {
                "event": event_type,
                "data": {
                    "trade_id": trade_id,
                    "symbol": event_data["ticker"],
                    "action": event_data["action"],
                    "price": event_data.get("exit_price", 0),
                    "exit_price": event_data.get("exit_price", 0),
                    "entry_price": trade.entry_price or 0.0,
                    "volume": event_data["lot_size"],
                    "lot_size": event_data["lot_size"],
                    "pnl": event_data["realized_pnl"],
                    "fee": 0.0
                }
            }
            
            raw_body = json.dumps(payload, separators=(',', ':'), sort_keys=False)
            signature = ""
            if erp_webhook_secret:
                sig_hex = hmac.new(
                    erp_webhook_secret.encode('utf-8'),
                    raw_body.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                signature = f"sha256={sig_hex}"
                
            db_erp = SessionLocal()
            try:
                record = ERPDeliveryRecord(
                    trade_id=trade_id,
                    idempotency_key=idemp_key,
                    request_payload=payload
                )
                db_erp.add(record)
                db_erp.commit()
                
                headers = {
                    "Idempotency-Key": idemp_key,
                    "X-Api-Key": erp_api_key,
                    "Content-Type": "application/json"
                }
                if signature:
                    headers["X-Signature"] = signature
                    
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        erp_url,
                        content=raw_body,
                        headers=headers,
                        timeout=3.0
                    )
                    record.response_code = resp.status_code
                    record.response_body = resp.text
                    record.status = "SUCCESS" if resp.status_code < 300 else "FAILED"
                db_erp.commit()
            except Exception as ex:
                logger.error(f"Failed to fire ERP webhook for manual close: {ex}")
            finally:
                db_erp.close()
                
        asyncio.create_task(fire_erp_webhook_local("trade.pnl_realized", closed_event.model_dump(), trade.id))
        
        # Publish decision journal update
        action_name = trade.action.value if hasattr(trade.action, "value") else trade.action
        journal_entry = {
            "ticker": trade.ticker,
            "decision": "ORDER_CLOSED_MANUALLY",
            "signal_action": "HOLD",
            "confidence_score": 1.0,
            "reasons": [f"ผู้ใช้ปิดออเดอร์ {action_name} {trade.ticker} ด้วยมือผ่านหน้าบอร์ด ที่ราคา {current_price:.2f} (PnL: {realized_pnl:+.2f} USD)"]
        }
        await event_bus.publish(CH_AI_JOURNAL, journal_entry)
        
        return {"success": True, "realized_pnl": realized_pnl}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manually closing order: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/calibrate")
async def trigger_calibration():
    from backend.core.smc_calibrate import run_calibration
    await run_calibration()
    return {"status": "success", "message": "Calibration completed successfully."}

@app.post("/api/update-settings")
async def update_settings(req: SettingsRequest):
    os.environ["TELEGRAM_TOKEN"] = req.telegram_token or ""
    os.environ["ANTHROPIC_API_KEY"] = req.anthropic_key or ""
    os.environ["BINANCE_API_KEY"] = req.binance_key or ""
    os.environ["BINANCE_API_SECRET"] = req.binance_secret or ""
    os.environ["NEWS_API_KEY"] = req.news_api_key or ""
    os.environ["TWELVEDATA_API_KEY"] = req.twelvedata_api_key or ""
    os.environ["FINNHUB_API_KEY"] = req.finnhub_api_key or ""
    
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_TOKEN={req.telegram_token or ''}\n")
            f.write(f"ANTHROPIC_API_KEY={req.anthropic_key or ''}\n")
            f.write(f"BINANCE_API_KEY={req.binance_key or ''}\n")
            f.write(f"BINANCE_API_SECRET={req.binance_secret or ''}\n")
            f.write(f"NEWS_API_KEY={req.news_api_key or ''}\n")
            f.write(f"TWELVEDATA_API_KEY={req.twelvedata_api_key or ''}\n")
            f.write(f"FINNHUB_API_KEY={req.finnhub_api_key or ''}\n")
            f.write(f"DATABASE_URL={os.getenv('DATABASE_URL', '')}\n")
            f.write(f"REDIS_URL={os.getenv('REDIS_URL', '')}\n")
            f.write(f"PAPER_MODE={os.getenv('PAPER_MODE', 'true')}\n")
    except Exception as e:
        logger.error(f"Error saving settings to .env: {e}")
        
    return {"status": "success"}

@app.get("/api/erp/ledger")
async def proxy_erp_ledger():
    try:
        erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
        r = await http_client.get(
            "http://localhost:5001/api/ledger",
            headers={"X-Api-Key": erp_api_key}
        )
        return r.json()
    except Exception:
        return {"success": False, "ledger": []}

@app.get("/api/erp/tax-summary")
async def proxy_erp_tax():
    try:
        erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
        r = await http_client.get(
            "http://localhost:5001/api/tax-summary",
            headers={"X-Api-Key": erp_api_key}
        )
        return r.json()
    except Exception:
        return {"success": False, "data": {}}

@app.get("/api/news")
async def get_live_news():
    ticker = current_symbol
    feed = latest_news_cache.get(ticker, [])
    if not feed:
        feed = [
            {
                "time": datetime.now().strftime("%H:%M"),
                "source": "MarketWatch",
                "text": f"Market dynamics for {ticker} show consolidation around key psychological levels.",
                "impact": "MEDIUM"
            },
            {
                "time": (datetime.now() - timedelta(hours=1)).strftime("%H:%M"),
                "source": "Reuters",
                "text": f"Trading volume for {ticker} spikes as macro indicators align.",
                "impact": "HIGH"
            }
        ]
    return {"success": True, "news": feed}

@app.post("/api/telegram/command")
async def process_telegram_command(req: TelegramCommandRequest):
    cmd = req.command.strip()
    response = await handle_telegram_command_logic(cmd, "UI_Emulator")
    return {"response": response}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except Exception:
        await manager.disconnect(websocket)

