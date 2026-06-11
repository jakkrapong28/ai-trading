import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from backend.shared.events.core import EventBus, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_SNAPSHOT, CH_SIGNALS, CH_AI_DECISION, CH_RISK_APPROVED, CH_RISK_REJECTED
from backend.shared.schema.events import ExecutionEvent, PortfolioSnapshotEvent, SignalEvent, AIDecisionEvent, RiskApprovedEvent, RiskRejectedEvent
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeAction, TradeStatus, PortfolioSnapshot, TradeLedger, TaxLedger

logger = logging.getLogger("portfolio-engine")

INITIAL_BALANCE = 10000.0
DAILY_DRAWDOWN_LIMIT = 0.03
WEEKLY_DRAWDOWN_LIMIT = 0.08
MAX_CONSECUTIVE_LOSSES = 5

global_metrics = {
    "Signals Generated": 0,
    "Signals Approved": 0,
    "Signals Rejected": 0,
    "Risk Rejected": 0,
    "Debate Rejected": 0,
    "Orders Opened": 0,
    "Orders Closed": 0,
    "Win Rate": 0.0,
    "Loss Rate": 0.0,
    "Profit Factor": 0.0,
    "Average RR": 0.0,
    "Current Drawdown": 0.0,
    "Portfolio Exposure": 0.0
}

class PortfolioEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.balance = INITIAL_BALANCE
        self.consecutive_losses = 0
        self.watch_mode = False
        
    def _init_from_db(self):
        db = SessionLocal()
        try:
            closed_trades = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
            total_pnl = sum([t.realized_pnl for t in closed_trades if t.realized_pnl])
            self.balance = INITIAL_BALANCE + total_pnl
            
            self.consecutive_losses = 0
            for t in sorted(closed_trades, key=lambda x: x.closed_at or datetime.min, reverse=True):
                if t.realized_pnl and t.realized_pnl < 0:
                    self.consecutive_losses += 1
                else:
                    break
                    
            self._update_metrics(db)
            self._check_watch_mode(db)
        except Exception as e:
            logger.error(f"Error initializing portfolio from DB: {e}")
        finally:
            db.close()
            
    def _update_metrics(self, db):
        closed_trades = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
        wins = [t.realized_pnl for t in closed_trades if t.realized_pnl and t.realized_pnl > 0]
        losses = [t.realized_pnl for t in closed_trades if t.realized_pnl and t.realized_pnl <= 0]
        
        global_metrics["Orders Closed"] = len(closed_trades)
        
        if closed_trades:
            global_metrics["Win Rate"] = len(wins) / len(closed_trades)
            global_metrics["Loss Rate"] = len(losses) / len(closed_trades)
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        global_metrics["Profit Factor"] = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

        # Drawdown calculation
        peak_equity = max([INITIAL_BALANCE] + [INITIAL_BALANCE + sum([t.realized_pnl for t in closed_trades[:i]]) for i in range(1, len(closed_trades)+1)])
        current_equity = self.balance
        global_metrics["Current Drawdown"] = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0

    def _check_watch_mode(self, db):
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_day - timedelta(days=now.weekday())
        
        daily_trades = db.query(Trade).filter(
            Trade.status == TradeStatus.CLOSED,
            Trade.closed_at >= start_of_day.replace(tzinfo=None)
        ).all()
        daily_pnl = sum([t.realized_pnl for t in daily_trades if t.realized_pnl])
        
        weekly_trades = db.query(Trade).filter(
            Trade.status == TradeStatus.CLOSED,
            Trade.closed_at >= start_of_week.replace(tzinfo=None)
        ).all()
        weekly_pnl = sum([t.realized_pnl for t in weekly_trades if t.realized_pnl])
        
        daily_dd = -daily_pnl / self.balance if daily_pnl < 0 else 0
        weekly_dd = -weekly_pnl / self.balance if weekly_pnl < 0 else 0
        
        if daily_dd >= DAILY_DRAWDOWN_LIMIT or weekly_dd >= WEEKLY_DRAWDOWN_LIMIT or self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            if not self.watch_mode:
                logger.warning(f"⚠️ PORTFOLIO WATCH MODE ACTIVATED. Daily DD: {daily_dd:.2%}, Weekly DD: {weekly_dd:.2%}, Consecutive Losses: {self.consecutive_losses}")
            self.watch_mode = True
            os.environ["PORTFOLIO_CRITICAL_WATCH"] = "true"
        else:
            if self.watch_mode:
                logger.info("🟢 PORTFOLIO WATCH MODE DEACTIVATED.")
            self.watch_mode = False
            os.environ["PORTFOLIO_CRITICAL_WATCH"] = "false"

    async def _track_metrics_events(self):
        # We just need to track the counters. Since event_bus.subscribe_group consumes, we use a different group name
        # to ensure it gets all events independently.
        
        async def count_signals():
            async for msg in self.event_bus.subscribe_group(CH_SIGNALS, "metrics_group", "metrics_worker_1"):
                global_metrics["Signals Generated"] += 1
                
        async def count_ai():
            async for msg in self.event_bus.subscribe_group(CH_AI_DECISION, "metrics_group", "metrics_worker_1"):
                decision = AIDecisionEvent(**msg)
                if decision.action == "REJECT":
                    global_metrics["Debate Rejected"] += 1
                    global_metrics["Signals Rejected"] += 1
                    
        async def count_risk():
            async for msg in self.event_bus.subscribe_group(CH_RISK_REJECTED, "metrics_group", "metrics_worker_1"):
                global_metrics["Risk Rejected"] += 1
                global_metrics["Signals Rejected"] += 1
                
        async def count_approved():
            async for msg in self.event_bus.subscribe_group(CH_RISK_APPROVED, "metrics_group", "metrics_worker_1"):
                global_metrics["Signals Approved"] += 1
                
        asyncio.create_task(count_signals())
        asyncio.create_task(count_ai())
        asyncio.create_task(count_risk())
        asyncio.create_task(count_approved())

    async def publish_snapshot(self):
        while True:
            try:
                db = SessionLocal()
                from backend.engines.market_data import latest_prices
                
                open_trades = db.query(Trade).filter(Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])).all()
                
                floating_pnl = 0.0
                margin_used = 0.0
                
                for t in open_trades:
                    current = latest_prices.get(t.ticker)
                    if current:
                        current_price = current["last_price"]
                        entry = t.entry_price or 0.0
                        lot = t.lot_size or 0.0
                        
                        if t.action == TradeAction.BUY:
                            pnl = (current_price - entry) * lot
                        else:
                            pnl = (entry - current_price) * lot
                            
                        floating_pnl += pnl
                        margin_used += entry * lot * 0.1 
                
                equity = self.balance + floating_pnl
                global_metrics["Portfolio Exposure"] = margin_used
                
                now = datetime.now(timezone.utc)
                start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
                start_of_week = start_of_day - timedelta(days=now.weekday())
                start_of_month = start_of_day.replace(day=1)
                
                closed = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()
                daily_pnl = sum([t.realized_pnl for t in closed if t.realized_pnl and t.closed_at and t.closed_at >= start_of_day.replace(tzinfo=None)])
                weekly_pnl = sum([t.realized_pnl for t in closed if t.realized_pnl and t.closed_at and t.closed_at >= start_of_week.replace(tzinfo=None)])
                monthly_pnl = sum([t.realized_pnl for t in closed if t.realized_pnl and t.closed_at and t.closed_at >= start_of_month.replace(tzinfo=None)])
                
                peak_equity = max([INITIAL_BALANCE] + [self.balance])
                drawdown = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
                
                snap_event = PortfolioSnapshotEvent(
                    balance=self.balance,
                    equity=equity,
                    margin=margin_used,
                    floating_pnl=floating_pnl,
                    daily_pnl=daily_pnl,
                    weekly_pnl=weekly_pnl,
                    monthly_pnl=monthly_pnl,
                    drawdown=drawdown
                )
                
                await self.event_bus.publish(CH_PORTFOLIO_SNAPSHOT, snap_event.model_dump())
                
                if now.minute == 0:
                    db_snap = PortfolioSnapshot(**snap_event.model_dump())
                    db.add(db_snap)
                    db.commit()
                
                db.close()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error publishing snapshot: {e}")
                await asyncio.sleep(60)

    async def process_executions(self):
        logger.info("Portfolio Engine listening to Executions...")
        
        async def handle_opened():
            async for msg in self.event_bus.subscribe_group(CH_EXEC_OPENED, "portfolio_group", "portfolio_worker_1"):
                try:
                    event = ExecutionEvent(**msg)
                    db = SessionLocal()
                    
                    ledger = TradeLedger(
                        trade_id=event.trade_id,
                        event_type="OPENED",
                        amount=0.0,
                        description=f"เปิดสัญญา {event.action} ขนาด {event.lot_size} Lot บนคู่ {event.ticker} ที่ราคา {event.entry_price}"
                    )
                    db.add(ledger)
                    db.commit()
                    db.close()
                    
                    global_metrics["Orders Opened"] += 1
                except Exception as e:
                    logger.error(f"Error recording open trade: {e}")

        async def handle_closed():
            async for msg in self.event_bus.subscribe_group(CH_EXEC_CLOSED, "portfolio_group", "portfolio_worker_1"):
                try:
                    event = ExecutionEvent(**msg)
                    db = SessionLocal()
                    
                    ledger = TradeLedger(
                        trade_id=event.trade_id,
                        event_type="CLOSED",
                        amount=event.realized_pnl,
                        description=f"ปิดสัญญาเทรดเรียบร้อย สรุปกำไร/ขาดทุนสุทธิ (PnL): ${event.realized_pnl}"
                    )
                    db.add(ledger)
                    
                    if event.realized_pnl and event.realized_pnl > 0:
                        tax = TaxLedger(
                            trade_id=event.trade_id,
                            tax_type="INCOME_TAX_EST",
                            amount=event.realized_pnl * 0.20
                        )
                        db.add(tax)
                        
                    db.commit()
                    
                    self.balance += (event.realized_pnl or 0)
                    if event.realized_pnl and event.realized_pnl < 0:
                        self.consecutive_losses += 1
                    else:
                        self.consecutive_losses = 0
                        
                    self._update_metrics(db)
                    self._check_watch_mode(db)
                    
                    db.close()
                    
                except Exception as e:
                    logger.error(f"Error recording closed trade: {e}")

        asyncio.create_task(handle_opened())
        asyncio.create_task(handle_closed())

def start_portfolio_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = PortfolioEngine(event_bus)
    engine._init_from_db()
    registry.register(engine._track_metrics_events(), name="portfolio_track_metrics")
    registry.register(engine.process_executions(), name="portfolio_process_exec")
    registry.register(engine.publish_snapshot(), name="portfolio_publish_snapshot")
