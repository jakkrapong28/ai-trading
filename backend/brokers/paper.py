import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.brokers.base import BrokerAdapter
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, TradeAction
from backend.alert import send_alert

logger = logging.getLogger("broker-paper")

class PaperBroker(BrokerAdapter):
    """
    Paper broker implementation.
    Reads and writes directly to the local Trade database table.
    """
    def __init__(self):
        self._mock_mt5_positions: Optional[List[str]] = None
        self._ping_fail: bool = False

    async def ping(self) -> bool:
        return not self._ping_fail

    async def get_mt5_positions(self) -> List[str]:
        if self._mock_mt5_positions is not None:
            return self._mock_mt5_positions
        db = SessionLocal()
        try:
            trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()
            return [t.id for t in trades]
        finally:
            db.close()

    async def reconcile_positions(self):
        db = SessionLocal()
        try:
            db_positions = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()
            mt5_positions = await self.get_mt5_positions()
            diverged_count = 0
            for pos in db_positions:
                if pos.id not in mt5_positions:
                    logger.warning(f"⚠️ Position {pos.id} diverged — DB says OPEN, MT5 says CLOSED")
                    pos.status = TradeStatus.CLOSED
                    pos.closed_at = datetime.utcnow()
                    diverged_count += 1
            if diverged_count > 0:
                db.commit()
                await send_alert("ERROR", f"⚠️ Position {diverged_count} trades diverged — auto-closed in DB")
        except Exception as e:
            db.rollback()
            logger.error(f"Error reconciling positions: {e}")
        finally:
            db.close()

    async def place_order(self, ticker: str, action: str, lot_size: float, stop_loss: float, take_profit: float, entry_price: float = None, market_regime: str = None, atr_at_entry: float = None) -> Dict[str, Any]:
        if entry_price is None:
            raise ValueError("entry_price is required for PaperBroker")

        trade_id = str(uuid.uuid4())
        
        db = SessionLocal()
        try:
            trade = Trade(
                id=trade_id,
                ticker=ticker,
                action=TradeAction[action],
                status=TradeStatus.OPEN,
                lot_size=lot_size,
                entry_price=entry_price,
                sl_price=stop_loss,
                tp_price=take_profit,
                market_regime=market_regime,
                atr_at_entry=atr_at_entry
            )
            db.add(trade)
            db.commit()
            
            return {
                "order_id": trade_id,
                "status": "OPEN",
                "filled_price": entry_price
            }
        finally:
            db.close()

    async def close_order(self, order_id: str, exit_price: float = None) -> Dict[str, Any]:
        if exit_price is None:
            raise ValueError("exit_price is required for closing paper order")
            
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == order_id).first()
            if not trade:
                raise ValueError(f"Trade {order_id} not found")
                
            trade.status = TradeStatus.CLOSED
            trade.exit_price = exit_price
            trade.closed_at = datetime.utcnow()
            
            # Calculate PnL
            if trade.action == TradeAction.BUY:
                realized = (exit_price - trade.entry_price) * trade.lot_size
            else:
                realized = (trade.entry_price - exit_price) * trade.lot_size
                
            trade.realized_pnl = realized
            db.commit()
            
            return {
                "order_id": order_id,
                "status": "CLOSED",
                "exit_price": exit_price,
                "realized_pnl": realized
            }
        finally:
            db.close()

    async def partial_close_order(self, order_id: str, close_pct: float, exit_price: float) -> Dict[str, Any]:
        if exit_price is None:
            raise ValueError("exit_price is required for partial close")
        if not (0.0 < close_pct < 1.0):
            raise ValueError("close_pct must be between 0 and 1 (exclusive)")

        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == order_id).first()
            if not trade:
                raise ValueError(f"Trade {order_id} not found")

            closed_lot = round(trade.lot_size * close_pct, 4)
            remaining_lot = round(trade.lot_size - closed_lot, 4)

            # Calculate realized PnL for the closed portion
            if trade.action == TradeAction.BUY:
                realized = (exit_price - trade.entry_price) * closed_lot
            else:
                realized = (trade.entry_price - exit_price) * closed_lot

            # Update the existing trade lot size to remaining
            trade.lot_size = remaining_lot
            trade.status = TradeStatus.PARTIAL
            if trade.realized_pnl is None:
                trade.realized_pnl = 0.0
            trade.realized_pnl += realized

            db.commit()

            return {
                "order_id": order_id,
                "status": "PARTIAL",
                "closed_lot": closed_lot,
                "remaining_lot": remaining_lot,
                "exit_price": exit_price,
                "realized_pnl": realized
            }
        finally:
            db.close()

    async def modify_order(self, order_id: str, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            trade = db.query(Trade).filter(Trade.id == order_id).first()
            if not trade:
                raise ValueError(f"Trade {order_id} not found")
                
            if stop_loss is not None:
                trade.sl_price = stop_loss
            if take_profit is not None:
                trade.tp_price = take_profit
                
            db.commit()
            
            return {
                "order_id": order_id,
                "status": trade.status.value,
                "sl_price": trade.sl_price,
                "tp_price": trade.tp_price
            }
        finally:
            db.close()

    async def get_positions(self) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()
            
            return [
                {
                    "order_id": t.id,
                    "ticker": t.ticker,
                    "action": t.action.value,
                    "status": t.status.value,
                    "lot_size": t.lot_size,
                    "entry_price": t.entry_price,
                    "sl_price": t.sl_price,
                    "tp_price": t.tp_price
                }
                for t in trades
            ]
        finally:
            db.close()

class SimulationBroker(PaperBroker):
    """
    SimulationBroker behaves identically to PaperBroker for now.
    """
    pass

class BrokerHeartbeat:
    _instance = None
    
    def __init__(self, broker: PaperBroker, interval: int = 30):
        self.broker = broker
        self.interval = interval
        self.last_heartbeat: Optional[datetime] = None
        self.reconnect_attempts = 0
        BrokerHeartbeat._instance = self

    async def start(self):
        logger.info("Starting Broker Heartbeat loop...")
        while True:
            try:
                ok = await self.broker.ping()
                if ok:
                    self.last_heartbeat = datetime.now(timezone.utc)
                    self.reconnect_attempts = 0
                    await self.broker.reconcile_positions()
                else:
                    logger.warning("⚠️ MT5 heartbeat failed")
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= 3:
                        await self.handle_disconnect()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broker heartbeat loop: {e}")
                await asyncio.sleep(self.interval)

    async def handle_disconnect(self):
        await send_alert("CRITICAL", f"🚨 MT5 disconnect after {self.reconnect_attempts} attempts — last heartbeat: {self.last_heartbeat}")
