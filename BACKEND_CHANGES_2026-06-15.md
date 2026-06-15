# Backend Changes — 2026-06-15 (ก่อนตลาดเปิด 20:30)

สรุปสิ่งที่แก้ **หลังจาก pull code ล่าสุด** (baseline = commit `39233cf`) รอบนี้เน้น
**"คำนวณถูกต้องทุกจุด ไม่ข้ามขั้น ไม่เดาสุ่ม ทุก data ต้องผ่านการคำนวณ"** และเตรียมรันจริง

ทุกการเปลี่ยน verify ด้วย: `py_compile` + import จริง + **backtest จริง** + **smoke test boot แอปจริง**

ไฟล์ที่แก้ (7 ไฟล์ backend + 1 DB migration):
`agents.py · backtest.py · core/base.py · engines/market_regime.py · engines/risk.py · engines/strategy.py · main.py`

---

## 🔴 Critical (ถ้าไม่แก้ = รันจริงพัง)

### 1. DB schema ขาด column `trades.lowest_price` → **execution trade-monitor พังทั้งหมด**
- **อาการ:** ตอน boot ขึ้น log รัว `column trades.lowest_price does not exist` — execution จัดการ SL/TP/trailing ของออเดอร์ที่เปิดอยู่**ไม่ได้เลย**, strategy เช็ค open trade ก็ error
- **เหตุ:** `Base.metadata.create_all` สร้างตารางใหม่ได้แต่ไม่ ALTER ตารางเก่า → model มี `lowest_price` แต่ DB ไม่มี
- **แก้:** `ALTER TABLE trades ADD COLUMN lowest_price DOUBLE PRECISION` (ไม่กระทบข้อมูลเดิม) → verify แล้ว schema ตรง model ครบ, error = 0
- ⚠️ **ข้อควรระวังต่อไป:** ระบบไม่มี migration อัตโนมัติ — ถ้าเพิ่ม column ใน model ต้อง ALTER เอง (พิจารณาใช้ Alembic ที่มีใน venv อยู่แล้ว)

### 2. Bug ใน `calculate_regime_from_h1` (market_regime.py) → **regime H1 ล้มเงียบ**
- **เดิม:** `rsi = ... if not rs.iloc[-1:] == 0 else 50.0` → `rs.iloc[-1:]` คืน Series → `not Series` โยน `ValueError` → ทั้ง H1 regime fail แล้วถูก try/except กลืน (ไม่มีใครรู้)
- **แก้:** เทียบ scalar `rs_last = rs.iloc[-1]` → RSI/regime คำนวณได้จริง

---

## 🟢 ความถูกต้องของการคำนวณ (เลิก proxy/เดา → ใช้ data จริง)

### 3. `risk.py` — SL/TP ใช้ **ATR จริง** แทน tick proxy
- **เดิม:** ATR = std ของ returns จาก tick (`calculate_indicators` บน `ticker_data`) — proxy หยาบ
- **ใหม่:** ใช้ **H1 true-range ATR** (`calculate_atr_ohlc` บน candle จริง) + regime จาก H1 → SL/TP สะท้อนความผันผวนจริง (tick proxy เหลือเป็น fallback เท่านั้น)

### 4. รวม "2 สมอง" เป็นสมองเดียว (`strategy.py`)
- **เดิม:** auto-trade ใช้ multi-factor (regime proxy หยาบ) แต่ dashboard/backtest ใช้ `evaluate_strategy_rules` → **วิเคราะห์ไม่ตรงกัน**
- **ใหม่:** live engine เรียก `evaluate_strategy_rules` ตัวเดียวกับ dashboard + backtest (regime-aware, MTF filter, calibrated thresholds) → **test == dashboard == live**

### 5. ไม่ข้ามขั้น — คำนวณ regime สดถ้า event ยังไม่มา (`strategy.py`)
- **เดิม:** `if not regime: continue` → ข้ามทั้ง ticker ถ้า regime event ยังไม่ส่งมา
- **ใหม่:** คำนวณ regime สดจาก H1 candle ทันที → วิเคราะห์ต่อด้วยข้อมูลที่มี ไม่ข้าม

### 6. Dashboard `/api/state` ตรงกับ live (`main.py`)
- **เดิม:** ไม่ส่ง `macro_trend_1h` → **ข้าม MTF filter**, และ regime เป็น None ได้
- **ใหม่:** คำนวณ macro_1h + regime สดจาก H1 → signal บน dashboard = signal ที่ live เทรดเป๊ะ

---

## 🧠 สภา AI (agents.py) — เลิกโหวตตาม, ให้คำนวณโดเมนจริงทุกตัว

- **เดิม:** 3/6 agent (News/Macro/AssetSpecialist) โหวตตามสัญญาณเสมอด้วย confidence ตายตัว — ละคร
- **ใหม่:** ทั้ง 6 agent อ่านโดเมนจริงจาก `score_breakdown`:
  Chart→trend/momentum · Risk→prob/ATR (**มีสิทธิ veto**) · News→`final_news_score` จริง · Macro→regime · Asset→volume · CEO→composite
- โหวต**ถ่วงน้ำหนัก** (รวม weight = 1.0, ผ่านเกณฑ์ support ≥ 0.50) — verify แล้ว 6/6 agent คำนวณทุกครั้ง
- อัปเดต Claude fallback model → `claude-haiku-4-5-20251001` (ของเดิม `claude-3-haiku` เก่า)
- strategy ป้อน **momentum (RSI+MACD) + volume จริง** เข้า breakdown (เดิม momentum=copy เทรนด์, volume=50 ตายตัว)

---

## 🆕 ฟีเจอร์ใหม่ (มีหลักการ + พิสูจน์ด้วย backtest)

### 7. Asset-class regime-gate บน reversal (`core/base.py`)
- **หลักการ:** mean-reversion ได้ผลใน range แต่**เลือดไหลในเทรนด์แรง** (เหตุผลที่ reversal ทองเจ๊ง)
- **ทำ:** บล็อก counter-trend reversal เฉพาะ **non-crypto** (metals/forex/stocks) ใน BULL/BEAR; **crypto ปล่อย** (มัน mean-revert จริงแม้ในเทรนด์ — gate มันทำลาย edge)
- **backtest ยืนยัน:** ทอง reversal **-$6,520 → -$112**; crypto ไม่กระทบ
- crypto ยังข้าม generic RSI_THRESHOLDS override ด้วย (override ทำร้าย BTC/ETH ที่ calibrate มาดี)

### 8. `backtest.py` คำนวณ + ส่ง `regime` จริงต่อ bar
- เดิมส่ง regime=None → backtest ไม่ตรง live; ตอนนี้ **test == live**
- ⚠️ backtest ดึง Yahoo 30 วัน relative-to-now → PnL absolute เทียบข้ามเวลาไม่ได้ ใช้ `validate` (walk-forward) ตัดสิน

---

## ✅ ตรวจแล้วว่า "ไม่ใช่ปัญหา"
- **ราคา:** สดจริงทุกตัว — crypto=`binance`, หุ้น=`yahoo`, ทอง=`twelvedata` (smoke test ยืนยัน 0 mock)
- **News sub-scores:** relevance/recency/source_quality คำนวณจริงเมื่อมีข่าว (0.5 เป็นแค่ fallback ไม่มีข่าว)
- **Pipeline:** signal → committee → risk → execution ต่อกันครบ
- **Mode:** `watch` (default) = ต้อง approve เอง, `auto` = เทรดเอง (ปุ่มสลับ sync เข้า env ถูกต้อง)
- **Spread/Equity:** deterministic (ไม่สุ่ม), equity single-source

## 🟡 ค้าง (ไม่ใช่ blocker วันนี้)
- `transformers`/FinBERT ไม่ติดตั้ง → news sentiment ใช้ vader fallback (ยังคำนวณได้ คุณภาพลด) — ไม่ลงก่อนตลาดเปิดเพราะ torch หนัก/เสี่ยง
- execution monitor ยังใช้ sync DB ใน loop (ทำงานได้ แต่ควรเป็น async ภายหลัง)
- dead code `generate_price_history` (random) ใน core/base.py — ไม่อยู่ใน calc path, ลบทีหลังได้
- **กลยุทธ์ยังไม่ผ่าน walk-forward** (XAU 2/6, BTC 3/9, ETH 1/9) → คอขวดคือ "edge" ไม่ใช่ "โค้ด" — เก็บ flag auto-trade/smc/kelly ปิดไว้ถูกต้อง

---

## ▶️ วิธีรัน (จาก repo root!)
```bash
cd /Users/lucifer/Desktop/ai-trading
backend/venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
เช็คสุขภาพ: `curl localhost:8000/health` → `{"status":"ok","paper_mode":true}`
เช็คคำนวณสด: `curl localhost:8000/debug/prices` → `source` ต้องเป็น binance/yahoo/twelvedata (ไม่ใช่ mock)

**Prereq:** Redis + Postgres (docker `ai_trading_redis` + `ai_trading_db` — healthy แล้ว), keys ใน `.env` ครบ
