import asyncio
import logging

from backend.shared.events.core import EventBus, CH_SIGNALS, CH_RISK_APPROVED, CH_RISK_REJECTED
from backend.shared.schema.events import SignalEvent, RiskApprovedEvent, RiskRejectedEvent

logger = logging.getLogger("risk-engine")

# Hardcoded config for MVP
MAX_POSITION_SIZE = 1000.0
MAX_DRAWDOWN = 0.05
ACCOUNT_BALANCE = 10000.0
OPEN_POSITIONS = {} # {ticker: exposure}

class RiskEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def process_signals(self):
        logger.info("Risk Engine listening to CH_SIGNALS...")
        async for msg in self.event_bus.subscribe(CH_SIGNALS):
            try:
                signal = SignalEvent(**msg)
                
                # Check current exposure
                current_exposure = OPEN_POSITIONS.get(signal.ticker, 0.0)
                
                if current_exposure > MAX_POSITION_SIZE:
                    reject = RiskRejectedEvent(
                        ticker=signal.ticker,
                        action=signal.signal_type,
                        reason="Max position size reached"
                    )
                    await self.event_bus.publish(CH_RISK_REJECTED, reject.model_dump())
                    logger.info(f"Rejected {signal.signal_type} for {signal.ticker}: Max position size reached")
                    continue
                    
                if signal.confidence_score < 0.7:
                    reject = RiskRejectedEvent(
                        ticker=signal.ticker,
                        action=signal.signal_type,
                        reason="Confidence score too low"
                    )
                    await self.event_bus.publish(CH_RISK_REJECTED, reject.model_dump())
                    logger.info(f"Rejected {signal.signal_type} for {signal.ticker}: Confidence < 0.7")
                    continue
                    
                # Calculate lot size and dynamic SL/TP based on confidence
                lot_size = min(ACCOUNT_BALANCE * 0.02, MAX_POSITION_SIZE - current_exposure) # 2% risk per trade
                
                approve = RiskApprovedEvent(
                    ticker=signal.ticker,
                    action=signal.signal_type,
                    lot_size=lot_size,
                    signal_price=signal.price_at_signal,
                    stop_loss=signal.price_at_signal * 0.95 if signal.signal_type == "BUY" else signal.price_at_signal * 1.05,
                    take_profit=signal.price_at_signal * 1.10 if signal.signal_type == "BUY" else signal.price_at_signal * 0.90,
                    strategy_name=signal.strategy_name
                )
                
                await self.event_bus.publish(CH_RISK_APPROVED, approve.model_dump())
                logger.info(f"Approved {signal.signal_type} for {signal.ticker}. Lot: {lot_size}")
                
            except Exception as e:
                logger.error(f"Error processing signal in Risk Engine: {e}")

def start_risk_engine(event_bus: EventBus):
    engine = RiskEngine(event_bus)
    asyncio.create_task(engine.process_signals())
