# แผนพัฒนา AI Trading Command Center (Development Plan)

> อ้างอิงจาก [system_analysis.md](system_analysis.md) (อ่านโค้ดจริงทุกชั้น)
> เรียงตาม **ผลกระทบต่อความถูกต้องของเงิน → ความครบบัญชี → ความปลอดภัย/เสถียร → คุณภาพ → ฟีเจอร์**
> อัปเดตล่าสุด: 14 มิ.ย. 2026 · **เทสรวม 89 ผ่านทั้งหมด** (เริ่มต้น 49 → +40)

---

## สถานะภาพรวม (Status Board)

| งาน | ประเภท | สถานะ |
|---|---|---|
| **P0-1** realized PnL คูณ contractSize | 🔴 บั๊กเงิน | ✅ เสร็จ |
| **P0-2** คำนวณ fee จริง + VAT เดิน | 🔴 บั๊กเงิน | ✅ เสร็จ |
| **P0-3** รวมศูนย์สูตร PnL (`trade_pnl`) | 🔴 หนี้เทคนิค | ✅ เสร็จ |
| **P1-1** webhook break_even/trailing/partial → ERP | 🟡 บัญชีไม่ครบ | ✅ เสร็จ |
| **P1-2** จำกัด CORS ฝั่ง Core + .env merge | 🟡 ความปลอดภัย | ✅ เสร็จ (CORS-only) |
| **P1-3** heartbeat alert + broker disconnect freeze | 🟡 เสถียรภาพ | ✅ เสร็จ |
| **P2** cleanup (WS dead path, mock data, schema, ERP seed) | 🟢 คุณภาพ | ✅ เสร็จ (เว้น manual-approve) |
| **P4-1** backtest validation gate (`validate` + exit code) | 🟢 process | ✅ เสร็จ |
| **P4-3** integration test Core↔ERP (รัน live ผ่าน) | 🟢 process | ✅ เสร็จ |
| **P3** เปิด flag SMC/confirmation/kelly | 🟢 ฟีเจอร์ | ⏳ รอข้อมูลจริง |
| **P4-2** dashboard: feed badge + SMC/VP overlay | 🟢 ฟีเจอร์ | ✅ เสร็จ |
| **P4-4** metrics → Prometheus + Grafana | 🟢 ops | ✅ เสร็จ (พร้อมรัน) |
| **Manual-approve validate** | 🟡 behavioral | ✅ เสร็จ (warn + override + log) |
| **BUG-1** หุ้น mock ราคาเพี้ยน (mock vs Yahoo คนละสเกล) | 🔴 บั๊กข้อมูล | ✅ เสร็จ |
| **BUG-2** หุ้นดึงราคาจริง (Yahoo feed) + แก้ key corruption | 🔴 ข้อมูลจริง | ✅ เสร็จ |
| **P5** เทรดจริง (Live Broker: Binance/MT5) | 🔴 ของใหญ่ · เงินจริง | ⏳ ยังไม่เริ่ม (ดู §P5) |

---

# ✅ สิ่งที่แก้ไปแล้ว (Completed)

## P0 — ความถูกต้องของเงิน

**ปัญหาเดิม:** realized PnL ใน [paper.py](backend/brokers/paper.py) คำนวณ `(exit−entry)×lot` **ไม่คูณ contractSize** ขณะที่ floating PnL คูณ → equity กระโดดตอนปิดไม้ (XAUUSD ผิด 100×, EURUSD 100,000×); fee = 0 ตลอด → ค่าธรรมเนียม/VAT ใน ERP ไม่เดิน

**แก้แล้ว:**
- [core/base.py](backend/core/base.py) เพิ่ม `compute_fee()` คู่กับ `trade_pnl()` → **single source** ของทั้ง PnL และ fee
- [config.py](backend/config.py) เพิ่ม `COMMISSION_RATE` ต่อ asset class (override ได้ผ่าน env `COMMISSION_RATE_*`)
- [paper.py](backend/brokers/paper.py) `close_order` + `partial_close_order` ใช้ `trade_pnl()` (คูณ contractSize) + `compute_fee()`; เปลี่ยนเป็น **สะสม** `realized_pnl`/`fee` (เดิมเขียนทับ → partial+full close ทำกำไรส่วนแรกหาย)
- [models.py](backend/shared/database/models.py) เพิ่มคอลัมน์ `trades.fee` + migration `ADD COLUMN IF NOT EXISTS` ใน `core.ensure_schema_migrations()` (เรียกใน `lifespan` หลัง `create_all` — กันปัญหา column-mismatch 500 ที่ README เตือน)
- [events.py](backend/shared/schema/events.py) `ExecutionEvent` เพิ่มฟิลด์ `fee`; [execution.py](backend/engines/execution.py) (3 จุด) + [main.py](backend/main.py) (closeall, close-order) ส่ง fee เข้า event
- [webhooks.py](backend/shared/webhooks.py) ส่ง `fee` จริงใน `trade.pnl_realized` (เดิม hardcode 0.0)
- [accounting.py](backend/services/accounting.py) `floating_pnl` ใช้ `trade_pnl()` (เลิกคำนวณเอง); `list_orders` คืน `t.fee` จริง
- เทส: [test_realized_pnl_contract_size.py](backend/tests/test_realized_pnl_contract_size.py)

## P1-1 — ยิง webhook เหตุการณ์ระหว่างไม้ → ERP

**ปัญหาเดิม:** ERP เขียนรองรับ break_even/trailing/partial แต่ Core ไม่เคยยิง → audit trail ใน ERP ไม่ตรงสถานะจริง

**แก้แล้ว:**
- [webhooks.py](backend/shared/webhooks.py) `_build_payload` รองรับ 3 event ใหม่ (map `ticker→symbol`, `realized_pnl→pnl` ให้ตรงกับที่ ERP handler อ่าน)
- [execution.py](backend/engines/execution.py) ยิงจริง:
  - `trade.break_even` ตอน 1R→BE (ทั้ง standard และ partial-TP1) — fire ครั้งเดียว (gate ด้วย status OPEN→RUNNING / tp1_hit)
  - `trade.trailing_activated` ตอน SL ล็อกเหนือ entry ครั้งแรก — gate ด้วยคอลัมน์ใหม่ `trades.trailing_notified` (กัน ERP ledger บวมเพราะยิงทุก tick)
  - `trade.partial_closed` แทน `trade.pnl_realized` ในเส้น partial close
- migration: `trades.trailing_notified`; เทส: [test_webhook_payloads.py](backend/tests/test_webhook_payloads.py)

## P1-2 — จำกัด CORS ฝั่ง Core + แก้ .env merge

**เลือกแนวทาง:** CORS-only (ไม่ใส่ API key) — เหมาะ single-user/localhost และไม่ทำให้ frontend พัง

**แก้แล้ว:**
- [main.py](backend/main.py) CORS เปลี่ยนจาก `allow_origins=["*"]` → อ่านจาก env `FRONTEND_ORIGIN` (default `http://localhost:3000,http://127.0.0.1:3000`) เว็บอื่นยิง API ฝั่ง Core ไม่ได้แล้ว
- `update-settings` เปลี่ยนจากเขียนทับ `.env` ทั้งไฟล์ → **merge** (รักษา `ERP_API_KEY`, `ERP_WEBHOOK_SECRET`, `STARTING_BALANCE`, `COMMISSION_RATE_*` ฯลฯ ที่ไม่ได้อยู่ในฟอร์ม — เดิมโดนลบทุกครั้งที่กดบันทึก settings)

## P1-3 — Market data heartbeat + broker disconnect

**แก้แล้ว:**
- [market_data.py](backend/engines/market_data.py) `heartbeat_monitor` ยิง `send_alert("ERROR")` เมื่อ feed stale >120s (edge-triggered ต่อ symbol + แจ้งตอน recover) — เดิม log เฉยๆ
- [paper.py](backend/brokers/paper.py) `handle_disconnect` **freeze เทรด** (ตั้ง `CURRENT_MODE=watch` + `PORTFOLIO_CRITICAL_WATCH=true` + alert CRITICAL) — paper broker ปิดไม้ที่ venue ภายนอกไม่ได้ จึงหยุดเปิด exposure ใหม่แทนการ blind-close; อัปเดต [test_mt5_heartbeat.py](backend/tests/test_mt5_heartbeat.py)

## P2 — Cleanup / ลด dead path

| งาน | สิ่งที่ทำ |
|---|---|
| **WS dead path** | ลบ handler `init`/`market_update` ที่ backend ไม่เคยส่ง + helper `mapJournalTypeToAgent` ที่ตายตาม ([DashboardContext.tsx](frontend/src/context/DashboardContext.tsx)); state เริ่มต้นมาจาก REST `/api/state` (typecheck ผ่าน) |
| **Mock client data** | `activityLogs` + `newsFeed` เริ่มจาก `[]` (เดิม hardcoded เวลา/ข่าวปลอมทำให้ดูเหมือนข้อมูลจริง) |
| **Schema source** | พบว่า `database/schema.sql`+`seeds.sql` เป็น **ตาราง orphan ทั้งชุด** (market_snapshots/trade_orders/account_balances + audit_logs NOT NULL ที่ชนกับ ERP) ที่ไม่มี service ไหนใช้ → **เลิก mount ใน [docker-compose.yml](docker-compose.yml)** (ของจริงมาจาก create_all + initDb) |
| **ERP seed** | ลบ hardcode `accumulated_pnl=2340.50, fees=145.20` → เริ่มที่ `0,0` ([database.mjs](erp/db/database.mjs)) |

## P4-1 — Backtest validation gate

**ปัญหาเดิม:** `backtest.py walkforward` มีเกณฑ์ pass/fail แต่ print เฉยๆ แล้ว exit 0 เสมอ → ใช้เป็น gate จริงไม่ได้

**แก้แล้ว:** ([backtest.py](backend/backtest.py))
- คำสั่งใหม่ `python backend/backtest.py validate [SYMBOL]` → รัน walk-forward แล้ว **คืน exit code 0 (ผ่าน) / 1 (ไม่ผ่าน)** ใช้เป็น gate ก่อนเปิด flag หรือ deploy
- แยก logic เป็น `evaluate_walk_forward()` (pure, ไม่มี I/O) + constant `WALK_FORWARD_PASS_CRITERIA` (ใช้ร่วมกับ report เดิม กันค่าเกณฑ์ drift)
- เกณฑ์ต่อ window: Sharpe≥1.0, PF≥1.3, MaxDD≤15%, Ruin≤5%; **gate ผ่านเมื่อ ≥60% ของ ≥3 windows** ผ่าน
- เทส: [test_backtest_gate.py](backend/tests/test_backtest_gate.py) (6 เคส, ไม่ใช้ network)

## P4-3 — Integration test Core↔ERP (E2E)

**แก้แล้ว:**
- [test_erp_integration.py](backend/tests/test_erp_integration.py) ยิง signed webhook (opened→pnl_realized) เข้า ERP จริง ตรวจ double-entry สมดุล (debit=credit), fee/VAT เดินจริง, closed trade ใน `/api/trades`, idempotency กันซ้ำ; **auto-skip เมื่อ ERP ไม่รัน** (โหลด `erp/.env` ให้เอง)
- [test_webhook_payloads.py](backend/tests/test_webhook_payloads.py) contract test ล็อก field ทุก event ให้ตรงกับที่ ERP อ่าน
- **รันจริงกับ ERP live ผ่านแล้ว** → ยืนยัน PnL=100.0 (contractSize-correct), fee 1.61, VAT ถึง ledger, idempotency duplicate=true

---

## ✅ BUG-1 — หุ้น mock ราคาเพี้ยน (mock vs Yahoo คนละสเกล)

**อาการ (จากภาพจริง):** AAPL — RISK GATE/header ราคา ~187 แต่กราฟแท่งเทียน ~290, มีแท่งดิ่งปลอม 290→187 ขวาสุด, RSI 4.8 สุดขั้ว, EMA Bearish แต่ Signal BUY, change -327.85

**สาเหตุราก:** หุ้น US ไม่มี API key (TwelveData/Finnhub) → fallback เป็น mock ที่ random-walk จาก **base hardcode เก่า ($190)** ขณะที่ CandleManager bootstrap ราคา **จริงจาก Yahoo (~$290)** — mock tick (187) ถูก feed เข้า candle เดียวกัน → แท่งพัง → RSI/EMA/signal เพี้ยนตาม (หุ้น US ทุกตัว ไม่ใช่แค่ AAPL)

**แก้แล้ว ([mock.py](backend/engines/providers/mock.py)):**
- mock **seed จากราคา candle จริง** (Yahoo close) ตั้งแต่ tick แรก แทน base hardcode
- ถ้า mock drift ห่างจากสเกล candle จริง >5% → **resync snap กลับ** อัตโนมัติ (กันกรณีเริ่มก่อน candle พร้อม)
- step random-walk ปรับเป็นสัดส่วนของราคา (290 กับ 2350 ขยับสมเหตุผล)
- ครอบคลุมหุ้น+ทองทุกตัวจาก `SYMBOLS` (เพิ่ม AMZN ที่เดิมตกหล่น)
- เทส [test_mock_resync.py](backend/tests/test_mock_resync.py) (6 เคส)
> ⚠️ Core ที่รันอยู่ต้อง **restart** ก่อนถึงจะเห็นผล (โค้ดใหม่). หรือใส่ API key หุ้นจริงก็หายเช่นกัน

## ✅ BUG-2 — หุ้น US ดึงราคาจริง (Yahoo) + แก้ key corruption

**ปัญหา:** AAPL/NVDA/TSLA/MSFT/AMZN เป็น **mock** ทั้งที่ใส่ key — เพราะ (ก) TwelveData/Finnhub **free tier ไม่สตรีมหุ้น US ทาง WebSocket** (TD รับแค่ XAU/USD, Finnhub free ไม่มี stock trade), (ข) **key ใน .env ถูก corrupt เป็นค่า masked 8 ตัว** (`****5062`) จากบั๊ก settings-save ที่ frontend ส่ง mask กลับมาแล้วเขียนทับ key จริง

**แก้แล้ว:**
- **YahooProvider ใหม่** ([providers/yahoo.py](backend/engines/providers/yahoo.py)) — poll Yahoo v8 chart (`regularMarketPrice`) ทุก ~12s ดึงราคาหุ้น **จริง ฟรี ไม่ต้องใช้ key** (แหล่งเดียวกับ candle → สเกลตรงกัน); อยู่เหนือ mock, ใต้ WS feed จริง (yield ให้ถ้ามี real-time WS); ลงทะเบียนใน [market_data.py](backend/engines/market_data.py); ครอบ AAPL/NVDA/TSLA/MSFT/AMZN
- **แก้ root cause key corruption** ([main.py](backend/main.py) `update-settings`) — ข้ามค่าที่เป็น mask (`****…`) ไม่ให้เขียนทับ key จริง (`_is_masked`)
- เทส [test_yahoo_provider.py](backend/tests/test_yahoo_provider.py) (5) + [test_settings_mask_guard.py](backend/tests/test_settings_mask_guard.py) (2)

**ยืนยันรันจริง:** หุ้นทั้ง 5 → `source=yahoo, status=live` ราคาจริง (AAPL 291, NVDA 205, TSLA 406, MSFT 391, AMZN 238); candle/RSI/signal สอดคล้อง ไม่มีหน้าผา/RSI เพี้ยน
> หมายเหตุ: Yahoo เป็น near-real-time (อาจดีเลย์เล็กน้อย) — ถ้าต้องการ real-time แท้ ใส่ key **จริง** ของ TwelveData/Finnhub (paid) แล้ว WS provider จะ override Yahoo เอง

---

# ⏳ สิ่งที่เหลือ (Remaining)

## P3 — เปิด Intelligence Features (ติดเงื่อนไขข้อมูลจริง)

> ⚠️ ทำตอนนี้ไม่ได้ — ต้องเดินระบบสะสม closed trades จริงก่อน แล้วเปิดทีละ flag + เฝ้าดู 1 สัปดาห์ ตอนนี้มีเครื่องมือ gate (`backtest.py validate`) พร้อมแล้ว

| ขั้น | Flag ([config.py](backend/config.py)) | เงื่อนไขเปิด | วิธีวัด |
|---|---|---|---|
| 1 | `smc_strategy` | closed trades ≥ 50 **และ** calibrated win-rate ≥ baseline | `/api/state.calibration` + ERP `/api/performance` |
| 2 | `confirmation_candle` | SMC ทำงาน 1 สัปดาห์ไม่มี error | log review |
| 3 | `partial_tp` | RR เฉลี่ยจาก ERP ≥ 1.5 | `/api/performance.averageRR` |
| 4 | `kelly_sizing` | `backtest.py validate` ผ่าน (≥60% windows) | exit code = 0 |
| 5 | `session_filter` | ยืนยัน session boost จาก data จริง | smc_calibrate |
| 6 | `claude_fallback` | ตั้ง `ANTHROPIC_API_KEY` + ยอมรับ latency/cost | agent vote ใช้ AI จริง |

> agent vote ([agents.py](backend/agents.py)) ตอนนี้เป็น rule-based — ถ้าจะใช้ "AI จริง" ต้องเปิด `claude_fallback` และพิจารณาอัปเกรดจาก `claude-3-haiku-20240307` เป็นรุ่นปัจจุบัน

## P4-2 — Dashboard เพิ่มเติม (frontend)

✅ **เสร็จส่วนแรก (feed badge + calibration timestamp):**
- backend: เพิ่ม `feed_status()` ([providers/base.py](backend/engines/providers/base.py)) คืน `{source, age, status}` (live/stale/mock/offline) + ใส่ `data_sources` และ `calibration.last_calibrated_at` ใน `/api/state` ([main.py](backend/main.py)); เทส [test_feed_status.py](backend/tests/test_feed_status.py)
- frontend: [DashboardContext.tsx](frontend/src/context/DashboardContext.tsx) เก็บ `dataSources` + `calibration.last_calibrated_at`; [Topbar.tsx](frontend/src/components/Topbar.tsx) แสดง **badge แหล่งข้อมูลของ symbol ปัจจุบัน** (LIVE/STALE/MOCK/OFFLINE สี + tooltip source/age) และแก้ badge "WS Connected" ให้สะท้อน `wsStatus` จริง (เดิม hardcoded)

✅ **เสร็จส่วน SMC/Volume Profile overlay:**
- backend: เพิ่ม `detect_smc_levels()` ([smc.py](backend/core/smc.py)) คืน **price levels ที่วาดได้จริง** (order_blocks/fvgs zone top-bottom, swings, mss) + endpoint `/api/smc` ([main.py](backend/main.py)) ส่ง levels + Volume Profile (POC/VAH/VAL/VWAP) + ATR; เทส [test_smc_levels.py](backend/tests/test_smc_levels.py) (5 เคส)
- frontend: [AIChartWidget.tsx](frontend/src/components/AIChartWidget.tsx) เพิ่มปุ่ม **SMC** วาด overlay บน lightweight-charts — POC (เส้นทึบ), VAH/VAL (ประ), OB zone (เขียว/แดงตาม bull/bear), FVG zone (ม่วง), MSS (เหลือง) ดึงจาก `/api/smc` + poll 15s
- **ยืนยันรันจริงกับ Core live** — `/api/smc?symbol=XAUUSD` คืน swings + POC/VAH/VAL ถูกต้อง

## ✅ P4-4 — Metrics → Prometheus + Grafana (เสร็จ · พร้อมรัน)

**แก้แล้ว:**
- backend: เพิ่ม `/metrics/prometheus` ([main.py](backend/main.py)) ในรูปแบบ Prometheus text 0.0.4 (JSON เดิมที่ `/metrics` ยังอยู่) — exposition builder แยกเป็น pure module [metrics_prom.py](backend/shared/metrics_prom.py) (signals/orders/win-rate/drawdown + nan/correlation counters + active tasks + **feed live/age ต่อ symbol**); เทส [test_metrics_prom.py](backend/tests/test_metrics_prom.py) · **ยืนยันรันจริงกับ Core live**
- ERP: เพิ่ม `/metrics/prometheus` ([handlers.mjs](erp/routes/handlers.mjs) + [server.mjs](erp/server.mjs)) — PnL/fees/win-rate/avgRR/**deliveryFailures**/uptime; ตั้งเป็น public path ใน [apiKeyAuth.mjs](erp/middleware/apiKeyAuth.mjs) ให้ scraper ยิงได้โดยไม่ต้องมี key
- infra: [docker-compose.yml](docker-compose.yml) เพิ่ม service `prometheus` (:9090) + `grafana` (:3001) พร้อม config ใน [monitoring/](monitoring/) — prometheus scrape Core/ERP ผ่าน `host.docker.internal`, Grafana auto-provision datasource + **dashboard สำเร็จรูป** (Net PnL, Win Rate, Webhook failures, feed health, signal pipeline)

**วิธีรัน:**
```bash
docker compose up -d prometheus grafana
# เปิด Grafana: http://localhost:3001  (admin/admin) → dashboard "AI Trading — System Health"
# Prometheus targets: http://localhost:9090/targets  (ควรเห็น core+erp = UP)
```
> ⚠️ ERP ที่รันอยู่ต้อง **restart** ก่อนถึงจะมี route `/metrics/prometheus` (โค้ดใหม่). Core endpoint ทดสอบ live แล้ว
> *(ยังไม่ launch container ให้ — เป็น image pull หนัก สั่งเองด้วยคำสั่งด้านบนได้เลย)*

## ✅ Manual-approve validate (เสร็จ · แนวทาง "warn + override + log")

**ปัญหาเดิม:** `POST /api/approve` สร้าง `RiskApprovedEvent` ส่งตรงเข้า Execution **ข้ามด่านความปลอดภัยทั้งหมด** — แม้ circuit breaker (daily-loss lockout) ทำงานอยู่ ก็ยังกดเปิดออเดอร์ได้

**แก้แล้ว (เลือกแนวทาง: เตือนแต่ override ได้ + log):**
- [main.py](backend/main.py) `/api/approve` ตอนนี้เช็ค `check_trade_risk()` (พับ circuit breaker เข้าไปด้วย) ก่อนยิง:
  - ติดกฎ + ไม่ override → คืน `{status:"blocked", reasons:[...]}` **ไม่เปิดออเดอร์**
  - override=true (หรือผ่านกฎ) → เปิด; ถ้าเป็น override จะ **log `MANUAL_OVERRIDE` ลง journal + `send_alert("WARNING")`** เก็บ audit
  - รับ body `{override: bool}` แบบ optional (เข้ากันได้กับ caller เดิม)
- [DashboardContext.tsx](frontend/src/context/DashboardContext.tsx) `handleApprove` — ถ้า backend ตอบ `blocked` เด้ง `confirm` แสดงเหตุผลที่ติด แล้วถ้ายืนยันค่อยยิงซ้ำด้วย `override:true`; กัน MouseEvent ไม่ให้กลายเป็น override โดยบังเอิญ (`=== true`) + แก้ call site เป็น `() => handleApprove()`
- เทส [test_manual_approve_gate.py](backend/tests/test_manual_approve_gate.py) (clean ผ่าน, circuit breaker บล็อก, lot ใหญ่เกิน risk%)

---

## 🔴 P5 — เทรดจริง (Live Broker Execution) · ยังไม่เริ่ม

> ⚠️ **เงินจริง — งานนี้ใหญ่และเสี่ยงสุดในระบบ** ห้ามต่อเงินจริงจนกว่าจะผ่าน testnet + paper validation (P3) ครบ
> สถานะปัจจุบัน: **paper trading 100%** — ทุกออเดอร์ใช้ `PaperBroker` ([execution.py:36](backend/engines/execution.py#L36)) เขียนลง DB อย่างเดียว; Binance/MT5 เชื่อมแค่ **อ่านราคา** (Binance public WS `@ticker`, MT5 bridge `GET /ticks`) ไม่มีการส่งออเดอร์; `PAPER_MODE` env มีแต่ยังไม่ wire ให้สลับ broker

### สถาปัตยกรรมเป้าหมาย

```
RiskApprovedEvent → ExecutionEngine → broker = (PaperBroker | BinanceBroker | MT5Broker)
                                              ↑ เลือกตาม PAPER_MODE / BROKER env
                  live: ส่ง order จริง → exchange → reconcile position จริงกลับ DB
```

### งานย่อย (ทำตามลำดับ — แต่ละขั้นต้องผ่านก่อนไปต่อ)

| # | งาน | รายละเอียด | ไฟล์หลัก |
|---|---|---|---|
| **P5-1** | **Broker factory + wiring** | `make_broker()` เลือก broker ตาม env `PAPER_MODE`/`BROKER`; execution + main.py close paths เรียกผ่าน factory แทน `PaperBroker()` ตรงๆ; default = paper (กันอุบัติเหตุ) | `brokers/__init__.py` (ใหม่), `engines/execution.py`, `main.py` |
| **P5-2** | **BinanceBroker (Testnet ก่อน)** | implement `BrokerAdapter` — place/close/modify ผ่าน Binance REST (spot/futures testnet); แปลง lot↔qty, symbol mapping (BTCUSDT…); จัดการ response/error จริง | `brokers/binance.py` (ใหม่) |
| **P5-3** | **Order reconciliation จริง** | `reconcile_positions` query position จาก exchange (ไม่ใช่ DB ตัวเอง); sync fill price/qty/status จริง; ตรวจ order ค้าง/หลุด | `brokers/binance.py`, `brokers/base.py` |
| **P5-4** | **Fill / slippage / partial / reject จริง** | paper เติม fill ที่ราคา signal ทันที — live ต้องอ่าน fill จริง (อาจ slip/partial/reject), อัปเดต `entry_price`/`lot_size`/fee จาก exchange | `engines/execution.py`, `brokers/binance.py` |
| **P5-5** | **Kill-switch + safety rails** | env `LIVE_TRADING_ENABLED` (ต้อง = true ชั้นที่ 2), จำกัด max notional/leverage ต่อไม้, ปุ่มหยุดฉุกเฉินตัด live, แสดง **badge "LIVE 🔴" เด่นชัดบน UI** เมื่อไม่ใช่ paper | `config.py`, `main.py`, frontend `Topbar.tsx` |
| **P5-6** | **MT5Broker (option)** | ขยาย MT5 bridge ให้รับออเดอร์ (`POST /order` ฝั่ง bridge) + `brokers/mt5.py` polling/ส่งคำสั่ง; ต้องมี MT5 terminal + demo account | `tools/mt5_bridge_server.py`, `brokers/mt5.py` (ใหม่) |
| **P5-7** | **Reliability ตอน live** | กรณี network หลุดกลางออเดอร์ (idempotent order id), retry ที่ปลอดภัย, reconcile หลัง reconnect, alert ทุก state ผิดปกติ | `brokers/binance.py`, `engines/execution.py` |
| **P5-8** | **Secrets + permissions** | Binance API key/secret ที่มีสิทธิ์ **trade เท่านั้น** (ปิด withdraw), IP whitelist; เก็บใน `.env` ไม่ commit; ไม่ส่ง key ออก `/api/state` (mask อยู่แล้ว) | `.env`, `main.py` |

### เกณฑ์ก่อนเปิดเงินจริง (Go-Live Gate)

1. ผ่าน **P3** — closed trades (paper) ≥ 50, `backtest.py validate` ผ่าน, win-rate/expectancy เป็นบวก
2. รัน **Binance Testnet** ต่อเนื่อง ≥ 1 สัปดาห์ ไม่มี order desync / state ผิด
3. reconciliation ตรง 100% (exchange position == DB) ในช่วงทดสอบ
4. ทดสอบ kill-switch + network-drop recovery ได้จริง
5. เริ่มเงินจริงด้วย **notional เล็กสุด** + max 1 position ก่อน scale

### Definition of Done (P5)

- สลับ paper ↔ live ผ่าน env ได้ปลอดภัย, default paper
- BinanceBroker เปิด/ปิด/แก้ออเดอร์บน **testnet** ได้ + reconcile ตรง
- มี kill-switch + LIVE badge + safety limits
- ผ่าน Go-Live Gate ครบทุกข้อก่อนแตะเงินจริง

---

## งานตอน Deploy (สำคัญ)

- ⚠️ ข้อมูล `trades` / ERP ledger เก่าที่เกิดก่อนแก้ P0 มี `realized_pnl`/fee ผิด (XAUUSD เล็กไป 100×) — ควร `reset-data` หรือ backfill ก่อนเชื่อถือ equity/รายงาน
- ตั้ง env ให้ครบ: `FRONTEND_ORIGIN`, `ERP_API_KEY`, `ERP_WEBHOOK_SECRET`, (option) `COMMISSION_RATE_*`

---

## Definition of Done ต่อ Phase

- **P0** ✅ — XAUUSD เปิด-ปิดไม้แล้ว equity ต่อเนื่องไม่กระโดด; `realized_pnl` ใน DB ตรงกับ floating ก่อนปิด; fee สะสมใน ERP โตจริง; เทสผ่าน
- **P1** ✅ — ERP เห็น BREAK_EVEN/TRAILING/partial; เว็บนอก origin ยิง API ไม่ได้; feed ตาย >120s มี alert + freeze
- **P2** ✅ — ไม่มี dead WS handler; ERP เริ่มที่ 0; schema ไม่มี orphan source แล้ว
- **P4-1/P4-3** ✅ — มี backtest gate (exit code) + integration test ที่รัน live ผ่าน
- **P4-2/P4-4** ✅ — dashboard feed badge + SMC/VP overlay + Prometheus/Grafana
- **Manual-approve** ✅ — กด Approve ติดกฎ → บล็อก/override + log
- **P3** ⏳ — เปิด flag ตามเงื่อนไขโดยมีตัวเลข backtest/calibration รองรับ (รอ closed trades จริง)
- **P5** ⏳ — Live broker (Binance/MT5): สลับ paper↔live ปลอดภัย, testnet ผ่าน, มี kill-switch + Go-Live Gate ครบก่อนแตะเงินจริง

---

## ไฟล์ที่แก้ในรอบนี้ (สรุป)

**Backend:** `config.py`, `core/base.py`, `core/smc.py`, `brokers/paper.py`, `services/accounting.py`, `engines/execution.py`, `engines/market_data.py`, `engines/providers/base.py`, `engines/providers/mock.py`, `engines/providers/yahoo.py` (ใหม่), `engines/providers/__init__.py`, `shared/schema/events.py`, `shared/webhooks.py`, `shared/metrics_prom.py`, `shared/database/models.py`, `shared/database/core.py`, `main.py`, `backtest.py`
**Frontend:** `src/context/DashboardContext.tsx`, `src/components/Topbar.tsx`, `src/components/AIChartWidget.tsx`, `src/app/(dashboard)/trading/page.tsx`
**ERP / Infra:** `erp/db/database.mjs`, `erp/routes/handlers.mjs`, `erp/server.mjs`, `erp/middleware/apiKeyAuth.mjs`, `docker-compose.yml`, `monitoring/*`
**Tests (ใหม่):** `test_realized_pnl_contract_size.py`, `test_webhook_payloads.py`, `test_erp_integration.py`, `test_backtest_gate.py`, `test_feed_status.py`, `test_smc_levels.py`, `test_metrics_prom.py`, `test_manual_approve_gate.py`, `test_mock_resync.py`, `test_yahoo_provider.py`, `test_settings_mask_guard.py` · (อัปเดต) `test_mt5_heartbeat.py`
