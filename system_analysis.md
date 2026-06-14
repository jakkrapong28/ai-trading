# รายงานวิเคราะห์ระบบ AI Trading Command Center (System Analysis)

> จัดทำจากการอ่านซอร์สโค้ดจริงทุกชั้น (backend engines/core/brokers/services, ERP Node.js, Frontend Next.js)
> อัปเดต: 14 มิ.ย. 2026 · เวอร์ชันระบบ: `FastAPI 3.0.0`
>
> เอกสารนี้อธิบาย "สิ่งที่โค้ดทำจริง" ไม่ใช่สิ่งที่ตั้งใจให้ทำ — จุดที่โค้ดต่างจากเอกสารเดิมจะถูกทำเครื่องหมาย ⚠️

---

## 1. ภาพรวมสถาปัตยกรรม (Architecture Overview)

ระบบเป็น **micro-service 3 ชิ้น + 2 datastore** ที่สื่อสารผ่าน Redis Streams (ภายใน backend) และ HTTP/Webhook (ข้าม service)

```
┌──────────────────────┐         ┌────────────────────────────────────────────┐
│  Frontend (Next.js)  │  HTTP   │  Backend Trading Core (FastAPI · :8000)     │
│  :3000               │ ──────► │  ┌────────────────────────────────────────┐ │
│  - DashboardContext  │  WS     │  │ EventBus (Redis Streams + Pub/Sub)     │ │
│  - 3D Office Canvas   │ ◄─────► │  │  market_data → regime → strategy →     │ │
│  - Risk Gate Panel    │         │  │  agents(vote) → risk → execution →     │ │
└──────────────────────┘         │  │  portfolio                             │ │
            │                     │  └────────────────────────────────────────┘ │
            │ /api/erp/* (proxy)  │  PaperBroker → trades table (PostgreSQL)     │
            ▼                     └───────────────┬──────────────────────────────┘
┌──────────────────────┐   Webhook (HMAC+Idem)   │
│  ERP Service          │ ◄───────────────────────┘
│  (Express · :5001)    │   trade.opened / pnl_realized / ...
│  - Double-entry ledger│
│  - Tax (VAT/CIT)      │ ──► PostgreSQL (erp_ledger, trade_positions, ...)
└──────────────────────┘
```

| Service | เทคโนโลยี | พอร์ต | หน้าที่ | Entry point |
|---|---|---|---|---|
| Trading Core | Python / FastAPI / SQLAlchemy / asyncio | 8000 | engine pipeline, paper broker, REST+WS, Telegram bot | [backend/main.py](backend/main.py) |
| ERP | Node.js / Express (ESM) / `pg` | 5001 | บัญชีคู่ + ภาษี + audit | [erp/server.mjs](erp/server.mjs) |
| Frontend | Next.js (App Router) / React / TS | 3000 | dashboard, virtual office, settings | [frontend/src/app/(dashboard)/](frontend/src/app/) |
| PostgreSQL | 15-alpine (docker) | 5432 | **DB เดียวกัน** `ai_trading` ใช้ร่วม 2 service | [docker-compose.yml](docker-compose.yml) |
| Redis | 7-alpine (docker) | 6379 | event bus (streams + consumer groups + DLQ) | [backend/shared/events/core.py](backend/shared/events/core.py) |

> ⚠️ **ข้อสังเกตสถาปัตยกรรม:** Trading Core (SQLAlchemy models) และ ERP (raw SQL) เขียนลง **ฐานข้อมูล PostgreSQL ตัวเดียวกัน** แต่คนละชุดตาราง — Core เป็นเจ้าของ `trades`, `ai_decision_journal`, ฯลฯ ส่วน ERP เป็นเจ้าของ `erp_ledger`, `trade_positions`, `erp_stats`. ทั้งสองฝั่งต่างมี `initDb()/create_all()` ของตัวเอง ทำให้มีตาราง `erp_delivery_records` ที่ทั้งสองฝั่งพยายามนิยาม (มี migration `ADD COLUMN IF NOT EXISTS` คอยประสาน schema ที่ erp/db/database.mjs:129)

---

## 2. Backend Trading Core — Engine Pipeline

ทุก engine เป็น async task ที่ลงทะเบียนใน `TaskRegistry` ([backend/shared/tasks.py](backend/shared/tasks.py)) และสตาร์ทใน `lifespan()` ([backend/main.py:718](backend/main.py#L718)) สื่อสารกันผ่าน Redis Stream channel ([events/core.py:184](backend/shared/events/core.py#L184))

### 2.1 ลำดับการไหลของสัญญาณ (Signal Flow)

```
MarketDataEngine ──(CH_MARKET_DATA: tick)──► MarketRegimeEngine ──(CH_MARKET_REGIME)─┐
                                                                                     ▼
                          StrategyEngine (evaluate ทุก 60s) ◄── regime + news + candles
                                     │ ผลิต SignalEvent (CH_SIGNALS)
                                     ▼
                          AIDecisionEngine (6 agents vote) ──(CH_AI_DECISION)──►
                                     │ ต้องได้ ≥4/6 เสียง จึงเป็น BUY/SELL
                                     ▼
                          RiskEngine (กฎเหล็ก ~10 ด่าน) ──(CH_RISK_APPROVED)──►
                                     ▼
                          ExecutionEngine → PaperBroker → trades table
                                     │ fire_erp_webhook("trade.opened")
                                     ▼
                          monitor_active_trades (ต่อ tick: SL/TP/Trailing/Partial)
```

### 2.2 รายละเอียดแต่ละ Engine

| Engine | ไฟล์ | กลไกหลัก |
|---|---|---|
| **Market Data** | [engines/market_data.py](backend/engines/market_data.py) | Multi-provider router + failover: crypto→Binance WS, stock/metal→TwelveData→Finnhub→MT5 bridge→Mock. ทุก provider เขียนผ่าน `emit_tick` เดียว; mock เติมเฉพาะ gap. มี heartbeat 30s |
| **Market Regime** | [engines/market_regime.py](backend/engines/market_regime.py) | คำนวณ regime (BULL/BEAR/SIDEWAYS/VOLATILE) จาก **H1 OHLC candle จริง** (EMA50/200, RSI, MACD, ATR) + hysteresis (confirmation bars) |
| **Strategy** | [engines/strategy.py](backend/engines/strategy.py) | ประเมินทุก 60s ต่อ 6 ticker; ถ้า `smc_strategy` ON ใช้ SMC+MTF+VolumeProfile มิฉะนั้น multi-factor (trend 30% + momentum 25% + volume 15% + news 20% + vol 10%). มี cooldown 15 นาที (เก็บใน DB) + กันไม้ซ้ำ |
| **AI Decision (Agents)** | [backend/agents.py](backend/agents.py) | 6 agent (CEO/Chart/Risk/News/Macro/AssetSpecialist) โหวต — **เป็น rule-based deterministic** เป็นค่าเริ่มต้น; เรียก Claude API จริงเฉพาะเมื่อ `claude_fallback=True` (ใช้ `claude-3-haiku-20240307`) ⚠️ |
| **Risk** | [engines/risk.py](backend/engines/risk.py) | CircuitBreakerManager (daily/weekly/consecutive/news/volatility/correlation) + ด่าน: watch-mode, max position/symbol(2), correlation cap/group(1), min confidence(0.6), exposure/asset(10%)/portfolio(20%), spread/reject, spread spike(5×), RR filter, risk% ต่อไม้, order dedup |
| **Execution** | [engines/execution.py](backend/engines/execution.py) | รับ approved → PaperBroker.place_order → ติดตามต่อ tick: 1R→BE, 3R trailing, adaptive trailing (2/1.5/1 ATR + chandelier), partial TP (1R/2R/3R), SL/TP hit, regime-change exit |
| **Portfolio** | [engines/portfolio.py](backend/engines/portfolio.py) | snapshot balance/equity/drawdown → feed circuit breakers + `global_metrics` (/metrics) |

### 2.3 เส้นทางคำสั่งแบบ Manual vs Auto

- **Auto:** `CURRENT_MODE=auto` → RiskEngine ประมวล `CH_AI_DECISION` ครบทุกด่านก่อน approve
- **Manual approve:** ปุ่มบนหน้าเว็บ → `POST /api/approve` ([main.py:1081](backend/main.py#L1081)) สร้าง `RiskApprovedEvent` (strategy_name=`ManualApproval`) **ส่งตรงเข้า Execution โดยข้ามด่าน RiskEngine** — execution จะข้าม dedup-by-open-trade ให้กับ ManualApproval ด้วย ⚠️ (ตั้งใจให้ user เป็นผู้ตัดสิน แต่หมายความว่าปุ่ม Approve ไม่ผ่านกฎเหล็ก)

---

## 3. การคำนวณ PnL, Balance, Equity (สำคัญที่สุด)

ระบบมี **3 จุดคำนวณ PnL** และ **ใช้สูตรไม่ตรงกัน** — นี่คือจุดที่ต้องแก้เร่งด่วน:

| จุด | ไฟล์ | สูตร | คูณ contractSize? |
|---|---|---|---|
| Floating PnL (equity ระหว่างถือ) | [services/accounting.py:34](backend/services/accounting.py#L34) | `dir × (price−entry) × lot × contractSize` | ✅ ใช่ |
| **Realized PnL (ตอนปิดไม้)** | [brokers/paper.py:107](backend/brokers/paper.py#L107) | `(exit−entry) × lot_size` | ❌ **ไม่คูณ** |
| Realized PnL (partial close) | [brokers/paper.py:140](backend/brokers/paper.py#L140) | `(exit−entry) × closed_lot` | ❌ **ไม่คูณ** |
| Backtest/util | [core/base.py:146](backend/core/base.py#L146) `trade_pnl()` | `diff × lot × contractSize` | ✅ ใช่ |

> 🔴 **บั๊กวิกฤต (ยืนยันจากโค้ด):** สำหรับ XAUUSD (`contractSize=100`) และ EURUSD (`100000`) equity ระหว่างถือไม้จะถูกคูณ contractSize แต่ "พอปิดไม้" realized PnL ที่เขียนลง `trades.realized_pnl` **เล็กกว่าจริง 100× (XAUUSD) หรือ 100,000× (EURUSD)**. ผลคือ:
> - equity **กระโดดลง** ทันทีที่ปิดไม้ (floating ใหญ่ → realized เล็ก)
> - `account_balance = STARTING_BALANCE + Σ realized_pnl` ต่ำกว่าจริง → circuit breaker / risk% เพี้ยน
> - รายงาน ERP (ที่รับ `pnl` จาก `realized_pnl`) ต่ำกว่าจริง
>
> เอกสาร `development_plan.md` เดิมระบุว่า "Floating PnL fixed ✅" — ถูกเฉพาะฝั่ง floating; **ฝั่ง realized ใน PaperBroker ยังไม่ถูกแก้** สำหรับ crypto (contractSize=1) ไม่มีผล จึงตรวจไม่เจอเวลาเทสด้วย BTC

นอกจากนี้ **fee ไม่เคยถูกคำนวณ** — `list_orders` คืน `fee: 0.0` ตายตัว และ webhook ส่ง `"fee": 0.0` ([webhooks.py:49](backend/shared/webhooks.py#L49)) ทำให้ ERP `accumulated_fees` ไม่โตจากการเทรดจริง (โตเฉพาะค่า seed เริ่มต้น)

`STARTING_BALANCE` = 45,750 (config) แต่ ERP seed ทุนเริ่มต้น `INITIAL_CAPITAL` = 45,750 พร้อม **hardcode `accumulated_pnl=2340.50, accumulated_fees=145.20`** ([erp/db/database.mjs:158](erp/db/database.mjs#L158)) ⚠️ — ขัดกับที่เอกสารเดิมอ้างว่า "ไม่มี hardcoded"

---

## 4. ERP Service (บัญชี + ภาษี)

- **Auth:** ทุก route (ยกเว้น `/health*`) ผ่าน `apiKeyAuth` (`X-Api-Key`); webhook ผ่าน `validateWebhookSignature` (HMAC SHA-256 บน raw body) + correlation id
- **Idempotency:** `Idempotency-Key` → ตาราง `erp_delivery_records`; ถ้า status=`SUCCESS` แล้ว ตอบ duplicate ทันที (rollback)
- **Double-entry ledger** ([erp/routes/handlers.mjs:34](erp/routes/handlers.mjs#L34)): map event → debit/credit ผังบัญชี (10100 เงินสด, 10200 พอร์ต, 40100 รายได้, 50100 ขาดทุน, 50200 ค่าธรรมเนียม, 18100 ภาษีซื้อ)
- **เหตุการณ์รองรับ:** `trade.opened`, `trade.partial_closed`, `trade.break_even`, `trade.trailing_activated`, `trade.closed`/`trade.pnl_realized`, `fee.recorded`
- **ภาษี:** VAT 7% (input vat ขอคืนจากค่าธรรมเนียม), CIT 20% บน taxable income
- **API:** `/api/ledger`, `/api/tax-summary`, `/api/summary`, `/api/open-positions`, `/api/trades`, `/api/performance` (winRate/profitFactor/avgRR/expectancy/maxDD), `/metrics`, `/health/deep`
- **Reliability:** graceful shutdown (SIGTERM/SIGINT), connection pool, error handler

> ⚠️ **ช่องว่างเหตุการณ์:** Execution ยิงเฉพาะ `trade.opened` และ `trade.pnl_realized` เท่านั้น ([execution.py](backend/engines/execution.py)) — event `break_even` / `trailing_activated` / `partial_closed` **ฝั่ง ERP เขียนรองรับไว้แต่ฝั่ง Core ไม่เคยยิง** ดังนั้นสถานะ `trade_positions` ใน ERP จะไม่เห็น BREAK_EVEN/TRAILING และ partial close ถูกส่งเป็น `trade.pnl_realized` ธรรมดา

---

## 5. Frontend (Next.js Dashboard)

- **State กลาง:** [DashboardContext.tsx](frontend/src/context/DashboardContext.tsx) ถือ WebSocket เดียว + REST polling, อยู่ใน dashboard layout จึงคงอยู่ข้ามแท็บ
- **การเชื่อมต่อ:** WS `ws://localhost:8000/ws` (auto-reconnect 5s) + REST `/api/state`, `/api/erp/*`, `/api/news`
- **หน้า (App Router):** `page` (virtual office), `agents`, `analytics`, `chat`, `performance`, `reports`, `risk`, `settings`, `trading`, `workflow`
- **องค์ประกอบเด่น:** 3D isometric office canvas (agent มีฟองคำพูด), Risk Gate panel (lot/SL/TP/spread/reject/risk%), ปุ่ม Approve/Reject (เปิดเฉพาะตอนสัญญาณ BUY/SELL), AIChartWidget (ดึง `/api/candles`), ERP ledger/tax view
- **WS message types ที่ frontend จัดการ:** `init`, `market_update`, `price_tick`, `agent_typing`, `order_opened`, `order_closed`, `risk:signal:approved/rejected`, `ai:decision:final`

> ⚠️ **ความไม่ตรงกัน frontend/backend:** Context handle `msg.type === "init"` และ `"market_update"` แต่ backend `websocket_bridge` ([main.py:600](backend/main.py#L600)) ส่ง `agent_typing`, `price_tick`, `order_opened/closed`, และ raw `{"type": channel, "data": msg}` — **ไม่เคยส่ง `init`/`market_update`** ดังนั้น state เริ่มต้นมาจาก REST `/api/state` ล้วน (โค้ด init handler เป็น dead path). ค่าเริ่มต้นบางส่วน (activityLogs, newsFeed) เป็น mock hardcoded ในฝั่ง client

---

## 6. ฐานข้อมูลและสคีมา

**Trading Core (SQLAlchemy, [models.py](backend/shared/database/models.py)):** `positions`, `trades`, `ai_decision_journal`, `performance_metrics`, `market_data`, `news_sentiment`, `portfolio_snapshots`, `trade_ledger`, `tax_ledger`, `erp_delivery_records`, `signal_cooldowns`, `smc_signal_logs`, `strategy_stats`

**ERP (raw SQL, [database.mjs](erp/db/database.mjs)):** `erp_ledger`, `erp_stats` (singleton), `erp_delivery_records`, `trade_positions`, `audit_logs` + ดัชนี 9 ตัว

> ⚠️ `database/schema.sql` + `seeds.sql` ถูก mount ตอน docker init แต่ทั้ง Core (`create_all`) และ ERP (`initDb`) สร้างตารางเองตอน startup อยู่แล้ว — มี source-of-truth สคีมาซ้อนกัน 3 ที่ (schema.sql / models.py / database.mjs)

---

## 7. ความปลอดภัยและการตั้งค่า (Security & Config)

| ประเด็น | สถานะปัจจุบัน | หมายเหตุ |
|---|---|---|
| CORS | `allow_origins=["*"]` ทั้ง Core และ ERP | เปิดกว้าง — เหมาะ dev เท่านั้น ⚠️ |
| API auth (Core) | **ไม่มี** — ทุก `/api/*` เปิด public | ERP มี API key แต่ Core ไม่มี ⚠️ |
| Secret ใน `.env` | `backend/.env`, `erp/.env` (มี key จริง) | `update-settings` เขียนทับ `.env` ทั้งไฟล์ ([main.py:1305](backend/main.py#L1305)) — เสี่ยงทับ key ที่ไม่ได้อยู่ในฟอร์ม |
| Webhook integrity | HMAC SHA-256 + idempotency | ✅ แข็งแรง |
| `mask_secret` | mask ค่า key ใน `/api/state` | ✅ |
| Telegram bot | long-poll ใน background | ปิดถ้า token ว่าง/มีคำว่า "กรอก" |

---

## 8. การทดสอบ (Tests)

backend มี **19 ไฟล์เทส** ([backend/tests/](backend/tests/)) ครอบคลุม: circuit breaker, correlation cap, emergency stop, order dedup, partial TP, trailing stop, spread/RR filter, signal cooldown, max positions, candle manager, NaN guard, MT5 heartbeat, DB transaction, alerting, D1 candle close

> ⚠️ ไม่มีเทสที่ตรวจ **realized PnL × contractSize** (จึงทำให้บั๊กข้อ 3 หลุดรอด) และไม่มีเทส integration ระหว่าง Core↔ERP webhook end-to-end

---

## 9. สรุปจุดแข็ง / จุดที่ต้องระวัง

**จุดแข็ง**
- สถาปัตยกรรม event-driven ชัดเจน, มี consumer group + auto-claim + DLQ
- Safety layer ครบ (circuit breaker, dedup, cooldown, correlation cap, NaN guard)
- ERP บัญชีคู่ + HMAC + idempotency ระดับ production
- Data foundation ใช้ OHLC candle จริง (ไม่ใช่ tick) แล้ว
- มีเทสครอบคลุม logic ความเสี่ยงหลายตัว

**ต้องระวัง / หนี้เทคนิค** (รายละเอียดแผนแก้อยู่ใน [development_plan.md](development_plan.md))
1. 🔴 Realized PnL ไม่คูณ contractSize (paper.py) — ตัวเลขเงินผิดสำหรับ XAUUSD/EURUSD
2. 🔴 Fee = 0 ตลอด → บัญชีค่าธรรมเนียม/ภาษีซื้อไม่เดินจริง
3. 🟡 ERP seed PnL/fee hardcoded + แหล่งความจริง balance ซ้อนกัน
4. 🟡 Event break_even/trailing/partial ฝั่ง ERP ไม่ถูกยิงจาก Core
5. 🟡 Core ไม่มี API auth + CORS `*`
6. 🟡 WS `init`/`market_update` เป็น dead path (frontend คาดหวังแต่ backend ไม่ส่ง)
7. 🟢 schema source ซ้อน 3 ที่, mock client data, agent vote ไม่ได้ใช้ AI จริงโดยปริยาย
