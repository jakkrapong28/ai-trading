# System Upgrade — 2026-06-18

สรุปการอัปเกรดระบบ AI-Trading รอบวันที่ 18 มิ.ย. 2026: **ก่อนแก้ → หลังแก้** ทุกส่วน
และ **roadmap** ว่าจะอัปเดตอะไรต่อ

หลักการที่ยึดตลอด: **"ไม่ปล่อยมั่ว"** — ทุกการเปลี่ยนกลยุทธ์ต้องผ่าน backtest walk-forward
ก่อนเชื่อ ไม่เดาว่าดีขึ้น และ auto-trade ปิดไว้จนกว่าจะผ่าน gate จริง

---

## 1. กลยุทธ์ (Strategy) — หัวใจของระบบ

### 1.1 SMC v2 — สมองสัญญาณใหม่
| | ก่อน (v1) | หลัง (v2) |
|---|---|---|
| ทิศทางสัญญาณ | EMA fast/slow crossover (SMC แค่กรองว่าจะเทรดไหม) | มาจาก**โครงสร้างจริง**: MSS/BOS + โซน Demand/Supply + H1 bias + liquidity sweep |
| การจัดเกรด | ไม่มี (binary เทรด/ไม่เทรด) | **TIER A/B/C** ต่ำกว่า C = WATCH (ไม่เทรด) — funnel Stage 1→5b |
| Stop Loss | ATR สมมาตร | **อิงโครงสร้าง** (ใต้โซน Demand / บนโซน Supply) + ปรับ lot ให้ความเสี่ยง $ คงที่ |
| Regime gate | บางส่วน | hard-gate ห้ามสวนเทรนด์ใหญ่ + กรอง RSI overbought/oversold |

ไฟล์: `backend/core/smc.py` (`evaluate_smc_signal`), เทสต์ `backend/tests/test_smc_signal.py` (7 ตัว)

### 1.2 ผลลัพธ์ — คุณภาพต่อเทรด (single-run 90 วัน)
| Symbol | ก่อน PF | หลัง PF | ก่อน WR | หลัง WR |
|---|---|---|---|---|
| XAUUSD | 1.44 | **2.23** | 42% | **53%** |
| BTCUSDT | 0.82 | **1.14** | 29% | **37%** |
| ETHUSDT | 0.68 | **0.81** | 34% | **35%** |

→ **แม่นขึ้นทุกตัว** (โดยเฉพาะทอง) เทรดน้อยลง ~⅓ แต่คุณภาพสูงขึ้น

### 1.3 ผลลัพธ์ — ความทนข้าม regime (walk-forward 730 วัน, window 500 แท่ง)
| Symbol | ก่อน (v1) | หลัง (v2) | ผล |
|---|---|---|---|
| XAUUSD | 29.6% | **44.4%** | +15pp |
| BTCUSDT | 32.4% | **41.2%** | +9pp |
| ETHUSDT | 29.4% | 29.4% | เสมอ |

> เกณฑ์ผ่าน gate = ≥60% ของ window — **ยังไม่ผ่านทุกตัว → auto-trade ปิดต่อ**
> แต่ดีขึ้นจริงทั้งทองและคริปโต

### 1.4 Validation gate ซื่อสัตย์ขึ้น (thin-window guard)
| | ก่อน | หลัง |
|---|---|---|
| window ที่มีเทรด < 5 ตัว | นับเป็น "ผ่าน" ได้ (เช่น 2 เทรด Sharpe 2611 จากความบังเอิญ) | **ผ่านไม่ได้เด็ดขาด** (THIN ⚪) |

ไฟล์: `backend/backtest.py` (`WALK_FORWARD_MIN_TRADES=5`), เทสต์ `test_backtest_gate.py` (9 ตัว)

### 1.5 จูนเพิ่ม — ทดสอบแล้วไม่เก็บ
ลอง `min_tier=B`, `require_bias`, circuit-breaker ในการ backtest — **ไม่มีอันไหนดันให้ถึง 60%**
(เลือกหนักไป→เทรดน้อย→แย่ลง) เก็บ knob ไว้แบบปิด default; คง **base v2** เป็นค่าหลัก

### 1.6 Backtest reproducible (สำคัญสำหรับ 2 เครื่อง)
| | ก่อน | หลัง |
|---|---|---|
| `calculate_risk_of_ruin` | `np.random` ไม่ seed → เลขเปลี่ยนทุกครั้ง | seeded `default_rng(12345)` → **เลขเดียวกันทุกครั้ง ทุกเครื่อง** |

---

## 2. Backend — ฟีเจอร์/การเชื่อมต่อ

| | ก่อน | หลัง |
|---|---|---|
| Live strategy engine | ทิศทาง = `trend_strength > 0` (จุดอ่อนเดียวกับ v1) | ใช้ `evaluate_smc_signal` — **engine จริง = backtest = สมองเดียวกัน** (`strategy.py`) |
| Daily plan endpoint | ไม่มี | `GET /api/daily-plan?symbol=` — bias/regime, setup+TIER, SL อิงโครงสร้าง, TP1/2/3, แนวรับ-ต้าน |
| CLI backtest | `validate` (v1) | เพิ่ม `validate2` (v2) สำหรับ A/B |

---

## 3. Frontend

| | ก่อน | หลัง |
|---|---|---|
| หน้า Office (home) | canvas pixel-art isometric office | **JARVIS / Stark HUD**: arc-reactor core (เลขทุนนับขึ้น), เกจวงกลม (pos/signal/RSI/PnL), market feed สด แยก Crypto/Metal-FX/Equities, กราฟ Market Pulse รายวัน (candles จริง), boot sequence + radar sweep + reveal stagger |
| หน้า Trading | แชต/กราฟ/positions | + การ์ด **แผนเทรดรายวัน** (`DailyPlanCard`) |
| เมนู Sidebar | flat 10 หน้า + Settings | **3 กลุ่ม** WORKSPACE / INTELLIGENCE / PORTFOLIO, **ลบ Settings** (secrets อยู่ใน .env) |
| หน้าซ้ำ | — | ตรวจแล้ว: analytics/performance/workflow/risk/reports **เนื้อต่างกันจริง ไม่ใช่ของซ้ำ** (ไม่ตัด) |

ไฟล์ใหม่/แก้: `(dashboard)/page.tsx`, `components/DailyPlanCard.tsx`, `components/Sidebar.tsx`, `globals.css` (HUD keyframes + reduced-motion guard)

---

## 4. Infra / การบูตระบบ

**กราฟไม่โหลด = backend ไม่ได้สตาร์ท (ไม่ใช่โค้ดพัง)** วิธีบูตบนเครื่อง dev:
```bash
brew services start postgresql@14        # brew pg ไม่มี role postgres/DB ai_trading โดย default
#   (ครั้งแรก) สร้าง role postgres/'yourpassword' + createdb ai_trading ให้ตรง backend/.env
# redis รันอยู่แล้ว
backend/venv/bin/python -m uvicorn backend.main:app --port 8000   # deps อยู่ใน backend/venv ไม่ใช่ system py3
# frontend รันที่ :3000 อยู่แล้ว
```
> ⚠️ มี warning เก่าไม่ร้ายแรงตอนบูต: `[D1 Pre-flight] 'int' object has no attribute 'tzinfo'` (regime ยังคำนวณได้) — ไว้แก้รอบหน้า

---

## 5. สถานะเทสต์
- Backend: **98 passed, 1 skipped** (เพิ่ม smc_signal 7 + gate guard 3)
- Frontend: คอมไพล์ผ่าน, ทุกหน้า render 200

---

## 6. Roadmap — จะอัปเดตอะไรต่อ

### 🔜 ลำดับถัดไป (ตกลงแล้ว)
1. **MT5 Option A — ทำให้ทองเหมือนกันทั้ง 2 เครื่อง (ดีที่สุด)**
   - PC (Windows+MT5) ดูทอง, Mac ดูคริปโต; คริปโต Binance เหมือนกันอยู่แล้ว
   - ปรับ provider ให้ MT5 เป็นแหล่งทองอันดับแรกเมื่อมี `MT5_BRIDGE_URL`
   - ชี้ Mac ไปที่ bridge ของ PC (HTTP) → ราคาทอง MT5 จริงเหมือนกัน, PC ปิดเมื่อไหร่ Mac fallback Binance อัตโนมัติ
   - เขียน `.env.example` + คู่มือตั้ง bridge
   - **กฎเหล็ก:** 2 เครื่องต้องอยู่ git commit เดียวกัน + `.env` FEATURE_FLAGS เหมือนกัน

### 🎯 กลยุทธ์ (ดัน edge ให้ถึง 60% เพื่อเปิด auto-trade ได้จริง)
2. **ฆ่า window หายนะ** ที่ยังเหลือ (บาง window ruin 99%) — regime/volatility filter ที่ลึกกว่าเครื่องมือเดิม
3. หา **feature ใหม่/timeframe ใหม่** (งาน quant research จริง ไม่ใช่จูน filter)
4. ทดสอบ **per-symbol strategy assignment** อย่างเป็นระบบ

### 🔧 Engineering (จาก memory, ยังค้าง)
5. **async-DB ใน execution monitor loop** — ตอนนี้ใช้ blocking `SessionLocal()` ทุก tick (บล็อก event loop)
6. **แก้บั๊ก D1 pre-flight** `'int' object has no attribute 'tzinfo'`
7. split `main.py` (god-file ~1600 บรรทัด) + circular import (เสี่ยงสุด ทำทีหลัง)
8. ติดตั้ง **FinBERT** (ตอนนี้ news ใช้ vader fallback คุณภาพต่ำกว่า)

### ✨ Frontend (ถ้าต้องการเพิ่ม)
9. เอฟเฟกต์ HUD เพิ่ม: particles, data-stream, ตัวเลขวิ่ง
10. ต่อ `DailyPlanCard` / Market Pulse เข้ากับ symbol switcher ให้ครบทุกหน้า

---

## 7. หมายเหตุการ commit
งานทั้งหมดข้างต้น **ยังไม่ได้ commit** (uncommitted บน `main`) — รอสั่งก่อน commit

---

# อัปเดตรอบ 2026-06-20 — เชื่อมต่อ MetaTrader 5 (MT5) จริง

ต่อยอด roadmap ข้อ 1 (MT5 Option A) ให้สำเร็จ + ต่อยอดเป็น "หน้าเชื่อม MT5" และ
"สะท้อนบัญชี MT5 จริงบนเว็บ" หลักการเดิม: **read-only ก่อน ไม่ส่งออเดอร์จริงจนกว่าจะสั่ง**

## 8. เชื่อม MT5 ได้จริง (ราคา + บัญชี)

| | ก่อน | หลัง |
|---|---|---|
| สถานะ MT5 | ไม่เคยเชื่อม (`MT5_BRIDGE_URL` ไม่ตั้ง → provider ปิดเงียบ) | **เชื่อมจริง** บัญชี Exness demo `433787236` / server `Exness-MT5Trial7` / balance 500 USD |
| ราคาทอง XAUUSD | TwelveData/Binance gold | **มาจาก MT5** (`XAUUSDm` → emit เป็น `XAUUSD`) |
| EURUSD | ไม่มี feed เลย | **มาจาก MT5** (`EURUSDm`) |
| คริปโต / หุ้น | Binance / Yahoo | **คงเดิม** (Binance เป็น spot จริง, หุ้น Exness ไม่ quote) |

> Exness ใช้ symbol ลงท้าย `m` (XAUUSDm) → provider map กลับเป็นชื่อ canonical อัตโนมัติ
> (ปรับ suffix ได้ที่ `MT5_SYMBOL_SUFFIX`)

## 9. หน้า "MT5 Connection" (ใหม่) + Sidebar

- หน้าใหม่ `frontend/src/app/(dashboard)/mt5/page.tsx` (เมนู WORKSPACE → **MT5 Connection**)
- กรอก Login / Master password / Server → **กดเชื่อม/ตัดการเชื่อมต่อ** ได้จากเว็บ
- การ์ดสถานะบัญชีสด: balance, equity, leverage, build + ไฟเขียว CONNECTED
- ช่อง **Server เป็น combobox ช่องเดียว** (กดเลือกจากรายชื่อ Exness ที่พบบ่อย + พิมพ์เองได้)
- หลังกดเชื่อม/ตัด → สั่ง `fetchStateData()` ของ context ทันที (HUD อัปเดตเองไม่ต้อง refresh)

## 10. Bridge server ยกระดับ (`tools/mt5_bridge_server.py`)

| ก่อน | หลัง |
|---|---|
| มีแค่ `/health`, `/ticks`, ใช้ `mt5.initialize()` เปล่า | เพิ่ม `/connect` `/disconnect` `/status` `/orders` + **login ด้วย account+password** |
| ไม่มี session | เซฟ creds ที่ `tools/.mt5_session.json` (gitignored) → **auto-connect ตอน start** |
| หลุดแล้วค้าง | **self-heal**: `/status` เจอว่าหลุด → reconnect จาก session อัตโนมัติ |
| — | thread-lock กัน MT5 IPC ชนกัน, คืน `margin_free`, endpoint `/orders` = positions + history |
| รันด้วย python ไหนก็ได้ | **ต้องรันด้วย `py -3.13`** (มี MetaTrader5) — มีสคริปต์ `tools/run_mt5_bridge.ps1` |

## 11. Backend / Provider

- `backend/main.py`: เพิ่ม proxy `POST /api/mt5/connect`, `GET /api/mt5/status`, `POST /api/mt5/disconnect` (ไม่เก็บรหัสฝั่ง backend) + helper `_fetch_mt5_account()` / `_fetch_mt5_orders()`
- `GET /api/state` **MT5-aware**: เมื่อเชื่อมต่ออยู่ → ส่ง `balances`/`orders` จาก MT5 จริง + เพิ่มฟิลด์ `base_balance`, `equity_source` (ถ้าหลุด → fallback ค่า simulated เดิมอัตโนมัติ)
- `backend/engines/providers/mt5_bridge.py`: map `XAUUSDm/EURUSDm` → canonical, default ชี้ `localhost:8765`, เงียบ error เมื่อ bridge ยังไม่รัน
- `backend/.env`: เพิ่ม `MT5_BRIDGE_URL=http://localhost:8765`, `MT5_SYMBOL_SUFFIX=m`

## 12. Dashboard สะท้อนบัญชี MT5 จริง (read-only)

| | ก่อน | หลัง |
|---|---|---|
| TOTAL EQUITY / BASE | เงินจำลอง `STARTING_BALANCE=45,750` | **ยอด MT5 จริง 500 USD** (เมื่อเชื่อมต่อ); หลุด → กลับไป 45,750 อัตโนมัติ |
| ประวัติ/ออเดอร์ | paper trades ใน DB | **positions + history จากบัญชี MT5** (ตอนนี้ว่าง = ตรงกับ demo) |
| PnL บนแกน | today realised (paper) | floating P/L = equity − balance (label "MT5 · FLOATING P/L") |

ไฟล์: `frontend/src/context/DashboardContext.tsx` (state `baseBalance`/`equitySource`),
`frontend/src/app/(dashboard)/page.tsx` (BASE ใช้ค่าจริงแทน hardcode 45,750)

## 13. บทเรียน / ข้อควรรู้ (gotchas)

- **`MetaTrader5` รันได้แค่ Python 3.13** บนเครื่องนี้ (backend venv เป็น 3.14 import ไม่ได้) → bridge ต้อง `py -3.13`
- **Login ด้วย email ใช้กับ API ไม่ได้** (`-6 Authorization failed`) ต้องใช้ **account number + master password** (ตั้งใน Exness Personal Area → บัญชีเทรด → เปลี่ยนรหัสผ่านการซื้อขาย)
- Terminal build 5830 ใหม่กว่าแพ็กเกจ pip 5735 — **ใช้ด้วยกันได้ ไม่ใช่ปัญหา**
- ต้องเปิด **Algo Trading** ใน terminal + เปิด terminal ค้างไว้

## 14. ยังไม่ทำ / ขั้นต่อไป

- ❌ **ส่งออเดอร์จริงไป MT5 ยังไม่ได้** — กดออเดอร์บนเว็บยังเข้า PaperBroker (DB) ไม่ขึ้นใน MT5
  (ต้องเพิ่ม `mt5.order_send` + route execution → MT5 ถ้าต้องการเทรดจริงบน demo)
- equity บน HUD sync ตอน "กดเชื่อม" + ตอนโหลดหน้า; ยังไม่ poll สด ๆ ตลอดเวลา
- งานรอบนี้ **ยังไม่ได้ commit** — `.env` และ `.mt5_session.json` ถูก gitignore (ไม่หลุดขึ้น git)

---

# อัปเดตรอบ 2026-06-20 — Roadmap ข้อ 2: ฆ่า window หายนะ (research + วัดผลจริง)

ต่อยอด roadmap ข้อ 2 ("ดัน edge ให้ถึง 60%") ด้วยกระบวนการ **ไล่ต้นเหตุ → ซ่อมเครื่องวัด →
วัดซ้ำด้วยตัวเลขจริง** (ไม่ปล่อยมั่ว)

## 15. เครื่องมือที่เพิ่ม (ทุก knob default ปิด)
- `evaluate_smc_signal` ([smc.py](backend/core/smc.py)) — 3 stand-aside gate: `block_volatile_regime`,
  `max_atr_expansion`, `min_adx` (chop guard, ADX จาก `calculate_adx`)
- `backtest.py` — consecutive-loss CB เปิดผ่าน cfg (`cb_max_losses`), window size ปรับได้
  (`BT_IN_LEN/BT_OOS_LEN/BT_STEP_LEN`), knob A/B ผ่าน env (`_experiment_knobs`),
  คอลัมน์ vol diagnostic ใน walk-forward report
- เทสต์ใหม่: smc gates, ADX, window-config → **110 passed, 1 skipped**

## 16. ข้อค้นพบ (XAUUSD, SMC v2 walk-forward, ตัวเลขจริง)
1. **window หายนะ #65** (Ruin 100%, Sharpe -1326) = **range chop/whipsaw** ไม่ใช่ volatility
   (vol 0%) — ทุกเทรดโดน SL, regime สลับ BULL↔BEAR ราย ๆ วัน, ไม่มีเบรกตัดขาดทุนรัว
2. **คอขวดตัวจริง = เครื่องวัดพัง** — OOS window 200 แท่ง H1 ได้เทรด ~3-4 ไม้ → **47/67 window
   เป็น THIN (เทรด<5) → เพดาน pass-ratio ~30%** filter ยิ่งตัดเทรดยิ่งแย่

| config (XAUUSD v2) | pass-ratio | thin | เทรด/win |
|---|---|---|---|
| baseline OOS=200 (เดิม) | 19.4% | 47/67 | ~3-4 |
| baseline OOS=400 (วัดถูก) | **35.3%** | 7/34 | 8.3 |
| **OOS=400 + CB(3) + ADX(20)** | **47.1%** | 5/34 | 7.7 |
| 15m/60d baseline OOS=400 | 18.2% | 3/11 | 7.2 |
| 15m/60d + CB(3)+ADX(20) | 27.3% | 4/11 | 6.2 |

3. แค่ขยาย OOS เป็น 400 (ไม่แตะกลยุทธ์) → 19.4%→**35.3%** (ส่วนใหญ่ของ "ความล้มเหลว" เดิมคือ
   noise จาก thin ไม่ใช่ edge แย่)
4. เปิด **CB+ADX** → 35.3%→**47.1%** (+~12pp) — filter พิสูจน์แล้วว่าได้ผล **เมื่อ window ไม่ thin**
5. **M15 ไม่ใช่คำตอบ** — edge อ่อนกว่า 1h ทุกมุม (timeframe ใหม่แบบ M15 noisy เกิน)

## 17. สรุป / ขั้นต่อไป
- **ดีสุด = 1h + CB(3) + ADX(20) = 47.1%** — ดีขึ้นมากจาก 19.4% แต่ **ยังไม่ถึง 60% → auto-trade ปิดต่อ**
- ช่องว่าง 47→60 **ต้องใช้ edge ใหม่จริง (ข้อ 3)** ไม่ใช่แค่ filter/ปรับ window อีกแล้ว
- เฟสถัดไป (A): **เก็บเทรด paper จริง** — journal มีอยู่แล้ว (`SMCSignalLog` + `smc_calibrate` +
  `StrategyStats`) แต่ "อด" เพราะ watch mode ไม่ลงเทรด → outcome ค้าง PENDING; เปิด paper
  auto-execute + หน้ารีวิว เพื่อสะสม ground truth ก่อนตัดสินใจ auto-trade จริง

## 18. Roadmap ข้อ 3 — หา edge ใหม่ iteration 1 (adaptive TP / session) — ตัวเลขจริง
ทดสอบ 2 สมมุติฐานบน base ที่ดีสุด (1h/730d OOS=400 + CB3 + ADX20 = 47.1%):

| config | pass-ratio | Δ vs base | blowups |
|---|---|---|---|
| base (CB3+ADX20) | 47.1% | — | 3 |
| +H1 adaptive-TP (RR ตาม regime) | **50.0%** | +2.9pp | 4 |
| +H2 session gate (ตัด Asian/Sydney) | 47.1% | 0 | 6 |
| +H1+H2 | 32.4% | −14.7pp | 3 |

- **H1 (adaptive TP)** ช่วยนิดเดียว — เพราะตลาด chop ถูก label เป็น BULL/BEAR สลับ (ไม่ใช่
  SIDEWAYS) → RR ต่ำไม่ได้ลงตรงจุดที่หายนะจริง
- **H2 (session gate)** ไม่ช่วย + blowups เพิ่ม (yahoo timestamp เป็น local-tz → session map
  เพี้ยน และ/หรือ ทองไม่ขึ้นกับ session) ; รวม H1+H2 ยิ่งแย่ (ตัดเทรด→thin เพิ่ม)
- **สรุป: เพดานกลยุทธ์ SMC-breakout ≈ 50%** การจูน TP/filter ให้ผลลดน้อยถอยลง knob ทั้งหมด
  คง **default ปิด** (H1 marginal, H2 ติดลบ ไม่เก็บ)

**บทเรียนเชิงกลยุทธ์:** breakout แพ้เชิงโครงสร้างในตลาด range (โดน SL รัว) การกรองออกได้แค่
"ไม่เทรด" แต่ window ก็ยัง fail เพราะ thin/ไม่มีฝั่งชนะ → เลเวอร์จริงที่เหลือคือ **เพิ่มกลยุทธ์
mean-reversion สำหรับ regime range** (ข้อ 4: per-regime strategy) ให้ "ตลาดที่ breakout แพ้"
กลายเป็นตลาดที่ MR ชนะ — หรือไปเฟส A (forward-test config 50% บน paper) เก็บ ground truth จริง

---

# สรุปสถานะรวม + แผนถัดไป (อัปเดต 2026-06-20)

## 19. สถานะ Roadmap (commit milestone แล้ว — branch `strategy-research-milestone`, commit `2525844`)

| ข้อ | งาน | สถานะ | ผล/หมายเหตุ |
|---|---|---|---|
| 1 | MT5 Option A | ✅ เสร็จ | เพิ่ม `backend/.env.example` (+ `erp/.env.example`), un-ignore `*.env.example` |
| 6 | D1 pre-flight `tzinfo` bug | ✅ เสร็จ | อ่าน timestamp column แทน int index + regression test |
| 5 | async-DB ใน execution monitor | ✅ เสร็จ | `run_db()`/snapshot pattern — ไม่ถือ session ข้าม await + เทสต์จริง |
| 2 | ฆ่า window หายนะ | ✅ research เสร็จ | เครื่องวัด+filter ดัน **19.4%→47.1%**; ต้นเหตุ = chop + เครื่องวัดพัง |
| 3 | edge ใหม่ (iter 1) | ✅ เสร็จ | adaptive-TP/session ดันแค่ →50%; **เพดาน SMC-breakout ~50%** |
| 4 | per-regime / mean-reversion | ⬜ ยังไม่ทำ | เลเวอร์จริงที่เหลือดัน 50→60 |
| 7-8 | split main.py / FinBERT | ⬜ ค้าง | engineering เดิม (ยังไม่แตะ) |

**ความจริงสำคัญ:** ทุก knob ใหม่ (vol/CB/ADX/RR/session) **default ปิดหมด** → พฤติกรรม live
ไม่เปลี่ยน; **auto-trade ยังปิด** เพราะ walk-forward gate (≥60%) ยังไม่ผ่าน (ดีสุด ~50%)
config ที่ validate แล้วว่าดีสุด = **1h + CB(3) + ADX(20) [+ adaptive-TP]**

## 20. แผนถัดไป (เลือกเส้นทาง)

### เส้นทาง A — Forward-test paper (แนะนำ: เก็บ ground truth จริง, เลี่ยง backtest overfit)
1. เปิด **paper auto-execute** (ปลอดภัย ไม่ใช่เงินจริง) ด้วย config ดีสุด → ระบบลงเทรด paper เอง
2. เปิด knob ที่ validate แล้ว: ตั้ง `RR_BY_REGIME` + เปิด ADX/CB ใน live ให้ตรง backtest
3. ปล่อยให้ journal เติม: `SMCSignalLog` resolve outcome → `smc_calibrate` → `StrategyStats`
   (ตอนนี้ "อด" เพราะ watch mode — pre-req คือต้องลงเทรด paper จริง)
4. ทำ **หน้ารีวิว journal** (win-rate ต่อ confidence/regime, equity curve จริง)
5. **เกณฑ์เปิด auto-trade จริง:** track record paper ≥ N เทรด + สถิติจริงผ่านเกณฑ์ (ไม่ใช่แค่ backtest)

### เส้นทาง B — ข้อ 4: mean-reversion สำหรับ regime range (ดัน 50→60 ใน backtest)
1. กลยุทธ์ MR: ในตลาด range/SIDEWAYS → ซื้อแนวรับ/ขายแนวต้าน (ตรงข้าม breakout) ทดแทน
   window ที่ breakout แพ้
2. Router ต่อ regime: trending → SMC-breakout, range → MR (ต่อยอด regime ที่มีอยู่)
3. A/B ผ่าน walk-forward เดิม (1h OOS=400) → เป้า pass-ratio เข้าใกล้ 60%

### Engineering ค้าง (ทำคู่ขนานได้)
- ข้อ 7: split `main.py` (~1600 บรรทัด) + circular import
- ข้อ 8: ติดตั้ง FinBERT (news ใช้ vader fallback)
- (เก็บงาน) merge `strategy-research-milestone` → main + push origin เมื่อพร้อม

## 21. เครื่องมือ research ที่เพิ่ม (ใช้ต่อได้)
- `backend/scratch/ab_validate.py` — A/B walk-forward หลาย config ผ่าน env knobs (`BT_*`)
- `backend/scratch/investigate_window65.py` — dump เทรดต่อ window พร้อม context (ไล่ root cause)
- `_experiment_knobs()` ([backtest.py](backend/backtest.py)) — เปิด/ปิด filter ผ่าน env (CB/ADX/vol/RR/session/window-size)
  โดยไม่ต้องแก้โค้ด

---

# อัปเดตรอบ 2026-06-21 — Roadmap ข้อ 4: mean-reversion + per-regime router (research + วัดผลจริง)

ต่อยอด roadmap ข้อ 4 (เลเวอร์ที่เหลือดัน 50→60): เพิ่มกลยุทธ์ที่ 2 (mean-reversion)
ให้ "ตลาดที่ breakout แพ้ (range/chop)" กลายเป็นตลาดที่ MR ชนะ ผ่าน router ต่อ regime
หลักการเดิม **"ไม่ปล่อยมั่ว"**: ทุก knob default ปิด, A/B walk-forward ก่อนเชื่อ

## 22. เครื่องมือที่เพิ่ม (ทุก knob default ปิด)
- `evaluate_mean_reversion` ([mean_reversion.py](backend/core/mean_reversion.py)) — fade ขอบ
  Donchian range (ซื้อพื้น/ขายยอด = ตรงข้าม breakout), gate ด้วย RSI สุดขั้ว + range width +
  regime hard-gate (ห้าม fade สวนเทรนด์ใหญ่) คืน dict รูปแบบเดียวกับ `evaluate_smc_signal`
- Router ใน [backtest.py](backend/backtest.py): `BT_MR_ROUTER` → bar ที่ ADX < `BT_MR_ADX`
  ส่งให้ MR, ADX สูง = trend ส่งให้ SMC-breakout (knob: `BT_MR_RSI_BUY/SELL/LOOKBACK/BAND_ATR/RR`)
- เทสต์ใหม่: `test_mean_reversion.py` (8 ตัว) → **121 passed, 1 skipped**
- เครื่องมือ research: `backend/scratch/ab_mr_router.py`

## 23. ข้อค้นพบ (XAUUSD, walk-forward 1h/730d OOS=400, ตัวเลขจริง)
1. **MR เดี่ยว ๆ มี edge จริงในตลาด chop** (isolate SMC ออก, วัด MR-only):

   | MR-only config | n | WR | PF | maxDD |
   |---|---|---|---|---|
   | ADX<20, rr=2.0 | 5 | 20% | 0.48 | — ❌ |
   | ADX<30, rr=2.0 | 22 | 41% | 1.38 | 9.3% |
   | **ADX<30, rr=1.0** | 28 | **61%** | **1.54** | **5.6%** ✅ |
   | ADX<40, rr=1.0 | 57 | 56% | 1.28 | 7.3% |

   บทเรียน MR: ต้องใช้ **RR=1.0** (เป้า = กลาง range ไม่ใช่ยืด 2R) + route ที่ **ADX<30** (chop
   หายนะไม่ได้อยู่แค่ใต้ 20) — รอบแรกตั้ง rr=2.0 + ADX<20 ผิดทั้งคู่ → MR ยิงแค่ 1 ไม้/288, แพ้

2. **แต่ combined router ไม่ดัน gate** — pass-ratio ราย window:

   | config | pass-ratio | thin | blowups |
   |---|---|---|---|
   | base CB3+ADX20 | 41.2% | 5 | 4 |
   | router adx25 rr1.0 (ดีสุด) | **44.1%** | 4 | 4 |
   | router adx30 rr1.0 | 38.2% | 8 | 4 |
   | router adx35 rr1.0 | 32.4% | 5 | 5 |

3. **ทำไม edge จริงแต่ gate ไม่ขยับ:** MR ยิง ~28 ไม้/730วัน = **<1 ไม้/window** → บางเกินจะพลิก
   verdict ราย window; blowups ยังคา 4 (MR ไม่ได้ซ่อม window หายนะ); routing บาง bar ไป MR ที่ไม่
   ยิง → ลบเทรด SMC ตรงนั้น → thin เพิ่ม (8 vs 5)
4. **การวัดมี noise:** base เดิม 47.1% (§16) รอบนี้ 41.2% — Yahoo คืน bars ต่างกัน (13736 vs 13719)
   → pass-ratio แกว่ง ±หลาย pp บน config เดียวกัน ⇒ **+3pp ของ router จมใน noise** สรุปว่าดีขึ้นไม่ได้

## 24. สรุป / ขั้นต่อไป
- **เพดาน backtest ยังคา ~45-50%** — ทั้ง filter (ข้อ2), adaptive-TP/session (ข้อ3), และ MR router
  (ข้อ4) ดันไม่ถึง 60% คอขวดตัวจริง = **thin window (เทรดน้อยเกินต่อ window) + blowup ไม่กี่ window**
  ซึ่งกลยุทธ์ใหม่บน 1h ไม่แก้ (ความถี่ไม่พอ)
- **MR knob คง default ปิดทั้งหมด** (เหมือน knob อื่นที่ยังไม่ผ่าน) — live ไม่เปลี่ยน, auto-trade ปิดต่อ
  เก็บ engine+router+เทสต์ไว้เป็น scaffolding (edge เดี่ยวพิสูจน์แล้ว ใช้ต่อได้ถ้าแก้ occupancy/ความถี่)
- **บทเรียนเชิงยุทธศาสตร์:** การจูน backtest ชนเพดานซ้ำ ๆ → เลเวอร์ที่เหลือคือ **เส้นทาง A
  (forward-test paper เก็บ ground truth จริง)** มากกว่าจะดัน backtest ต่อ; หรือถ้าจะดัน edge ต่อต้อง
  ขยับ **timeframe ที่เทรดถี่ขึ้น** เพื่อแก้ thin-window โดยตรง (งาน research ก้อนใหม่)

## 25. Root-cause ราย window (2026-06-21) — คอขวดจริง ≠ thin (พลิกความเชื่อเดิม)
แยกแยะทุก OOS window ของ base (1h/730d OOS=400 + CB3 + ADX20) ว่าตกเพราะ thin หรือ edge จริง
และตกเกณฑ์ข้อไหน (`backend/scratch/diagnose_failures.py`):

| symbol | pass | **เพดานถ้าแก้ thin หมด** | real-fail (เทรดพอ แต่ขาดทุน) | blowups (ruin≥50%) |
|---|---|---|---|---|
| XAUUSD | 41.2% | **44.1%** (มี thin ที่จะผ่านแค่ 1) | 15 | 4 |
| BTCUSDT | 48.8% | **48.8%** (ไม่มี thin ที่จะผ่านเลย) | 20 | 12 |
| ETHUSDT | 34.9% | **37.2%** (มี thin ที่จะผ่านแค่ 1) | 24 | 3 |

**ข้อสรุปชี้ขาด (แก้ความเข้าใจผิดที่ฝังมาตั้งแต่ §16):**
- **thin/frequency ไม่ใช่คอขวด** — แก้ thin ให้หมดก็ยังไม่ถึง 50% ทุกตัว
- คอขวดจริง = **window ที่ขาดทุนจริง (PF<1)** จำนวนมาก, ตก PF+Sharpe+Ruin พร้อมกัน (ขาดทุนสุทธิ
  ไม่ใช่เฉียดเส้น) — SMC-breakout เข้าแล้วโดน SL net ในตลาดที่ไม่เป็นใจ
- **filter/stand-aside ดัน pass-ratio ไม่ได้** (FAIL→ยืนเฉย = THIN = ยังไม่ผ่าน) → ทางเดียวสู่ 60%
  คือ **ทำให้ window ขาดทุน → ชนะจริง** = เพิ่ม edge ต่อเทรด หรือเปลี่ยนทิศ/กลยุทธ์ใน window พวกนั้น
  ให้มี "ไม้ชนะพอจะพลิก net" (MR router เดิมยิง <1 ไม้/window จึงพลิกไม่ได้)
- กลุ่มน่าสนใจ (XAU): #13/#16/#19/#22/#31 อยู่ที่ PF 0.98-1.00 — เฉียดเส้น แค่ตัดไม้แพ้ไม่กี่ไม้ก็พลิก

## 26. Engineering — เร่ง walk-forward harness 9x (2026-06-21)
**ปัญหา:** `optimize_smc_parameters` sweep 20 configs/window แต่ละ config เรียก `run_strategy_backtest`
ที่ recompute **indicators + macro + regime ต่อทุก bar ใหม่หมด** ทั้งที่ 20 configs ต่างกันแค่
`ob_size_atr/fvg_gap_atr` (ป้อน SMC level detection เท่านั้น) — regime/indicators เหมือนกันทุก config
→ คำนวณ regime (EMA200/RSI/MACD/ATR บนหน้าต่าง 200 แท่ง) ซ้ำ 20 เท่าโดยเปล่าประโยชน์

**แก้:** เพิ่ม `_precompute_smc_bars()` คำนวณ context ที่ไม่ขึ้นกับ cfg (indicators/macro/regime/atr)
**ครั้งเดียว** ต่อ window แล้ว `run_strategy_backtest(precomputed=...)` ใช้ซ้ำ; งานที่ขึ้นกับ cfg
(SMC levels + scoring + trade sim) ยังรันต่อ config ตามเดิม

| | ก่อน | หลัง |
|---|---|---|
| sweep 20 cfgs / 550 แท่ง | 24.4s | **2.7s (9.0x)** |
| ผลลัพธ์ | — | **เท่าเดิมเป๊ะ** (XAU walk-forward 14/34 = 41.2% ตรงกับโค้ดเก่า) |

- เทสต์ใหม่ `test_backtest_precompute.py` (2 ตัว) pin invariant: precomputed == self-computed
  (trade/PnL/PF เท่ากันทุกไม้) → **123 passed, 1 skipped**
- ผลพลอยได้: validate/walkforward/research (ทุกอย่างที่พึ่ง sweep) เร็วขึ้น ~5-9x → เฟสกลยุทธ์ถัดไป
  ทดลองได้ถี่ขึ้นมาก

---

# อัปเดตรอบ 2026-06-21 (ต่อ) — Pin dataset + Paper auto-execute + MR-primary research

ต่อยอด 3 เรื่องในวันเดียว: (A) ทำเครื่องวัดให้นิ่งก่อน (B) เปิด paper auto-execute ตามเส้นทาง A
(C) research edge รอบถัดไป (MR-as-primary) บนเครื่องวัดที่นิ่งแล้ว หลักการเดิม **"ไม่ปล่อยมั่ว"**

## 27. Pin dataset — walk-forward reproducible (แก้ก่อน research)

**ปัญหา:** config เดียวกันให้ pass-ratio ต่างกัน (47.1% §16 vs 41.2% §23) เพราะ Yahoo คืน
จำนวนแท่งไม่เท่ากันทุกครั้ง (13736 vs 13719) — `range=730d` เลื่อนตามเวลาจริง + ไม่มี cache
→ "+3pp ของ router จมใน noise" (§23.4) ตีความ delta เล็กไม่ได้

| | ก่อน | หลัง |
|---|---|---|
| `fetch_backtest_data` | ยิง Yahoo สดทุกครั้ง ไม่ cache | **disk-cache** ที่ chokepoint เดียว (ทุก caller รวม scratch ได้ cache อัตโนมัติ) |
| ผลซ้ำ | แกว่ง ±หลาย pp บน config เดิม | **เท่ากันเป๊ะ** — walk-forward 2 รอบ = `20.000000%` ทั้งคู่ |
| ข้าม 2 เครื่อง | ไม่การันตี | freeze เป็นไฟล์ commit ได้ → PC/Mac ใช้แท่งเดียวกัน (ตรงกฎเหล็ก §1.6) |

- key = `{symbol}_{interval}_{range}` (sanitize `GC=F`→`GC_F`), parquet→fallback pickle (venv py3.14
  ไม่มี parquet engine), env `BT_DATA_CACHE` + `BT_CACHE_REFRESH=1` (re-pin)
- pin แล้ว 3 symbol → `backend/data/cache/` (XAU 13719 / BTC 17477 / ETH 17474 แท่ง)
- ไฟล์: [`fetch_backtest_data` backtest.py](backend/backtest.py), `backend/scratch/pin_dataset.py`,
  เทสต์ `test_backtest_cache.py` (4 ตัว) → **128 passed**

## 28. Paper auto-execute (เส้นทาง A) — "ทำไมไม่มีออเดอร์เข้า"

**คำถามผู้ใช้:** "ตั้งกฎสูงไปหรือเปล่า ไม่มีออเดอร์เข้าเลย" — ตรวจ backend จริง: **ไม่ใช่กฎเข้มเกิน**
ระบบอยู่ **Watch Mode** ([risk.py:221](backend/engines/risk.py#L221)) ปัดทุกสัญญาณ **ก่อน** ประเมินกฎ
TIER/confidence/spread ด้วยซ้ำ (ฟีเจอร์ปลอดภัยตามหลัก auto-trade ปิด)

| | ก่อน | หลัง |
|---|---|---|
| โหมดตอนบูต | hardcode `"watch"` + ทับ env | honor `CURRENT_MODE` env → **persist ข้าม restart** (default ยัง watch) |
| สมองสัญญาณ live | `smc_strategy=False` → unified ตัวเก่า | **`True`** → TIER A/B/C (สมองเดียวกับ backtest) |
| knob ใน live call | ไม่ส่งเลย (default ล้วน) | ส่ง `min_tier=C` + `min_adx=20` → **live == validated backtest config** |
| โหมดปัจจุบัน | watch | **auto** (flip ผ่าน API ทันที) — ยืนยัน `/api/state` = auto, smc_strategy True |

- ไฟล์: [main.py:138](backend/main.py#L138), [config.py:56](backend/config.py#L56) + `SMC_LIVE_MIN_TIER/ADX`,
  [strategy.py:219](backend/engines/strategy.py#L219), `backend/.env` (+`.env.example`)
- **paper-only/reversible:** MT5 `order_send` ยังไม่ wire → ลง PaperBroker (DB) เท่านั้น ไม่มีเงินจริง;
  กลับ watch ได้ทุกเมื่อ
- **ที่ออเดอร์โผล่:** หน้า journal/ประวัติ + orders ของ dashboard — **ไม่ใช่** แผง MT5 positions (demo ว่าง §12)
- ground-truth loop พร้อม: `run_calibration` resolve `SMCSignalLog` PENDING→WIN/LOSS → `StrategyStats`
- หมายเหตุ: 1h + min_adx=20 + AI committee → ออเดอร์ไม่ถี่ อาจรอเป็นชั่วโมงกว่าจะเห็นไม้แรก (ปกติ)

## 29. Roadmap ข้อ 4 (รอบถัดไป) — MR-as-primary ราย window (ตัวเลขจริง)

**Hypothesis (§25):** คอขวด = window ที่ขาดทุนสุทธิ (PF<1) ไม่ใช่ thin; MR เดี่ยวมี edge (§23) แต่
router เดิม per-**bar** ยิง <1 ไม้/window พลิกไม่ได้ → รอบนี้จัด regime ราย **window** จาก in-sample ADX
(ไม่ lookahead) ให้ window range-dominant ใช้ **MR เป็น engine หลักทั้ง window** เพื่อยิงพอจะพลิก
- knob `BT_MR_PRIMARY` + `BT_MR_PRIMARY_ADX` (default ปิด), per-window decision ใน walk-forward,
  sim branch reuse `evaluate_mean_reversion`; research `ab_mr_primary.py`; เทสต์ `test_mr_primary.py`
  (4 ตัว, spy พิสูจน์ routing) → **132 passed**
- วัดบน **pinned data** → delta = edge จริง ไม่ใช่ noise; ตัวชี้ขาด = window ที่ base PF<1 ถูกพลิกเป็น
  PF≥1.3 กี่อัน (`losing->flipped`)

| symbol | config | pass-ratio | Δ | thin | flipped | regressed |
|---|---|---|---|---|---|---|
| XAUUSD | base CB3+ADX20 | 41.2% (14/34) | — | 5 | — | — |
| | MR-primary adx<20 | 29.4% | −11.8pp | 10 | **0/11** | 5 |
| | MR-primary adx<25 | 26.5% | −14.7pp | 12 | **0/11** | 6 |
| | MR-primary adx<30 | 11.8% | −29.4pp | 19 | **0/11** | 11 |
| BTCUSDT | base CB3+ADX20 | 48.8% (21/43) | — | 2 | — | — |
| | MR-primary adx<20 | 34.9% | −13.9pp | 8 | **0/18** | 7 |
| | (BTC adx<25/30 + ETHUSDT ยังรันอยู่ — เติมเมื่อเสร็จ) | | | | | |

**ข้อสรุป (ชัดเจนจากทุกค่าที่วัด):** MR-as-primary **ไม่เวิร์ก** — แย่ลงทุก config, **flipped 0 ทุกครั้ง**
(พลิก window ขาดทุนเป็นชนะไม่ได้เลย) + regressed window ดี + thin เพิ่มทุกค่า สาเหตุ: regime hard-gate
ของ MR (ห้าม fade สวนเทรนด์) + range-width gate บล็อกที่ขอบ range พอดี → MR ยิงไม่พอแม้เป็น primary
**occupancy ที่ §23 เจอยังไม่หาย** → knob **คง default ปิด** เก็บเป็น scaffolding ไม่ดันแบบ overfit

**บทเรียน:** การเปลี่ยน "ตัวเลือก engine" ราย window ไม่ใช่เลเวอร์ — MR แพ้เพราะ gate ของมันเองบล็อก
ตรงจุดที่ควรยิง เลเวอร์จริงสู่ 60% ต้อง (ก) ผ่อน gate ของ MR ให้ยิงในตลาด chop ได้จริง หรือ (ข) เพิ่ม
edge ต่อเทรดของ breakout ใน window ที่แพ้ หรือ (ค) เน้นเส้นทาง A (forward-test paper เก็บ ground truth)
ที่เพิ่งเปิด (§28) มากกว่าดัน backtest ที่ชนเพดานซ้ำ ๆ — **live ไม่เปลี่ยน (knob ปิด)**
