import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 5001;

app.use(cors());
app.use(express.json());

// 1. ระบบบัญชีแยกประเภททั่วไปจำลอง (General Ledger State)
const ledger = [
  {
    id: "tx_001",
    timestamp: new Date(Date.now() - 3600000 * 2).toISOString(),
    event: "system.init",
    description: "บันทึกทุนจดทะเบียนเริ่มต้นระบบนิเวศการลงทุน",
    debit: { account: "10100 - เงินสดในบัญชีเทรด", amount: 45750.00 },
    credit: { account: "30100 - ทุนจดทะเบียน (คุณโทนี่)", amount: 45750.00 }
  }
];

// 2. ระบบคำนวณภาษีสะสม (Team Tax Compliance State)
const TAX_CONFIG = {
  vatRate: 0.07,         // VAT 7%
  corporateTaxRate: 0.20 // ภาษีเงินได้นิติบุคคล 20%
};

let accumulatedFees = 145.20; // ค่าธรรมเนียมการเทรดสะสม (ใช้สิทธิ์ขอคืนภาษีซื้อ)
let accumulatedPnL = 2340.50;  // กำไรสะสมจากการเทรด

// 3. API - ดึงรายการสมุดบัญชีแยกประเภท (General Ledger)
app.get('/api/ledger', (req, res) => {
  res.json({
    success: true,
    ledger: ledger
  });
});

// 4. API - สรุปภาษี Team Tax Compliance
app.get('/api/tax-summary', (req, res) => {
  // คำนวณ VAT ซื้อจากค่าธรรมเนียมการเทรดที่โบรกเกอร์หรือ CEX เรียกเก็บ
  const claimableInputVat = Number((accumulatedFees * TAX_CONFIG.vatRate).toFixed(2));
  
  // คำนวณภาษีเงินได้จากกำไรสุทธิ
  const taxableIncome = Math.max(0, accumulatedPnL - accumulatedFees);
  const estimatedIncomeTax = Number((taxableIncome * TAX_CONFIG.corporateTaxRate).toFixed(2));

  res.json({
    success: true,
    data: {
      accumulatedPnL,
      accumulatedFees,
      taxableIncome,
      vatRate: `${TAX_CONFIG.vatRate * 100}%`,
      inputVatClaimable: claimableInputVat, // ภาษีซื้อที่นำไปหักภาษีขายได้
      corporateTaxRate: `${TAX_CONFIG.corporateTaxRate * 100}%`,
      estimatedIncomeTax,                  // ประมาณการภาษีเงินได้ที่ต้องจ่าย
      netAfterTax: Number((taxableIncome - estimatedIncomeTax).toFixed(2)),
      lastUpdated: new Date().toISOString()
    }
  });
});

// 5. Webhook - รับ Domain Events จากระบบเทรด
app.post('/webhook/trade-event', (req, res) => {
  const { event, data } = req.body;
  console.log(`[ERP Engine] ได้รับ Domain Event: ${event}`, data);

  if (!event || !data) {
    return res.status(400).json({ success: false, message: "ข้อมูล Event หรือ Data ไม่ครบถ้วน" });
  }

  const timestamp = new Date().toISOString();
  const txId = `tx_${Date.now()}`;

  switch (event) {
    case 'trade.opened':
      ledger.push({
        id: txId,
        timestamp,
        event,
        description: `เปิดออเดอร์ ${data.action} ${data.symbol} ที่ราคา ${data.price} (Lot: ${data.volume || 1})`,
        debit: { account: "10200 - พอร์ตลงทุน (ระหว่างเทรด)", amount: Number((data.price * (data.volume || 1)).toFixed(2)) },
        credit: { account: "10100 - เงินสดในบัญชีเทรด", amount: Number((data.price * (data.volume || 1)).toFixed(2)) }
      });
      break;

    case 'trade.pnl_realized':
      const pnlAmount = Number(data.pnl);
      const feeAmount = Number(data.fee || 0.0);
      
      accumulatedPnL += pnlAmount;
      accumulatedFees += feeAmount;

      if (pnlAmount >= 0) {
        // กรณีบันทึกกำไร
        ledger.push({
          id: txId,
          timestamp,
          event,
          description: `รับรู้กำไรจากการปิดดีล ${data.symbol} (PnL: +$${pnlAmount})`,
          debit: { account: "10100 - เงินสดในบัญชีเทรด", amount: pnlAmount },
          credit: { account: "40100 - รายได้จากการลงทุนเทรด", amount: pnlAmount }
        });
      } else {
        // กรณีบันทึกขาดทุน
        ledger.push({
          id: txId,
          timestamp,
          event,
          description: `บันทึกการขาดทุนจากการปิดดีล ${data.symbol} (PnL: $${pnlAmount})`,
          debit: { account: "50100 - ขาดทุนจากการลงทุนเทรด", amount: Math.abs(pnlAmount) },
          credit: { account: "10100 - เงินสดในบัญชีเทรด", amount: Math.abs(pnlAmount) }
        });
      }

      // บันทึกค่าธรรมเนียม
      if (feeAmount > 0) {
        ledger.push({
          id: `${txId}_fee`,
          timestamp,
          event: "fee.recorded",
          description: `บันทึกค่าธรรมเนียมบริการเทรดดีล ${data.symbol}`,
          debit: { account: "50200 - ค่าธรรมเนียมโบรกเกอร์ (รอขอคืน VAT ซื้อ)", amount: feeAmount },
          credit: { account: "10100 - เงินสดในบัญชีเทรด", amount: feeAmount }
        });
      }
      break;

    case 'fee.recorded':
      const feeOnly = Number(data.amount);
      accumulatedFees += feeOnly;
      ledger.push({
        id: txId,
        timestamp,
        event,
        description: `บันทึกค่าธรรมเนียมธุรกรรมทั่วไป (${data.description || 'ไม่มีรายละเอียด'})`,
        debit: { account: "50200 - ค่าธรรมเนียมโบรกเกอร์ (รอขอคืน VAT ซื้อ)", amount: feeOnly },
        credit: { account: "10100 - เงินสดในบัญชีเทรด", amount: feeOnly }
      });
      break;

    default:
      console.log(`[ERP Engine] ข้ามการประมวลผล Event ที่ไม่มีผลต่อบัญชีโดยตรง: ${event}`);
  }

  res.json({
    success: true,
    message: "บันทึกข้อมูลเข้าสู่ระบบ ERP Ledger เรียบร้อย",
    ledgerLength: ledger.length
  });
});

app.listen(PORT, () => {
  console.log(`🚀 [Team ERP Server] รันบนพอร์ต http://localhost:${PORT}`);
});
