// TAB: 📊 Reports — ERP general ledger (double-entry) and accumulated tax summary.
import type { LedgerEntry, TaxSummary } from "@/types";
import { parseUTCDate } from "@/lib/datetime";

interface ReportsTabProps {
  active: boolean;
  ledger: LedgerEntry[];
  taxSummary: TaxSummary | null;
  onResetData: () => void;
}

const ReportsTab = ({ active, ledger, taxSummary, onResetData }: ReportsTabProps) => {
  return (
    <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${active ? "block" : "hidden"}`}>
      <div className="border-b border-[#1e2d45] pb-4 flex justify-between items-center flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-white">📊 รายงานบัญชีและระเบียบภาษีคลัง (Team ERP Ledger & Tax Sheet)</h2>
          <p className="text-xs text-[#7a9bbf] mt-1">สมุดรายการเดบิต/เครดิต และประมาณการการชำระภาษีสะสมในไทย</p>
        </div>
        <button
          onClick={onResetData}
          className="text-xs px-3 py-1.5 bg-red-600/20 hover:bg-red-600 border border-red-500/30 hover:border-red-500 text-red-200 hover:text-white rounded-lg transition-all duration-300 font-bold flex items-center gap-1.5 shadow-[0_0_10px_rgba(239,68,68,0.1)] hover:shadow-[0_0_15px_rgba(239,68,68,0.3)] font-sans"
        >
          🗑️ ล้างประวัติการเทรด & บัญชี ERP
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* รายงานเดบิต เครดิต ERP */}
        <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-xl p-5 space-y-4 backdrop-blur-md">
          <div className="text-xs text-white font-bold uppercase tracking-wider font-mono flex justify-between items-center">
            <span>สมุดบัญชีแยกประเภททั่วไป (General Ledger Double-Entry)</span>
            <span className="text-[10px] text-slate-500 font-normal font-sans">ล่าสุด: {ledger.length} รายการ</span>
          </div>
          <div className="space-y-3 max-h-[450px] overflow-y-auto pr-1">
            {ledger.length === 0 ? (
              <div className="text-center text-slate-500 py-24 text-xs font-sans">
                ยังไม่มีรายการบันทึกในสมุดบัญชีแยกประเภท
              </div>
            ) : (
              ledger.map((tx, idx) => (
                <div key={idx} className="bg-black/60 border border-white/5 p-4 rounded-lg text-xs space-y-2.5 font-mono hover:border-white/10 transition-colors">
                  <div className="flex justify-between text-[10px] text-slate-500">
                    <span>TX ID: {tx.id}</span>
                    <span>{parseUTCDate(tx.timestamp).toLocaleString('th-TH')}</span>
                  </div>
                  <div className="font-semibold text-slate-200">{tx.description}</div>
                  <div className="grid grid-cols-2 gap-4 text-[10px] border-t border-white/5 pt-2">
                    <div className="text-emerald-400">
                      Dr: {tx.debit.account}
                      <div className="font-bold text-white text-xs mt-0.5">${tx.debit.amount.toLocaleString()}</div>
                    </div>
                    <div className="text-amber-400">
                      Cr: {tx.credit.account}
                      <div className="font-bold text-white text-xs mt-0.5">${tx.credit.amount.toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* แบบสรุปภาษี Team Tax */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-5 space-y-5 backdrop-blur-md">
          <div className="text-xs text-white font-bold uppercase tracking-wider font-mono">แบบสรุปการยื่นภาษีสะสม (Team Tax Summary)</div>
          {taxSummary ? (
            <div className="text-xs space-y-4 font-mono">
              <div className="flex justify-between py-2 border-b border-white/5">
                <span className="text-slate-400">กำไรสะสม (Accumulated PnL):</span>
                <span className="font-bold text-emerald-400">${taxSummary.accumulatedPnL.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-white/5">
                <span className="text-slate-400">ค่าธรรมเนียมสะสม (Accumulated Fees):</span>
                <span className="font-bold text-red-400">${taxSummary.accumulatedFees.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-white/5">
                <span className="text-slate-400">รายได้สุทธิเพื่อคำนวณ (Taxable Income):</span>
                <span className="font-bold text-white">${taxSummary.taxableIncome.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-white/5">
                <span className="text-emerald-400 font-bold">ภาษีซื้อขอคืนสะสม (VAT {taxSummary.vatRate}):</span>
                <span className="font-bold text-emerald-400">+${taxSummary.inputVatClaimable.toLocaleString()}</span>
              </div>
              <div className="flex justify-between py-2 border-b border-white/5">
                <span className="text-red-400 font-bold">ภาษีนิติบุคคลหักสะสม ({taxSummary.corporateTaxRate}):</span>
                <span className="font-bold text-red-400">-${taxSummary.estimatedIncomeTax.toLocaleString()}</span>
              </div>
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex justify-between items-center text-sm font-bold mt-4 shadow-[0_0_15px_rgba(16,185,129,0.05)] font-sans">
                <span className="text-emerald-400">กำไรสุทธิหลังหักภาษี (Net profit):</span>
                <span className="text-emerald-400 text-base font-black">${taxSummary.netAfterTax.toLocaleString()}</span>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-500 py-12 text-xs font-sans">ยังไม่มีข้อมูลภาษีสะสม</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportsTab;
