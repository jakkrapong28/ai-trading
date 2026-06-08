import asyncio
import logging
from typing import Dict

from backend.shared.events.core import (
    EventBus, CH_SIGNALS, CH_RISK_APPROVED, CH_RISK_REJECTED,
    CH_EXEC_OPENED, CH_EXEC_CLOSED
)
from backend.shared.schema.events import SignalEvent, RiskApprovedEvent, RiskRejectedEvent, ExecutionEvent
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus

logger = logging.getLogger("risk-engine")

# Risk Config
MAX_DRAWDOWN_PCT = 0.05        # 5% max drawdown
RISK_PER_TRADE_PCT = 0.02      # 2% per trade
MIN_CONFIDENCE = 0.65          # ต้องมีความมั่นใจ ≥ 65%
ACCOUNT_BALANCE = 10000.0      # จะถูก sync จาก portfolio

class RiskEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # open_positions: {ticker: exposure_dollars} — sync กับ DB จริง
        self.open_positions: Dict[str, float] = {}
        self.account_balance = ACCOUNT_BALANCE

    def _sync_positions_from_db(self):
        """โหลด open positions จริงจาก PostgreSQL"""
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING])
            ).all()

            self.open_positions = {}
            for trade in open_trades:
                exposure = (trade.lot_size or 0.01) * (trade.entry_price or 0) * 100
                self.open_positions[trade.ticker] = (
                    self.open_positions.get(trade.ticker, 0.0) + exposure
                )
            logger.debug(f"[Risk] Synced positions from DB: {self.open_positions}")
        except Exception as e:
            logger.error(f"[Risk] Error syncing positions from DB: {e}")
        finally:
            db.close()

    def _get_total_exposure(self) -> float:
        return sum(self.open_positions.values())

    def _check_max_drawdown(self) -> bool:
        """ตรวจสอบว่า total exposure ไม่เกิน max drawdown"""
        total_exposure = self._get_total_exposure()
        return total_exposure <= self.account_balance * MAX_DRAWDOWN_PCT * 10

    async def process_signals(self):
        """รับ signals จาก CH_SIGNALS และประเมิน risk"""
        logger.info("Risk Engine listening to CH_SIGNALS...")
        async for msg in self.event_bus.subscribe(CH_SIGNALS):
            try:
                signal = SignalEvent(**msg)

                # Sync positions จาก DB ก่อนประเมินทุกครั้ง
                await asyncio.to_thread(self._sync_positions_from_db)

                # ─── Check 1: Confidence Score ───
                if signal.confidence_score < MIN_CONFIDENCE:
                    await self._reject(signal, f"Confidence {signal.confidence_score:.2f} < {MIN_CONFIDENCE}")
                    continue

                # ─── Check 2: Per-ticker max exposure ───
                current_exposure = self.open_positions.get(signal.ticker, 0.0)
                max_position = self.account_balance * 0.20  # max 20% per ticker
                if current_exposure >= max_position:
                    await self._reject(
                        signal,
                        f"Ticker {signal.ticker} exposure ${current_exposure:.0f} ≥ max ${max_position:.0f}"
                    )
                    continue

                # ─── Check 3: Total portfolio exposure ───
                total_exp = self._get_total_exposure()
                max_total = self.account_balance * 0.40  # max 40% total
                if total_exp >= max_total:
                    await self._reject(
                        signal,
                        f"Total portfolio exposure ${total_exp:.0f} ≥ max ${max_total:.0f}"
                    )
                    continue

                # ─── Calculate dynamic lot size (ATR-based) ───
                risk_dollars = self.account_balance * RISK_PER_TRADE_PCT
                stop_distance_pct = 0.02  # 2% stop distance from price
                lot_size = min(
                    risk_dollars,
                    max_position - current_exposure
                )
                lot_size = max(lot_size, 10.0)  # floor $10

                # Calculate SL/TP from confidence-adjusted ATR proxy
                price = signal.price_at_signal
                if price and price > 0:
                    sl_pct = stop_distance_pct * (2.0 - signal.confidence_score)  # tighter SL on high confidence
                    tp_pct = sl_pct * 2.0  # 1:2 RR minimum
                    if signal.signal_type == "BUY":
                        stop_loss = round(price * (1 - sl_pct), 4)
                        take_profit = round(price * (1 + tp_pct), 4)
                    else:
                        stop_loss = round(price * (1 + sl_pct), 4)
                        take_profit = round(price * (1 - tp_pct), 4)
                else:
                    stop_loss = 0.0
                    take_profit = 0.0

                # ─── Approve ───
                approve = RiskApprovedEvent(
                    ticker=signal.ticker,
                    action=signal.signal_type,
                    lot_size=round(lot_size, 2),
                    signal_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy_name=signal.strategy_name
                )

                await self.event_bus.publish(CH_RISK_APPROVED, approve.model_dump())
                logger.info(
                    f"[Risk] ✅ Approved {signal.signal_type} {signal.ticker} "
                    f"| Conf: {signal.confidence_score:.2f} | Lot: ${lot_size:.2f}"
                )

            except Exception as e:
                logger.error(f"[Risk] Error processing signal: {e}")

    async def track_executions(self):
        """ติดตาม execution events เพื่ออัปเดต exposure realtime"""
        async def on_opened():
            async for msg in self.event_bus.subscribe(CH_EXEC_OPENED):
                try:
                    event = ExecutionEvent(**msg)
                    exposure = (event.lot_size or 0) * (event.entry_price or 0) * 100
                    self.open_positions[event.ticker] = (
                        self.open_positions.get(event.ticker, 0.0) + exposure
                    )
                    logger.debug(f"[Risk] Updated exposure for {event.ticker}: ${self.open_positions[event.ticker]:.0f}")
                except Exception as e:
                    logger.error(f"[Risk] Error tracking opened: {e}")

        async def on_closed():
            async for msg in self.event_bus.subscribe(CH_EXEC_CLOSED):
                try:
                    event = ExecutionEvent(**msg)
                    # Re-sync from DB on close
                    await asyncio.to_thread(self._sync_positions_from_db)
                except Exception as e:
                    logger.error(f"[Risk] Error tracking closed: {e}")

        asyncio.create_task(on_opened())
        asyncio.create_task(on_closed())

    async def _reject(self, signal: SignalEvent, reason: str):
        reject = RiskRejectedEvent(
            ticker=signal.ticker,
            action=signal.signal_type,
            reason=reason
        )
        await self.event_bus.publish(CH_RISK_REJECTED, reject.model_dump())
        logger.info(f"[Risk] ❌ Rejected {signal.signal_type} {signal.ticker}: {reason}")


def start_risk_engine(event_bus: EventBus):
    engine = RiskEngine(event_bus)
    asyncio.create_task(engine.process_signals())
    asyncio.create_task(engine.track_executions())
