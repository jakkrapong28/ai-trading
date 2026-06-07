import asyncio
import logging
import uuid
import random

from backend.shared.events.core import EventBus, CH_RISK_APPROVED, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_EXEC_FAILED
from backend.shared.schema.events import RiskApprovedEvent, ExecutionEvent

logger = logging.getLogger("execution-engine")

class ExecutionEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def process_approved_signals(self):
        logger.info("Execution Engine listening to CH_RISK_APPROVED...")
        async for msg in self.event_bus.subscribe(CH_RISK_APPROVED):
            try:
                approved = RiskApprovedEvent(**msg)
                
                # Simulate execution delay and slippage
                await asyncio.sleep(random.uniform(0.1, 1.0))
                
                slippage = random.uniform(-0.001, 0.001)
                entry_price = approved.signal_price * (1 + slippage)
                
                trade_id = str(uuid.uuid4())
                
                if random.random() < 0.05: # 5% failure rate simulation
                    failed = ExecutionEvent(
                        trade_id=trade_id,
                        ticker=approved.ticker,
                        action=approved.action,
                        status="FAILED",
                        lot_size=approved.lot_size,
                        message="Exchange API timeout"
                    )
                    await self.event_bus.publish(CH_EXEC_FAILED, failed.model_dump())
                    logger.error(f"Trade {trade_id} failed to execute.")
                else:
                    opened = ExecutionEvent(
                        trade_id=trade_id,
                        ticker=approved.ticker,
                        action=approved.action,
                        status="OPEN",
                        lot_size=approved.lot_size,
                        entry_price=entry_price
                    )
                    await self.event_bus.publish(CH_EXEC_OPENED, opened.model_dump())
                    logger.info(f"Trade {trade_id} opened. {approved.action} {approved.ticker} at {entry_price:.2f}")
                    
            except Exception as e:
                logger.error(f"Error in Execution Engine: {e}")

def start_execution_engine(event_bus: EventBus):
    engine = ExecutionEngine(event_bus)
    asyncio.create_task(engine.process_approved_signals())
