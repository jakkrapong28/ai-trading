# 🚀 AI Trading Command Center — System Upgrade Roadmap
> วิเคราะห์จากโค้ดจริงทั้งหมด: `main.py`, `core.py`, `agents.py`, `engines/`, `erp/server.mjs`
> อัปเดต: 2026-06-08

---

## 🔴 ระดับ 1 — Critical Bugs & Security (แก้ก่อนทันที)

### 1.1 Secret Keys ถูก Expose ใน API Response
**ไฟล์:** [`main.py#L949-L959`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L949-L959)

```python
# ❌ อันตราย! ส่ง API Keys ทั้งหมดออก REST endpoint สาธารณะ
@app.get("/api/state")
def get_state_endpoint():
    return {
        "settings": {
            "telegram_token": state.telegram_token,   # ← โชว์ Token จริง!
            "anthropic_key": state.anthropic_key,     # ← โชว์ API Key จริง!
            "binance_key": state.binance_key,         # ← อันตรายมาก!
        }
    }
```

**แก้ไข:** Mask ค่าก่อนส่งออก และเพิ่ม Authentication Middleware บน endpoint นี้

```python
# ✅ ถูกต้อง
def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "ยังไม่ได้ตั้งค่า"
    return key[:4] + "****" + key[-4:]
```

---

### 1.2 Race Condition ใน `broadcast()` + `disconnect()`
**ไฟล์:** [`main.py#L60-L66`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L60-L66)

```python
# ❌ วนลูปและแก้ไข list ขณะกำลังวนอยู่ = RuntimeError
async def broadcast(self, message: dict):
    for connection in self.active_connections:  # ← ถ้า disconnect ระหว่างนี้ = crash
        try:
            await connection.send_json(message)
        except:
            self.disconnect(connection)  # ← แก้ list ระหว่าง iteration!
```

**แก้ไข:**
```python
async def broadcast(self, message: dict):
    dead = []
    for connection in list(self.active_connections):  # ← copy ก่อน iterate
        try:
            await connection.send_json(message)
        except Exception:
            dead.append(connection)
    for c in dead:
        self.disconnect(c)
```

---

### 1.3 Hardcoded Absolute Path ใน Settings Endpoint
**ไฟล์:** [`main.py#L1114`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L1114)

```python
# ❌ Path ชี้ไปที่เครื่อง Mac ของผู้ใช้โดยตรง
env_path = "/Users/lucifer/Desktop/ai-trading/backend/.env"
```

**แก้ไข:**
```python
from pathlib import Path
env_path = Path(__file__).parent / ".env"
```

---

### 1.4 `get_orders_from_db()` ใช้ Synchronous Session ใน Async Context
**ไฟล์:** [`main.py#L140-L161`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L140-L161)

ฟังก์ชัน `SessionLocal()` เป็น Sync แต่ถูกเรียกจากภายใน async functions — นี่ทำให้ event loop **หยุดรอ** ทุกครั้งที่ query ฐานข้อมูล

**แก้ไข:** เปลี่ยนเป็น `asyncio.to_thread()` หรือใช้ `AsyncSession` ของ SQLAlchemy

```python
# วิธีเร็ว (ไม่ต้อง refactor มาก)
orders = await asyncio.to_thread(get_orders_from_db)
```

---

### 1.5 `OPEN_POSITIONS` ใน Risk Engine เป็น Global In-Memory dict ที่ไม่เคยอัปเดต
**ไฟล์:** [`engines/risk.py#L13`](file:///Users/lucifer/Desktop/ai-trading/backend/engines/risk.py#L13)

```python
OPEN_POSITIONS = {}  # ← ไม่เคยมีอะไร write ค่าเข้ามาเลย!
```

ทำให้ Risk Engine ไม่เคยเห็น exposure จริง และ Approve ทุก signal ที่ confidence > 0.7 โดยไม่ตรวจสอบ position จริง

---

### 1.6 ERP Ledger เก็บข้อมูลไว้ใน Memory เท่านั้น (ไม่ Persistent)
**ไฟล์:** [`erp/server.mjs#L11`](file:///Users/lucifer/Desktop/ai-trading/erp/server.mjs#L11)

```js
const ledger = [...];  // ← reset ทุกครั้งที่ restart server!
```

บัญชีและภาษีทั้งหมดหายเมื่อ restart — ไม่เหมาะสำหรับใช้งานจริง

---

## 🟠 ระดับ 2 — Performance & Architecture Improvements

### 2.1 แยก `TradingState` ออกจาก Global Singleton
ปัจจุบัน `state = TradingState()` เป็น Global object ที่ทุกคนแก้ไขพร้อมกัน ทำให้เกิด Data Inconsistency ระหว่าง engines

**แนวทาง:** ใช้ `asyncio.Lock()` ป้องกัน concurrent writes บน critical fields เช่น `state.balances`, `state.orders`

```python
state_lock = asyncio.Lock()

async def update_balance_safe(source: str, delta: float):
    async with state_lock:
        for b in state.balances:
            if b["source"] == source:
                b["balance"] = round(b["balance"] + delta, 2)
```

---

### 2.2 Price History รีเซ็ตทุก Market Update (ข้อมูลไม่ต่อเนื่อง)
**ไฟล์:** [`main.py#L264`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L264)

```python
state.prices = generate_price_history(state.symbol)  # ← สร้างใหม่ทุกครั้ง!
```

ทำให้ RSI, EMA, ATR คำนวณจากข้อมูลสุ่มใหม่ทุกครั้ง ไม่ใช่ราคาต่อเนื่องที่เก็บสะสม

**แก้ไข:** เก็บ price history แยกต่อ symbol ใน dict และ append จากราคาจริง

```python
price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

# อัปเดต
price_history[symbol].append(live_price)
state.prices = list(price_history[symbol])
```

---

### 2.3 httpx AsyncClient ถูกสร้างใหม่ทุกครั้ง (ไม่มี Connection Pool)
**ไฟล์:** [`main.py`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py) — หลายจุด

```python
# ❌ สร้าง client ใหม่ทุก request = TCP handshake ทุกครั้ง
async with httpx.AsyncClient() as client:
    ...
```

**แก้ไข:** สร้าง Singleton `httpx.AsyncClient` ตั้งแต่ startup

```python
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app):
    global http_client
    http_client = httpx.AsyncClient(timeout=5.0)
    yield
    await http_client.aclose()
```

---

### 2.4 Telegram Poller ยิง `trigger_market_update()` ทุกครั้งที่รับ `/analyze`
**ไฟล์:** [`main.py#L593`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L593)

`trigger_market_update()` จะ spawn `run_agent_debate_simulation()` ซึ่งต้องการ Claude API — ถ้า user ส่งหลายครั้งพร้อมกัน จะเกิด multiple concurrent debates

`is_debating` flag ป้องกัน debate ซ้อนกัน แต่ไม่ได้ queue request ไว้ — request ที่มาทีหลังจะ **หายไปเงียบๆ**

**แก้ไข:** ใช้ `asyncio.Queue` รับ analyze requests และประมวลผลทีละรายการ

---

### 2.5 Strategy Engine ใน `core.py` vs `engines/strategy.py` — ซ้อนทับกัน
มีการคำนวณ Strategy 2 ชั้น:
1. [`core.py#L112`](file:///Users/lucifer/Desktop/ai-trading/backend/core.py#L112) → `evaluate_strategy_rules()` — ใช้กับ Dashboard โดยตรง
2. [`engines/strategy.py`](file:///Users/lucifer/Desktop/ai-trading/backend/engines/strategy.py) → `StrategyEngine` — ใช้กับ Event Bus

แต่ทั้ง 2 ระบบทำงานแบบ **แยกกันอิสระ ไม่คุยกัน** — สัญญาณจาก Engine ไม่ไหลกลับมาอัปเดต Dashboard

**แก้ไข:** ให้ Dashboard subscribe `CH_SIGNALS` channel จาก Redis เพื่อรับ signal จากทุก Engine

---

### 2.6 `evaluate_strategy_rules()` มี Random Signal 70%
**ไฟล์:** [`core.py#L133-L135`](file:///Users/lucifer/Desktop/ai-trading/backend/core.py#L133-L135)

```python
# ❌ ถ้าไม่มีสัญญาณชัดเจน ให้สุ่ม BUY/SELL 70% ของเวลา
if action == "WAIT" and random.random() < 0.7:
    action = random.choice(["BUY", "SELL"])
    reason = "[จำลองสัญญาณทดสอบระบบ]..."
```

นี่คือ **Gambler's Fallacy** — สัญญาณสุ่มนี้จะไปกระตุ้น AI Debate, Telegram notification และ ERP logging ทุก 15 วินาที ทำให้ระบบดูเหมือนทำงานแต่ไม่มี Alpha จริง

**แก้ไข:** ลบ random fallback ออก ให้คืนค่า WAIT จริงๆ เมื่อไม่มีสัญญาณ

---

## 🟡 ระดับ 3 — AI Model Upgrades

### 3.1 Debate ถูก Generate แบบ Template (ไม่ใช่ AI จริง)
**ไฟล์:** [`agents.py`](file:///Users/lucifer/Desktop/ai-trading/backend/agents.py)

Debate ทั้ง 7 steps ถูก hardcode เป็น f-string template ทำให้:
- ทุกการประชุมมีรูปแบบเดิมซ้ำๆ
- ไม่มีการ "คิด" จริงๆ จาก Agent
- News AI พูดเรื่องข่าวปลอมเสมอ

**แนวทางยกระดับ:** เชื่อม Claude Sonnet จริงกับแต่ละ Agent ด้วย System Prompt ที่แตกต่างกัน

```python
async def generate_agent_opinion(agent_name: str, context: dict) -> str:
    system_prompts = {
        "Chart": "คุณคือนักวิเคราะห์เทคนิคอล มีข้อมูล: {context}. วิเคราะห์สัญญาณ EMA/RSI และตอบในฐานะ Chart Analyst",
        "Risk": "คุณคือ Risk Manager. ประเมินความเสี่ยงของการเทรดนี้และแสดงตัวเลขชัดเจน",
        ...
    }
    # เรียก Claude จริงแต่ละ Agent
    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-5",
        system=system_prompts[agent_name].format(context=context),
        messages=[{"role": "user", "content": "วิเคราะห์สถานการณ์นี้"}]
    )
```

---

### 3.2 News Intelligence ใช้ Mock Headline ตายตัว
**ไฟล์:** [`engines/news_intelligence.py#L18`](file:///Users/lucifer/Desktop/ai-trading/backend/engines/news_intelligence.py#L18)

```python
# ❌ headline เดิมทุก 5 นาที = sentiment score เดิมตลอด
headline = f"Market updates and economic data affecting {ticker}"
```

VADER ให้ค่า compound ≈ 0.0 กับทุก ticker ตลอดเวลา

**แนวทาง:** เชื่อม NewsAPI จริงที่มี key อยู่แล้วใน settings

```python
async def fetch_real_news(ticker: str, api_key: str) -> List[str]:
    keywords = {
        "XAUUSD": "gold price inflation", 
        "BTCUSDT": "bitcoin crypto",
        "NVDA": "nvidia AI chips"
    }
    url = f"https://newsapi.org/v2/everything?q={keywords[ticker]}&apiKey={api_key}&pageSize=5&sortBy=publishedAt"
    # ดึงข่าวจริง → คำนวณ VADER → publish ค่า sentiment จริง
```

---

### 3.3 ATR Calculation ไม่ใช่ ATR จริง (ขาด High/Low)
**ไฟล์:** [`core.py#L80-L85`](file:///Users/lucifer/Desktop/ai-trading/backend/core.py#L80-L85)

```python
# ⚠️ นี่คือ Average of |Close-Close| ไม่ใช่ True Range จริง
def calculate_atr(values: List[float], period: int = 14) -> float:
    ranges = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
```

ATR จริงต้องใช้: `max(High-Low, |High-PrevClose|, |Low-PrevClose|)`

**แก้ไข:** รับ OHLCV data แทน Close-only, หรืออย่างน้อยเพิ่ม note ว่าเป็น approximation

---

### 3.4 Lot Size ถูก Hardcode ที่ 0.1 ทุกครั้ง
**ไฟล์:** [`main.py#L399`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L399), [`main.py#L277`](file:///Users/lucifer/Desktop/ai-trading/backend/main.py#L277)

```python
volume = 0.1  # ← ไม่เคยเปลี่ยน
# และ
state.risk = check_trade_risk(..., 0.1, 15.0, 1.8)  # ← hardcoded params
```

**แก้ไข:** คำนวณ Lot Size จาก Kelly Criterion หรือ Fixed Fractional Method โดยใช้ ATR เป็น stop distance จริง

```python
def calculate_lot_size(equity: float, risk_pct: float, stop_distance: float, tick_value: float) -> float:
    risk_dollars = equity * (risk_pct / 100)
    lot = risk_dollars / (stop_distance * tick_value * 100)
    return round(max(0.01, min(lot, 10.0)), 2)
```

---

### 3.5 Sharpe Ratio, Max Drawdown ยังไม่มีการคำนวณจริง
`/api/metrics` ส่งแค่ win_rate และ total_pnl — ขาดตัวชี้วัดสำคัญ:

- **Sharpe Ratio** = (Mean PnL - Risk Free Rate) / Std(PnL)
- **Max Drawdown** = max peak-to-trough decline
- **Profit Factor** = Gross Profit / Gross Loss
- **Calmar Ratio** = Annual Return / Max Drawdown

---

## 🟢 ระดับ 4 — ฟีเจอร์ใหม่ที่ควรเพิ่ม

### 4.1 Backtesting Engine
ระบบปัจจุบันไม่มี Backtester เลย — ไม่สามารถทดสอบ strategy กับข้อมูลประวัติก่อน live ได้

**แนวทาง:**
- เพิ่ม endpoint `POST /api/backtest` รับ symbol + date range + strategy params
- รัน `evaluate_strategy_rules()` บน historical OHLCV จาก CCXT
- ส่งผล equity curve กลับมาให้ frontend พล็อต

---

### 4.2 Multi-Symbol Portfolio Dashboard
ปัจจุบัน `state.symbol` มีแค่ 1 symbol ต่อครั้ง แต่ระบบ engines รองรับหลาย tickers แล้ว

**แนวทาง:** Dashboard แสดง watchlist grid แต่ละ symbol แสดง mini chart + สัญญาณ + สถานะ risk พร้อมกัน

---

### 4.3 Alert System ที่ใช้ได้จริง
ปัจจุบัน `/alerts` ใน Telegram แค่ตอบ hardcode ว่า "ระบบปกติ 100%"

**แนวทาง:**
- ตั้ง threshold สำหรับ RSI overbought/oversold (>75, <25)
- ตั้ง alert เมื่อ drawdown เกิน X%
- Push notification จริงผ่าน Telegram เมื่อ threshold ถูกทริกเกอร์

---

### 4.4 ERP — เพิ่ม Database Persistence
**ไฟล์:** [`erp/server.mjs`](file:///Users/lucifer/Desktop/ai-trading/erp/server.mjs)

เพิ่ม SQLite หรือ JSON file persistence ง่ายๆ

```js
import { Low } from 'lowdb';
import { JSONFile } from 'lowdb/node';

const db = new Low(new JSONFile('erp-data.json'), { ledger: [], pnl: 0 });
await db.read();
// ทุก write: db.data.ledger.push(...); await db.write();
```

---

### 4.5 Claude Streaming Response สำหรับ Chat
ปัจจุบัน Claude Chat รอผลลัพธ์ครั้งเดียว ทำให้ UX ดูช้า

**แนวทาง:** ใช้ `anthropic.stream()` และ forward chunks ผ่าน WebSocket

```python
async with client.messages.stream(model=...) as stream:
    async for text in stream.text_stream:
        await manager.broadcast({"type": "chat_chunk", "text": text})
```

---

### 4.6 Position Sizing แบบ Dynamic (Kelly + ATR-based SL)
```python
def calculate_position(equity, risk_pct, price, atr, symbol):
    stop_distance = atr * 2.0          # Stop = 2x ATR
    risk_dollars = equity * risk_pct / 100
    tick_val = SYMBOLS[symbol]["tickValue"]
    lot = risk_dollars / (stop_distance * tick_val * 100)
    take_profit = price + (stop_distance * 2.0)  # RR 1:2
    return {
        "lot": round(lot, 2),
        "stop_loss": round(price - stop_distance, SYMBOLS[symbol]["decimals"]),
        "take_profit": round(take_profit, SYMBOLS[symbol]["decimals"])
    }
```

---

## 🔵 ระดับ 5 — Long-Term Architecture Roadmap

### Phase 1 (1-2 สัปดาห์) — Stability & Security
- [ ] แก้ Race Condition ใน ConnectionManager
- [ ] Mask API Keys ใน `/api/state`
- [ ] แก้ Absolute Path ใน settings
- [ ] เพิ่ม `asyncio.to_thread()` ให้ DB calls
- [ ] ลบ Random Signal Fallback ออกจาก `core.py`
- [ ] Fix `OPEN_POSITIONS` ใน Risk Engine

### Phase 2 (2-4 สัปดาห์) — Real Data & Better AI
- [ ] เชื่อม NewsAPI จริงกับ VADER engine
- [ ] Price History แบบ Continuous (ไม่ reset)
- [ ] Singleton `httpx.AsyncClient`
- [ ] Claude Streaming Chat
- [ ] ATR คำนวณจาก OHLCV จริง
- [ ] ERP Persistence ด้วย LowDB หรือ SQLite

### Phase 3 (1-2 เดือน) — Alpha Generation
- [ ] Backtesting Engine ใน Backend
- [ ] Dynamic Lot Sizing (ATR-based)
- [ ] Claude-powered Agents (ไม่ใช่ template)
- [ ] Multi-symbol Portfolio View
- [ ] Sharpe Ratio, Max Drawdown, Profit Factor
- [ ] Real Alert System (RSI/Drawdown threshold)

### Phase 4 (2-3 เดือน) — Production Ready
- [ ] เพิ่ม Authentication (JWT) บน Dashboard
- [ ] Rate Limiting บน API endpoints
- [ ] Paper Trading → Live Trading toggle แบบ safe
- [ ] Database Migration tool (Alembic)
- [ ] Health Check endpoint + monitoring
- [ ] Unit Tests + Integration Tests

---

## 📊 สรุปคะแนนสถานะปัจจุบัน

| ด้าน | คะแนน | หมายเหตุ |
|------|--------|----------|
| 🏗️ สถาปัตยกรรม | 7/10 | Async Monolith + Event Bus ดีมาก |
| 🔒 Security | 3/10 | API Key Exposure เป็นจุดอ่อนหลัก |
| 🤖 AI Quality | 4/10 | Template-based ไม่ใช่ AI จริง |
| 📊 Data Accuracy | 5/10 | Random prices + Mock news |
| ⚡ Performance | 6/10 | WebSocket ดี แต่ DB calls blocking |
| 💰 Trading Logic | 4/10 | Random fallback ลดคุณค่า signal |
| 🔄 Persistence | 3/10 | ERP in-memory, ข้อมูลหายเมื่อ restart |
| 🎨 Dashboard UX | 9/10 | สวยงามและ responsive มาก |

**คะแนนรวม: 5.1/10** — ระบบเหมาะสำหรับ Demo/Showcase แต่ต้องแก้ไขหลายจุดก่อนใช้งานจริง
