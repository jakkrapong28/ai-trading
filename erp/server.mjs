import express from 'express';
import cors from 'cors';
import pg from 'pg';

const app = express();
const PORT = process.env.PORT || 5001;

app.use(cors());
app.use(express.json());

// ─────────────────────────────────────────────────────────
// Persistent Storage Layer (PostgreSQL Migration)
// ─────────────────────────────────────────────────────────

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:yourpassword@localhost:5432/ai_trading'
});

// Initialize DB schema
async function initDb() {
  try {
    await pool.query(`CREATE TABLE IF NOT EXISTS erp_ledger (
      id VARCHAR(50) PRIMARY KEY,
      timestamp TIMESTAMPTZ NOT NULL,
      event VARCHAR(100) NOT NULL,
      description TEXT,
      pnl DOUBLE PRECISION,
      debit_account VARCHAR(100),
      debit_amount DOUBLE PRECISION,
      credit_account VARCHAR(100),
      credit_amount DOUBLE PRECISION
    )`);

    await pool.query(`CREATE TABLE IF NOT EXISTS erp_stats (
      id INT PRIMARY KEY,
      accumulated_fees DOUBLE PRECISION NOT NULL,
      accumulated_pnl DOUBLE PRECISION NOT NULL,
      last_updated TIMESTAMPTZ NOT NULL
    )`);

    const statsRes = await pool.query('SELECT count(*) as count FROM erp_stats');
    if (parseInt(statsRes.rows[0].count) === 0) {
      await pool.query(
        'INSERT INTO erp_stats (id, accumulated_fees, accumulated_pnl, last_updated) VALUES (1, 145.20, 2340.50, $1)',
        [new Date().toISOString()]
      );
      await pool.query(
        `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING`,
        [
          'tx_001', 
          new Date(Date.now() - 3600000 * 2).toISOString(), 
          'system.init', 
          'บันทึกทุนจดทะเบียนเริ่มต้นระบบนิเวศการลงทุน', 
          '10100 - เงินสดในบัญชีเทรด', 
          45750.00, 
          '30100 - ทุนจดทะเบียน', 
          45750.00
        ]
      );
    }
    console.log('[ERP] PostgreSQL database initialized successfully.');
  } catch (err) {
    console.error('[ERP] Failed to initialize PostgreSQL:', err);
  }
}

// Start Schema Init
await initDb();

// Tax Configuration
const TAX_CONFIG = {
  vatRate: 0.07,          // VAT 7%
  corporateTaxRate: 0.20  // ภาษีเงินได้นิติบุคคล 20%
};

// ─────────────────────────────────────────────────────────
// API Routes
// ─────────────────────────────────────────────────────────

// GET /api/ledger — สมุดบัญชีแยกประเภท (paginated)
app.get('/api/ledger', async (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 50;
  const offset = (page - 1) * limit;
  try {
    const countRes = await pool.query('SELECT count(*) as count FROM erp_ledger');
    const total = parseInt(countRes.rows[0].count);
    
    const rowsRes = await pool.query(
      'SELECT * FROM erp_ledger ORDER BY timestamp DESC LIMIT $1 OFFSET $2',
      [limit, offset]
    );
    
    const ledger = rowsRes.rows.map(r => ({
      id: r.id,
      timestamp: r.timestamp,
      event: r.event,
      description: r.description,
      pnl: r.pnl,
      debit: { account: r.debit_account, amount: r.debit_amount },
      credit: { account: r.credit_account, amount: r.credit_amount }
    }));
    
    const statsRes = await pool.query('SELECT last_updated FROM erp_stats WHERE id = 1');
    const lastUpdated = statsRes.rows[0]?.last_updated || new Date().toISOString();
    
    res.json({
      success: true,
      ledger,
      total,
      page,
      lastUpdated
    });
  } catch (err) {
    console.error('[ERP] Error fetching ledger:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET /api/tax-summary — สรุปภาษี
app.get('/api/tax-summary', async (req, res) => {
  try {
    const statsRes = await pool.query('SELECT * FROM erp_stats WHERE id = 1');
    const stats = statsRes.rows[0] || { accumulated_fees: 145.20, accumulated_pnl: 2340.50, last_updated: new Date().toISOString() };
    
    const accumulatedPnL = stats.accumulated_pnl;
    const accumulatedFees = stats.accumulated_fees;
    const lastUpdated = stats.last_updated;
    
    const claimableInputVat = Number((accumulatedFees * TAX_CONFIG.vatRate).toFixed(2));
    const taxableIncome = Math.max(0, accumulatedPnL - accumulatedFees);
    const estimatedIncomeTax = Number((taxableIncome * TAX_CONFIG.corporateTaxRate).toFixed(2));
    const netAfterTax = Number((taxableIncome - estimatedIncomeTax).toFixed(2));

    res.json({
      success: true,
      data: {
        accumulatedPnL: Number(accumulatedPnL.toFixed(2)),
        accumulatedFees: Number(accumulatedFees.toFixed(2)),
        taxableIncome: Number(taxableIncome.toFixed(2)),
        vatRate: `${TAX_CONFIG.vatRate * 100}%`,
        inputVatClaimable: claimableInputVat,
        corporateTaxRate: `${TAX_CONFIG.corporateTaxRate * 100}%`,
        estimatedIncomeTax,
        netAfterTax,
        lastUpdated
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET /api/summary — Dashboard summary
app.get('/api/summary', async (req, res) => {
  try {
    // Query closed trades from ledger
    const tradesRes = await pool.query("SELECT * FROM erp_ledger WHERE event = 'trade.pnl_realized'");
    const trades = tradesRes.rows;
    
    const openedRes = await pool.query("SELECT count(*) as count FROM erp_ledger WHERE event = 'trade.opened'");
    const opened = parseInt(openedRes.rows[0].count);
    
    const closedWin = trades.filter(t => (t.pnl || 0) > 0).length;
    const closedLoss = trades.filter(t => (t.pnl || 0) <= 0).length;
    const winRate = trades.length > 0 ? ((closedWin / trades.length) * 100).toFixed(1) : '0.0';
    
    const statsRes = await pool.query('SELECT * FROM erp_stats WHERE id = 1');
    const stats = statsRes.rows[0] || { accumulated_fees: 145.20, accumulated_pnl: 2340.50, last_updated: new Date().toISOString() };
    
    const totalRes = await pool.query('SELECT count(*) as count FROM erp_ledger');
    const totalEntries = parseInt(totalRes.rows[0].count);

    res.json({
      success: true,
      summary: {
        totalTrades: opened,
        closedTrades: trades.length,
        winTrades: closedWin,
        lossTrades: closedLoss,
        winRate: parseFloat(winRate),
        totalPnL: Number(stats.accumulated_pnl.toFixed(2)),
        totalFees: Number(stats.accumulated_fees.toFixed(2)),
        netPnL: Number((stats.accumulated_pnl - stats.accumulated_fees).toFixed(2)),
        ledgerEntries: totalEntries,
        lastUpdated: stats.last_updated
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST /webhook/trade-event — รับ Domain Events จากระบบเทรด
app.post('/webhook/trade-event', async (req, res) => {
  const { event, data } = req.body;
  console.log(`[ERP] ← Event: ${event}`, JSON.stringify(data));

  if (!event || !data) {
    return res.status(400).json({ success: false, message: 'ข้อมูล Event หรือ Data ไม่ครบถ้วน' });
  }

  const timestamp = new Date().toISOString();
  const txId = `tx_${Date.now()}`;
  
  try {
    await pool.query('BEGIN');
    
    switch (event) {
      case 'trade.opened': {
        const amount = Number(((data.price || 0) * (data.volume || 0.01)).toFixed(2));
        const description = `เปิดออเดอร์ ${data.action} ${data.symbol} @ ${data.price} (Lot: ${data.volume})`;
        
        await pool.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, '10200 - พอร์ตลงทุน (ระหว่างเทรด)', amount, '10100 - เงินสดในบัญชีเทรด', amount]
        );
        break;
      }

      case 'trade.pnl_realized': {
        const pnlAmount = Number(data.pnl);
        const feeAmount = Number(data.fee || 0.0);
        
        // Update stats
        await pool.query(
          `UPDATE erp_stats SET accumulated_pnl = accumulated_pnl + $1, accumulated_fees = accumulated_fees + $2, last_updated = $3 WHERE id = 1`,
          [pnlAmount, feeAmount, timestamp]
        );
        
        // Insert PnL
        const description = pnlAmount >= 0 
          ? `กำไรจากการปิดดีล ${data.symbol} (PnL: +$${pnlAmount.toFixed(2)})` 
          : `ขาดทุนจากการปิดดีล ${data.symbol} (PnL: $${pnlAmount.toFixed(2)})`;
        const debitAccount = pnlAmount >= 0 ? '10100 - เงินสดในบัญชีเทรด' : '50100 - ขาดทุนจากการลงทุน';
        const creditAccount = pnlAmount >= 0 ? '40100 - รายได้จากการลงทุน' : '10100 - เงินสดในบัญชีเทรด';
        const amountVal = Math.abs(pnlAmount);
        
        await pool.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, pnl, debit_account, debit_amount, credit_account, credit_amount) 
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, description, pnlAmount, debitAccount, amountVal, creditAccount, amountVal]
        );
        
        // Insert fee
        if (feeAmount > 0) {
          const feeDesc = `ค่าธรรมเนียมดีล ${data.symbol} ($${feeAmount.toFixed(2)})`;
          await pool.query(
            `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING`,
            [`${txId}_fee`, timestamp, 'fee.recorded', feeDesc, '50200 - ค่าธรรมเนียมโบรกเกอร์', feeAmount, '10100 - เงินสดในบัญชีเทรด', feeAmount]
          );
        }
        
        // VAT
        const vatOnFee = Number((feeAmount * TAX_CONFIG.vatRate).toFixed(2));
        if (vatOnFee > 0) {
          const vatDesc = `ภาษีซื้อ VAT 7% บนค่าธรรมเนียม ${data.symbol}`;
          await pool.query(
            `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING`,
            [`${txId}_vat`, timestamp, 'tax.vat_input', vatDesc, '18100 - ภาษีซื้อ (ขอคืนได้)', vatOnFee, '10100 - เงินสดในบัญชีเทรด', vatOnFee]
          );
        }
        break;
      }

      case 'fee.recorded': {
        const feeOnly = Number(data.amount || 0);
        const feeDesc = `ค่าธรรมเนียม: ${data.description || 'ไม่มีรายละเอียด'} ($${feeOnly})`;
        
        await pool.query(
          `UPDATE erp_stats SET accumulated_fees = accumulated_fees + $1, last_updated = $2 WHERE id = 1`,
          [feeOnly, timestamp]
        );
        
        await pool.query(
          `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING`,
          [txId, timestamp, event, feeDesc, '50200 - ค่าธรรมเนียมโบรกเกอร์', feeOnly, '10100 - เงินสดในบัญชีเทรด', feeOnly]
        );
        break;
      }
    }
    
    await pool.query('COMMIT');
    
    // Query updated stats for response
    const statsRes = await pool.query('SELECT * FROM erp_stats WHERE id = 1');
    const updatedStats = statsRes.rows[0];
    const totalRes = await pool.query('SELECT count(*) as count FROM erp_ledger');
    const totalEntries = parseInt(totalRes.rows[0].count);
    
    res.json({
      success: true,
      message: 'บันทึกข้อมูลเข้าสู่ระบบ ERP Ledger เรียบร้อย',
      ledgerLength: totalEntries,
      totalPnL: Number(updatedStats.accumulated_pnl.toFixed(2))
    });
    
  } catch (err) {
    await pool.query('ROLLBACK');
    console.error('[ERP] Webhook error:', err);
    res.status(500).json({ success: false, error: err.message });
  }
});

// DELETE /api/reset — รีเซ็ต ERP (สำหรับ dev/test)
app.delete('/api/reset', async (req, res) => {
  try {
    await pool.query('BEGIN');
    await pool.query('DELETE FROM erp_ledger');
    await pool.query('UPDATE erp_stats SET accumulated_fees = 0, accumulated_pnl = 0, last_updated = $1 WHERE id = 1', [new Date().toISOString()]);
    
    await pool.query(
      `INSERT INTO erp_ledger (id, timestamp, event, description, debit_account, debit_amount, credit_account, credit_amount) 
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      ['tx_reset', new Date().toISOString(), 'system.reset', 'รีเซ็ตระบบ ERP Ledger', '10100 - เงินสด', 0, '30100 - ทุน', 0]
    );
    await pool.query('COMMIT');
    res.json({ success: true, message: 'ERP รีเซ็ตฐานข้อมูล PostgreSQL เรียบร้อย' });
  } catch (err) {
    await pool.query('ROLLBACK');
    res.status(500).json({ success: false, error: err.message });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    const countRes = await pool.query('SELECT count(*) as count FROM erp_ledger');
    const total = parseInt(countRes.rows[0].count);
    
    const statsRes = await pool.query('SELECT * FROM erp_stats WHERE id = 1');
    const stats = statsRes.rows[0] || { accumulated_pnl: 0 };
    
    res.json({
      status: 'ok',
      uptime: process.uptime(),
      ledgerEntries: total,
      totalPnL: stats.accumulated_pnl
    });
  } catch (err) {
    res.status(500).json({ status: 'error', error: err.message });
  }
});

const server = app.listen(PORT, () => {
  console.log(`🚀 [Team ERP Server] รันบนพอร์ต http://localhost:${PORT}`);
  console.log(`🗄️ [ERP] Database PostgreSQL connected`);
});

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`\n❌ [ERP] Port ${PORT} ถูกใช้งานอยู่แล้ว!`);
    console.error(`   วิธีแก้: รันคำสั่งนี้ก่อน แล้ว npm start ใหม่`);
    console.error(`   lsof -ti :${PORT} | xargs kill -9\n`);
    process.exit(1);
  } else {
    console.error('[ERP] Server error:', err);
    process.exit(1);
  }
});
