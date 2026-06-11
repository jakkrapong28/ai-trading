import uuid
from typing import List, Dict, Any
from datetime import datetime

from backend.brokers.base import BrokerAdapter
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus, TradeAction

class PaperBroker(BrokerAdapter):
    """
    Paper broker implementation.
    Reads and writes directly to the local Trade database table.
    """

    async def place_order(self, ticker: str, action: str, lot_size: float, stop_loss: float, take_profit: float, entry_price: float = None) -> Dict[str, Any]:
        if entry_price is None:
            # We would typically fetch latest price from market data engine here, 
            # but Execution Engine provides it.
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
                tp_price=take_profit
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
