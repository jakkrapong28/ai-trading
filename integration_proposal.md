# ข้อเสนอสถาปัตยกรรมและการรวมระบบ (System Integration & Upgrade Proposal)

เอกสารนี้จัดทำขึ้นเพื่อเสนอแนวทางในการนำระบบเก่าของคุณที่เป็นสถาปัตยกรรม **Event-Driven Microservices (8 Services + Redis Pub/Sub + PostgreSQL)** มาผสมผสานและอัปเกรดเข้ากับโครงสร้างของระบบปัจจุบัน (FastAPI Backend + Next.js Frontend + Express ERP Server) ให้กลายเป็นระบบเดียวกันอย่างมีประสิทธิภาพ

---

## 1. เปรียบเทียบสถาปัตยกรรม: ปัจจุบัน vs เป้าหมายการรวมระบบ

```mermaid
graph TD
    %% Current Architecture (Simplified)
    subgraph ปัจจุบัน (In-Memory Monolith)
        A1[FastAPI Backend - main.py] <-->|In-Memory State| B1(state = TradingState)
        A1 <-->|WebSocket| C1[Next.js Frontend]
        A1 -->|REST Webhook| D1[Node.js ERP Service]
    end

    %% Combined Architecture (Target)
    subgraph สถาปัตยกรรมเป้าหมาย (Event-Driven Microservices)
        MD[market-data-service] -->|Publish: market:tick| RDB[(Redis Pub/Sub)]
        NI[news-intelligence] -->|Publish: news:sentiment| RDB
        RDB -->|Subscribe| MRE[market-regime-engine]
        MRE -->|Publish: market:regime:current| RDB
        
        RDB -->|Subscribe| STE[strategy-engine]
        STE -->|Publish: ai:signal:generated| RDB
        STE -->|Save Journal| PG[(PostgreSQL)]
        
        RDB -->|Subscribe| RKE[risk-engine]
        RKE -->|Publish: risk:signal:approved/rejected| RDB
        
        RDB -->|Subscribe| EXE[execution-engine]
        EXE -->|Publish: execution:trade:opened/closed| RDB
        EXE -->|Update Trade/Position| PG
        EXE -->|Webhook| D2[Node.js ERP Service]
        
        RDB -->|Subscribe| PTE[portfolio-engine]
        PTE -->|Publish: portfolio:metrics:updated| RDB
        PTE -->|Save Metrics| PG
        
        RDB -->|Subscribe to All| GW[API Gateway / FastAPI]
        GW <-->|WebSocket| C2[Next.js Client Dashboard]
    end
```

### การจัดแนวแกนหลัก (Alignment Strategy)
1. **API Gateway / Backend (`backend/main.py`)**: ปรับบทบาทจากผู้ประมวลผลการเทรดแบบ In-Memory ให้กลายเป็น **API Gateway** ที่ทำหน้าที่รับคำสั่ง REST API จาก Dashboard, จัดการ WebSockets, และทำหน้าที่ Subscribe ทุกช่องทางจาก Redis Pub/Sub เพื่อ Broadcast ข้อมูลสดส่งตรงไปยัง Next.js UI
2. **การสตรีมมิ่งข้อมูล (Event Broker)**: นำ **Redis Pub/Sub** เข้ามาทำหน้าที่เป็นตัวกลางส่งต่อสาร (Event Bus) ระหว่าง 8 บริการย่อย
3. **การบันทึกข้อมูลแบบคงทน (Persistence)**: นำโครงสร้างตารางของ PostgreSQL จาก [schema.sql](file:///Users/lucifer/Desktop/ai-trading/database/schema.sql) มาใช้งานจริงแทนการใช้ In-Memory State ของ Python เพื่อรองรับการทำบัญชี, Audit Trail และประมวลผล Metrics

---

## 2. ขั้นตอนการเตรียมการและติดตั้ง Dependency

ก่อนเริ่มเขียนโค้ดเพิ่ม จำเป็นต้องติดตั้ง Libraries เพิ่มเติมใน Python Environment และเปิดระบบช่วยเหลือพื้นฐาน:

### A. อัปเดต `backend/requirements.txt`
เพิ่มไลบรารีสำหรับเชื่อมต่อ Redis, PostgreSQL และรัน NLP:
```text
redis>=5.0.0
psycopg2-binary>=2.9.9
asyncpg>=0.29.0
nltk>=3.8.1
```

> [!NOTE]
> * **`redis`**: สำหรับการทำ Pub/Sub และ Message Broker
> * **`asyncpg` / `psycopg2`**: สำหรับการคิวรีและเชื่อมต่อ PostgreSQL แบบ asynchronous
> * **`nltk`**: เพื่อใช้โมดูล **VADER** ในการวิเคราะห์อารมณ์ข่าวสาร (Sentiment Analysis) โดยไม่ต้องใช้โมดูล AI ขนาดใหญ่

### B. จัดเตรียม Infrastructure (Docker Compose เป็นมิตรที่สุด)
สร้างไฟล์ `docker-compose.yml` ในระดับ Root Project เพื่อรัน Redis และ PostgreSQL คู่กันในการพัฒนา:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    container_name: ai_trading_db
    environment:
      POSTGRES_DB: ai_trading
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: yourpassword
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/schema.sql
      - ./database/seeds.sql:/docker-entrypoint-initdb.d/seeds.sql

  redis:
    image: redis:7-alpine
    container_name: ai_trading_redis
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

---

## 3. รายละเอียดการอัปเกรด 8 บริการย่อย (Microservices Implementation Guide)

ในการนำโค้ดเดิมเข้ามาประสม คุณสามารถเลือกพัฒนาได้ 2 รูปแบบ:
* **Option A (Distributed)**: แยกโฟลเดอร์รัน Python Script 8 ตัวแยกกัน (เหมาะสำหรับการใช้งานจริงบน Cloud/Docker)
* **Option B (Asynchronous Monolith - แนะนำสำหรับพัฒนาร่วมกับระบบเดิม)**: เขียนเป็น Class แยกภายในโปรเจค Python เดิม แล้วรันเป็น `asyncio.create_task` ใน `main.py` โดยทำงานแยกอิสระผ่าน Redis Pub/Sub ซึ่งจะช่วยให้จัดสรร Thread/Task ในโปรเจคปัจจุบันได้ง่ายขึ้นและไม่ซับซ้อนในการรัน

รายละเอียดการเขียนแต่ละ Engine มีดังนี้:

### 1. `market-data-service` (สตรีมมิ่งราคา)
* **การทำงาน**: ดึงราคาจาก WebSocket ของ Binance (`wss://stream.binance.com`) และ Finnhub (`wss://ws.finnhub.io`)
* **จุดอัปเกรด**: ย้าย Logic การสตรีมราคาจากเดิมที่เป็นแบบ Fetch ดึงราคาทีละ 5 วินาทีใน API ให้กลายเป็น WebSocket Client ที่รันทำงานตลอดเวลา (Persistent Loop) แล้วส่งข้อมูลราคาดิบเข้า Redis Channel `market:tick`
* **ตัวอย่างข้อความ (Event Payload)**:
  ```json
  {"symbol": "BTCUSDT", "price": 68150.00, "timestamp": "2026-06-07T14:30:00Z"}
  ```

### 2. `news-intelligence` (NLP Sentiment Score)
* **การทำงาน**: ดึงข้อมูลข่าวจาก API แบบ Real-time
* **จุดอัปเกรด**: นำโมดูล **VADER (SentimentIntensityAnalyzer)** ของ `nltk` มาเขียนเป็นโมดูลประเมินคะแนน โดยนำหัวข้อข่าวมาแปลงเป็นคะแนนเชิงบวก/ลบ (Sentiment Score ระหว่าง -1.0 ถึง +1.0)
* **การคำนวณ**:
  ```python
  from nltk.sentiment.vader import SentimentIntensityAnalyzer
  sia = SentimentIntensityAnalyzer()
  score = sia.polarity_scores(news_title)["compound"] # ดึงคะแนนสรุปรวม
  ```
  จากนั้น Publish ไปที่ Redis Channel `news:sentiment` และเก็บข้อมูลลงตาราง `analysis_runs` ใน PostgreSQL

### 3. `market-regime-engine` (จำแนกสภาวะตลาด)
* **การทำงาน**: คำนวณความผันผวนและแนวโน้มตลาด
* **จุดอัปเกรด**: นำอินดิเคเตอร์ ATR และ EMA จาก `core.py` มาประมวลผลแบบ Real-time ร่วมกับปริมาณการซื้อขาย เพื่อจัดกลุ่มตลาดเป็น 4 สภาวะหลัก:
  * **Bullish High Volatility** (แนวโน้มขาขึ้น ผันผวนสูง)
  * **Bullish Low Volatility** (แนวโน้มขาขึ้น ผันผวนต่ำ)
  * **Bearish High Volatility** (แนวโน้มขาลง ผันผวนสูง)
  * **Sideways Low Volatility** (ตลาดออกข้าง ผันผวนต่ำ)
  ส่งสถานะปัจจุบันไปยัง Redis Channel `market:regime:current`

### 4. `strategy-engine` (ตัดสินใจเทรดด้วย AI)
* **การทำงาน**: รวมสัญญาณและออกคำแนะนำ BUY, SELL, WAIT
* **จุดอัปเกรด**: แทนที่จะสุ่มสัญญาณสั้นๆ หรือเช็คสัญญาณ EMA/RSI ดิบๆ ให้ดักฟัง Redis Channel `market:tick`, `news:sentiment`, และ `market:regime:current` เมื่อครบเงื่อนไข ให้ประเมินผล:
  * หาก **Sentiment Score > 0.3** และสภาวะตลาดเป็น **Bullish Low Volatility** => เพิ่มน้ำหนักส่งสัญญาณ **BUY**
  * หาก **Sentiment Score < -0.3** และสภาวะตลาดเป็น **Bearish High Volatility** => ส่งสัญญาณ **SELL** (หรือหลีกเลี่ยงการเปิดคำสั่งตาม Risk Policy)
  * ส่งข้อมูลไปยัง Redis Channel `ai:signal:generated` และบันทึกลงฐานข้อมูล PostgreSQL ตาราง `trade_signals` และ `ai_decision_journal`

### 5. `risk-engine` (คำนวณขนาดพอร์ตแบบไดนามิก)
* **การทำงาน**: ตรวจสอบกฎการเทรดและความเสี่ยง
* **จุดอัปเกรด**: ย้ายฟังก์ชัน `check_trade_risk` จาก [core.py](file:///Users/lucifer/Desktop/ai-trading/backend/core.py) มาอยู่ใน Risk Engine:
  * **Dynamic Stop Loss (SL)**: ใช้ค่า ATR ล่าสุดคูณด้วยตัวแปรทวีคูณ (เช่น 1.5 * ATR) เพื่อตั้งระยะ Stop Loss แบบไดนามิกตามสภาพความผันผวนจริงของตลาด
  * **Dynamic Lot Sizing (Lot Sizer)**: คำนวณขนาดไม้เทรดโดยอิงจาก Equity ปัจจุบันในระบบ บัญชีจริง เช่น ยอมรับการขาดทุนต่อไม้สูงสุด 2% ของยอดเงินในบัญชีจริง
  * ส่งคำสั่งที่ประเมินผ่านแล้วไปที่ Redis Channel `risk:signal:approved` (หากไม่ผ่านส่งไปที่ `risk:signal:rejected`)

### 6. `execution-engine` (จำลอง Slippage & เฝ้าระวังราคา)
* **การทำงาน**: เปิด/ปิด ออเดอร์และมอนิเตอร์ราคาชน SL/TP
* **จุดอัปเกรด**:
  * **Slippage 0.01%**: เมื่อได้รับคำร้องขอจาก `risk:approved` ให้ทำรายการคำนวณราคาเปิดออเดอร์โดยบวก/ลบ Slippage 0.01% (เช่น หาก Buy ทองที่ราคา 2340.00 ให้บันทึกราคาเปิดจริงเป็น `2340.00 * 1.0001 = 2340.23`)
  * **SL/TP Tracker Loop**: สร้างระบบ Thread หรือ Task คอยฟังราคาสดจาก `market:tick` เพื่อเช็คตำแหน่งออเดอร์ทั้งหมดใน PostgreSQL หากราคาตลาดตัดผ่าน Stop Loss หรือ Take Profit ให้ประมวลผล **ปิดออเดอร์ทันที** คืนค่า Realized PnL และส่งสัญญาณไปที่ Redis Channel `execution:trade:closed` พร้อมส่ง Webhook ไปยัง ERP ของ Node.js เพื่อลงบัญชี

### 7. `portfolio-engine` (ประเมินตัวเลขชี้วัดการลงทุน)
* **การทำงาน**: คำนวณ Net Worth, ROI, Sharpe Ratio
* **จุดอัปเกรด**: เมื่อได้รับเหตุการณ์ `execution:trade:closed` ให้โหลดประวัติรายการซื้อขายทั้งหมดจาก PostgreSQL มาคำนวณ Metrics เชิงลึก:
  * **Win Rate**: สัดส่วนไม้ชนะจากทั้งหมด
  * **Profit Factor**: ผลรวมของกำไรทั้งหมดหารด้วยผลรวมของขาดทุนทั้งหมด
  * **Sharpe Ratio**: ค่าประสิทธิภาพพอร์ตเปรียบเทียบความเสี่ยง:
    $$\text{Sharpe Ratio} = \frac{\text{Mean of PnL} - \text{Risk Free Rate}}{\text{Standard Deviation of PnL}}$$
  * ส่งข้อมูลชุดตัวเลขที่อัปเดตแล้วไปยัง Redis Channel `portfolio:metrics:updated` เพื่อแสดงผล Equity Curve บนหน้าจอ

---

## 4. แผนการอัปเกรดหน้าจอ Next.js Frontend (UI Enhancements)

สถาปัตยกรรมแบบ Event-Driven จะแสดงแสนยานุภาพบน UI ได้เป็นอย่างดีเมื่อเราผูกสายสัญญาณเข้ากับ Canvas นีออนแบบ 3D และเพิ่มหน้าวิเคราะห์พอร์ต:

### A. อัปเกรด Canvas 3D (Glowing Event Flow Animation)
เพิ่มการจำลองการส่งข้อมูลในห้องบัญชาการแบบ 3D บนไฟล์ [page.tsx](file:///Users/lucifer/Desktop/ai-trading/frontend/src/app/page.tsx):
* เมื่อได้รับข้อความผ่าน WebSocket ใน Channel ต่างๆ ให้วาดเส้นสีนีออนเรืองแสงวิ่ง (Laser Pulse) เชื่อมโยงระหว่างแต่ละห้องในแผง Canvas 3D:
  * จากห้อง **Chart AI (Market Data)** วิ่งไปที่ **Strategy AI** เมื่อมีราคาไหลเข้ามา
  * จากห้อง **Risk AI** วิ่งไปที่ **EA Bot (Execution)** เมื่อความเสี่ยงผ่านเกณฑ์
  * จากห้อง **EA Bot** วิ่งไปที่ **Finance AI (ERP)** เมื่อปิดดีลสำเร็จ
* เพิ่มสถานะไฟสีเขียว/แดงกระพริบตามห้องต่างๆ (เช่น Risk AI กะพริบแดงเมื่อพบสัญญาณเสี่ยงเกินเกณฑ์)

### B. หน้าวิเคราะห์ประสิทธิภาพ (Performance Dashboard Tab)
สร้างหน้าแท็บใหม่ในส่วนควบคุมของ Next.js เพื่อใช้ในการดูสถิติพอร์ตโฟลิโอ:
1. **หน้าแสดงตัวเลข Metrics**:
   * การ์ดแสดง Win Rate (%), Profit Factor, ROI (%), และ Sharpe Ratio
2. **กราฟเส้นมูลค่าพอร์ต (Equity Line Chart)**:
   * ใช้ไลบรารีเบาๆ เช่น `chart.js` หรือ `recharts` (หรือจะวาดดิบลงบน HTML Canvas เพื่อความเร็วสูงสุดและไม่ต้องติดตั้ง Dependency เยอะ) เพื่อพล็อตจุดข้อมูล Equity สะสมจากการปิดดีลในพอร์ตแต่ละครั้ง ช่วยให้ผู้ใช้เห็นการเติบโตของทุน
3. **Sentiment & Regime Monitor**:
   * แสดงมิเตอร์เข็มวัดอารมณ์ตลาดล่าสุด (NLP Sentiment Meter) ตั้งแต่ Extreme Fear (-1.0) ไปจนถึง Extreme Greed (+1.0)
   * แสดงป้ายไฟนีออนระบุสภาวะตลาดปัจจุบัน (เช่น "Sideways Low Volatility")

---

## 5. การรวมระบบ ERP (General Ledger & Tax Synchronization)

ระบบ Node.js ERP ปัจจุบัน ([server.mjs](file:///Users/lucifer/Desktop/ai-trading/erp/server.mjs)) ดีมากอยู่แล้ว เนื่องจากรับ Domain Events และลงบัญชีแยกประเภททันที แต่เราจะเพิ่มมิติให้ทนทานยิ่งขึ้น:

* **การยิงข้อมูลผ่าน Webhook**:
  ให้ `execution-engine` และ `portfolio-engine` ทำหน้าที่เป็นผู้ยิง Webhook ไปหา `http://localhost:5001/webhook/trade-event` ทุกครั้งเมื่อเกิดเหตุการณ์ `trade.opened` หรือ `trade.pnl_realized` (มีประวัติการหักค่าธรรมเนียมและภาษีอย่างโปร่งใส)
* **การซิงค์ผ่าน Redis**:
  อีกทางเลือกหนึ่งคืออัปเกรดระบบ ERP ให้ทำหน้าที่ Subscribe ช่องข้อมูล `execution:trade:closed` โดยตรงจาก Redis (แทนการยิง Webhook REST API) เพื่อให้ระบบเป็นสถาปัตยกรรมแบบ Event-Driven สมบูรณ์แบบ (ลดภาระ HTTP Overhead ของเซิร์ฟเวอร์หลังบ้าน)

---

## 6. แนวทางการดำเนินงานทีละขั้น (Implementation Roadmap)

เพื่อให้เห็นภาพการทำงานที่จะเกิดขึ้นจริงในการพัฒนาร่วมกัน แนะนำให้เริ่มปรับเปลี่ยนตามเฟสต่างๆ ดังนี้:

| เฟสงาน | รายละเอียดการดำเนินงาน | เป้าหมายที่จับต้องได้ |
| :--- | :--- | :--- |
| **เฟส 1** | รัน Docker Compose (Postgres + Redis) และเชื่อมต่อ Database Driver ใน Python | เชื่อมต่อ Database สำเร็จ ทดสอบรัน SQL Schema ตั้งต้นได้ |
| **เฟส 2** | อัปเกรด `news-intelligence` ติดตั้ง NLP VADER วิเคราะห์อารมณ์ข่าว และสร้าง `market-regime-engine` คำนวณสภาวะตลาด | ได้ข้อมูล Sentiment Score และ Regime แสดงผลผ่าน Terminal/Log |
| **เฟส 3** | ย้ายระบบประมวลผลการเทรดใน `main.py` เข้าสู่ `execution-engine` จริง โดยเฝ้าดูราคาจาก `market:tick` เพื่อปิดออเดอร์ตาม SL/TP และคิดค่าธรรมเนียมกับ Slippage 0.01% | จลนศาสตร์การเทรดสมจริง ไม่ใช้การหน่วงเวลา 5 วินาทีอีกต่อไป |
| **เฟส 4** | สร้าง `portfolio-engine` ในฝั่ง Python ทำหน้าที่ดึงข้อมูลประวัติการเทรดมาคำนวณ Win Rate, Profit Factor, Sharpe Ratio และส่งอัปเดต | ได้ตัวเลขชี้วัดทางการเงินและพิกัดสำหรับวาดกราฟพอร์ต |
| **เฟส 5** | อัปเดต Next.js Frontend ให้ดึงตัวเลข Metrics มาพล็อตกราฟ Equity Line และใส่ Animation เส้นสว่างเชื่อมโยงห้องทำงานจำลองเมื่อมีการยิงข้อมูล | หน้าจอ Dashboard ดูสวยงาม ไฮเทคแบบมีชีวิตชีวา และส่งข้อมูลอัปเดตเรียลไทม์ได้ |
