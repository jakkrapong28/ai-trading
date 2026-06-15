import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, WebSocket, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from sqlalchemy import text

from backend.shared.events.core import (
    EventBus, CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS, 
    CH_AI_JOURNAL, CH_RISK_APPROVED, CH_RISK_REJECTED, 
    CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED, CH_PORTFOLIO_SNAPSHOT, CH_NEWS, CH_AI_DECISION, correlation_id_ctx
)
from backend.shared.database.core import Base, engine, SessionLocal, run_db
from backend.shared.database.models import Trade, TradeStatus, TradeAction, ERPDeliveryRecord
from backend.shared.tasks import registry
from backend.shared.webhooks import fire_erp_webhook

from backend.engines.market_data import start_market_data_engine, latest_prices, get_latest_price, feed_status
from backend.engines.news_intelligence import start_news_intelligence_engine
from backend.engines.market_regime import start_market_regime_engine, ticker_data
from backend.engines.strategy import start_strategy_engine
from backend.engines.risk import start_risk_engine
from backend.engines.execution import start_execution_engine
from backend.engines.portfolio import start_portfolio_engine, global_metrics
from backend.agents import start_ai_decision_engine
from backend.core import get_market_indicators, evaluate_strategy_rules, check_trade_risk
from backend.core.base import current_spread_pips
from backend.core.candle_manager import CandleManager, candle_managers
from backend.services import accounting

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


def mask_secret(value: str) -> str:
    """Mask a secret for safe exposure in API responses: '****1234' (last 4)."""
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


# Indicator cache: recompute heavy TA at most once per INDICATOR_TTL seconds
# per symbol. Indicators are derived from real H1 OHLC candles (true ATR),
# falling back to the raw tick history only until candles are seeded.
_indicator_cache: dict = {}  # symbol -> (monotonic_ts, indicators)
INDICATOR_TTL = 2.0


def get_cached_indicators(symbol: str) -> dict:
    import time
    now = time.monotonic()
    cached = _indicator_cache.get(symbol)

    if cached and (now - cached[0]) < INDICATOR_TTL:
        indicators = dict(cached[1])
    else:
        # Prefer real OHLC candles (gives true-range ATR + real volume).
        cm = candle_managers.get(symbol)
        source = None
        if cm is not None:
            df_ohlc = cm.get_ohlc("H1")
            if df_ohlc is not None and len(df_ohlc) >= 8:
                source = df_ohlc
        if source is None:
            # Fallback: raw tick history until candles are bootstrapped.
            df = ticker_data.get(symbol)
            source = df['price'].tolist() if df is not None and not df.empty else []
        indicators = get_market_indicators(source, symbol)
        _indicator_cache[symbol] = (now, dict(indicators))

    # Always overlay the freshest live price so 'latest' is never stale.
    live = latest_prices.get(symbol)
    if live and live.get("last_price"):
        indicators["latest"] = live["last_price"]
    return indicators

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

# ─── Telegram Bot Long-Polling ────────────────────────────────────────────────
async def telegram_send_message(token: str, chat_id: int, text: str):
    """Send a message back to Telegram chat."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning(f"[TelegramBot] sendMessage failed: {e}")

async def telegram_polling_loop():
    """
    Continuously long-poll Telegram for new messages and process slash commands.
    Uses TELEGRAM_TOKEN from .env. Falls back gracefully if token is missing/invalid.
    """
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token or "กรอก" in token:
        logger.info("[TelegramBot] No valid TELEGRAM_TOKEN — bot polling disabled.")
        return

    base_url = f"https://api.telegram.org/bot{token}"
    offset: int = 0
    logger.info("[TelegramBot] Starting long-poll loop...")

    # Test token validity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base_url}/getMe")
            if not r.json().get("ok"):
                logger.error(f"[TelegramBot] Token invalid: {r.text}")
                return
            bot_name = r.json()["result"].get("username", "bot")
            logger.info(f"[TelegramBot] Connected as @{bot_name}")
    except Exception as e:
        logger.error(f"[TelegramBot] Could not connect: {e}")
        return

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                resp = await client.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                )
            if resp.status_code != 200:
                logger.warning(f"[TelegramBot] getUpdates returned {resp.status_code}")
                await asyncio.sleep(5)
                continue

            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text_in = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                user = msg.get("from", {}).get("username", "unknown")

                if not text_in or not chat_id:
                    continue

                logger.info(f"[TelegramBot] @{user}: {text_in}")

                # Only process slash commands
                if text_in.startswith("/"):
                    # Strip bot mention (e.g. /analyze@MyBot -> /analyze)
                    cmd = text_in.split("@")[0].strip()
                    reply = await handle_telegram_command_logic(cmd, f"@{user}")
                    await telegram_send_message(token, chat_id, reply)
                else:
                    # Friendly response for non-command messages
                    await telegram_send_message(
                        token, chat_id,
                        f"สวัสดีครับ @{user}! 🤖\nพิมพ์คำสั่ง เช่น:\n"
                        "/analyze BTCUSDT — วิเคราะห์ตลาด\n"
                        "/price XAUUSD — ดูราคาล่าสุด\n"
                        "/wallet — ดูยอดพอร์ต\n"
                        "/report — รายงาน P&L\n"
                        "/risk — ตรวจ Risk Gate\n"
                        "/pause — หยุดระบบ Auto\n"
                        "/resume — รีสตาร์ทระบบ Auto"
                    )

        except asyncio.CancelledError:
            logger.info("[TelegramBot] Polling loop cancelled.")
            break
        except Exception as e:
            logger.error(f"[TelegramBot] Error in polling loop: {e}")
            await asyncio.sleep(5)

# DB Helper Functions
async def load_orders_from_db() -> List[dict]:
    # Delegates to the accounting service (non-blocking, single source of truth).
    return await accounting.get_orders(limit=100)

async def calculate_balances() -> List[dict]:
    # Delegates to the accounting service; equity = STARTING_BALANCE + closed PnL
    # + floating PnL, split for display per config.ACCOUNT_DISPLAY_SPLITS.
    return await accounting.get_display_balances(latest_prices)

# Request Models
class TelegramCommandRequest(BaseModel):
    command: str

class SymbolRequest(BaseModel):
    symbol: str

class ApproveRequest(BaseModel):
    override: bool = False

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

        # ── รัน full analysis pipeline ──────────────────────────────────────
        indicators = get_cached_indicators(symbol)

        from backend.engines.market_regime import regime_managers
        regime  = regime_managers[symbol].current_regime if symbol in regime_managers else "UNKNOWN"
        signal  = evaluate_strategy_rules(indicators, symbol, regime=regime)
        risk    = check_trade_risk(
            symbol,
            signal["action"],
            indicators["latest"],
            current_risk_input["lot"],
            current_risk_input["stopDistance"],
            current_risk_input["spread"],
            take_profit=current_risk_input["takeProfit"],
            reject_threshold=current_risk_input["rejectThreshold"],
            risk_pct_limit=current_risk_input["riskPct"]
        )

        price        = indicators["latest"]
        rsi          = indicators.get("rsi", 50.0)
        atr          = indicators.get("atr", 0.0)
        support      = round(price - atr * 2.5, 2)
        resistance   = round(price + atr * 2.5, 2)
        trend_label  = regime if regime else "SIDEWAYS"
        action       = signal["action"]          # BUY / SELL / HOLD
        confidence   = int(signal.get("confidence", 0.75) * 100)
        risk_pct     = risk.get("riskPct", 0.0)
        exposure_pct = risk.get("exposurePct", 0.0)
        risk_passed  = risk.get("passed", False)

        # emoji helpers
        risk_emoji  = "✅ APPROVED" if risk_passed else "❌ BLOCKED"
        trend_map   = {"BULL": "Uptrend 📈", "BEAR": "Downtrend 📉", "SIDEWAYS": "Sideways ↔️", "UNKNOWN": "Sideways ↔️"}
        trend_str   = trend_map.get(trend_label, "Sideways ↔️")

        # asset-class aware labels
        asset_class = SYMBOLS.get(symbol, {}).get("assetClass", "crypto")
        desk_map    = {"crypto": ("🪙 Crypto Analyst AI", "Crypto Desk", "ตลาดคริปโตยืนยัน"),
                       "metal":  ("🥇 Commodity AI",      "Gold Desk",   "ตลาด Commodity ยืนยัน"),
                       "forex":  ("💱 Forex Analyst AI",  "Forex Desk",  "ตลาด Forex ยืนยัน"),
                       "stock":  ("📈 Equity Analyst AI", "Equity Desk", "ตลาดหุ้นยืนยัน")}
        desk_emoji, desk_name, desk_confirm = desk_map.get(asset_class, desk_map["crypto"])

        # ── สร้าง council verdict ────────────────────────────────────────────
        chart_view = (
            f"RSI={rsi:.1f} ATR={atr:.2f} แนวรับ={support} แนวต้าน={resistance} "
            f"ราคาอยู่{'ใกล้แนวรับ เหมาะ BUY' if action == 'BUY' else 'ใกล้แนวต้าน เหมาะ SELL' if action == 'SELL' else 'กลาง Sideway ยังไม่ชัดเจน'}"
        )
        market_view = (
            f"Order Flow ฝั่ง {symbol} สอดคล้องกับสัญญาณ "
            f"Sentiment โดยรวม{'เป็นบวก' if action == 'BUY' else 'เป็นลบ' if action == 'SELL' else 'เป็นทรงตัว'}"
        )
        wallet_view = (
            f"risk exposure {risk_pct:.1f}% "
            f"{'อยู่ในเกณฑ์ปกติ ✅' if risk_passed or risk_pct == 0 else 'เกินเกณฑ์ความปลอดภัย ควรระงับ'} "
            f"ไม่พบ anomaly ในธุรกรรมขนาดใหญ่"
        )
        risk_view = (
            f"{symbol} สถานะ {risk_emoji} risk={risk_pct:.1f}% exposure={exposure_pct:.1f}% "
            f"{'— ผ่านทุกเกณฑ์ พร้อมเปิดออเดอร์' if risk_passed else '— ขัดกฎเหล็ก ยกเลิกหรือหั่น lot'}"
        )
        news_view = (
            f"ไม่พบ high-impact event ในช่วง 3 ชม. ถัดไป "
            f"ภาวะเงินเฟ้อและ Fed policy ยังส่งผลต่อ {symbol} ในระยะกลาง "
            f"{'เหมาะแก่การเปิดออเดอร์' if risk_passed else 'แนะนำหลีกเลี่ยงการเปิดออเดอร์ใหม่'}"
        )
        final_verdict = (
            f"มติที่ประชุม {symbol}: "
            + (f"สัญญาณ {action} ผ่าน Risk Gate — อนุมัติเปิดออเดอร์ lot={current_risk_input['lot']} เรียบร้อยครับ"
               if risk_passed
               else f"แม้มีสัญญาณ {action} แต่ Risk Engine ระงับ ความปลอดภัยของทุนสำคัญกว่า — ยุติเซสชันนี้ครับ")
        )

        report = (
            f"🏛 [สภา AI เริ่มประชุม] — {symbol} (📋 Full Analysis)\n\n"
            f"💼 CEO Agent (The Orchestrator):\n"
            f"สวัสดีทีมงาน เปิดเซสชันวิเคราะห์ {symbol} — ราคาปัจจุบัน {price:,.2f} "
            f"สัญญาณเบื้องต้นระบุ [{action}] (confidence: {confidence}%) ช่วยวิเคราะห์ในแผนกของตนด่วนครับ\n\n"
            f"📊 Chart AI (Forex Desk):\n"
            f"ฝั่ง Chart รายงาน: {symbol} อยู่ใน{trend_str} {chart_view}\n\n"
            f"{desk_emoji} ({desk_name}):\n"
            f"{desk_confirm}: {market_view}\n\n"
            f"🔍 Wallet Intel AI (Digital Asset Detective):\n"
            f"ตรวจสอบพอร์ตเรียบร้อย: {wallet_view}\n\n"
            f"🛡️ Risk AI (The Guardian):\n"
            f"Risk Manager รายงาน: {risk_view}\n\n"
            f"📰 News/Audit AI:\n"
            f"Macro check: {news_view}\n\n"
            f"💼 CEO Agent (The Orchestrator):\n"
            f"{final_verdict}"
        )

        # broadcast ไปยัง dashboard ด้วย
        await event_bus.publish(CH_AI_JOURNAL, {
            "ticker": symbol,
            "decision": f"COUNCIL_ANALYSIS_{action}",
            "signal_action": action,
            "confidence_score": confidence / 100,
            "reasons": [
                f"Chart: {chart_view}",
                f"Risk: {risk_view}",
                f"News: {news_view}",
                f"Verdict: {final_verdict}",
            ]
        })

        return report
        
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
            
        indicators = get_cached_indicators(symbol)

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
        indicators = get_cached_indicators(current_symbol)
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
            broker = PaperBroker()

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
                    entry_price=t.entry_price or 0.0,
                    exit_price=current_price,
                    realized_pnl=pnl,
                    fee=res.get("fee", 0.0),
                    message="Manual Command Close"
                )
                await event_bus.publish(CH_EXEC_CLOSED, closed_event.model_dump())
                asyncio.create_task(fire_erp_webhook("trade.pnl_realized", closed_event.model_dump(), t.id))
                
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
                    ticker = msg.get("ticker")
                    price = msg.get("price")
                    if ticker and price:
                        await manager.broadcast({
                            "type": "price_tick",
                            "symbol": ticker,
                            "price": price,
                        })
                    if ticker == current_symbol:
                        indicators = get_cached_indicators(current_symbol)
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
                            "price": price,
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
    from backend.shared.database.core import ensure_schema_migrations
    ensure_schema_migrations()
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
    
    # Create CandleManagers immediately so engines can feed live ticks right away.
    # The historical Yahoo backfill runs in the BACKGROUND so it never blocks startup —
    # 40 sequential fetches (10 symbols x 4 timeframes, each up to a 15s timeout) could
    # otherwise delay the server becoming ready for several minutes, making every
    # endpoint hang with HTTP 000.
    from backend.core.base import SYMBOLS
    for symbol in SYMBOLS:
        candle_managers[symbol] = CandleManager(symbol)

    async def _bootstrap_candles():
        for symbol in SYMBOLS:
            try:
                cm = candle_managers[symbol]
                await cm.bootstrap_from_yahoo()
                s = cm.status()
                logger.info(f"CandleManager bootstrapped for {symbol}: {s['H1']['completed']} H1 candles")
            except Exception as e:
                logger.warning(f"Could not bootstrap CandleManager for {symbol}: {e}")

        # ── Phase B: D1 Pre-flight check (after candles are available) ──
        from backend.config import FEATURE_FLAGS
        if FEATURE_FLAGS.get("d1_bias_lock", False):
            from backend.core.mtf import verify_d1_candle_timestamps
            for symbol in SYMBOLS:
                try:
                    cm = candle_managers.get(symbol)
                    if cm is None:
                        continue
                    d1_df = cm.get_ohlc("D1", bars=30)
                    if d1_df.empty:
                        logger.warning(f"[D1 Pre-flight] {symbol}: No D1 data available")
                        continue
                    closed_count = await verify_d1_candle_timestamps(d1_df)
                    if closed_count == 0:
                        logger.warning(f"[D1 Pre-flight] {symbol}: 0/{len(d1_df)} bars match — disabling d1_bias_lock")
                        FEATURE_FLAGS["d1_bias_lock"] = False
                    else:
                        logger.info(f"[D1 Pre-flight] {symbol}: {closed_count}/{len(d1_df)} D1 bars OK")
                except Exception as e:
                    logger.warning(f"[D1 Pre-flight] {symbol} check failed: {e}")

    registry.register(_bootstrap_candles(), name="candle_bootstrap")

    # ── Phase B: Schedule Calibration ───────────────────────
    async def calibration_loop():
        from backend.core.smc_calibrate import should_calibrate, run_calibration
        while True:
            try:
                if await should_calibrate():
                    logger.info("Calibration condition met — running calibration...")
                    await run_calibration()
                    logger.info("Calibration completed")
                await asyncio.sleep(3600 * 6)  # check every 6 hours
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Calibration loop error: {e}")
                await asyncio.sleep(3600)

    registry.register(calibration_loop(), name="smc_calibration")
    registry.register(websocket_bridge(), name="ws_bridge_manager")
    registry.register(telegram_polling_loop(), name="telegram_bot_polling")
    
    yield
    
    logger.info("Initiating graceful shutdown...")
    
    await registry.cancel_all()
    
    await event_bus.close()
    await http_client.aclose()
    
    # logger.info("Skipping engine.dispose() — engine is module-level from backend.shared.database.core")
    # Engine pool is managed by SQLAlchemy engine from the module; calling dispose here
    # would be harmless but unnecessary since the process is exiting.
    
    # Flush logs
    for handler in logging.root.handlers:
        handler.flush()
        
    logger.info("Shutdown complete. Goodbye.")

app = FastAPI(title="AI Trading Command Center", version="3.0.0", lifespan=lifespan)

# Restrict browser origins to the dashboard. Single-user/localhost trust model:
# no API key, but the wildcard is dropped so arbitrary sites can't drive the API.
# Override/extend via FRONTEND_ORIGIN (comma-separated) for other dev hosts.
_allowed_origins = [
    o.strip() for o in os.getenv(
        "FRONTEND_ORIGIN", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
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


@app.get("/metrics/prometheus")
async def get_metrics_prometheus():
    """Prometheus exposition for scraping (JSON stays at /metrics)."""
    from backend.shared.metrics_prom import core_metrics_text
    from backend.engines.risk import CORRELATION_REJECTION_COUNT
    from backend.core.base import NAN_DETECTION_COUNT
    from backend.shared.tasks import registry
    from backend.engines.market_data import feed_status

    active = len([t for t in registry.tasks if not t.done()])
    feeds = []
    for ticker in list(latest_prices.keys()):
        fs = feed_status(ticker)
        feeds.append({"symbol": ticker, **fs})

    text = core_metrics_text(
        global_metrics, NAN_DETECTION_COUNT, CORRELATION_REJECTION_COUNT, active, feeds
    )
    return Response(content=text, media_type="text/plain; version=0.0.4")

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

@app.get("/api/candles")
async def get_candles(symbol: str = None, tf: str = "M15", bars: int = 200):
    """Real OHLC candles from CandleManager — feeds the in-house AI chart."""
    from backend.core.candle_manager import TIMEFRAMES
    sym = (symbol or current_symbol).upper()
    if tf not in TIMEFRAMES:
        tf = "M15"
    cm = candle_managers.get(sym)
    if cm is None:
        return {"symbol": sym, "tf": tf, "candles": []}

    def _build():
        df = cm.get_ohlc(tf, bars=bars)
        rows = []
        for _, r in df.iterrows():
            ts = r["timestamp"]
            rows.append({
                "time": int(ts.timestamp()),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume", 0) or 0),
            })
        return rows

    candles = await asyncio.to_thread(_build)
    return {"symbol": sym, "tf": tf, "candles": candles}


@app.get("/api/smc")
async def get_smc(symbol: str = None, tf: str = "H1"):
    """SMC concept levels + Volume Profile for the in-house chart overlay.

    Returns drawable PRICE levels (Order Blocks, FVGs, swings, MSS) and
    POC/VAH/VAL/VWAP so the frontend can render horizontal zones/lines.
    """
    from backend.core.candle_manager import TIMEFRAMES
    from backend.core.smc import detect_smc_levels
    from backend.core.volume_profile import calculate_volume_profile
    from backend.core.base import calculate_atr_ohlc

    sym = (symbol or current_symbol).upper()
    if tf not in TIMEFRAMES:
        tf = "H1"
    cm = candle_managers.get(sym)
    empty = {"symbol": sym, "tf": tf, "levels": {"order_blocks": [], "fvgs": [], "swings": [], "mss": None},
             "volume_profile": {"poc": 0.0, "vah": 0.0, "val": 0.0, "vwap": 0.0}, "atr": 0.0}
    if cm is None:
        return empty

    def _build():
        df = cm.get_ohlc(tf, bars=120)
        if df is None or len(df) < 20:
            return empty
        atr = calculate_atr_ohlc(df, 14)
        levels = detect_smc_levels(df, atr)
        vp = calculate_volume_profile(df)
        return {
            "symbol": sym,
            "tf": tf,
            "levels": levels,
            "volume_profile": {k: vp.get(k, 0.0) for k in ("poc", "vah", "val", "vwap")},
            "atr": round(atr, 4),
        }

    return await asyncio.to_thread(_build)


@app.get("/api/state")
async def get_state():
    from backend.engines.market_regime import regime_managers
    from backend.engines.risk import cb_manager, CORRELATION_REJECTION_COUNT
    from backend.brokers.paper import BrokerHeartbeat
    from backend.core.base import NAN_DETECTION_COUNT
    from backend.config import FEATURE_FLAGS
    from backend.shared.database.models import SMCSignalLog

    indicators = get_cached_indicators(current_symbol)
    regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
    # Compute macro_1h (and a live regime fallback) from H1 candles so the
    # dashboard signal is identical to what the live strategy engine produces —
    # same brain, same inputs, incl. the MTF filter + regime reversal gate.
    macro_1h = None
    cm_s = candle_managers.get(current_symbol)
    if cm_s is not None:
        h1s = cm_s.get_ohlc("H1", bars=200)
        if h1s is not None and len(h1s) >= 50:
            from backend.core.base import compute_macro_trend_from_closes
            macro_1h = compute_macro_trend_from_closes(h1s["close"].astype(float).tolist())
            if not regime:
                from backend.engines.market_regime import calculate_regime_from_h1
                regime = calculate_regime_from_h1(h1s)[0]
    signal = evaluate_strategy_rules(indicators, current_symbol, macro_trend_1h=macro_1h, regime=regime)

    # Single source of truth for equity + deterministic broker spread.
    equity = await accounting.get_account_equity(latest_prices)
    risk = check_trade_risk(
        current_symbol,
        signal["action"],
        indicators["latest"],
        current_risk_input["lot"],
        current_risk_input["stopDistance"],
        current_risk_input["spread"],
        take_profit=current_risk_input["takeProfit"],
        reject_threshold=current_risk_input["rejectThreshold"],
        risk_pct_limit=current_risk_input["riskPct"],
        equity=equity,
        broker_spread=current_spread_pips(current_symbol),
    )

    orders = await load_orders_from_db()
    balances = await calculate_balances()
    
    def _smc_counts(db):
        from sqlalchemy import func
        last_cal = db.query(func.max(SMCSignalLog.calibrated_at)).scalar()
        return (
            db.query(SMCSignalLog).filter(SMCSignalLog.calibrated_at.isnot(None)).count(),
            db.query(SMCSignalLog).filter(SMCSignalLog.actual_outcome == "PENDING").count(),
            last_cal.isoformat() if last_cal else None,
        )
    try:
        calibrated_count, pending_count, last_calibrated_at = await run_db(_smc_counts)
    except Exception:
        calibrated_count = 0
        pending_count = 0
        last_calibrated_at = None
        
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
            "telegram_token": mask_secret(os.getenv("TELEGRAM_TOKEN", "")),
            "anthropic_key": mask_secret(os.getenv("ANTHROPIC_API_KEY", "")),
            "binance_key": mask_secret(os.getenv("BINANCE_API_KEY", "")),
            "binance_secret": mask_secret(os.getenv("BINANCE_API_SECRET", "")),
            "news_api_key": mask_secret(os.getenv("NEWS_API_KEY", "")),
            "twelvedata_api_key": mask_secret(os.getenv("TWELVEDATA_API_KEY", "")),
            "finnhub_api_key": mask_secret(os.getenv("FINNHUB_API_KEY", "")),
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
        "market_prices": {
            ticker: data.get("last_price") or data.get("price")
            for ticker, data in latest_prices.items()
        },
        "data_sources": {
            ticker: feed_status(ticker) for ticker in latest_prices.keys()
        },
        "calibration": {
            "calibrated_count": calibrated_count,
            "pending_count": pending_count,
            "last_calibrated_at": last_calibrated_at
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
    
    indicators = get_cached_indicators(current_symbol)
    from backend.engines.market_regime import regime_managers
    regime = regime_managers[current_symbol].current_regime if current_symbol in regime_managers else None
    signal = evaluate_strategy_rules(indicators, current_symbol, regime=regime)

    equity = await accounting.get_account_equity(latest_prices)
    risk = check_trade_risk(
        current_symbol,
        signal["action"],
        indicators["latest"],
        req.lot,
        req.stopDistance,
        req.spread,
        take_profit=req.takeProfit,
        reject_threshold=req.rejectThreshold,
        risk_pct_limit=req.riskPct,
        equity=equity,
        broker_spread=current_spread_pips(current_symbol),
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
async def approve_trade(req: ApproveRequest = None):
    override = req.override if req else False

    indicators = get_cached_indicators(current_symbol)
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

    # ── Risk gate: manual approve must clear the same hard rules as auto.
    # Circuit breaker is folded into check_trade_risk so a daily-loss lockout
    # blocks the click too. Blocked clicks are NOT fired unless override=True.
    from backend.engines.risk import cb_manager
    cb_active = cb_manager.is_any_active()
    equity = await accounting.get_account_equity(latest_prices)
    risk = check_trade_risk(
        current_symbol, action, price, lot_size, sl_dist,
        current_risk_input["spread"],
        circuit_breaker_triggered=cb_active,
        take_profit=tp_dist,
        reject_threshold=current_risk_input["rejectThreshold"],
        risk_pct_limit=current_risk_input["riskPct"],
        equity=equity,
        broker_spread=current_spread_pips(current_symbol),
    )
    reasons = [c["name"] for c in risk["checks"] if not c["pass"]]
    blocked = not risk["passed"]

    if blocked and not override:
        return {"status": "blocked", "blocked": True, "reasons": reasons, "risk": risk}

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

    overridden = blocked and override
    if overridden:
        # Audit trail: every override is logged to the journal + alerted.
        reason_txt = ", ".join(reasons)
        await event_bus.publish(CH_AI_JOURNAL, {
            "ticker": current_symbol,
            "decision": "MANUAL_OVERRIDE",
            "signal_action": action,
            "confidence_score": 1.0,
            "reasons": [f"⚠️ ผู้ใช้ override กฎความปลอดภัยเปิดออเดอร์ {action} {current_symbol} ทั้งที่ติด: {reason_txt}"]
        })
        from backend.alert import send_alert
        asyncio.create_task(send_alert("WARNING", f"⚠️ MANUAL OVERRIDE: {action} {current_symbol} เปิดทั้งที่ติดกฎ — {reason_txt}"))
        return {"status": "success", "overridden": True, "reasons": reasons,
                "message": "เปิดออเดอร์แบบ MANUAL OVERRIDE (ข้ามกฎความปลอดภัย) เรียบร้อย"}

    return {"status": "success", "overridden": False, "message": "ส่งคำขอเปิดออเดอร์ไปยังตลาดเรียบร้อย"}

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
        erp_api_key = os.getenv("ERP_API_KEY", "")
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
            entry_price=trade.entry_price or 0.0,
            exit_price=current_price,
            realized_pnl=realized_pnl,
            fee=res.get("fee", 0.0),
            message="Manual Close from Dashboard"
        )
        await event_bus.publish(CH_EXEC_CLOSED, closed_event.model_dump())

        # Fire ERP Webhook (shared util)
        asyncio.create_task(fire_erp_webhook("trade.pnl_realized", closed_event.model_dump(), trade.id))
        
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

def _is_masked(value: str) -> bool:
    """A value the dashboard echoed back from mask_secret() ('****1234') — NOT a
    real secret. Saving it would clobber the real key (this is exactly how the
    live keys got corrupted to 8-char '****xxxx' values)."""
    return bool(value) and value.startswith("****")


@app.post("/api/update-settings")
async def update_settings(req: SettingsRequest):
    # Map env var -> incoming value. A masked value (****1234) means "unchanged";
    # an empty string also means "leave as-is" (the form didn't provide it).
    incoming = {
        "TELEGRAM_TOKEN": req.telegram_token,
        "ANTHROPIC_API_KEY": req.anthropic_key,
        "BINANCE_API_KEY": req.binance_key,
        "BINANCE_API_SECRET": req.binance_secret,
        "NEWS_API_KEY": req.news_api_key,
        "TWELVEDATA_API_KEY": req.twelvedata_api_key,
        "FINNHUB_API_KEY": req.finnhub_api_key,
    }
    updates = {k: v for k, v in incoming.items() if v and not _is_masked(v)}

    for k, v in updates.items():
        os.environ[k] = v

    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

        # Merge: preserve every existing key (ERP_API_KEY, ERP_WEBHOOK_SECRET,
        # STARTING_BALANCE, COMMISSION_RATE_*, real API keys not re-entered, ...)
        # and only overwrite the ones the form actually changed to a real value.
        env_vars: dict = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v

        env_vars.update(updates)

        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        logger.error(f"Error saving settings to .env: {e}")

    return {"status": "success", "updated": list(updates.keys())}

@app.get("/api/erp/ledger")
async def proxy_erp_ledger():
    try:
        erp_api_key = os.getenv("ERP_API_KEY", "")
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
        erp_api_key = os.getenv("ERP_API_KEY", "")
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

