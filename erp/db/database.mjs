import pg from 'pg';

const {
  DATABASE_URL,
  DB_POOL_MAX,
  DB_IDLE_TIMEOUT_MS,
  DB_CONNECT_TIMEOUT_MS
} = process.env;

// ─────────────────────────────────────────────────────────
// Tuned connection pool
// ─────────────────────────────────────────────────────────
export const pool = new pg.Pool({
  connectionString: DATABASE_URL || 'postgresql://postgres:yourpassword@127.0.0.1:5432/ai_trading',
  max: parseInt(DB_POOL_MAX) || 20,
  idleTimeoutMillis: parseInt(DB_IDLE_TIMEOUT_MS) || 30000,
  connectionTimeoutMillis: parseInt(DB_CONNECT_TIMEOUT_MS) || 5000,
});

pool.on('error', (err) => {
  console.error('[ERP][DB] Unexpected pool error:', err.message);
});

// ─────────────────────────────────────────────────────────
// Schema Initialization — all tables + indexes
// ─────────────────────────────────────────────────────────
export async function initDb() {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Core accounting ledger
    await client.query(`
      CREATE TABLE IF NOT EXISTS erp_ledger (
        id VARCHAR(100) PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        event VARCHAR(100) NOT NULL,
        description TEXT,
        pnl DOUBLE PRECISION,
        debit_account VARCHAR(100),
        debit_amount DOUBLE PRECISION,
        credit_account VARCHAR(100),
        credit_amount DOUBLE PRECISION,
        trade_id VARCHAR(100),
        correlation_id VARCHAR(100)
      )
    `);

    // Stats row (singleton)
    await client.query(`
      CREATE TABLE IF NOT EXISTS erp_stats (
        id INT PRIMARY KEY,
        accumulated_fees DOUBLE PRECISION NOT NULL DEFAULT 0,
        accumulated_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
        last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    // Idempotency table for webhook deduplication
    await client.query(`
      CREATE TABLE IF NOT EXISTS erp_delivery_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idempotency_key VARCHAR(255) UNIQUE NOT NULL,
        event VARCHAR(100) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
        response_code INTEGER,
        payload JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    // Trade positions audit trail
    await client.query(`
      CREATE TABLE IF NOT EXISTS trade_positions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trade_id VARCHAR(100) UNIQUE NOT NULL,
        symbol VARCHAR(50) NOT NULL,
        action VARCHAR(20) NOT NULL,
        entry_price DOUBLE PRECISION,
        exit_price DOUBLE PRECISION,
        lot_size DOUBLE PRECISION,
        stop_loss DOUBLE PRECISION,
        take_profit DOUBLE PRECISION,
        atr_at_entry DOUBLE PRECISION,
        realized_pnl DOUBLE PRECISION,
        fee DOUBLE PRECISION DEFAULT 0,
        rr_ratio DOUBLE PRECISION,
        duration_minutes INTEGER,
        opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        closed_at TIMESTAMPTZ,
        status VARCHAR(30) NOT NULL DEFAULT 'OPEN'
      )
    `);

    // Audit log
    await client.query(`
      CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_type VARCHAR(100) NOT NULL,
        user_agent TEXT,
        ip_address VARCHAR(100),
        correlation_id VARCHAR(100),
        payload JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    // ── Migrations for existing tables (add columns if missing) ─
    await client.query(`
      ALTER TABLE erp_ledger 
        ADD COLUMN IF NOT EXISTS trade_id VARCHAR(100),
        ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(100)
    `);

    // audit_logs may have been created with old schema — ensure all columns exist and constraints are relaxed
    try {
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS event_type VARCHAR(100)`);
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent TEXT`);
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(100)`);
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(100)`);
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS payload JSONB`);
      await client.query(`ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()`);
      
      // Relax old schema NOT NULL constraints so ERP inserts can succeed
      await client.query(`ALTER TABLE audit_logs ALTER COLUMN event_name DROP NOT NULL`);
      await client.query(`ALTER TABLE audit_logs ALTER COLUMN actor DROP NOT NULL`);
    } catch (_) { /* fresh table: columns created via CREATE TABLE above */ }

    // erp_delivery_records may have been created with Python schema — ensure all columns exist
    try {
      await client.query(`ALTER TABLE erp_delivery_records ADD COLUMN IF NOT EXISTS event VARCHAR(100)`);
      await client.query(`ALTER TABLE erp_delivery_records ADD COLUMN IF NOT EXISTS payload JSONB`);
    } catch (_) { /* fresh table: columns created via CREATE TABLE above */ }




    // ── Indexes ──────────────────────────────────────────

    await client.query(`CREATE INDEX IF NOT EXISTS idx_erp_ledger_timestamp ON erp_ledger(timestamp DESC)`);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_erp_ledger_event ON erp_ledger(event)`);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_erp_ledger_trade_id ON erp_ledger(trade_id)`);

    await client.query(`CREATE INDEX IF NOT EXISTS idx_trade_positions_trade_id ON trade_positions(trade_id)`);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_trade_positions_symbol ON trade_positions(symbol)`);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_trade_positions_status ON trade_positions(status)`);

    await client.query(`CREATE INDEX IF NOT EXISTS idx_delivery_records_ikey ON erp_delivery_records(idempotency_key)`);

    await client.query(`CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type)`);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC)`);

    // ── Seed default stats row ────────────────────────────
    const statsCount = await client.query('SELECT count(*) as c FROM erp_stats');
    if (parseInt(statsCount.rows[0].c) === 0) {
      const initialCapital = parseFloat(process.env.INITIAL_CAPITAL || '45750.00');
      await client.query(
        `INSERT INTO erp_stats (id, accumulated_fees, accumulated_pnl, last_updated) VALUES (1, 145.20, 2340.50, NOW())`
      );
      // Opening balance ledger entry
      await client.query(
        `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount)
         VALUES ('tx_001', NOW(), 'system.init', 'บันทึกทุนจดทะเบียนเริ่มต้นระบบนิเวศการลงทุน',
                 '10100 - เงินสดในบัญชีเทรด', $1, '30100 - ทุนจดทะเบียน', $1)
         ON CONFLICT (id) DO NOTHING`,
        [initialCapital]
      );
    }

    await client.query('COMMIT');
    console.log('[ERP][DB] Schema initialized with all tables and indexes.');
  } catch (err) {
    await client.query('ROLLBACK');
    console.error('[ERP][DB] Schema initialization failed:', err.message);
    throw err;
  } finally {
    client.release();
  }
}

// ─────────────────────────────────────────────────────────
// Health check helpers
// ─────────────────────────────────────────────────────────
export async function checkDbHealth() {
  try {
    const res = await pool.query('SELECT 1 AS ok');
    return res.rows[0].ok === 1;
  } catch {
    return false;
  }
}

export async function getPendingDeliveries() {
  try {
    const res = await pool.query(
      `SELECT count(*) as c FROM erp_delivery_records WHERE status IN ('PENDING', 'ERROR')`
    );
    return parseInt(res.rows[0].c);
  } catch {
    return -1;
  }
}
