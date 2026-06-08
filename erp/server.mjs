import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_FILE = path.join(__dirname, 'erp-data.json');

const app = express();
const PORT = process.env.PORT || 5001;

app.use(cors());
app.use(express.json());

// ─────────────────────────────────────────────────────────
// Persistent Storage Layer
// ─────────────────────────────────────────────────────────

function loadData() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      const raw = fs.readFileSync(DATA_FILE, 'utf-8');
      return JSON.parse(raw);
    }
  } catch (e) {
    console.error('[ERP] Error loading data file:', e.message);
  }
  // Default initial state
  return {
    ledger: [
      {
        id: 'tx_001',
        timestamp: new Date(Date.now() - 3600000 * 2).toISOString(),
        event: 'system.init',
        description: 'บันทึกทุนจดทะเบียนเริ่มต้นระบบนิเวศการลงทุน',
        debit: { account: '10100 - เงินสดในบัญชีเทรด', amount: 45750.00 },
        credit: { account: '30100 - ทุนจดทะเบียน', amount: 45750.00 }
      }
    ],
    accumulatedFees: 145.20,
    accumulatedPnL: 2340.50,
    lastUpdated: new Date().toISOString()
  };
}

function saveData(data) {
  try {
    data.lastUpdated = new Date().toISOString();
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), 'utf-8');
  } catch (e) {
    console.error('[ERP] Error saving data file:', e.message);
  }
}

// Load on startup
let db = loadData();
console.log(`[ERP] Loaded ${db.ledger.length} ledger entries from storage.`);

// ─────────────────────────────────────────────────────────
// Tax Configuration
// ─────────────────────────────────────────────────────────

const TAX_CONFIG = {
  vatRate: 0.07,          // VAT 7%
  corporateTaxRate: 0.20  // ภาษีเงินได้นิติบุคคล 20%
};

// ─────────────────────────────────────────────────────────
// API Routes
// ─────────────────────────────────────────────────────────

// GET /api/ledger — สมุดบัญชีแยกประเภท (paginated)
app.get('/api/ledger', (req, res) => {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 50;
  const start = (page - 1) * limit;
  const slice = db.ledger.slice(-limit * page).reverse().slice(0, limit);

  res.json({
    success: true,
    ledger: slice,
    total: db.ledger.length,
    page,
    lastUpdated: db.lastUpdated
  });
});

// GET /api/tax-summary — สรุปภาษี
app.get('/api/tax-summary', (req, res) => {
  const claimableInputVat = Number((db.accumulatedFees * TAX_CONFIG.vatRate).toFixed(2));
  const taxableIncome = Math.max(0, db.accumulatedPnL - db.accumulatedFees);
  const estimatedIncomeTax = Number((taxableIncome * TAX_CONFIG.corporateTaxRate).toFixed(2));
  const netAfterTax = Number((taxableIncome - estimatedIncomeTax).toFixed(2));

  res.json({
    success: true,
    data: {
      accumulatedPnL: Number(db.accumulatedPnL.toFixed(2)),
      accumulatedFees: Number(db.accumulatedFees.toFixed(2)),
      taxableIncome: Number(taxableIncome.toFixed(2)),
      vatRate: `${TAX_CONFIG.vatRate * 100}%`,
      inputVatClaimable: claimableInputVat,
      corporateTaxRate: `${TAX_CONFIG.corporateTaxRate * 100}%`,
      estimatedIncomeTax,
      netAfterTax,
      lastUpdated: db.lastUpdated
    }
  });
});

// GET /api/summary — Dashboard summary
app.get('/api/summary', (req, res) => {
  const trades = db.ledger.filter(e => e.event === 'trade.pnl_realized');
  const opened = db.ledger.filter(e => e.event === 'trade.opened').length;
  const closedWin = trades.filter(e => e.pnl > 0).length;
  const closedLoss = trades.filter(e => e.pnl <= 0).length;
  const winRate = trades.length > 0 ? ((closedWin / trades.length) * 100).toFixed(1) : '0.0';

  res.json({
    success: true,
    summary: {
      totalTrades: opened,
      closedTrades: trades.length,
      winTrades: closedWin,
      lossTrades: closedLoss,
      winRate: parseFloat(winRate),
      totalPnL: Number(db.accumulatedPnL.toFixed(2)),
      totalFees: Number(db.accumulatedFees.toFixed(2)),
      netPnL: Number((db.accumulatedPnL - db.accumulatedFees).toFixed(2)),
      ledgerEntries: db.ledger.length,
      lastUpdated: db.lastUpdated
    }
  });
});

// POST /webhook/trade-event — รับ Domain Events จากระบบเทรด
app.post('/webhook/trade-event', (req, res) => {
  const { event, data } = req.body;
  console.log(`[ERP] ← Event: ${event}`, JSON.stringify(data));

  if (!event || !data) {
    return res.status(400).json({ success: false, message: 'ข้อมูล Event หรือ Data ไม่ครบถ้วน' });
  }

  const timestamp = new Date().toISOString();
  const txId = `tx_${Date.now()}`;

  switch (event) {
    case 'trade.opened': {
      const amount = Number(((data.price || 0) * (data.volume || 0.01)).toFixed(2));
      db.ledger.push({
        id: txId,
        timestamp,
        event,
        description: `เปิดออเดอร์ ${data.action} ${data.symbol} @ ${data.price} (Lot: ${data.volume})`,
        debit: { account: '10200 - พอร์ตลงทุน (ระหว่างเทรด)', amount },
        credit: { account: '10100 - เงินสดในบัญชีเทรด', amount }
      });
      break;
    }

    case 'trade.pnl_realized': {
      const pnlAmount = Number(data.pnl);
      const feeAmount = Number(data.fee || 0.0);

      db.accumulatedPnL = Number((db.accumulatedPnL + pnlAmount).toFixed(2));
      db.accumulatedFees = Number((db.accumulatedFees + feeAmount).toFixed(2));

      // บันทึก PnL
      if (pnlAmount >= 0) {
        db.ledger.push({
          id: txId,
          timestamp,
          event,
          pnl: pnlAmount,
          description: `กำไรจากการปิดดีล ${data.symbol} (PnL: +$${pnlAmount.toFixed(2)})`,
          debit: { account: '10100 - เงินสดในบัญชีเทรด', amount: pnlAmount },
          credit: { account: '40100 - รายได้จากการลงทุน', amount: pnlAmount }
        });
      } else {
        db.ledger.push({
          id: txId,
          timestamp,
          event,
          pnl: pnlAmount,
          description: `ขาดทุนจากการปิดดีล ${data.symbol} (PnL: $${pnlAmount.toFixed(2)})`,
          debit: { account: '50100 - ขาดทุนจากการลงทุน', amount: Math.abs(pnlAmount) },
          credit: { account: '10100 - เงินสดในบัญชีเทรด', amount: Math.abs(pnlAmount) }
        });
      }

      // บันทึกค่าธรรมเนียม
      if (feeAmount > 0) {
        db.ledger.push({
          id: `${txId}_fee`,
          timestamp,
          event: 'fee.recorded',
          description: `ค่าธรรมเนียมดีล ${data.symbol} ($${feeAmount.toFixed(2)})`,
          debit: { account: '50200 - ค่าธรรมเนียมโบรกเกอร์', amount: feeAmount },
          credit: { account: '10100 - เงินสดในบัญชีเทรด', amount: feeAmount }
        });
      }

      // คำนวณภาษี VAT หักที่จ่าย (ตัวแทน)
      const vatOnFee = Number((feeAmount * TAX_CONFIG.vatRate).toFixed(2));
      if (vatOnFee > 0) {
        db.ledger.push({
          id: `${txId}_vat`,
          timestamp,
          event: 'tax.vat_input',
          description: `ภาษีซื้อ VAT 7% บนค่าธรรมเนียม ${data.symbol}`,
          debit: { account: '18100 - ภาษีซื้อ (ขอคืนได้)', amount: vatOnFee },
          credit: { account: '10100 - เงินสดในบัญชีเทรด', amount: vatOnFee }
        });
      }
      break;
    }

    case 'fee.recorded': {
      const feeOnly = Number(data.amount || 0);
      db.accumulatedFees = Number((db.accumulatedFees + feeOnly).toFixed(2));
      db.ledger.push({
        id: txId,
        timestamp,
        event,
        description: `ค่าธรรมเนียม: ${data.description || 'ไม่มีรายละเอียด'} ($${feeOnly})`,
        debit: { account: '50200 - ค่าธรรมเนียมโบรกเกอร์', amount: feeOnly },
        credit: { account: '10100 - เงินสดในบัญชีเทรด', amount: feeOnly }
      });
      break;
    }

    default:
      console.log(`[ERP] Unhandled event: ${event}`);
  }

  // Persist ทุกครั้งที่มีการเปลี่ยนแปลง
  saveData(db);

  res.json({
    success: true,
    message: 'บันทึกข้อมูลเข้าสู่ระบบ ERP Ledger เรียบร้อย',
    ledgerLength: db.ledger.length,
    totalPnL: Number(db.accumulatedPnL.toFixed(2))
  });
});

// DELETE /api/reset — รีเซ็ต ERP (สำหรับ dev/test)
app.delete('/api/reset', (req, res) => {
  db = {
    ledger: [{
      id: 'tx_reset',
      timestamp: new Date().toISOString(),
      event: 'system.reset',
      description: 'รีเซ็ตระบบ ERP Ledger',
      debit: { account: '10100 - เงินสด', amount: 0 },
      credit: { account: '30100 - ทุน', amount: 0 }
    }],
    accumulatedFees: 0,
    accumulatedPnL: 0,
    lastUpdated: new Date().toISOString()
  };
  saveData(db);
  res.json({ success: true, message: 'ERP รีเซ็ตเรียบร้อย' });
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    ledgerEntries: db.ledger.length,
    totalPnL: db.accumulatedPnL,
    dataFile: DATA_FILE
  });
});

const server = app.listen(PORT, () => {
  console.log(`🚀 [Team ERP Server] รันบนพอร์ต http://localhost:${PORT}`);
  console.log(`📁 [ERP] Data persisted at: ${DATA_FILE}`);
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
