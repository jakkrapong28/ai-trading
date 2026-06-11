import asyncio
import hashlib
import hmac
import json
import logging
import uuid
import httpx
import os
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_RISK_APPROVED, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_MARKET_DATA
from backend.shared.schema.events import RiskApprovedEvent, ExecutionEvent, MarketTickEvent
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, ERPDeliveryRecord
from backend.brokers.paper import PaperBroker

logger = logging.getLogger("execution-engine")

class ExecutionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.broker = PaperBroker()
        
    async def process_approved_signals(self):
        logger.info("Execution Engine listening to CH_RISK_APPROVED...")
        async for msg in self.event_bus.subscribe_group(CH_RISK_APPROVED, "execution_group", "execution_worker_1"):
            try:
                approved = RiskApprovedEvent(**msg)
                
                if approved.strategy_name != "ManualApproval":
                    db = SessionLocal()
                    existing = db.query(Trade).filter(
                        Trade.ticker == approved.ticker,
                        Trade.status.in_([TradeStatus.PENDING, TradeStatus.OPEN, TradeStatus.RUNNING])
                    ).first()
                    db.close()
                    if existing:
                        logger.warning(f"[Execution] Trade already active for {approved.ticker}. Skipping duplicate.")
                        continue
                
                # Paper Broker creates the Trade in the database
                res = await self.broker.place_order(
                    ticker=approved.ticker,
                    action=approved.action,
                    lot_size=approved.lot_size,
                    stop_loss=approved.stop_loss,
                    take_profit=approved.take_profit,
                    entry_price=approved.signal_price
                )
                
                trade_id = res["order_id"]
                
                opened = ExecutionEvent(
                    trade_id=trade_id,
                    ticker=approved.ticker,
                    action=approved.action,
                    status="OPEN",
                    lot_size=approved.lot_size,
                    entry_price=res["filled_price"]
                )
                
                await self.event_bus.publish(CH_EXEC_OPENED, opened.model_dump())
                logger.info(f"Trade {trade_id} opened. {approved.action} {approved.ticker} at {res['filled_price']:.2f}")
                
                asyncio.create_task(self._fire_erp_webhook("trade.opened", opened.model_dump(), trade_id))
                
            except Exception as e:
                logger.error(f"Error in Execution Engine: {e}")

    async def monitor_active_trades(self):
        logger.info("Execution Engine monitoring CH_MARKET_DATA for trade lifecycle...")
        async for msg in self.event_bus.subscribe_group(CH_MARKET_DATA, "execution_monitor_group", "execution_monitor_1"):
            try:
                tick = MarketTickEvent(**msg)
                ticker = tick.ticker
                price = tick.price
                
                positions = await self.broker.get_positions()
                for p in positions:
                    if p["ticker"] != ticker:
                        continue
                        
                    action = p["action"]
                    entry = p["entry_price"]
                    sl = p["sl_price"]
                    tp = p["tp_price"]
                    trade_id = p["order_id"]
                    lot_size = p["lot_size"]
                    status = p["status"]
                    
                    initial_risk = abs(entry - sl)
                    if initial_risk <= 0:
                        continue
                    
                    current_r = (price - entry) / initial_risk if action == "BUY" else (entry - price) / initial_risk
                        
                    if current_r >= 1.0 and status == "OPEN":
                        await self.broker.modify_order(trade_id, stop_loss=entry)
                        logger.info(f"[{ticker}] 1R Reached. SL moved to BE ({entry:.2f})")
                        
                    if current_r >= 3.0:
                        if action == "BUY":
                            new_sl = price - initial_risk
                            if new_sl > sl:
                                await self.broker.modify_order(trade_id, stop_loss=new_sl)
                        else:
                            new_sl = price + initial_risk
                            if new_sl < sl:
                                await self.broker.modify_order(trade_id, stop_loss=new_sl)
                    
                    # Exit conditions
                    sl_hit = (action == "BUY" and price <= sl) or (action == "SELL" and price >= sl)
                    tp_hit = (action == "BUY" and price >= tp) or (action == "SELL" and price <= tp)
                    
                    if sl_hit or tp_hit:
                        exit_price = sl if sl_hit else tp
                        res = await self.broker.close_order(trade_id, exit_price=exit_price)
                        realized = res["realized_pnl"]
                        
                        reason = "SL/Trailing Hit" if sl_hit else "TP Hit"
                        
                        closed = ExecutionEvent(
                            trade_id=trade_id,
                            ticker=ticker,
                            action=action,
                            status="CLOSED",
                            lot_size=lot_size,
                            exit_price=exit_price,
                            realized_pnl=realized,
                            message=reason
                        )
                        await self.event_bus.publish(CH_EXEC_CLOSED, closed.model_dump())
                        logger.info(f"[{ticker}] Trade {trade_id} {reason} at {exit_price:.2f}. Realized: {realized:.2f}")
                        
                        asyncio.create_task(self._fire_erp_webhook("trade.pnl_realized", closed.model_dump(), trade_id))
                        
            except Exception as e:
                logger.error(f"Error in trade monitor: {e}")

    async def _fire_erp_webhook(self, event_type: str, event_data: dict, trade_id: str):
        erp_url = os.getenv("ERP_WEBHOOK_URL", "http://localhost:5001/webhook/trade-event")
        erp_api_key = os.getenv("ERP_API_KEY", "erp_dev_key_change_in_production_32chars")
        erp_webhook_secret = os.getenv("ERP_WEBHOOK_SECRET", "")
        idemp_key = str(uuid.uuid4())

        # Prepare the payload for ERP
        if event_type == "trade.opened":
            payload = {
                "event": "trade.opened",
                "data": {
                    "trade_id": trade_id,
                    "symbol": event_data["ticker"],
                    "action": event_data["action"],
                    "price": event_data["entry_price"],
                    "volume": event_data["lot_size"],
                    "lot_size": event_data["lot_size"]
                }
            }
        elif event_type == "trade.pnl_realized":
            payload = {
                "event": "trade.pnl_realized",
                "data": {
                    "trade_id": trade_id,
                    "symbol": event_data["ticker"],
                    "action": event_data["action"],
                    "price": event_data.get("exit_price", 0),
                    "exit_price": event_data.get("exit_price", 0),
                    "entry_price": event_data.get("entry_price", 0),
                    "volume": event_data["lot_size"],
                    "lot_size": event_data["lot_size"],
                    "pnl": event_data["realized_pnl"],
                    "fee": 0.0
                }
            }
        else:
            payload = {
                "event": event_type,
                "data": {**event_data, "trade_id": trade_id}
            }

        # HMAC SHA256 signature
        raw_body = json.dumps(payload, separators=(',', ':'), sort_keys=False)
        signature = ""
        if erp_webhook_secret:
            sig_hex = hmac.new(
                erp_webhook_secret.encode('utf-8'),
                raw_body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            signature = f"sha256={sig_hex}"

        db = SessionLocal()
        record = ERPDeliveryRecord(
            trade_id=trade_id,
            idempotency_key=idemp_key,
            request_payload=payload
        )
        db.add(record)
        db.commit()

        headers = {
            "Idempotency-Key": idemp_key,
            "X-Api-Key": erp_api_key,
            "Content-Type": "application/json"
        }
        if signature:
            headers["X-Signature"] = signature

        try:
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
                logger.debug(f"[ERP] Webhook {event_type} → {resp.status_code}")
        except Exception as e:
            record.status = "ERROR"
            record.response_body = str(e)
            logger.debug(f"ERP Webhook failed (expected if ERP offline): {e}")

        db.commit()
        db.close()

def start_execution_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = ExecutionEngine(event_bus)
    registry.register(engine.process_approved_signals(), name="exec_process_signals")
    registry.register(engine.monitor_active_trades(), name="exec_monitor_trades")
