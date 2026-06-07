import asyncio
import logging

from backend.shared.events.core import EventBus, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED
from backend.shared.schema.events import ExecutionEvent
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeAction, TradeStatus

logger = logging.getLogger("portfolio-engine")

class PortfolioEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def process_executions(self):
        logger.info("Portfolio Engine listening to Executions...")
        
        async def handle_opened():
            async for msg in self.event_bus.subscribe(CH_EXEC_OPENED):
                try:
                    event = ExecutionEvent(**msg)
                    db = SessionLocal()
                    
                    trade = Trade(
                        id=event.trade_id,
                        ticker=event.ticker,
                        action=TradeAction[event.action],
                        status=TradeStatus.OPEN,
                        lot_size=event.lot_size,
                        entry_price=event.entry_price
                    )
                    
                    db.add(trade)
                    db.commit()
                    db.close()
                    logger.info(f"Recorded new trade for {event.ticker} in Database")
                    
                    # Publish updated metrics
                    await self._publish_metrics()
                    
                except Exception as e:
                    logger.error(f"Error recording open trade: {e}")

        async def handle_closed():
            async for msg in self.event_bus.subscribe(CH_EXEC_CLOSED):
                try:
                    event = ExecutionEvent(**msg)
                    db = SessionLocal()
                    
                    trade = db.query(Trade).filter(Trade.id == event.trade_id).first()
                    if trade:
                        trade.status = TradeStatus.CLOSED
                        trade.exit_price = event.exit_price
                        trade.realized_pnl = event.realized_pnl
                        db.commit()
                        logger.info(f"Recorded closed trade for {event.ticker}. PNL: {event.realized_pnl}")
                    
                    db.close()
                    await self._publish_metrics()
                    
                except Exception as e:
                    logger.error(f"Error recording closed trade: {e}")

        asyncio.create_task(handle_opened())
        asyncio.create_task(handle_closed())

    async def _publish_metrics(self):
        db = SessionLocal()
        trades = db.query(Trade).all()
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.realized_pnl and t.realized_pnl > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        metrics = {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": sum([t.realized_pnl for t in trades if t.realized_pnl])
        }
        db.close()
        
        await self.event_bus.publish(CH_PORTFOLIO_UPDATED, metrics)

def start_portfolio_engine(event_bus: EventBus):
    engine = PortfolioEngine(event_bus)
    asyncio.create_task(engine.process_executions())
