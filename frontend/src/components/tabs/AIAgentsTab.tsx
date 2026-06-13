// TAB: 🤖 AI Agents — Blueprint & role descriptions for the 9-agent virtual office.
// Purely static content; visibility is driven by the parent's active tab.

const AIAgentsTab = ({ active }: { active: boolean }) => {
  return (
    <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${active ? "block" : "hidden"}`}>
      <div className="border-b border-[#1e2d45] pb-4">
        <h2 className="text-xl font-bold text-white">🤖 บทบาทหน้าที่ทีมงาน AI (AI Trading Virtual Office Agents)</h2>
        <p className="text-xs text-[#7a9bbf] mt-1">อัปเดตบทบาทหน้าที่การทำงานของ 9 เอเจนต์หลัก ในระบบเทรดภาษาไทยอย่างถูกต้อง</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        {/* Agent 1 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#60a5fa] flex items-center gap-1.5 font-mono">🕴️ AGENT 1: CEO Agent</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: JARVIS-CEO | บทบาท: ผู้นำประสานงานกลาง</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            รับคำสั่งจากผู้ใช้ สั่งการวิเคราะห์ไปหา Chart AI, Risk AI และ News AI แบบขนาน รวบรวมสรุปผลโหวตและแผนเข้าตลาดเพื่อส่งคำขออนุมัติเทรด (Approve/Reject) หรือประมวลผลระบบเทรดอัตโนมัติ
          </div>
        </div>

        {/* Agent 2 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#34d399] flex items-center gap-1.5 font-mono">📊 AGENT 2: Chart AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: NOVA-CHART | บทบาท: นักวิเคราะห์เทคนิค</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            ประเมินแนวโน้มราคาทางเทคนิค คำนวณอินดิเคเตอร์เชิงซ้อน (RSI, ATR, Trend, EMA) และระบุแนวรับแนวต้าน พร้อมสรุปเป็นระดับความมั่นใจเทคนิค (Confluence Score)
          </div>
        </div>

        {/* Agent 3 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#f87171] flex items-center gap-1.5 font-mono">🛡️ AGENT 3: Risk AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: SHIELD-RISK | บทบาท: ผู้คุมความเสี่ยงพอร์ต</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            คำนวณขนาดไม้ (Lot Size) ที่เหมาะสมตามความเสี่ยง ตรวจสอบเกณฑ์ป้องกันความเสี่ยงสูงสุดต่อไม้สูงสุด 2% ป้องกันการขาดทุนสะสม (Daily Drawdown) และหยุดการเทรดหากชนขีดจำกัด
          </div>
        </div>

        {/* Agent 4 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">🎯 AGENT 4: Strategy AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ORACLE-STRATEGY | บทบาท: ผู้วางกลยุทธ์ตามสภาวะ</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            วิเคราะห์ Market Regime คัดกรองและปรับสภาวะการเทรดตามช่วงเวลาดัชนี (ADX, Volatility) เพื่อวางกฎการส่งออเดอร์และการวางแผน Stop Loss/Take Profit ที่เหมาะสม
          </div>
        </div>

        {/* Agent 5 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#f97316] flex items-center gap-1.5 font-mono">📰 AGENT 5: News AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ECHO-NEWS | บทบาท: นักสแกนอารมณ์ข่าว</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            สแกนหาข่าวด่วน ข้อมูลเศรษฐกิจรอบโลก ดึงค่า Sentiment ด้วย FinBERT เพื่อกรองผลลบ/ผลบวกในการลงทุน และบล็อกคำสั่งซื้อขายในช่วงเวลาข่าวผันผวนระดับสูง (High-impact News)
          </div>
        </div>

        {/* Agent 6 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#22d3ee] flex items-center gap-1.5 font-mono">💰 AGENT 6: Finance AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ATLAS-FINANCE | บทบาท: ฝ่ายการเงิน & ERP</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            มอนิเตอร์และสรุปยอดคงเหลือของแต่ละพอร์ต คำนวณ P&L รายดีล ยอดสะสม ค่าธรรมเนียมโบรกเกอร์ และภาษีสะสมเพื่อส่ง Webhook บันทึกบัญชีแยกประเภท ERP กลางทันทีที่มีธุรกรรม
          </div>
        </div>

        {/* Agent 7 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#a855f7] flex items-center gap-1.5 font-mono">🔍 AGENT 7: Audit AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: VIGIL-AUDIT | บทบาท: ผู้สอบบัญชีความถูกต้อง</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            ตรวจสอบความสม่ำเสมอและความถูกต้องของธุรกรรม (Consistency Check) เทียบประวัติการส่งคำสั่งซื้อขายจริงใน DB กับระบบ ERP บัญชีแยกประเภท เพื่อคัดกรองข้อมูลผิดพลาด
          </div>
        </div>

        {/* Agent 8 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#818cf8] flex items-center gap-1.5 font-mono">🤖 AGENT 8: EA Bot</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: APEX-EA | บทบาท: ผู้ส่งคำสั่งเทรด</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            จัดการเชื่อมต่อ API นำแผนงานส่งออเดอร์ (Market Order) เพื่อเปิด/ปิดคำสั่งจริงที่ Broker (MT5 หรือ Binance API) เฝ้าติดตาม Trailing Stop, SL และ TP อย่างใกล้ชิด
          </div>
        </div>

        {/* Agent 9 */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
          <h3 className="text-sm font-bold text-[#c084fc] flex items-center gap-1.5 font-mono">📋 AGENT 9: Report AI</h3>
          <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: SCRIBE-REPORT | บทบาท: ผู้จัดทำรายงานสรุป</p>
          <div className="text-xs text-[#c8d8f0] leading-relaxed">
            สรุปผลลัพธ์การเทรด อัตราส่วนชนะ (Win Rate), อัตราผลตอบแทนต่อความเสี่ยง (Profit Factor), สถิติ Max Drawdown และรวบรวมตัวชี้วัดประสิทธิภาพ จัดทำรายงานภาพรวมพอร์ต
          </div>
        </div>

      </div>
    </div>
  );
};

export default AIAgentsTab;
