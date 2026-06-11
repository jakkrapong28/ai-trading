# แผนพัฒนาระบบ AI Trading ให้แม่นยำขึ้น

> จัดทำจากการอ่าน `system_analysis.md`, `core.py`, `backtest.py`, `main.py` และ engines ทั้งหมด (strategy, execution, risk, market_data, market_regime, portfolio, news_intelligence)

---

## ปัญหาที่พบในระบบปัจจุบัน

| ปัญหา | รายละเอียด | ไฟล์ที่เกี่ยวข้อง |
|-------|-----------|------------------|
| **RSI + EMA พื้นฐานเกินไป** | ระบบใช้แค่ RSI, EMA, MACD, BB — ไม่มี Smart Money, Volume Profile, MTF จริง | `core.py` |
| **Entry ไม่มี "เหตุผลเชิงโครงสร้าง"** | สัญญาณ BUY/SELL เกิดจาก RSI ถึง threshold ไม่ได้ดู Liquidity, Order Block, FVG | `core.py`, `strategy.py` |
| **Position Sizing คงที่** | Lot size = 0.01 เสมอ ไม่ปรับตาม Win Rate หรือ Avg Win/Loss | `risk.py` |
| **No Partial TP / Scaling** | ปิดทั้งออเดอร์ตอน TP/SL — เสียโอกาสทำกำไรเพิ่ม | `execution.py` |
| **Circuit Breaker แบบง่าย** | Breaker เป็น boolean global ไม่แยกสาเหตุ | `risk.py`, `portfolio.py` |
| **No Correlation Hedge** | ถือหลายคู่ที่ correlation สูงพร้อมกัน เสี่ยง Drawdown พร้อมกัน | ไม่มี |
| **Backtest ขาด robustness check** | ไม่มี Walk-Forward / Monte Carlo | `backtest.py` |
| **R:R ไม่ถูกกรองก่อนเข้า** | รับทุกสัญญาณที่ผ่าน Risk Check โดยไม่ดู R:R ratio | `risk.py` (ไม่มี) |
| **NaN/Inf ไม่มี Guard** | ATR=0 หรือ NaN → Kelly division by zero, SL=NaN ส่งไป MT5 ได้ | `risk.py`, `execution.py` |
| **Order Duplication** | Signal ซ้ำจาก network retry หรือ restart → position ซ้อน | `execution.py` |
| **DB Transaction Broken** | ถ้า update หลายตารางแล้วตัวใดตัวหนึ่งล้ม ข้อมูล inconsistent | `portfolio.py` |
| **No Alerting** | เมื่อ CB trigger, NaN detect, MT5 disconnect — operator ไม่รู้ | ไม่มี |
| **Timezone ไม่ระบุ** | daily_loss reset "เที่ยงคืน" แต่ไม่รู้เป็น timezone อะไร | `config.py` (ไม่มี) |

---

## ลำดับการพัฒนา

| Phase | Tasks | Impact | ระยะเวลา |
|-------|-------|--------|----------|
| **1A 🔴** | Safety Layer: NaN Guard + Order Duplication + DB Transaction + MT5 Heartbeat + MAX_POSITIONS + Indentation Fix | **Critical — ป้องกัน error ก่อน deploy** | สัปดาห์ 1-2 |
| **1B 🔴** | Circuit Breaker 2.0 + R:R Filter + Spread Filter + Alerting (Telegram) + Emergency Stop + Correlation Cap + Signal Cooldown → Redis/DB + Time-based Regime Exit | **High — ลดขาดทุน + แจ้งเตือนทันที** | สัปดาห์ 2-4 |
| **1C 🟡** | Partial TP + Adaptive Trailing + Feature Flags + Tests + ATR-based Confirmation + Kelly Linear Ramp | **Medium — เพิ่มประสิทธิภาพ** | สัปดาห์ 4-6 (parallel กับ 1B) |
| **2** | SMC (confidence combos + MIN_TRADEABLE 0.55) + Session Filter 24h + D1 Bias Lock (ATR-normalized) + MTF + Volume Profile + Adaptive RSI + Regime Hysteresis | Medium — เพิ่มแม่นยำ | สัปดาห์ 7-8 |
| **3** | Kelly Criterion (linear ramp smooth) + Portfolio Heat (หลัง Phase 4 validate) | Medium — ปรับ sizing | สัปดาห์ 9 |
| **4** | Backtest 2.0 + Spread Cost + Signal Quality Log (rolling) + Graceful Shutdown + SMC Sweep + D1 Candle Test + Dashboard | Medium-Low — สรุปผล | สัปดาห์ 8-9 (parallel กับ Phase 3 setup) |

---

## Phase 1A 🔴 — Safety Layer (ต้องมีก่อน deploy)

### 1A.1 NaN/Inf Propagation Guard

**ปรับปรุง:** `backend/engines/risk.py`, `backend/engines/execution.py`, `backend/core.py`

เพิ่ม guard ทุกจุดที่ใช้ ATR, RSI, MACD, Kelly:

```python
import math

def validate_atr(atr: float, symbol: str = "XAUUSD", context: str = "") -> float:
    """NaN/Inf guard — ถ้า ATR เสีย ใช้ historical median หรือ symbol volatility แทนค่าคงที่"""
    if atr is None or math.isnan(atr) or math.isinf(atr) or atr <= 0:
        from backend.core import SYMBOLS
        fallback = SYMBOLS.get(symbol, SYMBOLS["XAUUSD"]).get("volatility", 5.0) * 0.5
        logger.warning(f"⚠️ Invalid ATR ({atr}) ใน {context} — fallback เป็น {fallback:.2f} ({symbol})")
        return fallback
    return atr

def validate_price(price: float, context: str = "") -> float:
    """NaN/Inf guard สำหรับราคา"""
    if price is None or math.isnan(price) or math.isinf(price) or price <= 0:
        logger.error(f"❌ Invalid price ({price}) ใน {context}")
        raise ValueError(f"Invalid price: {price} ใน {context}")
    return price
```

**จุดที่ต้องเพิ่ม guard:**
- `risk.py` — ก่อนใช้ `atr` คำนวณ stop_distance, lot, risk_dollars
- `execution.py` — ก่อนใช้ `atr` ใน trailing stop, ก่อนส่ง SL/TP ไป MT5
- `core.py:calculate_position_size()` — ก่อนคำนวณ lot
- `core.py:calc_trailing_stop()` — ก่อน return ค่า SL
- `portfolio.py` — ก่อนใช้ PnL, equity

### 1A.2 Order Duplication Guard

**ปรับปรุง:** `backend/engines/execution.py`

ใช้ `set` + `deque` รวมกัน — `deque` สำหรับ eviction, `set` สำหรับ O(1) lookup:

```python
from collections import deque
import hashlib

class OrderDeduplicator:
    def __init__(self, maxlen: int = 100):
        self._queue: deque = deque(maxlen=maxlen)
        self._set: set = set()  # O(1) lookup

    def make_signal_id(self, symbol: str, action: str, entry_price: float) -> str:
        rounded_ts = int(datetime.now(timezone.utc).timestamp() / 300) * 300
        raw = f"{symbol}_{action}_{entry_price:.2f}_{rounded_ts}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_duplicate(self, signal_id: str) -> bool:
        return signal_id in self._set  # O(1)

    def mark_executed(self, signal_id: str):
        if len(self._queue) == self._queue.maxlen:
            evicted = self._queue.popleft()
            self._set.discard(evicted)
        self._queue.append(signal_id)
        self._set.add(signal_id)
```

**จุดที่ใช้งาน:**
- `execution.py:process_approved_signals()` — ก่อน `broker.place_order()`
- `risk.py` — ก่อน publish `CH_RISK_APPROVED`

### 1A.3 Database Transaction Rollback

**ปรับปรุง:** `backend/engines/portfolio.py`, `backend/engines/risk.py`

```python
from sqlalchemy.exc import SQLAlchemyError

async def close_trade_and_update_stats(trade_id: str, realized_pnl: float):
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id).first()
        trade.status = TradeStatus.CLOSED
        trade.realized_pnl = realized_pnl
        trade.closed_at = datetime.utcnow()

        stats = db.query(StrategyStats).filter(
            StrategyStats.symbol == trade.ticker,
            StrategyStats.regime == current_regime
        ).first()
        if stats:
            stats.total_trades += 1
            if realized_pnl > 0:
                stats.wins += 1
                stats.avg_win = (stats.avg_win * (stats.wins - 1) + realized_pnl) / stats.wins if stats.wins > 1 else realized_pnl
            else:
                stats.losses += 1
                stats.avg_loss = (stats.avg_loss * (stats.losses - 1) + abs(realized_pnl)) / stats.losses if stats.losses > 1 else abs(realized_pnl)
            stats.win_rate = stats.wins / stats.total_trades

        signal_log = db.query(SMCSignalLog).filter(
            SMCSignalLog.trade_id == trade_id
        ).first()
        if signal_log:
            signal_log.actual_outcome = "WIN" if realized_pnl > 0 else "LOSS"
            signal_log.actual_rr = abs(realized_pnl / (trade.entry_price * trade.lot_size * 0.01 + 0.0001))

        db.commit()
        logger.info(f"✅ Trade {trade_id} closed + stats updated in single transaction")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"❌ Transaction failed for {trade_id}: {e}")
        raise
    finally:
        db.close()
```

### 1A.4 MT5 Heartbeat + Position Reconciliation

**ปรับปรุง:** `backend/brokers/paper.py` (หรือ broker interface)

```python
class BrokerHeartbeat:
    def __init__(self, broker, interval: int = 30):
        self.broker = broker
        self.interval = interval
        self.last_heartbeat: Optional[datetime] = None
        self.reconnect_attempts = 0

    async def start(self):
        while True:
            try:
                ok = await self.broker.ping()
                if ok:
                    self.last_heartbeat = datetime.now(timezone.utc)
                    self.reconnect_attempts = 0
                    await self.reconcile_positions()
                else:
                    logger.warning("⚠️ MT5 heartbeat failed")
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= 3:
                        await self.handle_disconnect()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break

    async def reconcile_positions(self):
        db_positions = await self.broker.get_db_positions()
        mt5_positions = await self.broker.get_mt5_positions()
        for pos in db_positions:
            if pos.trade_id not in mt5_positions:
                logger.warning(f"⚠️ Position {pos.trade_id} diverged — DB says OPEN, MT5 says CLOSED")
                pos.status = TradeStatus.CLOSED
                pos.closed_at = datetime.utcnow()

    async def handle_disconnect(self):
        await send_alert("CRITICAL", f"🚨 MT5 disconnect after {self.reconnect_attempts} attempts — last heartbeat: {self.last_heartbeat}")
```

### 1A.5 MAX_POSITIONS_PER_SYMBOL

**เพิ่ม:** `backend/engines/risk.py`

```python
MAX_POSITIONS_PER_SYMBOL = 2

async def process_decisions(self):
    async for msg in self.event_bus.subscribe_group(...):
        decision = AIDecisionEvent(**msg)
        db = SessionLocal()
        open_count = db.query(Trade).filter(
            Trade.ticker == decision.ticker,
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.PARTIAL])
        ).count()
        db.close()

        if open_count >= MAX_POSITIONS_PER_SYMBOL:
            await self._reject(decision, f"จำนวน open position ของ {decision.ticker} ({open_count}) ถึงขีดจำกัด {MAX_POSITIONS_PER_SYMBOL} แล้ว")
            continue
```

### 1A.0 Fix Indentation Error ใน calculate_mtf_indicators()

**บล็อคเกอร์ Phase 2 — ถ้าไม่แก้ D1 Bias Lock ทำงานไม่ได้เลย**

**ไฟล์:** `backend/core/mtf.py`

บรรทัด 677-679 มี indent ส่วนเกิน 4 spaces ที่ `ema_200_hist` และ `ema_200_slope` ทำให้ Python SyntaxError:

```python
# ก่อน (ผิด):
        ema_200 = close_series.ewm(span=200, adjust=False).mean().iloc[-1]
            ema_200_hist = close_series.ewm(span=200, adjust=False).mean()  # ← SyntaxError!
            ema_200_slope = (...)
# หลัง (ถูก):
        ema_200 = close_series.ewm(span=200, adjust=False).mean().iloc[-1]
        ema_200_hist = close_series.ewm(span=200, adjust=False).mean()
        ema_200_slope = (ema_200 - ema_200_hist.iloc[-20]) / abs(ema_200_hist.iloc[-20] + 0.0001) if len(closed) >= 220 else 0
```

**แก้ไข:** ลบ indent ส่วนเกิน 4 spaces ออกจาก 2 บรรทัดนี้

---

## Phase 1B 🔴 — Circuit Breaker 2.0 + Risk Filters + Alerting + Correlation Cap

### 1B.0 Alerting System (Telegram Primary, LINE Optional)

> ⚠️ LINE Notify (`notify-api.line.me`) **ปิดบริการตั้งแต่ปี 2025** — ใช้ Telegram Messaging API เป็น primary channel

**สร้าง:** `backend/alert.py` (ใหม่)

```python
# backend/config.py
ALERT_CHANNELS = {
    "telegram": {
        "enabled": True,
        "token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_CHAT_ID",
    },
    "line": {
        "enabled": False,  # Optional: ต้องมี LINE OA + Messaging API token
        "token_env": "LINE_CHANNEL_ACCESS_TOKEN",
    },
}

CALIBRATION_TRIGGER = {
    "min_trades": 20,
    "max_days": 7,
}

TRADING_DAY_RESET_TZ = "America/New_York"
DAILY_LOSS_RESET_HOUR_UTC = 22
```

```python
# backend/alert.py (ใหม่)
import os
import httpx
import logging

logger = logging.getLogger("alert")

async def send_alert(level: str, message: str, context: dict = None):
    """Push alert (Telegram primary) + structured log"""
    from backend.config import ALERT_CHANNELS

    extra = {"context": context or {}, "alert_level": level}
    if level in ("ERROR", "CRITICAL"):
        logger.error(f"[ALERT][{level}] {message}", extra=extra)
    else:
        logger.warning(f"[ALERT][{level}] {message}", extra=extra)

    if level not in ("ERROR", "CRITICAL"):
        return

    # Telegram (primary)
    tg = ALERT_CHANNELS.get("telegram", {})
    if tg.get("enabled"):
        token = os.getenv(tg["token_env"])
        chat_id = os.getenv(tg["chat_id_env"])
        if token and chat_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"🚨 [{level}] {message}"},
                        timeout=3.0,
                    )
            except Exception as e:
                logger.error(f"Telegram alert failed: {e}")

    # LINE (optional — ต้องมี LINE OA + Channel Access Token สำหรับ push)
    line = ALERT_CHANNELS.get("line", {})
    if line.get("enabled"):
        token = os.getenv(line["token_env"])
        user_id = os.getenv(line.get("chat_id_env", "LINE_USER_ID"))
        if token and user_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://api.line.me/v2/bot/message/push",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        json={"to": user_id, "messages": [{"type": "text", "text": f"🚨 [{level}] {message}"}]},
                        timeout=3.0,
                    )
            except Exception as e:
                logger.error(f"LINE push failed: {e}")
```

**จุด trigger alert (7 จุด):**

| Event | Level | Message |
|-------|-------|---------|
| CB trigger | CRITICAL | `🚨 Circuit Breaker: {name} — {reason} (reset: {est_reset})` |
| NaN/Inf detect | ERROR | `⚠️ NaN detected in ATR for {symbol} — fallback` |
| MT5 heartbeat fail 3 ครั้ง | CRITICAL | `🚨 MT5 disconnect — {attempts} attempts failed` |
| Position divergence | ERROR | `⚠️ Position {trade_id} diverged — auto-closed` |
| Emergency Stop | CRITICAL | `🚨 EMERGENCY STOP activated` |
| Kelly lot capped | WARNING | `⚠️ Kelly lot capped at 0.01 for {symbol}` |
| Spread spike | WARNING | `⚠️ Spread spike on {symbol}: {spread}x normal` |

### 1B.1 Feature Flags / Rollback Plan

**ไฟล์:** `backend/config.py`

```python
FEATURE_FLAGS = {
    "circuit_breaker_v2": True,
    "rr_filter": True,
    "partial_tp": False,
    "adaptive_trailing": True,
    "spread_filter": True,
    "emergency_stop": True,
    "alerting": True,
    "correlation_cap": True,      # Basic cap — active ตั้งแต่ Phase 1B
    "smc_strategy": False,        # Phase 2
    "kelly_sizing": False,        # Phase 3 (หลัง backtest validate)
    "mtf_strategy": False,
    "session_filter": False,
    "d1_bias_lock": False,
    "confirmation_candle": False,
}
```

**Rollback Plan** (`backend/DEPLOY.md`):

| Scenario | Action |
|----------|--------|
| Partial TP ทำให้ position ค้าง | `partial_tp = False` → กลับไปปิดทั้ง lot |
| CB 2.0 ทำงานผิด | `circuit_breaker_v2 = False` → boolean global |
| SMC signal ผิด | `smc_strategy = False` → RSI-evaluate |
| Kelly Lot ใหญ่ | `kelly_sizing = False` → lot 0.01 |
| Alerting ส่ง spam | `alerting = False` → ปิด push |
| Correlation cap ผิด | `correlation_cap = False` |

### 1B.2 Circuit Breaker 2.0 — Timezone-aware Reset

**ปรับปรุง:** `backend/engines/risk.py`, `backend/engines/portfolio.py`

```python
from pytz import timezone as tz
from datetime import timedelta

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
                # PLACEHOLDER: full implementation in Phase 3
                # Phase 1B uses basic correlation_cap flag instead
            }
        }

    def get_trade_lock(self, trade_id: str) -> asyncio.Lock:
        if trade_id not in self._locks:
            self._locks[trade_id] = asyncio.Lock()
        return self._locks[trade_id]

    def _get_next_reset(self, breaker_name: str) -> Optional[datetime]:
        ny_tz = tz(TRADING_DAY_RESET_TZ)
        now_ny = datetime.now(ny_tz)

        if breaker_name == "daily_loss":
            next_reset = now_ny.replace(hour=0, minute=0, second=0) + timedelta(days=1)
            return next_reset.astimezone(timezone.utc)

        if breaker_name == "weekly_loss":
            next_monday = now_ny + timedelta(days=(7 - now_ny.weekday()))
            return next_monday.replace(hour=0, minute=0, second=0).astimezone(timezone.utc)

        return None
```

**Recovery:**

| Breaker | Reset Trigger |
|---------|---------------|
| daily_loss | เที่ยงคืน NY (22:00 UTC) |
| weekly_loss | วันจันทร์ NY |
| consecutive_loss | เมื่อมี winning trade |
| news_flash | หลัง event + 1 ชม. |
| volatility_spike | ATR < 2× ค่าเฉลี่ย |
| correlation_break | correlation กลับมาปกติ (Phase 3) |

### 1B.3 Correlation Cap (Basic — Phase 1B แทนรอ Phase 3)

**เพิ่ม:** `backend/engines/risk.py` — ใช้ feature flag `correlation_cap`

เนื่องจาก Correlation Matrix เต็มรูปแบบอยู่ Phase 3 แต่ความเสี่ยงนี้มีทันที Phase 1 จึงเพิ่ม **basic hard-cap:**

```python
CORRELATION_GROUPS = {
    "GOLD_SILVER": ["XAUUSD"],  # กลุ่มทอง — สามารถขยายเพิ่ม XAGUSD ในอนาคต
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "US_STOCKS": ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"],
    "FOREX": ["EURUSD"],
}

MAX_POSITIONS_PER_GROUP = 1  # 1 position ต่อกลุ่ม

async def process_decisions(self):
    async for msg in ...:
        decision = AIDecisionEvent(**msg)

        if FEATURE_FLAGS.get("correlation_cap", False):
            # หา group ของ symbol นี้
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
                    await self._reject(decision, f"กลุ่ม {group} มี open position ({group_open}) ถึงขีดจำกัด {MAX_POSITIONS_PER_GROUP} แล้ว — กันความเสี่ยง correlation")
                    continue
```

### 1B.4 R:R Filter ก่อน Approve

| Market Regime | Minimum R:R |
|--------------|-------------|
| BULL | 1.5 |
| BEAR | 2.0 |
| SIDEWAYS | 1.0 |
| VOLATILE | 2.5 |

```python
rr_ratio = tp_distance / sl_distance + 0.0001
min_rr = {"BULL": 1.5, "BEAR": 2.0, "SIDEWAYS": 1.0, "VOLATILE": 2.5}.get(regime, 1.0)
if rr_ratio < min_rr:
    await self._reject(decision, f"R:R {rr_ratio:.2f} ต่ำกว่าเกณฑ์ {min_rr} สำหรับตลาด {regime}")
    continue
```

### 1B.5 Spread Filter

```python
if FEATURE_FLAGS["spread_filter"]:
    normal_spread = get_normal_spread(decision.ticker)
    spread_ratio = broker_spread / max(normal_spread, 0.1)
    if spread_ratio > 5.0:
        await self._reject(decision, f"สเปรด {broker_spread} สูงกว่าปกติ {spread_ratio:.1f}x")
        await send_alert("WARNING", f"Spread spike on {decision.ticker}: {broker_spread} ({spread_ratio:.1f}x normal)")
        continue
```

### 1B.6 Emergency Stop

**API:** `POST /api/emergency-stop`

```python
async def emergency_stop():
    os.environ["PORTFOLIO_CRITICAL_WATCH"] = "true"
    await broker.close_all_positions()
    for flag in FEATURE_FLAGS:
        if flag not in ("circuit_breaker_v2", "emergency_stop",):
            FEATURE_FLAGS[flag] = False
    await send_alert("CRITICAL", "🚨 EMERGENCY STOP activated by user")
    await manager.broadcast({"type": "emergency_stop", "message": "🛑 ระบบหยุดฉุกเฉิน!"})
    return {"success": True}
```

### 1B.7 Signal Cooldown → Redis / PostgreSQL

**เคลื่อนย้ายจาก in-memory `Dict` (restart-unsafe) ไป persisted storage**

**ปัญหาเดิม (Phase 2.1 ย้ายมาที่นี่):**
- `last_signal_time: Dict[Tuple[str, str], datetime]` — หายเมื่อ restart
- Race condition: check-then-write ไม่ atomic ใน async context

**แก้ไข — ใช้ Redis TTL หรือ PostgreSQL:**

```python
# ตัวเลือก A: Redis (SETEX มี TTL ในตัว)
async def is_cooldown_active(symbol: str, signal_type: str) -> bool:
    return await redis.exists(f"cooldown:{symbol}:{signal_type}")

async def mark_signal(symbol: str, signal_type: str):
    ttl = SIGNAL_COOLDOWN_MINUTES.get(signal_type, 30) * 60
    await redis.setex(f"cooldown:{symbol}:{signal_type}", ttl, "1")
```

```python
# ตัวเลือก B: PostgreSQL table signal_cooldowns
# ตาราง: (symbol, signal_type, last_signal_at)
# upsert: INSERT ... ON CONFLICT DO UPDATE
```

**ใช้ `signal_cooldown` feature flag** — fallback เป็น in-memory ถ้าไม่มี Redis

### 1B.8 Time-based Exit เมื่อ Regime เปลี่ยนระหว่างถือ Position

**เชื่อมโยง 1B.4 (R:R Filter ที่ entry) กับ 1C.2 (Adaptive Trailing)**

**ปัญหา:** ถ้า entry ใน VOLATILE (min R:R 2.5) แต่ regime เปลี่ยนเป็น SIDEWAYS หลัง entry — Chandelier Exit ที่ 3.5R+ อาจไม่มีวันถูกแตะ → position ค้างนาน

**แก้ไข — เพิ่ม `regime_change_exit` ใน `execution.py`:**

```python
# Generalized list of rules — สามารถเพิ่ม transition rule ได้โดยไม่ต้องแก้ logic
REGIME_CHANGE_EXIT_RULES = [
    {
        "from_regimes": ["VOLATILE", "BULL"],
        "to_regime": "SIDEWAYS",
        "max_hold_hours": 48,
        "partial_close_pct": 0.5,
        "tighten_sl_to": "BE",
    },
    # เพิ่ม rule เพิ่มเติมได้เช่น:
    # {
    #     "from_regimes": ["SIDEWAYS"],
    #     "to_regime": "BEAR",
    #     "max_hold_hours": 24,
    #     "partial_close_pct": 1.0,  # ปิดเต็ม lot
    #     "tighten_sl_to": None,
    # },
]
```

**Trigger:** ทุกครั้งที่ regime เปลี่ยน → iterate ทุก rule → scan open positions ที่ match `from_regimes` → ถ้าค้างเกิน `max_hold_hours` โดยยังไม่ถึง TP1 → ดำเนินการตาม rule

```python
async def on_regime_change(new_regime: str, old_regime: str):
    for rule in REGIME_CHANGE_EXIT_RULES:
        if new_regime == rule["to_regime"] and old_regime in rule["from_regimes"]:
            for pos in get_open_positions(pos_entry_regime=old_regime):
                hours_held = (datetime.now(timezone.utc) - pos.entry_time).total_seconds() / 3600
                if hours_held >= rule["max_hold_hours"] and pos.current_r < 1.0:
                    await partial_close(pos.trade_id, rule["partial_close_pct"])
                    if rule.get("tighten_sl_to") == "BE":
                        await move_sl_to_be(pos.trade_id)
```

---

## Phase 1C 🟡 — Partial TP + Adaptive Trailing + Tests

### 1C.1 Partial Take-Profit + Race Condition Protection

**🔴 ทุก operation ใช้ `async with cb_manager.get_trade_lock(trade_id):`**

| Level | R Multiple | % Lot | ผล |
|-------|-----------|-------|-----|
| TP1 | 1.0R | 50% | SL → Entry |
| TP2 | 2.0R | 30% | SL → 1R Profit Lock |
| TP3 | 3.0R | 20% | Trailing 1 ATR |

### 1C.2 Adaptive Trailing

| R Multiple | Action |
|-----------|--------|
| 0 → 0.8R | SL คงที่ |
| 0.8R → 1.0R | Monitor |
| 1.0R → 1.5R | BE |
| 1.5R → 2.5R | Trailing 2 ATR |
| 2.5R → 3.5R | Trailing 1.5 ATR |
| 3.5R+ | Chandelier Exit |

### 1C.4 ATR-based Confirmation Candle (แทน % คงที่)

**เปลี่ยนจาก:** `last_close > zone * 1.002` (0.2% fixed ข้ามทุก symbol)
**เป็น:** `last_close > zone + atr * 0.1` (10% ของ ATR — adaptive ตาม volatility)

```python
def confirm_signal(signal: dict, ohlc: pd.DataFrame, atr: float) -> bool:
    if not needs_confirmation(signal):
        return True
    zone = signal["zone_price"]
    last_close = ohlc["close"].iloc[-1]
    buffer = atr * 0.1  # 10% ของ ATR — adaptive
    if signal["action"] == "BUY":
        return last_close > zone + buffer
    else:
        return last_close < zone - buffer
```

**เหตุผล:** XAUUSD ($2400, 0.2% = $4.8 ~ noise) กับ BTCUSDT ($60000, 0.2% = $120 ~ overkill) ต้องการ buffer ต่างกัน — ATR-based ปรับให้เหมาะสมเฉพาะ symbol

### 1C.5 Kelly Cap — Linear Ramp Smooth (แก้ Discontinuity)

**เปลี่ยน `kelly_cap` จาก step function เป็น linear ramp:**

```python
# ก่อน (step ที่ trade 50):
kelly_cap = 0.10 if live_trades_count < 50 else min(0.25, 0.10 + (live_trades_count / 50) * 0.15)
# trade 49 → 0.10, trade 50 → 0.25 กระโดด 2.5x ทันที

# หลัง (linear ramp ตั้งแต่ trade 1):
kelly_cap = 0.10 + min(1.0, live_trades_count / 50) * 0.15
# trade 1: 0.10 + (1/50)*0.15 ≈ 0.103
# trade 25: 0.10 + (25/50)*0.15 = 0.175
# trade 50+: 0.10 + 1.0*0.15 = 0.25
```

**ย้ายโค้ดนี้ไปอัปเดตใน Phase 3.1 ด้วย**

### 1C.3 Unit Tests Phase 1 (14 ไฟล์)

```
backend/tests/
├── conftest.py
├── test_nan_inf_guard.py
├── test_order_dedup.py
├── test_db_transaction.py
├── test_circuit_breaker.py
├── test_alerting.py
├── test_correlation_cap.py        # ใหม่ — test basic group cap
├── test_partial_tp.py
├── test_rr_filter.py
├── test_spread_filter.py
├── test_trailing_stop.py
├── test_emergency_stop.py
├── test_max_positions.py
├── test_mt5_heartbeat.py
└── test_signal_cooldown.py        # ใหม่ — Redis/DB cooldown
```

---

## Phase 2 — SMC + Confirmation Candle + Session Filter + D1 Bias Lock + MTF

### 2.1 Smart Money Concepts (SMC)

**สร้างไฟล์:** `backend/core/smc.py`

| Concept | Detection Logic |
|---------|----------------|
| **Liquidity Zone** | Swing High/Low ที่ถูกทะลุแล้วกลับ (Liquidity Sweep) |
| **Order Block (OB)** | OB Size ≥ 0.5 ATR, Volume ≥ 1.5× avg |
| **Fair Value Gap (FVG)** | 3 candles gap ≥ 0.3 ATR |
| **Market Structure Shift** | BOS / CHOCH |

**Confirmation Candle:**

`needs_confirmation()` อยู่ด้านล่าง (ใช้ confidence จาก `calculate_signal_confidence()`):

```python
def needs_confirmation(signal: dict) -> bool:
    if signal["confidence"] >= 0.85:
        return False
    return True
```

`confirm_signal()` ดู implementation ที่ **1C.4** (ATR-based — `zone + atr * 0.1`)

**Session Filter (ครอบคลุม 24 ชม. + Overlap Boost):**
```python
SESSION_BOOST = {
    "LONDON_NY_OVERLAP": {"hours": (13, 17), "boost": 1.1},  # Volume สูงสุด
    "LONDON":            {"hours": (9, 13),  "boost": 1.0},
    "NY":                {"hours": (17, 22), "boost": 1.0},
    "ASIAN":             {"hours": (2, 9),   "boost": 0.8},
    "SYDNEY":            {"hours": (22, 24), "boost": 0.7},
}
# หมายเหตุ: ช่วง 0-2 UTC = Sydney ต่อเนื่อง (รวมกับ 22-24)
# รวมทั้งหมดครอบคลุม 24 ชม. ไม่มี gap
```

**D1 Bias Lock (ATR-normalized Slope):**
```python
D1_SLOPE_THRESHOLD = 1.5  # configurable — หน่วย: ATR (EMA200 เคลื่อนกี่ ATR ใน 20 วัน)

def check_d1_bias_lock(mtf_data: dict, signal_action: str, d1_atr: float = None) -> bool:
    d1 = mtf_data.get("D1")
    if not d1 or "ema_200" not in d1 or "ema_200_history" not in d1:
        return False
    ema_200 = d1["ema_200"]
    ema_200_20bars_ago = d1["ema_200_history"][-20]
    price_change = ema_200 - ema_200_20bars_ago  # signed: positive=UP, negative=DOWN

    if not d1_atr or d1_atr <= 0:
        return False  # ไม่มี ATR → ไม่สามารถ normalize → ไม่ lock

    normalized_slope = price_change / d1_atr  # "EMA200 เคลื่อนกี่ ATR ใน 20 วัน"
    d1_trend = "UP" if normalized_slope > D1_SLOPE_THRESHOLD else ("DOWN" if normalized_slope < -D1_SLOPE_THRESHOLD else "SIDEWAYS")
    if d1_trend == "DOWN" and signal_action == "BUY":
        return True
    if d1_trend == "UP" and signal_action == "SELL":
        return True
    return False
```

> **เหตุผล:** แทนที่จะ normalise % change ด้วย ATR ratio (ได้ dimensionless value), ใช้ `price_change / d1_atr` (หน่วย ATR) — slope ในรูป "EMA200 เคลื่อนกี่ ATR ใน 20 วัน" มี physical meaning ตรงตัว และ match `D1_SLOPE_THRESHOLD` scale (1.0-3.0 ATR)

**Priority Scoring (Combination-Weighted Logic):**

```python
# หมายเหตุ: calculate_signal_confidence() คืนค่า discrete (0.85/0.70/0.55/0.0)
# ไม่จำเป็นต้องใช้ MIN_TRADEABLE_CONFIDENCE แยก เพราะ threshold ถูก encode ใน
# return condition ของฟังก์ชันแล้ว (FVG-alone = 0.0 = ไม่ trade)

def calculate_signal_confidence(concepts: dict) -> float:
    """Return confidence score based on concept combinations.
    FVG-alone returns 0.0 (not tradeable) instead of 0.40.
    """
    if concepts.get("mss") and concepts.get("ob") and concepts.get("fvg") and concepts.get("d1_aligned"):
        return 0.85       # ไม่ต้อง confirmation candle
    if concepts.get("ob") and concepts.get("fvg") and concepts.get("sr_level"):
        return 0.70       # ต้อง confirmation candle
    if concepts.get("ob"):
        return 0.55       # OB alone — tradeable แต่ต้อง confirm
    return 0.0            # FVG เดี่ยวหรืออื่นๆ — ไม่ trade
```

| เงื่อนไข | Confidence | Tradeable? |
|---------|-----------|------------|
| MSS + OB + FVG + D1 เดียวทาง | ≥ 0.85 | ✅ ไม่ต้อง confirm |
| OB + FVG + แนวรับ/แนวต้าน | ≥ 0.70 | ✅ ต้อง confirm |
| OB อย่างเดียว | ≥ 0.55 | ✅ ต้อง confirm |
| FVG อย่างเดียว | 0.0 | ❌ ไม่ trade |

### 2.2 Multi-Timeframe (MTF) — Stale Candle Protection

**สร้างไฟล์:** `backend/core/mtf.py`

```python
TIMEFRAMES = {
    "M15": {"weight": 1, "bars": 96},
    "H1":  {"weight": 2, "bars": 48},
    "H4":  {"weight": 3, "bars": 30},
    "D1":  {"weight": 4, "bars": 20},
}

def is_candle_closed(tf: str, timestamp: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if tf == "M15": return timestamp.minute % 15 == 0 and timestamp < now
    if tf == "H1":  return timestamp.minute == 59 and timestamp < now
    if tf == "H4":  return timestamp.hour % 4 == 3 and timestamp.minute == 59
    if tf == "D1":  return timestamp.hour == 23 and timestamp.minute == 59
    return True

def calculate_mtf_indicators(ohlc: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    results = {}
    for tf, df in ohlc.items():
        closed = df[df.apply(lambda r: is_candle_closed(tf, r.name), axis=1)]
        if len(closed) < 20:
            continue
        close_series = closed["close"]
        ema_12 = close_series.ewm(span=12, adjust=False).mean().iloc[-1]
        ema_26 = close_series.ewm(span=26, adjust=False).mean().iloc[-1]
        ema_200_series = close_series.ewm(span=200, adjust=False).mean()
        ema_200 = ema_200_series.iloc[-1]
        results[tf] = {
            "rsi": calculate_rsi(close_series.tolist()),
            "ema_12": round(float(ema_12), 4),
            "ema_26": round(float(ema_26), 4),
            "ema_200": round(float(ema_200), 4),
            "ema_200_history": [round(float(v), 4) for v in ema_200_series.tail(20).tolist()] if len(closed) >= 220 else [],
            "trend": "Bullish" if ema_12 > ema_26 else "Bearish",
            "candle_count": len(closed),
        }
    return results
```

### 2.3 Volume Profile

**สร้างไฟล์:** `backend/core/volume_profile.py`

```python
VOLUME_PROFILE_CONFIG = {
    "lookback_bars": 100,       # H1 = ~4 วัน
    "value_area_pct": 0.70,     # 70% volume zone
    "data_source": "tick_volume",  # forex/gold ใช้ tick volume (broker ไม่ให้ real volume)
    "usage": "confluence_score",   # ไม่ใช่ hard filter — เป็น score ประกอบการตัดสินใจ
}
```

| Concept | รายละเอียด |
|---------|-----------|
| **VAH/VAL** | 70% volume zone — ถ้าราคาอยู่นอก zone = โอกาส breakout |
| **POC** | ราคาที่มี volume สูงสุด = จุดสมดุล |
| **VWAP** | Real-time VWAP = แนวโน้ม intraday |
| **Delta Volume** | Tick volume difference (buy-sell) |

> ⚠️ Forex/Gold ใช้ **tick volume** ไม่ใช่ real volume — ตีความว่าเป็น "activity proxy" ไม่ใช่ "money flow"

### 2.4 Adaptive Indicator Parameters — RSI Thresholds ตาม Regime

```python
RSI_THRESHOLDS = {
    "BULL":     {"oversold": 40, "overbought": 75},
    "BEAR":     {"oversold": 25, "overbought": 60},
    "SIDEWAYS": {"oversold": 35, "overbought": 65},
    "VOLATILE": {"oversold": 20, "overbought": 80},
}
```

> ค่าเหล่านี้เป็น initial guess — ต้องผ่าน walk-forward optimization ใน Phase 4 ก่อน finalize

### 2.5 Regime Transition Handling + Hysteresis

**สร้างไฟล์:** `backend/core/regime_transition.py`

```python
REGIME_CONFIRMATION_BARS = 3  # regime ใหม่ต้องคงอยู่ 3 bars ติดก่อน trigger
```

**ป้องกัน flapping:** ใช้ `regime_candidate` buffer — regime ใหม่ต้อง confirm `REGIME_CONFIRMATION_BARS` bars ก่อน execute transition action:

```python
class RegimeManager:
    def __init__(self):
        self.current_regime: str = "SIDEWAYS"
        self._candidate: Optional[str] = None
        self._confirmation_count: int = 0

    def update(self, detected_regime: str) -> Optional[str]:
        if detected_regime == self._candidate:
            self._confirmation_count += 1
        else:
            self._candidate = detected_regime
            self._confirmation_count = 1

        if self._confirmation_count >= REGIME_CONFIRMATION_BARS and self._candidate != self.current_regime:
            old = self.current_regime
            self.current_regime = self._candidate
            self._confirmation_count = 0
            return old  # caller trigger transition actions
        return None
```

| Transition | ปิด Position? | รับสัญญาณ? | มาตรการ |
|-----------|--------------|-----------|---------|
| BULL→VOLATILE | ไม่ | หยุด | Trailing tight 1 ATR |
| BULL→BEAR | ปิด BUY | หยุด | Close all BUY |
| VOLATILE→SIDEWAYS | ปิดไร้ทิศทาง | reversal | Tighten SL |
| SIDEWAYS→BULL/BEAR | ไม่ | ปกติ | Trend following |

### 2.6 Claude API Fallback

Fallback → rule-based เมื่อ latency > 5s หรือ rate limit

---

## Phase 3 — Kelly Criterion + Portfolio Heat (หลัง Backtest Validate)

> ⚠️ Phase 3 อยู่หลัง Phase 4 (Backtest) — Kelly จะ seed จาก backtest ที่ผ่าน walk-forward validation แล้วเท่านั้น

### 3.1 Dynamic Position Sizing (Kelly)

**Bootstrap:** seed จาก backtest ที่ผ่าน validate → `prior_weight = min(1.0, live_trades / 50)`

```python
def calc_kelly_lot(symbol, regime, equity, atr, contract_size, live_trades_count):
    stats = get_strategy_stats(symbol, regime)
    wr = stats["win_rate"]
    avg_w = stats["avg_win"]
    avg_l = abs(stats["avg_loss"])

    if avg_l < 0.01 or live_trades_count < 10:
        return {"lot": 0.01, "kelly_pct": 0, "mode": "fallback"}

    r = avg_w / max(avg_l, 0.01)
    kelly_raw = max(0, wr - ((1 - wr) / r))

    # Linear ramp ตั้งแต่ trade 1 — smooth, ไม่มี step discontinuity
    kelly_cap = 0.10 + min(1.0, live_trades_count / 50) * 0.15
    # trade 1: 0.103, trade 25: 0.175, trade 50+: 0.25
    kelly_pct = kelly_raw * kelly_cap
    stop_dist = max(atr * 2, 10.0)
    risk_dollars = kelly_pct * max(equity, 100)
    lot = risk_dollars / max(stop_dist * contract_size, 1.0)
    lot = max(0.01, min(lot, 10.0))

    return {"lot": round(lot, 2), "kelly_pct": round(kelly_pct, 4), "mode": "kelly"}
```

### 3.2 Portfolio Heat

- Correlation Matrix รายวัน
- Sector Limits: Crypto ≤ 15%, Stock ≤ 20%, Gold ≤ 30%
- VaR 95%: ≥ 20 trading days หรือ Monte Carlo synthetic fallback

---

## Phase 4 — Backtest 2.0 + Signal Quality Log + Graceful Shutdown + Dashboard

### 4.1 Walk-Forward + Spread Cost + SMC Parameter Sweep

> ก่อนเริ่ม Phase 3 (Kelly) ต้องผ่าน Phase 4 นี้ก่อน — Kelly seed จาก backtest ที่ validate แล้วเท่านั้น

```python
# Walk-Forward Criteria
WALK_FORWARD_CONFIG = {
    "in_sample_bars": 500,
    "out_of_sample_bars": 200,
    "slide_bars": 200,
    "monte_carlo_iterations": 10000,
    "pass_criteria": {
        "sharpe_ratio": 1.0,     # minimum Sharpe ใน out-of-sample
        "profit_factor": 1.3,    # minimum Profit Factor
        "max_drawdown": 0.15,    # maximum 15% drawdown
        "risk_of_ruin": 0.05,    # maximum 5% risk of ruin
    },
    "data_frequency": "H1",
    "smc_parameters_to_sweep": {     # SMC thresholds ต้องผ่าน walk-forward ด้วย
        "ob_size_atr": {"min": 0.4, "max": 0.7, "step": 0.1},
        "fvg_gap_atr": {"min": 0.2, "max": 0.4, "step": 0.05},
        "d1_slope_threshold": {"min": 0.5, "max": 3.0, "step": 0.25},  # EMA200 เคลื่อน 0.5-3.0 ATR ใน 20 วัน
        "confirmation_buffer_atr": {"min": 0.05, "max": 0.2, "step": 0.025},
    },
}

SPREAD_COST_DICT = {
    "XAUUSD": 25.0,
    "BTCUSDT": 10.0,
    "ETHUSDT": 8.0,
    "EURUSD": 2.0,
}
COMMISSION_PCT = {
    "XAUUSD": 0.0,
    "BTCUSDT": 0.01,
}

def apply_trade_costs(trade: dict, symbol: str) -> dict:
    spread_cost = SPREAD_COST_DICT.get(symbol, 5.0) * trade.get("lot", 0.01)
    commission = trade.get("pnl", 0.0) * COMMISSION_PCT.get(symbol, 0.0)
    trade["pnl"] = trade.get("pnl", 0.0) - spread_cost - commission
    trade["costs"] = {"spread": spread_cost, "commission": commission}
    return trade
```

### 4.2 Graceful Shutdown

```python
import signal

async def shutdown_handler(sig, frame):
    logger.info(f"🛑 Received {sig.name}. Starting graceful shutdown...")
    for task in registry.running_tasks:
        task.cancel()
    await engine.dispose()
    await asyncio.sleep(2)
    logger.info("✅ Graceful shutdown complete.")

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

### 4.3 Signal Quality Log — Rolling Calibration ทุก 7 วัน / 20 trades

**ตาราง:** `smc_signal_log` ใน PostgreSQL

```python
# backend/core/smc_calibrate.py
async def should_calibrate() -> bool:
    db = SessionLocal()
    try:
        total = db.query(SMCSignalLog).filter(
            SMCSignalLog.actual_outcome != "PENDING"
        ).count()
        if total == 0:
            return False
        recent = db.query(SMCSignalLog).order_by(
            SMCSignalLog.calibrated_at.desc()
        ).first()
        days_since = (datetime.now(timezone.utc) - recent.calibrated_at).days if recent and recent.calibrated_at else 999
        return total >= CALIBRATION_TRIGGER["min_trades"] or days_since >= CALIBRATION_TRIGGER["max_days"]
    finally:
        db.close()

async def run_calibration():
    db = SessionLocal()
    try:
        groups = db.query(
            SMCSignalLog.symbol, SMCSignalLog.signal_type, SMCSignalLog.confidence,
            func.count().label("total"),
            func.sum(case((SMCSignalLog.actual_outcome == "WIN", 1), else_=0)).label("wins"),
        ).filter(SMCSignalLog.actual_outcome != "PENDING"
        ).group_by(SMCSignalLog.symbol, SMCSignalLog.signal_type, SMCSignalLog.confidence).all()

        for g in groups:
            win_rate = g.wins / g.total if g.total > 0 else 0
            if g.total >= 20:
                db.query(SMCSignalLog).filter(
                    SMCSignalLog.symbol == g.symbol,
                    SMCSignalLog.signal_type == g.signal_type,
                    SMCSignalLog.confidence == g.confidence,
                ).update({"calibrated_confidence": round(win_rate, 2), "calibrated_at": datetime.utcnow()})
        db.commit()
        logger.info(f"✅ Calibration complete: {len(groups)} groups")
    finally:
        db.close()
```

### 4.4 D1 Timestamp Pre-flight Check + Unit Test

**Runtime check ก่อน deploy Phase 2:**

```python
async def verify_d1_candle_timestamps(symbol: str = "XAUUSD") -> int:
    """ตรวจสอบ timestamp convention ของ D1 bars จาก data source จริง
    ถ้า closed_count == 0 หลัง 30 bars → timestamp convention ไม่ตรง → ต้องแก้ is_candle_closed()"""
    df = await get_ohlc(symbol, "D1", bars=30)
    closed_count = sum(df.apply(lambda r: is_candle_closed("D1", r.name), axis=1))
    if closed_count == 0:
        await send_alert("CRITICAL", "❌ D1 timestamp convention mismatch — D1 Bias Lock จะไม่ทำงาน")
    logger.info(f"D1 candle pre-flight: {closed_count}/30 bars match convention")
    return closed_count
```

**Unit Test:** `backend/tests/test_is_candle_closed_d1.py`

```python
# ต้อง verify timestamp convention ของ data source จริงก่อน deploy Phase 2
# เพราะ D1 close time ต่างกันตาม broker:
#   - MT5: 23:59 UTC
#   - บาง broker: 00:00 UTC ของวันถัดไป
#   - บาง broker: 22:00 UTC (rollover)
def test_d1_candle_closed_with_mt5_timestamps():
    """MT5 daily bar timestamp convention"""
    assert is_candle_closed("D1", datetime(2024, 1, 15, 23, 59, tzinfo=timezone.utc)) == True
    assert is_candle_closed("D1", datetime(2024, 1, 15, 23, 0, tzinfo=timezone.utc)) == False

def test_d1_candle_closed_with_broker_00_utc():
    """ถ้า broker ใช้ 00:00 UTC timestamp"""
    pass  # TODO: วัด data source จริงแล้วปรับ
```

> ⚠️ **Critical:** ถ้า `is_candle_closed("D1")` ไม่เคย match timestamp convention → D1 data ไม่ถูกใช้เลย → D1 Bias Lock เสียทั้งหมดโดยไม่มี error (silent failure)

### 4.5 Dashboard Updates

| Component | Data |
|-----------|------|
| **Circuit Breaker Panel** | สถานะ + `triggered_at` + `estimated_reset_at` (timezone-aware) |
| **Feature Flag Status** | flag ไหน ON/OFF |
| **AI Status** | "AI Active" / "Rule-Based (Fallback)" |
| **🛑 Emergency Stop** | ปุ่มแดงตรึงมุมขวาบน |
| **Correlation Cap Stats** | จำนวนที่ถูก reject ตาม group |
| **Alert Log** | 10 รายการ alert ล่าสุด |
| **Kelly %** | kelly %, lot, mode |
| **Execution Quality** | slippage, latency, reject rate |
| **MT5 Heartbeat** | connection status, last heartbeat, divergence count |
| **NaN Guard Log** | NaN detect + fallback count |
| **Calibration Status** | calibrate ล่าสุด, groups อัปเดต |

---

## ไฟล์ทั้งหมด

| ไฟล์ | สถานะ | Phase |
|------|--------|-------|
| `backend/config.py` | **ใหม่** | 1B |
| `backend/alert.py` | **ใหม่** | 1B |
| `backend/DEPLOY.md` | **ใหม่** | 1B |
| `backend/core/smc_calibrate.py` | **ใหม่** | 4 |
| `backend/tests/conftest.py` | **ใหม่** | 1C |
| `backend/tests/test_nan_inf_guard.py` | **ใหม่** | 1C |
| `backend/tests/test_order_dedup.py` | **ใหม่** | 1C |
| `backend/tests/test_db_transaction.py` | **ใหม่** | 1C |
| `backend/tests/test_circuit_breaker.py` | **ใหม่** | 1C |
| `backend/tests/test_alerting.py` | **ใหม่** | 1C |
| `backend/tests/test_correlation_cap.py` | **ใหม่** | 1C |
| `backend/tests/test_partial_tp.py` | **ใหม่** | 1C |
| `backend/tests/test_rr_filter.py` | **ใหม่** | 1C |
| `backend/tests/test_spread_filter.py` | **ใหม่** | 1C |
| `backend/tests/test_trailing_stop.py` | **ใหม่** | 1C |
| `backend/tests/test_emergency_stop.py` | **ใหม่** | 1C |
| `backend/tests/test_max_positions.py` | **ใหม่** | 1C |
| `backend/tests/test_mt5_heartbeat.py` | **ใหม่** | 1C |
| `backend/tests/test_signal_cooldown.py` | **ใหม่** | 1B |
| `backend/tests/test_is_candle_closed_d1.py` | **ใหม่** | 4 |
| `backend/core/smc.py` | **ใหม่** | 2 |
| `backend/core/mtf.py` | **ใหม่** | 2 |
| `backend/core/volume_profile.py` | **ใหม่** | 2 |
| `backend/core/regime_transition.py` | **ใหม่** | 2 |
| `backend/engines/portfolio_risk.py` | **ใหม่** | 3 |
| `backend/engines/risk.py` | **แก้ไข** | 1A, 1B, 3 |
| `backend/engines/execution.py` | **แก้ไข** | 1A, 1C |
| `backend/engines/portfolio.py` | **แก้ไข** | 1A, 1B |
| `backend/engines/market_regime.py` | **แก้ไข** | 2 |
| `backend/engines/news_intelligence.py` | **แก้ไข** | 1B (news_flash) |
| `backend/engines/strategy.py` | **แก้ไข** | 2 |
| `backend/agents.py` | **แก้ไข** | 2 (fallback) |
| `backend/core.py` | **แก้ไข** | 2 |
| `backend/backtest.py` | **แก้ไข** | 4 |
| `backend/main.py` | **แก้ไข** | 1B (alerting + emergency), 2 (fallback), 4 (shutdown) |
| `backend/brokers/paper.py` | **แก้ไข** | 1A (heartbeat) |
| `backend/shared/database/models.py` | **แก้ไข** | 4 (smc_signal_log, strategy_stats) |
| `backend/brokers/MT5_BRIDGE_NOTES.md` | **ใหม่** | 1C |
| `frontend/src/app/page.tsx` | **แก้ไข** | 4 |

---

## สรุปประเด็นจาก Feedback รอบ 1-5 + Deep Analysis (ครบ 35 ข้อ)

| # | ประเด็น | Priority | Phase | การแก้ไข |
|---|---------|----------|-------|---------|
| 1 | **Race Condition Partial TP** | 🔴 | 1C | `asyncio.Lock` ต่อ trade_id |
| 2 | **Stale Candle MTF** | 🔴 | 2 | `is_candle_closed()` check |
| 3 | **Feature Flags / Rollback** | 🔴 | 1B | `config.py` + `DEPLOY.md` |
| 4 | **SMC OB size ≥ 0.5 ATR** | 🟡 | 2 | Volume + size filter |
| 5 | **Walk-Forward 500 bars** | 🟡 | 4 | in-sample 500, OOS 200, slide 200, pass criteria ชัดเจน |
| 6 | **Kelly ramp up** | 🟡 | 3 | Linear ramp 0.10 + min(1.0, trades/50)*0.15 — smooth ไม่มี step |
| 7 | **Kelly bootstrap** | 🟡 | 3 | seed จาก backtest ที่ผ่าน validate แล้วเท่านั้น |
| 8 | **VaR minimum sample** | 🟡 | 3 | ≥ 20 days, fallback Monte Carlo |
| 9 | **Signal cooldown** | 🟡 | 1B | ย้ายจาก in-memory Dict → Redis SETEX / PostgreSQL |
| 10 | **Partial TP MT5 fallback** | 🟡 | 1C | fallback ปิดทั้ง lot |
| 11 | **news_flash calendar source** | 🟡 | 1B | ForexFactory RSS + fallback |
| 12 | **correlation_break placeholder** | 🟡 | 1B | `# PLACEHOLDER` + basic cap ใน Phase 1B |
| 13 | **Dashboard timestamp** | 🟢 | 4 | `triggered_at`, `estimated_reset_at` |
| 14 | **NaN/Inf Guard** | 🔴 | 1A | `validate_atr()` fallback ตาม symbol |
| 15 | **Order Duplication Guard** | 🔴 | 1A | `set` + `deque`, O(1) lookup |
| 16 | **DB Transaction Rollback** | 🔴 | 1A | `db.begin()` + `db.rollback()` |
| 17 | **MT5 Heartbeat + Reconcile** | 🔴 | 1A | ping 30s, reconcile + alert |
| 18 | **MAX_POSITIONS_PER_SYMBOL** | 🔴 | 1A | limit = 2 |
| 19 | **Confirmation Candle** | 🟡 | 1C / 2 | เปลี่ยนเป็น ATR-based buffer (atr*0.1) แทน 0.2% fixed |
| 20 | **Session Filter** | 🟡 | 2 | ครอบคลุม 24 ชม. + LONDON_NY_OVERLAP boost 1.1 + SYDNEY 0.7 |
| 21 | **D1 Bias Lock** | 🟡 | 2 | ATR-normalized slope + configurable D1_SLOPE_THRESHOLD |
| 22 | **Spread Cost in Backtest** | 🟢 | 4 | หัก spread + commission ทุก trade |
| 23 | **Graceful Shutdown** | 🟢 | 4 | signal handler + cancel in-flight |
| 24 | **Timezone daily reset** | 🟡 | 1B | `TRADING_DAY_RESET_TZ = "America/New_York"` |
| 25 | **Cooldown เป็นนาที** | 🟡 | 2 | `SIGNAL_COOLDOWN_MINUTES` |
| 26 | **Calibrate ทุก 7 วัน / 20 trades** | 🟡 | 4 | `CALIBRATION_TRIGGER` + rolling |
| 27 | **Alerting (Telegram primary)** | 🔴 | 1B | `alert.py` + Telegram primary, LINE push |
| 28 | **Indentation Error MTF** | 🔴 | 1A | indent ส่วนเกินใน calculate_mtf_indicators — SyntaxError blocker |
| 29 | **Confidence Scoring Logic** | 🟡 | 2 | MIN_TRADEABLE_CONFIDENCE=0.55, FVG เดี่ยว=0.0, combination-weighted |
| 30 | **Volume Profile Config** | 🟡 | 2 | ระบุ lookback 100, tick_volume, confluence_score usage |
| 31 | **Adaptive RSI Thresholds** | 🟡 | 2 | ตาราง RSI_THRESHOLDS แยกตาม 4 regimes |
| 32 | **Regime Hysteresis** | 🟡 | 2 | REGIME_CONFIRMATION_BARS=3 ป้องกัน flapping |
| 33 | **Time-based Regime Exit** | 🟡 | 1B | ปิด partial 50% + tighten SL ถ้า regime→SIDEWAYS ค้าง >48h |
| 34 | **D1 Candle Timestamp Test** | 🟢 | 4 | unit test is_candle_closed("D1") verify convention ก่อน deploy |
| 35 | **SMC Parameters Sweep** | 🟡 | 4 | ob_size 0.4-0.7, fvg_gap 0.2-0.4, slope 0.003-0.01 ใน walk-forward |

---

## ผลที่คาดหวังหลังพัฒนา

| Metric | ปัจจุบัน | หลัง Phase 1 | หลัง Phase 2 | หลัง Phase 3-4 |
|--------|---------|-------------|-------------|----------------|
| Max Drawdown | ~15-25% | ≤ 12% | ≤ 10% | ≤ 8% |
| Win Rate | ~45-55% | ~50-58% | ~55-65% | ~55-70% |
| Avg R:R ต่อ Trade | ~1.2 | ~1.4 | ~1.6 | ~1.8-2.5 |
| Profit Factor | ~1.1-1.3 | ~1.3-1.5 | ~1.4-1.8 | ≥ 1.5 |
| Sharpe Ratio | ~0.3-0.5 | ~0.5-0.7 | ~0.7-1.0 | ≥ 1.0 |
| Risk of Ruin | ไม่ได้วัด | > 5% | < 3% | ≤ 1% |
| NaN/Inf Incident | ไม่มี guard | 0 (auto-fallback + alert) | 0 | 0 |
| Order Duplication | ไม่มี guard | 0 (idempotency O(1)) | 0 | 0 |
| Alert Response Time | ไม่มี | Push ทันที (Telegram) | Push ทันที | Push ทันที |
| Calibration Cycle | ไม่มี | — | — | ทุก 7 วัน / 20 trades |
