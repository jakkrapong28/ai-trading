# MT5 Bridge — ดึงราคาจาก MetaTrader 5 แบบไม่ติด limit

## ทำไมต้องมี bridge

แพ็กเกจ Python `MetaTrader5` (`import MetaTrader5 as mt5`) **รันได้บน Windows เท่านั้น**
เพราะมันคุยกับโปรแกรม MT5 terminal ผ่าน IPC ภายในเครื่อง Windows
→ บน Mac/Linux `pip install MetaTrader5` จะ fail

วิธีใช้บน Mac คือรัน **bridge server** (`mt5_bridge_server.py`) บน Windows VPS
ที่มี MT5 ติดตั้ง แล้วให้ backend ฝั่ง Mac โพลล์ราคา HTTP ผ่าน provider
`engines/providers/mt5_bridge.py`

ข้อดี: ราคาจาก broker จริง (forex / ทอง / CFD) สตรีมต่อเนื่อง ไม่มี API rate limit
เพราะเป็น IPC ในเครื่อง ไม่ใช่ REST quota

## ขั้นตอน (ฝั่ง Windows VPS)

```bat
:: 1. ติดตั้ง MetaTrader 5 terminal + login บัญชี broker ค้างไว้
:: 2. ติดตั้ง dependency
pip install MetaTrader5 fastapi uvicorn
:: 3. ตั้ง secret (แนะนำ)
set MT5_BRIDGE_KEY=your-shared-secret
:: 4. รัน
python mt5_bridge_server.py
:: เปิด port 8765 ให้ backend เข้าถึง (firewall / tunnel เช่น cloudflared)
```

## ขั้นตอน (ฝั่ง backend / Mac) — เพิ่มใน `backend/.env`

```env
MT5_BRIDGE_URL=http://<windows-host>:8765
MT5_BRIDGE_KEY=your-shared-secret
# (ออปชัน) ปรับความถี่โพลล์ วินาที
MT5_BRIDGE_POLL_SECONDS=1.0
```

ถ้าไม่ตั้ง `MT5_BRIDGE_URL` provider จะปิดตัวเงียบ ๆ — ระบบใช้ TwelveData เป็นหลักได้ตามปกติ

## ทดสอบ

```bash
curl "http://<windows-host>:8765/health"
curl "http://<windows-host>:8765/ticks?symbols=XAUUSD,EURUSD" -H "X-API-Key: your-shared-secret"
```

ควรได้ JSON `{"ticks":[{"symbol":"XAUUSD","bid":...,"ask":...}]}`
จากนั้นใน log ของ backend จะเห็น `[HEARTBEAT] XAUUSD OK ... (src=mt5)`
