import asyncio
import hashlib
import hmac
import json
import logging
import uuid
import httpx
import os
from typing import Dict, Any, List
from datetime import datetime, timezone

from backend.shared.events.core import EventBus, CH_RISK_APPROVED, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_MARKET_DATA, CH_MARKET_REGIME
from backend.shared.schema.events import RiskApprovedEvent, ExecutionEvent, MarketTickEvent, MarketRegimeEvent
from backend.core import validate_atr, validate_price
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, ERPDeliveryRecord, TradeAction
from backend.brokers.paper import PaperBroker
from backend.engines.risk import cb_manager
from backend.shared.webhooks import fire_erp_webhook

logger = logging.getLogger("execution-engine")

REGIME_CHANGE_EXIT_RULES = [
    {
        "from_regimes": ["VOLATILE", "BULL"],
        "to_regime": "SIDEWAYS",
        "max_hold_hours": 48,
        "partial_close_pct": 0.5,
        "tighten_sl_to": "BE",
    },
]

class ExecutionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.broker = PaperBroker()
        self.latest_prices: Dict[str, float] = {}
        
    async def process_approved_signals(self):
        logger.info("Execution Engine listening to CH_RISK_APPROVED...")
        async for msg in self.event_bus.subscribe_group(CH_RISK_APPROVED, "execution_group", "execution_worker_1"):
            try:
                approved = RiskApprovedEvent(**msg)
                approved.signal_price = validate_price(approved.signal_price, f"execution: signal_price for {approved.ticker}")
                approved.stop_loss = validate_price(approved.stop_loss, f"execution: stop_loss for {approved.ticker}")
                approved.take_profit = validate_price(approved.take_profit, f"execution: take_profit for {approved.ticker}")
                approved.atr_at_entry = validate_atr(approved.atr_at_entry or 0.0, approved.ticker, f"execution: atr_at_entry for {approved.ticker}")
                
                if approved.strategy_name != "ManualApproval":
                    db = SessionLocal()
                    existing = db.query(Trade).filter(
                        Trade.ticker == approved.ticker,
                        Trade.status.in_([TradeStatus.PENDING, TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
                    ).first()
                    db.close()
                    if existing:
                        logger.warning(f"[Execution] Trade already active for {approved.ticker}. Skipping duplicate.")
                        continue
                
                from backend.core import order_deduplicator
                if order_deduplicator.is_duplicate(approved.ticker, approved.action, approved.signal_price):
                    logger.warning(f"[Execution] Order duplication detected for {approved.ticker} {approved.action} at {approved.signal_price:.2f}. Skipping.")
                    continue
                order_deduplicator.mark_executed(approved.ticker, approved.action, approved.signal_price)
                
                # Paper Broker creates the Trade in the database
                res = await self.broker.place_order(
                    ticker=approved.ticker,
                    action=approved.action,
                    lot_size=approved.lot_size,
                    stop_loss=approved.stop_loss,
                    take_profit=approved.take_profit,
                    entry_price=approved.signal_price,
                    market_regime=approved.market_regime,
                    atr_at_entry=approved.atr_at_entry
                )
                
                trade_id = res["order_id"]
                
                # Initialize price extreme tracking
                db = SessionLocal()
                t_record = db.query(Trade).filter(Trade.id == trade_id).first()
                if t_record:
                    t_record.highest_price = approved.signal_price
                    t_record.lowest_price = approved.signal_price
                    db.commit()
                db.close()
                
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
                
                asyncio.create_task(fire_erp_webhook("trade.opened", opened.model_dump(), trade_id))
                
            except Exception as e:
                logger.error(f"Error in Execution Engine: {e}")

    async def _execute_close(self, trade: Trade, price: float, reason: str, close_pct: float = 1.0):
        ticker = trade.ticker
        trade_id = trade.id
        action = trade.action.value if hasattr(trade.action, "value") else trade.action
        
        if close_pct >= 1.0:
            res = await self.broker.close_order(trade_id, exit_price=price)
            realized = res["realized_pnl"]
            closed = ExecutionEvent(
                trade_id=trade_id,
                ticker=ticker,
                action=action,
                status="CLOSED",
                lot_size=trade.lot_size,
                exit_price=price,
                realized_pnl=realized,
                message=reason
            )
            await self.event_bus.publish(CH_EXEC_CLOSED, closed.model_dump())
            logger.info(f"[{ticker}] Trade {trade_id} closed ({reason}) at {price:.2f}. Realized: {realized:.2f}")
            asyncio.create_task(fire_erp_webhook("trade.pnl_realized", closed.model_dump(), trade_id))
        else:
            try:
                res = await self.broker.partial_close_order(trade_id, close_pct, exit_price=price)
                realized = res["realized_pnl"]
                closed = ExecutionEvent(
                    trade_id=trade_id,
                    ticker=ticker,
                    action=action,
                    status="PARTIAL",
                    lot_size=res["closed_lot"],
                    exit_price=price,
                    realized_pnl=realized,
                    message=f"Partial Close: {reason}"
                )
                await self.event_bus.publish(CH_EXEC_CLOSED, closed.model_dump())
                logger.info(f"[{ticker}] Trade {trade_id} partially closed {close_pct:.1%} ({reason}) at {price:.2f}. Realized: {realized:.2f}")
                asyncio.create_task(fire_erp_webhook("trade.pnl_realized", closed.model_dump(), trade_id))
            except Exception as e:
                logger.warning(f"Partial close failed for {trade_id}, falling back to full close: {e}")
                res = await self.broker.close_order(trade_id, exit_price=price)
                realized = res["realized_pnl"]
                closed = ExecutionEvent(
                    trade_id=trade_id,
                    ticker=ticker,
                    action=action,
                    status="CLOSED",
                    lot_size=trade.lot_size,
                    exit_price=price,
                    realized_pnl=realized,
                    message=f"{reason} (Fallback from partial close error)"
                )
                await self.event_bus.publish(CH_EXEC_CLOSED, closed.model_dump())
                asyncio.create_task(fire_erp_webhook("trade.pnl_realized", closed.model_dump(), trade_id))

    async def monitor_active_trades(self):
        logger.info("Execution Engine monitoring CH_MARKET_DATA for trade lifecycle...")
        from backend.config import FEATURE_FLAGS
        
        async for msg in self.event_bus.subscribe_group(CH_MARKET_DATA, "execution_monitor_group", "execution_monitor_1"):
            try:
                tick = MarketTickEvent(**msg)
                ticker = tick.ticker
                price = tick.price
                self.latest_prices[ticker] = price
                
                positions = await self.broker.get_positions()
                for p in positions:
                    if p["ticker"] != ticker:
                        continue
                        
                    trade_id = p["order_id"]
                    
                    # Race condition protection
                    async with cb_manager.get_trade_lock(trade_id):
                        db = SessionLocal()
                        trade = db.query(Trade).filter(Trade.id == trade_id).first()
                        if not trade or trade.status in [TradeStatus.CLOSED, TradeStatus.CANCELLED]:
                            db.close()
                            continue
                        
                        action = trade.action.value if hasattr(trade.action, "value") else trade.action
                        entry = trade.entry_price
                        sl = trade.sl_price
                        tp = trade.tp_price
                        lot_size = trade.lot_size
                        
                        # Initialize peak tracking if None
                        if trade.highest_price is None:
                            trade.highest_price = entry
                        if trade.lowest_price is None:
                            trade.lowest_price = entry
                        
                        # Track peak favorable price
                        if action == "BUY":
                            if price > trade.highest_price:
                                trade.highest_price = price
                        else:
                            if price < trade.lowest_price:
                                trade.lowest_price = price
                        
                        db.commit()
                        
                        initial_risk = abs(entry - sl)
                        if initial_risk <= 0:
                            db.close()
                            continue
                        
                        current_r = (price - entry) / initial_risk if action == "BUY" else (entry - price) / initial_risk
                        
                        # 1. Check Partial TP Levels (TP1: 1.0R, TP2: 2.0R, TP3: 3.0R)
                        if FEATURE_FLAGS.get("partial_tp", False):
                            if current_r >= 1.0 and not trade.tp1_hit:
                                logger.info(f"[{ticker}] TP1 target (1.0R) reached for trade {trade_id}.")
                                trade.tp1_hit = True
                                db.commit()
                                await self._execute_close(trade, price, "TP1 Hit (1.0R)", close_pct=0.5)
                                # Move SL to Entry (BE)
                                await self.broker.modify_order(trade_id, stop_loss=entry)
                                trade.sl_price = entry
                                db.commit()
                                db.close()
                                continue
                                
                            if current_r >= 2.0 and not trade.tp2_hit:
                                logger.info(f"[{ticker}] TP2 target (2.0R) reached for trade {trade_id}.")
                                trade.tp2_hit = True
                                db.commit()
                                # Close 30% of original lot. Since 50% remains, we close 60% of the remaining lot (0.3 / 0.5 = 0.6)
                                await self._execute_close(trade, price, "TP2 Hit (2.0R)", close_pct=0.6)
                                # Move SL to 1.0R Profit Lock
                                lock_sl = entry + initial_risk if action == "BUY" else entry - initial_risk
                                await self.broker.modify_order(trade_id, stop_loss=lock_sl)
                                trade.sl_price = lock_sl
                                db.commit()
                                db.close()
                                continue
                                
                            if current_r >= 3.0 and not trade.tp3_hit:
                                logger.info(f"[{ticker}] TP3 target (3.0R) reached for trade {trade_id}. Closing remaining position.")
                                trade.tp3_hit = True
                                db.commit()
                                await self._execute_close(trade, price, "TP3 Hit (3.0R)", close_pct=1.0)
                                db.close()
                                continue
                        else:
                            # Standard 1R BE update if not using partial TP
                            if current_r >= 1.0 and trade.status == TradeStatus.OPEN:
                                await self.broker.modify_order(trade_id, stop_loss=entry)
                                trade.status = TradeStatus.RUNNING
                                trade.sl_price = entry
                                db.commit()
                                logger.info(f"[{ticker}] 1R Reached. SL moved to BE ({entry:.2f})")
                                
                            # Standard 3R trailing if not using partial TP
                            if current_r >= 3.0:
                                if action == "BUY":
                                    new_sl = price - initial_risk
                                    if new_sl > sl:
                                        await self.broker.modify_order(trade_id, stop_loss=new_sl)
                                        trade.sl_price = new_sl
                                        db.commit()
                                else:
                                    new_sl = price + initial_risk
                                    if new_sl < sl:
                                        await self.broker.modify_order(trade_id, stop_loss=new_sl)
                                        trade.sl_price = new_sl
                                        db.commit()
                        
                        # 2. Adaptive Trailing Stops
                        if FEATURE_FLAGS.get("adaptive_trailing", True) and not FEATURE_FLAGS.get("partial_tp", False):
                            atr = trade.atr_at_entry or (initial_risk * 0.5)
                            if 1.5 <= current_r < 2.5:
                                # Trailing 2 ATR
                                trailing_sl = price - 2 * atr if action == "BUY" else price + 2 * atr
                                if (action == "BUY" and trailing_sl > sl) or (action == "SELL" and trailing_sl < sl):
                                    await self.broker.modify_order(trade_id, stop_loss=trailing_sl)
                                    trade.sl_price = trailing_sl
                                    db.commit()
                                    logger.info(f"[{ticker}] Adaptive Trailing: SL moved to {trailing_sl:.2f} (2 ATR)")
                            elif 2.5 <= current_r < 3.5:
                                # Trailing 1.5 ATR
                                trailing_sl = price - 1.5 * atr if action == "BUY" else price + 1.5 * atr
                                if (action == "BUY" and trailing_sl > sl) or (action == "SELL" and trailing_sl < sl):
                                    await self.broker.modify_order(trade_id, stop_loss=trailing_sl)
                                    trade.sl_price = trailing_sl
                                    db.commit()
                                    logger.info(f"[{ticker}] Adaptive Trailing: SL moved to {trailing_sl:.2f} (1.5 ATR)")
                            elif current_r >= 3.5:
                                # Chandelier Exit (trailing 1 ATR from extreme price)
                                if action == "BUY":
                                    peak = trade.highest_price
                                    trailing_sl = peak - 1 * atr
                                else:
                                    peak = trade.lowest_price
                                    trailing_sl = peak + 1 * atr
                                if (action == "BUY" and trailing_sl > sl) or (action == "SELL" and trailing_sl < sl):
                                    await self.broker.modify_order(trade_id, stop_loss=trailing_sl)
                                    trade.sl_price = trailing_sl
                                    db.commit()
                                    logger.info(f"[{ticker}] Chandelier Exit: SL moved to {trailing_sl:.2f} (1 ATR from {'lowest' if action == 'SELL' else 'highest'} {peak:.2f})")
                        
                        # 3. Check Standard Exit Conditions
                        if sl is None:
                            logger.warning(f"[{ticker}] SL price is None for trade {trade_id}. Skipping SL check.")
                        if tp is None:
                            logger.warning(f"[{ticker}] TP price is None for trade {trade_id}. Skipping TP check.")
                        
                        sl_hit = sl is not None and ((action == "BUY" and price <= sl) or (action == "SELL" and price >= sl))
                        tp_hit = tp is not None and ((action == "BUY" and price >= tp) or (action == "SELL" and price <= tp))
                        
                        if sl_hit:
                            logger.info(f"[{ticker}] SL hit at {price:.4f} (SL: {sl:.4f}) for trade {trade_id}. Closing position.")
                            await self._execute_close(trade, sl, "SL/Trailing Hit", close_pct=1.0)
                        elif tp_hit:
                            logger.info(f"[{ticker}] TP hit at {price:.4f} (TP: {tp:.4f}) for trade {trade_id}. Closing position.")
                            await self._execute_close(trade, tp, "TP Hit", close_pct=1.0)
                        
                        db.close()
                        
            except Exception as e:
                logger.error(f"Error in trade monitor: {e}")

    async def process_regime_changes(self):
        logger.info("Execution Engine listening to CH_MARKET_REGIME...")
        from backend.config import FEATURE_FLAGS
        
        async for msg in self.event_bus.subscribe_group(CH_MARKET_REGIME, "exec_regime_group", "exec_regime_worker_1"):
            try:
                event = MarketRegimeEvent(**msg)
                ticker = event.ticker
                new_regime = event.regime
                
                db = SessionLocal()
                trades = db.query(Trade).filter(
                    Trade.ticker == ticker,
                    Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
                ).all()
                
                for trade in trades:
                    async with cb_manager.get_trade_lock(trade.id):
                        # Reload trade within the active transaction context
                        trade_rec = db.query(Trade).filter(Trade.id == trade.id).first()
                        if not trade_rec or trade_rec.status in [TradeStatus.CLOSED, TradeStatus.CANCELLED]:
                            continue
                            
                        for rule in REGIME_CHANGE_EXIT_RULES:
                            if new_regime == rule["to_regime"] and trade_rec.market_regime in rule["from_regimes"]:
                                hours_held = (datetime.utcnow() - trade_rec.opened_at).total_seconds() / 3600
                                if hours_held >= rule["max_hold_hours"]:
                                    price = self.latest_prices.get(ticker)
                                    if not price:
                                        continue
                                        
                                    initial_risk = abs(trade_rec.entry_price - trade_rec.sl_price)
                                    if initial_risk <= 0:
                                        continue
                                        
                                    action = trade_rec.action.value if hasattr(trade_rec.action, "value") else trade_rec.action
                                    current_r = (price - trade_rec.entry_price) / initial_risk if action == "BUY" else (trade_rec.entry_price - price) / initial_risk
                                    
                                    # Trigger if price hasn't reached TP1 (current_r < 1.0)
                                    if current_r < 1.0:
                                        logger.info(f"Regime change exit triggered for trade {trade_rec.id} ({ticker}): {trade_rec.market_regime} -> {new_regime}")
                                        
                                        # Partial or full close
                                        pct = rule["partial_close_pct"]
                                        await self._execute_close(trade_rec, price, f"Regime Exit ({trade_rec.market_regime} -> {new_regime})", close_pct=pct)
                                        
                                        # Tighten SL to BE
                                        if rule.get("tighten_sl_to") == "BE":
                                            await self.broker.modify_order(trade_rec.id, stop_loss=trade_rec.entry_price)
                                            trade_rec.sl_price = trade_rec.entry_price
                                            db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Error in process_regime_changes: {e}")

def start_execution_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    from backend.brokers.paper import BrokerHeartbeat
    engine = ExecutionEngine(event_bus)
    registry.register(engine.process_approved_signals(), name="exec_process_signals")
    registry.register(engine.monitor_active_trades(), name="exec_monitor_trades")
    registry.register(engine.process_regime_changes(), name="exec_process_regime_changes")
    
    heartbeat = BrokerHeartbeat(engine.broker, interval=30)
    registry.register(heartbeat.start(), name="broker_heartbeat")
