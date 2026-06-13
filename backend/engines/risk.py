import asyncio
import logging
import json
import pytz
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any


from backend.shared.events.core import (
    EventBus, CH_AI_DECISION, CH_RISK_APPROVED, CH_RISK_REJECTED,
    CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_SNAPSHOT
)
from backend.shared.schema.events import AIDecisionEvent, RiskApprovedEvent, RiskRejectedEvent, ExecutionEvent, PortfolioSnapshotEvent
from backend.core import validate_atr, validate_price
from backend.shared.database.core import SessionLocal
from backend.shared.database.models import Trade, TradeStatus

logger = logging.getLogger("risk-engine")

RISK_PER_TRADE_PCT = 0.01      # 1% per trade
MAX_ASSET_PCT = 0.10           # 10% max per asset
MAX_PORTFOLIO_PCT = 0.20       # 20% total portfolio risk limit
MIN_CONFIDENCE = 0.60          # 60% min confidence from AI
MAX_POSITIONS_PER_SYMBOL = 2

CORRELATION_GROUPS = {
    "GOLD_SILVER": ["XAUUSD"],  # กลุ่มทอง — สามารถขยายเพิ่ม XAGUSD ในอนาคต
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "US_STOCKS": ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"],
    "FOREX": ["EURUSD"],
}

MAX_POSITIONS_PER_GROUP = 1  # 1 position ต่อกลุ่ม

CORRELATION_REJECTION_COUNT = 0



class CircuitBreakerManager:
    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self.breakers = {
            "daily_loss": {
                "active": False, "limit": 0.03,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            },
            "weekly_loss": {
                "active": False, "limit": 0.08,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            },
            "consecutive_loss": {
                "active": False, "limit": 5,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            },
            "news_flash": {
                "active": False, "events": ["FOMC", "NFP", "CPI", "FED"],
                "cooldown_hours": 1,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            },
            "volatility_spike": {
                "active": False, "threshold": 3.0,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            },
            "correlation_break": {
                "active": False,
                "triggered_at": None, "estimated_reset_at": None, "reason": ""
            }
        }

    def get_trade_lock(self, trade_id: str) -> asyncio.Lock:
        if trade_id not in self._locks:
            self._locks[trade_id] = asyncio.Lock()
        return self._locks[trade_id]

    def _get_next_reset(self, breaker_name: str) -> Optional[datetime]:
        import pytz
        from backend.config import TRADING_DAY_RESET_TZ
        ny_tz = pytz.timezone(TRADING_DAY_RESET_TZ)
        now_ny = datetime.now(ny_tz)

        if breaker_name == "daily_loss":
            next_reset = now_ny.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            return next_reset.astimezone(timezone.utc)

        if breaker_name == "weekly_loss":
            next_monday = now_ny + timedelta(days=(7 - now_ny.weekday()))
            return next_monday.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

        return None

    def update_breakers(self, daily_dd: float, weekly_dd: float, consecutive_losses: int):
        import pytz
        from backend.config import TRADING_DAY_RESET_TZ
        from backend.alert import send_alert
        now_utc = datetime.now(timezone.utc)

        # 1. daily_loss
        if daily_dd >= self.breakers["daily_loss"]["limit"]:
            if not self.breakers["daily_loss"]["active"]:
                self.breakers["daily_loss"]["active"] = True
                self.breakers["daily_loss"]["triggered_at"] = now_utc
                self.breakers["daily_loss"]["estimated_reset_at"] = self._get_next_reset("daily_loss")
                self.breakers["daily_loss"]["reason"] = f"Daily drawdown {daily_dd:.2%} exceeded limit {self.breakers['daily_loss']['limit']:.2%}"
                asyncio.create_task(send_alert("CRITICAL", f"🚨 Circuit Breaker: daily_loss — {self.breakers['daily_loss']['reason']} (reset: {self.breakers['daily_loss']['estimated_reset_at']})"))
        else:
            if self.breakers["daily_loss"]["active"]:
                reset_time = self.breakers["daily_loss"]["estimated_reset_at"]
                if reset_time and now_utc >= reset_time:
                    self.breakers["daily_loss"]["active"] = False
                    self.breakers["daily_loss"]["triggered_at"] = None
                    self.breakers["daily_loss"]["estimated_reset_at"] = None
                    self.breakers["daily_loss"]["reason"] = ""

        # 2. weekly_loss
        if weekly_dd >= self.breakers["weekly_loss"]["limit"]:
            if not self.breakers["weekly_loss"]["active"]:
                self.breakers["weekly_loss"]["active"] = True
                self.breakers["weekly_loss"]["triggered_at"] = now_utc
                self.breakers["weekly_loss"]["estimated_reset_at"] = self._get_next_reset("weekly_loss")
                self.breakers["weekly_loss"]["reason"] = f"Weekly drawdown {weekly_dd:.2%} exceeded limit {self.breakers['weekly_loss']['limit']:.2%}"
                asyncio.create_task(send_alert("CRITICAL", f"🚨 Circuit Breaker: weekly_loss — {self.breakers['weekly_loss']['reason']} (reset: {self.breakers['weekly_loss']['estimated_reset_at']})"))
        else:
            if self.breakers["weekly_loss"]["active"]:
                reset_time = self.breakers["weekly_loss"]["estimated_reset_at"]
                if reset_time and now_utc >= reset_time:
                    self.breakers["weekly_loss"]["active"] = False
                    self.breakers["weekly_loss"]["triggered_at"] = None
                    self.breakers["weekly_loss"]["estimated_reset_at"] = None
                    self.breakers["weekly_loss"]["reason"] = ""

        # 3. consecutive_loss
        if consecutive_losses >= self.breakers["consecutive_loss"]["limit"]:
            if not self.breakers["consecutive_loss"]["active"]:
                self.breakers["consecutive_loss"]["active"] = True
                self.breakers["consecutive_loss"]["triggered_at"] = now_utc
                self.breakers["consecutive_loss"]["reason"] = f"Consecutive losses count {consecutive_losses} reached limit {self.breakers['consecutive_loss']['limit']}"
                asyncio.create_task(send_alert("CRITICAL", f"🚨 Circuit Breaker: consecutive_loss — {self.breakers['consecutive_loss']['reason']}"))
        else:
            if self.breakers["consecutive_loss"]["active"] and consecutive_losses == 0:
                self.breakers["consecutive_loss"]["active"] = False
                self.breakers["consecutive_loss"]["triggered_at"] = None
                self.breakers["consecutive_loss"]["reason"] = ""

    def is_any_active(self) -> bool:
        from backend.config import FEATURE_FLAGS
        if not FEATURE_FLAGS.get("circuit_breaker_v2", True):
            import os
            return os.getenv("PORTFOLIO_CRITICAL_WATCH", "false").lower() == "true"
        return any(b["active"] for b in self.breakers.values())

    def get_active_reason(self) -> str:
        active_reasons = [f"{k}: {v['reason']}" for k, v in self.breakers.items() if v["active"]]
        return f"Circuit Breaker Triggered: {', '.join(active_reasons)}"

cb_manager = CircuitBreakerManager()


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
                cb_active = cb_manager.is_any_active()

                if current_mode == "watch" or cb_active:
                    reason = "ระบบอยู่ในโหมดเฝ้าระวัง (Watch Mode) - ต้องอนุมัติเองด้วยมือ" if current_mode == "watch" else cb_manager.get_active_reason()
                    await self._reject(decision, reason)
                    continue

                await asyncio.to_thread(self._sync_positions_from_db)

                db = SessionLocal()
                open_count = db.query(Trade).filter(
                    Trade.ticker == decision.ticker,
                    Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
                ).count()
                db.close()

                if open_count >= MAX_POSITIONS_PER_SYMBOL:
                    await self._reject(decision, f"จำนวน open position ของ {decision.ticker} ({open_count}) ถึงขีดจำกัด {MAX_POSITIONS_PER_SYMBOL} แล้ว")
                    continue

                from backend.config import FEATURE_FLAGS
                if FEATURE_FLAGS.get("correlation_cap", False):
                    group = None
                    for g_name, symbols in CORRELATION_GROUPS.items():
                        if decision.ticker in symbols:
                            group = g_name
                            break

                    if group:
                        db = SessionLocal()
                        group_open = db.query(Trade).filter(
                            Trade.ticker.in_(CORRELATION_GROUPS[group]),
                            Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
                        ).count()
                        db.close()

                        if group_open >= MAX_POSITIONS_PER_GROUP:
                            global CORRELATION_REJECTION_COUNT
                            CORRELATION_REJECTION_COUNT += 1
                            await self._reject(decision, f"กลุ่ม {group} มี open position ({group_open}) ถึงขีดจำกัด {MAX_POSITIONS_PER_GROUP} แล้ว — กันความเสี่ยง correlation")
                            continue

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
                
                price = validate_price(price_data["last_price"], f"risk.py: last_price for {decision.ticker}")
                
                atr = price * 0.02 # Fallback 2%

                regime = "SIDEWAYS"
                from backend.engines.market_regime import calculate_indicators, ticker_data, calculate_regime
                df = ticker_data.get(decision.ticker)
                if df is not None and not df.empty:
                    inds = calculate_indicators(df)
                    atr = inds["atr"] or atr
                    if len(df) >= 200:
                        regime, _, _, _, _ = calculate_regime(df)

                atr = validate_atr(atr, decision.ticker, "risk.py: atr calculation")

                # Load dashboard risk configurations
                import backend.main as backend_main
                db_lot = backend_main.current_risk_input.get("lot", 0.01)
                db_sl = backend_main.current_risk_input.get("stopDistance", 20.0)
                db_tp = backend_main.current_risk_input.get("takeProfit", 40.0)
                db_spread = backend_main.current_risk_input.get("spread", 2.0)
                db_reject = backend_main.current_risk_input.get("rejectThreshold", 3.0)
                db_risk_pct = backend_main.current_risk_input.get("riskPct", 1.5)

                # Real broker spread from live bid/ask (no randomness — risk filters must reflect the market)
                bid = price_data.get("bid")
                ask = price_data.get("ask")
                if bid and ask and ask > bid:
                    broker_spread = round(ask - bid, 2)
                else:
                    # Fallback for feeds without bid/ask (e.g. mock stocks): use the configured normal spread, never random
                    broker_spread = 2.0

                # Check Reject > rejectThreshold (3.0) or broker_spread > spread limit
                if broker_spread > db_reject:
                    await self._reject(decision, f"สเปรดโบรกเกอร์ ({broker_spread}) เกินเกณฑ์ห้ามเทรดเด็ดขาด ({db_reject})")
                    continue
                if broker_spread > db_spread:
                    await self._reject(decision, f"สเปรดโบรกเกอร์ ({broker_spread}) เกินขีดจำกัดสเปรด ({db_spread})")
                    continue

                # Spread Spike Filter
                from backend.config import FEATURE_FLAGS
                if FEATURE_FLAGS.get("spread_filter", True):
                    normal_spread = 2.0
                    spread_ratio = broker_spread / max(normal_spread, 0.1)
                    if spread_ratio > 5.0:
                        from backend.alert import send_alert
                        await self._reject(decision, f"สเปรด {broker_spread} สูงกว่าปกติ {spread_ratio:.1f}x")
                        asyncio.create_task(send_alert("WARNING", f"⚠️ Spread spike on {decision.ticker}: {broker_spread} ({spread_ratio:.1f}x normal)"))
                        continue

                # Set parameters exactly from dashboard settings
                from backend.config import FEATURE_FLAGS
                if FEATURE_FLAGS.get("kelly_sizing", False):
                    from backend.engines.portfolio_risk import calc_kelly_lot, check_portfolio_heat
                    from backend.core import SYMBOLS
                    
                    db = SessionLocal()
                    live_trades_count = db.query(Trade).filter(Trade.status == TradeStatus.CLOSED).count()
                    db.close()
                    
                    spec = SYMBOLS.get(decision.ticker, SYMBOLS["XAUUSD"])
                    contract_size = spec.get("contractSize", 100)
                    
                    kelly_res = calc_kelly_lot(
                        symbol=decision.ticker,
                        regime=regime,
                        equity=self.account_balance,
                        atr=atr,
                        contract_size=contract_size,
                        live_trades_count=live_trades_count
                    )
                    lot_size = kelly_res["lot"]
                    
                    # Set volatility-adjusted SL/TP (e.g. 2 ATR SL and 4 ATR TP)
                    sl_dist = max(atr * 2, db_sl)
                    tp_dist = max(atr * 4, db_tp)
                    
                    # Portfolio heat check
                    heat_ok, heat_msg = check_portfolio_heat(decision.ticker, lot_size, sl_dist, self.account_balance)
                    if not heat_ok:
                        await self._reject(decision, f"Portfolio Heat rejection: {heat_msg}")
                        continue
                else:
                    lot_size = db_lot
                    sl_dist = db_sl
                    tp_dist = db_tp

                from backend.config import FEATURE_FLAGS
                if FEATURE_FLAGS.get("rr_filter", True):
                    rr_ratio = tp_dist / (sl_dist + 0.0001)
                    min_rr = {"BULL": 1.5, "BEAR": 2.0, "SIDEWAYS": 1.0, "VOLATILE": 2.5}.get(regime, 1.0)
                    if rr_ratio < min_rr:
                        await self._reject(decision, f"R:R {rr_ratio:.2f} ต่ำกว่าเกณฑ์ {min_rr} สำหรับตลาด {regime}")
                        continue

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

                from backend.core import order_deduplicator
                if order_deduplicator.is_duplicate(decision.ticker, decision.action, price):
                    await self._reject(decision, f"Order duplication detected for {decision.ticker} {decision.action} at {price:.2f}.")
                    continue

                approve = RiskApprovedEvent(
                    ticker=decision.ticker,
                    action=decision.action,
                    lot_size=round(lot_size, 4),
                    signal_price=price,
                    stop_loss=round(stop_loss, 4),
                    take_profit=round(take_profit, 4),
                    strategy_name="AIVotingStrategy",
                    atr_at_entry=atr,
                    market_regime=regime
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
