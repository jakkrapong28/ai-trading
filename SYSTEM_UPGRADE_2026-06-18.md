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
