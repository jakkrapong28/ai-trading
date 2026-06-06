-- PostgreSQL Database Schema สำหรับ AI Trading Command Center & Netiwat ERP

-- 1. บันทึกข้อมูลราคาและตัวชี้วัด (Market Snapshots)
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    price_open NUMERIC(20, 8),
    price_high NUMERIC(20, 8),
    price_low NUMERIC(20, 8),
    price_close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8),
    indicators JSONB -- RSI, EMA, ATR, etc.
);

-- 2. บันทึกประวัติการวิเคราะห์ของ AI (Analysis Runs)
CREATE TABLE IF NOT EXISTS analysis_runs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    analysis_text TEXT NOT NULL,
    sentiment VARCHAR(20) -- BULLISH, BEARISH, NEUTRAL
);

-- 3. บันทึกสัญญาณการเทรดที่เกิดขึ้น (Trade Signals)
CREATE TABLE IF NOT EXISTS trade_signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL, -- BUY, SELL, WAIT
    price NUMERIC(20, 8) NOT NULL,
    reason TEXT,
    source_agent VARCHAR(50) DEFAULT 'CEO_Agent'
);

-- 4. บันทึกผลการประเมินความเสี่ยง (Risk Checks)
CREATE TABLE IF NOT EXISTS risk_checks (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    signal_id INT REFERENCES trade_signals(id) ON DELETE SET NULL,
    passed BOOLEAN NOT NULL,
    risk_pct NUMERIC(5, 2) NOT NULL, -- e.g. 1.50%
    exposure_pct NUMERIC(5, 2) NOT NULL,
    check_details JSONB -- รายละเอียดกฎ เช่น 2% rule, Stop Loss check
);

-- 5. บันทึกคำสั่งซื้อขายจริง/กระดาษ (Trade Orders)
CREATE TABLE IF NOT EXISTS trade_orders (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL, -- BUY, SELL
    volume NUMERIC(15, 4) NOT NULL, -- Lot หรือขนาดเหรียญ
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    status VARCHAR(20) NOT NULL, -- PENDING, FILLED, CLOSED, REJECTED
    order_type VARCHAR(10) DEFAULT 'PAPER', -- PAPER, LIVE
    pnl NUMERIC(20, 8) DEFAULT 0.00
);

-- 6. บันทึกไดอารี่การเทรดและเหตุการณ์ระบบ (Trade Journal & Audit Trails)
CREATE TABLE IF NOT EXISTS trade_journal (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    log_type VARCHAR(50) NOT NULL, -- market_snapshot, analysis_run, risk_check, trade_executed, erp_sync
    message TEXT NOT NULL,
    metadata JSONB
);

-- 7. บันทึกประวัติยอดเงินของบัญชีต่างๆ (Account Balances)
CREATE TABLE IF NOT EXISTS account_balances (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) NOT NULL, -- MT5, BINANCE, ONCHAIN_WALLET
    equity NUMERIC(20, 2) NOT NULL,
    balance NUMERIC(20, 2) NOT NULL,
    free_margin NUMERIC(20, 2)
);

-- 8. บันทึกการตรวจสอบระบบ (Audit Logs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    event_name VARCHAR(100) NOT NULL,
    actor VARCHAR(50) NOT NULL, -- SYSTEM, TONY, TELEGRAM_BOT
    ip_address VARCHAR(45),
    details TEXT
);
