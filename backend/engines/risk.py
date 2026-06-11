import asyncio
import logging
import json
from typing import Dict

from backend.shared.events.core import (
    EventBus, CH_AI_DECISION, CH_RISK_APPROVED, CH_RISK_REJECTED,
    CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_SNAPSHOT
)
from backend.shared.schema.events import AIDecisionEvent, RiskApprovedEvent, RiskRejectedEvent, ExecutionEvent, PortfolioSnapshotEvent
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus

logger = logging.getLogger("risk-engine")

RISK_PER_TRADE_PCT = 0.01      # 1% per trade
MAX_ASSET_PCT = 0.10           # 10% max per asset
MAX_PORTFOLIO_PCT = 0.20       # 20% total portfolio risk limit
MIN_CONFIDENCE = 0.60          # 60% min confidence from AI

class RiskEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.open_positions: Dict[str, float] = {} 
        self.account_balance = 10000.0 
        self.watch_mode = False 

    async def bootstrap_portfolio(self):
        try:
            logger.info("Bootstrapping portfolio snapshot from Redis Stream...")
            raw_data = await self.event_bus.redis.xrevrange("stream:portfolio:snapshot", "+", "-", count=10)
            if raw_data:
                msg_id, fields = raw_data[0]
                msg = json.loads(fields["payload"])
                snap = PortfolioSnapshotEvent(**msg)
                self.account_balance = snap.balance
                logger.info(f"Bootstrapped account balance: {self.account_balance}")
        except Exception as e:
            logger.error(f"Error bootstrapping portfolio: {e}")

    async def update_portfolio(self):
        await self.bootstrap_portfolio()
        async for msg in self.event_bus.subscribe_group(CH_PORTFOLIO_SNAPSHOT, "risk_portfolio_group", "risk_portfolio_worker_1"):
            try:
                snap = PortfolioSnapshotEvent(**msg)
                self.account_balance = snap.balance
            except Exception as e:
                logger.error(f"[Risk] Error updating portfolio: {e}")

    def _sync_positions_from_db(self):
        db = SessionLocal()
        try:
            open_trades = db.query(Trade).filter(
                Trade.status.in_([TradeStatus.PENDING, TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
            ).all()

            self.open_positions = {}
            for trade in open_trades:
                exposure = (trade.lot_size or 0.0) * (trade.entry_price or 0.0)
                self.open_positions[trade.ticker] = (
                    self.open_positions.get(trade.ticker, 0.0) + exposure
                )
        except Exception as e:
            logger.error(f"[Risk] Error syncing positions from DB: {e}")
        finally:
            db.close()

    def _get_total_exposure(self) -> float:
        return sum(self.open_positions.values())

    async def process_decisions(self):
        logger.info("Risk Engine listening to CH_AI_DECISION...")
        async for msg in self.event_bus.subscribe_group(CH_AI_DECISION, "risk_decision_group", "risk_decision_worker_1"):
            try:
                decision = AIDecisionEvent(**msg)

                if decision.action == "HOLD" or decision.action == "REJECT":
                    continue

                import os
                current_mode = os.getenv("CURRENT_MODE", "watch")
                portfolio_critical = os.getenv("PORTFOLIO_CRITICAL_WATCH", "false").lower() == "true"

                if current_mode == "watch" or portfolio_critical:
                    reason = "ระบบอยู่ในโหมดเฝ้าระวัง (Watch Mode) - ต้องอนุมัติเองด้วยมือ" if current_mode == "watch" else "พอร์ตชนขีดจำกัดขาดทุนสะสม (Drawdown Limit) - บังคับเข้าโหมดเฝ้าระวังอัตโนมัติ"
                    await self._reject(decision, reason)
                    continue

                await asyncio.to_thread(self._sync_positions_from_db)

                if decision.confidence < MIN_CONFIDENCE:
                    await self._reject(decision, f"ระดับความมั่นใจของ AI {decision.confidence:.2f} ต่ำกว่าเกณฑ์ขั้นต่ำ {MIN_CONFIDENCE}")
                    continue

                current_exposure = self.open_positions.get(decision.ticker, 0.0)
                max_asset_exp = self.account_balance * MAX_ASSET_PCT
                if current_exposure >= max_asset_exp:
                    await self._reject(decision, f"สัดส่วนการลงทุนสูงสุดสำหรับคู่ {decision.ticker} เกินขีดจำกัดแล้ว")
                    continue

                total_exp = self._get_total_exposure()
                max_total_exp = self.account_balance * MAX_PORTFOLIO_PCT
                if total_exp >= max_total_exp:
                    await self._reject(decision, "สัดส่วนการลงทุนรวมของทั้งพอร์ตเกินขีดจำกัด 20% แล้ว")
                    continue

                from backend.engines.market_data import get_latest_price
                price_data = get_latest_price(decision.ticker)
                if not price_data:
                    await self._reject(decision, "ไม่พบข้อมูลราคาตลาดสดล่าสุดเพื่อทำคำสั่งซื้อขาย")
                    continue
                
                price = price_data["last_price"]
                
                atr = price * 0.02 # Fallback 2%

                from backend.engines.market_regime import calculate_indicators, ticker_data
                df = ticker_data.get(decision.ticker)
                if df is not None and not df.empty:
                    inds = calculate_indicators(df)
                    atr = inds["atr"] or atr

                if atr <= 0:
                    await self._reject(decision, "ค่าความผันผวน ATR ผิดปกติ (<= 0)")
                    continue

                # Load dashboard risk configurations
                import backend.main as backend_main
                db_lot = backend_main.current_risk_input.get("lot", 0.01)
                db_sl = backend_main.current_risk_input.get("stopDistance", 20.0)
                db_tp = backend_main.current_risk_input.get("takeProfit", 40.0)
                db_spread = backend_main.current_risk_input.get("spread", 2.0)
                db_reject = backend_main.current_risk_input.get("rejectThreshold", 3.0)
                db_risk_pct = backend_main.current_risk_input.get("riskPct", 1.5)

                # Simulate broker spread
                import random
                broker_spread = round(random.uniform(1.5, 3.2), 2)
                
                # Check Reject > rejectThreshold (3.0) or broker_spread > spread limit
                if broker_spread > db_reject:
                    await self._reject(decision, f"สเปรดโบรกเกอร์ ({broker_spread}) เกินเกณฑ์ห้ามเทรดเด็ดขาด ({db_reject})")
                    continue
                if broker_spread > db_spread:
                    await self._reject(decision, f"สเปรดโบรกเกอร์ ({broker_spread}) เกินขีดจำกัดสเปรด ({db_spread})")
                    continue

                # Set parameters exactly from dashboard settings
                lot_size = db_lot
                sl_dist = db_sl
                tp_dist = db_tp

                if decision.action == "BUY":
                    stop_loss = price - sl_dist
                    take_profit = price + tp_dist
                else: 
                    stop_loss = price + sl_dist
                    take_profit = price - tp_dist

                # Validate order risk percentage against dashboard limit
                from backend.core import SYMBOLS
                spec = SYMBOLS.get(decision.ticker, SYMBOLS["XAUUSD"])
                contract_size = spec.get("contractSize", 100)
                risk_dollars = lot_size * sl_dist * contract_size
                risk_pct = (risk_dollars / self.account_balance) * 100
                if risk_pct > db_risk_pct:
                    await self._reject(decision, f"ความเสี่ยงของออเดอร์ ({risk_pct:.2f}%) เกินขีดจำกัดที่ตั้งไว้ ({db_risk_pct}%)")
                    continue

                approve = RiskApprovedEvent(
                    ticker=decision.ticker,
                    action=decision.action,
                    lot_size=round(lot_size, 4),
                    signal_price=price,
                    stop_loss=round(stop_loss, 4),
                    take_profit=round(take_profit, 4),
                    strategy_name="AIVotingStrategy",
                    atr_at_entry=atr
                )

                await self.event_bus.publish(CH_RISK_APPROVED, approve.model_dump())
                logger.info(f"[Risk] ✅ Approved {decision.action} {decision.ticker} | Lot: {lot_size:.4f} | SL: {stop_loss:.4f} | TP: {take_profit:.4f}")

            except Exception as e:
                logger.error(f"[Risk] Error processing AI decision: {e}")

    async def _reject(self, decision: AIDecisionEvent, reason: str):
        reject = RiskRejectedEvent(
            ticker=decision.ticker,
            action=decision.action,
            reason=reason
        )
        await self.event_bus.publish(CH_RISK_REJECTED, reject.model_dump())
        logger.info(f"[Risk] ❌ Rejected {decision.action} {decision.ticker}: {reason}")

def start_risk_engine(event_bus: EventBus):
    from backend.shared.tasks import registry
    engine = RiskEngine(event_bus)
    registry.register(engine.process_decisions(), name="risk_process_decisions")
    registry.register(engine.update_portfolio(), name="risk_update_portfolio")
