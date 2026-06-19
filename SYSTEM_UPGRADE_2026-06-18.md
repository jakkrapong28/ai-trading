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
