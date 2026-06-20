import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from backend.brokers.base import BrokerAdapter
from backend.shared.database.core import run_db
from backend.shared.database.models import Trade, TradeStatus, TradeAction
from backend.core.base import trade_pnl, compute_fee
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

        def _work(db):
            trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()
            return [t.id for t in trades]
        return await run_db(_work)

    async def reconcile_positions(self):
        try:
            def _open_ids(db):
                return [
                    t.id for t in db.query(Trade).filter(
                        Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
                    ).all()
                ]
            db_position_ids = await run_db(_open_ids)
            mt5_positions = await self.get_mt5_positions()
            diverged = [pid for pid in db_position_ids if pid not in mt5_positions]
            for pid in diverged:
                logger.warning(f"⚠️ Position {pid} diverged — DB says OPEN, MT5 says CLOSED")

            if diverged:
                def _close(db):
                    for pid in diverged:
                        pos = db.query(Trade).filter(Trade.id == pid).first()
                        if pos:
                            pos.status = TradeStatus.CLOSED
                            pos.closed_at = datetime.utcnow()
                    db.commit()
                await run_db(_close)
                await send_alert("ERROR", f"⚠️ Position {len(diverged)} trades diverged — auto-closed in DB")
        except Exception as e:
            logger.error(f"Error reconciling positions: {e}")

    async def place_order(self, ticker: str, action: str, lot_size: float, stop_loss: float, take_profit: float, entry_price: float = None, market_regime: str = None, atr_at_entry: float = None) -> Dict[str, Any]:
        if entry_price is None:
            raise ValueError("entry_price is required for PaperBroker")

        trade_id = str(uuid.uuid4())

        def _work(db):
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
        return await run_db(_work)

    async def close_order(self, order_id: str, exit_price: float = None) -> Dict[str, Any]:
        if exit_price is None:
            raise ValueError("exit_price is required for closing paper order")

        def _work(db):
            trade = db.query(Trade).filter(Trade.id == order_id).first()
            if not trade:
                raise ValueError(f"Trade {order_id} not found")

            trade.status = TradeStatus.CLOSED
            trade.exit_price = exit_price
            trade.closed_at = datetime.utcnow()

            # PnL via single source of truth (contractSize-correct for XAUUSD/EURUSD).
            action = trade.action.value if hasattr(trade.action, "value") else trade.action
            realized = trade_pnl(trade.ticker, action, trade.entry_price, exit_price, trade.lot_size)
            fee = compute_fee(trade.ticker, exit_price, trade.lot_size)

            trade.realized_pnl = (trade.realized_pnl or 0.0) + realized
            trade.fee = (trade.fee or 0.0) + fee
            db.commit()

            return {
                "order_id": order_id,
                "status": "CLOSED",
                "exit_price": exit_price,
                "realized_pnl": realized,
                "fee": fee
            }
        return await run_db(_work)

    async def partial_close_order(self, order_id: str, close_pct: float, exit_price: float) -> Dict[str, Any]:
        if exit_price is None:
            raise ValueError("exit_price is required for partial close")
        if not (0.0 < close_pct < 1.0):
            raise ValueError("close_pct must be between 0 and 1 (exclusive)")

        def _work(db):
            trade = db.query(Trade).filter(Trade.id == order_id).first()
            if not trade:
                raise ValueError(f"Trade {order_id} not found")

            closed_lot = round(trade.lot_size * close_pct, 4)
            remaining_lot = round(trade.lot_size - closed_lot, 4)

            # Realized PnL + fee for the closed portion (contractSize-correct).
            action = trade.action.value if hasattr(trade.action, "value") else trade.action
            realized = trade_pnl(trade.ticker, action, trade.entry_price, exit_price, closed_lot)
            fee = compute_fee(trade.ticker, exit_price, closed_lot)

            # Update the existing trade lot size to remaining
            trade.lot_size = remaining_lot
            trade.status = TradeStatus.PARTIAL
            trade.realized_pnl = (trade.realized_pnl or 0.0) + realized
            trade.fee = (trade.fee or 0.0) + fee

            db.commit()

            return {
                "order_id": order_id,
                "status": "PARTIAL",
                "closed_lot": closed_lot,
                "remaining_lot": remaining_lot,
                "exit_price": exit_price,
                "realized_pnl": realized,
                "fee": fee
            }
        return await run_db(_work)

    async def modify_order(self, order_id: str, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        def _work(db):
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
        return await run_db(_work)

    async def get_positions(self) -> List[Dict[str, Any]]:
        def _work(db):
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
        return await run_db(_work)

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
        # Freeze trading: drop to watch mode + raise the critical-watch flag so the
        # Risk Engine stops approving new orders. A paper broker can't reach an
        # external venue to flatten, so we halt new exposure rather than blind-close.
        import os
        os.environ["CURRENT_MODE"] = "watch"
        os.environ["PORTFOLIO_CRITICAL_WATCH"] = "true"
        await send_alert(
            "CRITICAL",
            f"🚨 MT5 disconnect after {self.reconnect_attempts} attempts — last heartbeat: "
            f"{self.last_heartbeat}. Trading frozen (mode→watch).",
        )
