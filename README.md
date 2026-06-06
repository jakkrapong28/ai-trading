# AI Trading Command Center MVP

MVP นี้เริ่มจาก deterministic trading pipeline ก่อน แล้วให้ AI เป็น analyst/explainer ไม่ใช่ trader หลัก

## เปิดใช้งาน

เปิดไฟล์ `index.html` ใน browser ได้ทันที ไม่ต้องติดตั้ง dependency

หรือรัน local server:

```bash
node server.mjs
```

แล้วเปิด `http://localhost:4173`

## สิ่งที่มีใน MVP

- Market snapshot แบบ demo สำหรับ `XAUUSD`, `BTCUSDT`, `ETHUSDT`, `EURUSD`
- Indicator calculator: EMA, RSI, ATR-like volatility
- Rule engine ที่ออก `BUY`, `SELL`, หรือ `WAIT`
- Claude analysis adapter placeholder สำหรับสรุป market context และ trade thesis
- Hard-coded risk engine:
  - max risk per trade
  - stop loss required
  - max spread
  - max exposure
  - block trade เมื่อ signal เป็น `WAIT`
- Human approval ก่อนสร้าง paper order
- Trade journal และ audit log เก็บใน `localStorage`
- Telegram command simulator:
  - `/price XAUUSD`
  - `/analyze XAUUSD`
  - `/risk XAUUSD 0.10 lot`
  - `/journal`
  - `/wallet`

## Next Architecture

```text
Python Trading Service
  MT5 connector
  Binance/CCXT connector
  indicator calculator
  strategy rule engine
  risk engine
  Claude analysis adapter
  Telegram bot

PostgreSQL
  market_snapshots
  analysis_runs
  trade_signals
  risk_checks
  trade_orders
  trade_journal
  account_balances
  audit_logs

Next.js Dashboard
  AI office view
  signal board
  open positions
  risk dashboard
  journal/history

ERP Integration
  consume domain events
  record ledger entries
  tax/compliance summaries
```

## Domain Events

- `market.snapshot_created`
- `analysis.run_completed`
- `trade.signal_created`
- `risk.check_passed`
- `risk.check_blocked`
- `trade_order.paper_created`
- `trade.opened`
- `trade.closed`
- `trade.pnl_realized`
- `account.balance_updated`
- `fee.recorded`
- `tax_event.created`

## Live Trading Guardrails

ก่อนต่อ live execution ควรเพิ่ม:

- paper trading environment
- persisted PostgreSQL audit trail
- backtest report per strategy version
- API key vault
- news blackout calendar
- broker spread/slippage validation
- manual approval through Telegram callback buttons
- immutable event log for ERP/tax integration
