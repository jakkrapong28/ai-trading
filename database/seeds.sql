-- ข้อมูลจำลองสำหรับเริ่มต้นระบบ AI Trading Command Center & Netiwat ERP

-- 1. ยอดเงินของบัญชีต่างๆ (Account Balances)
INSERT INTO account_balances (source, equity, balance, free_margin) VALUES
('MT5', 25000.00, 24850.00, 24850.00),
('BINANCE', 12500.00, 12500.00, 12500.00),
('ONCHAIN_WALLET', 8400.00, 8400.00, 8400.00);

-- 2. ข้อมูลราคาล่าสุดจำลอง (Market Snapshots)
INSERT INTO market_snapshots (symbol, price_open, price_high, price_low, price_close, volume, indicators) VALUES
('XAUUSD', 2340.50, 2345.20, 2338.10, 2342.30, 1500.00, '{"rsi": 58.5, "ema_12": 2341.2, "ema_26": 2339.8, "atr": 7.1}'),
('BTCUSDT', 68100.00, 68350.00, 67900.00, 68150.00, 120.50, '{"rsi": 62.1, "ema_12": 68110.0, "ema_26": 68020.0, "atr": 340.0}');

-- 3. บันทึกไดอารี่ตั้งต้น (Trade Journal)
INSERT INTO trade_journal (log_type, message, metadata) VALUES
('system_init', 'ระบบนิเวศ AI Trading Virtual Office เริ่มต้นการทำงานเสร็จสมบูรณ์', '{"version": "1.0.0"}'),
('market_snapshot', 'ดึงข้อมูล XAUUSD ล่าสุดจาก MT5 สำเร็จ', '{"price": 2342.30}'),
('market_snapshot', 'ดึงข้อมูล BTCUSDT ล่าสุดจาก Binance สำเร็จ', '{"price": 68150.00}');
