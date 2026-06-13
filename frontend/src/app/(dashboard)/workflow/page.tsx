"use client";

import { parseUTCDate } from "@/lib/datetime";
import { useDashboard } from "@/context/DashboardContext";

export default function WorkflowPage() {
  const { priceMap, mode, orders, filterDate, setFilterDate, signalActivity, setSignalActivity, handleCloseOrder } = useDashboard();
  return (
      <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6`}>
        <div className="border-b border-[#26262b] pb-4">
          <h2 className="text-xl font-bold text-white">📋 คู่มือระบบ & ประวัติธุรกรรมตามวันที่ (Workflow & Trade History)</h2>
          <p className="text-xs text-[#7a9bbf] mt-1">คู่มือการใช้งานระบบเทรดอัจฉริยะภาษาไทย และการเรียกดูประวัติการเทรดแยกตามวันเดือนปี</p>
        </div>

        {/* 1. คู่มือการใช้งานภาษาไทย */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
          <h3 className="text-sm font-bold text-emerald-400 flex items-center gap-1.5 font-mono">📖 คู่มือการใช้งานระบบ (System Operation Guide)</h3>
              
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs text-[#c8d8f0] leading-relaxed">
            <div className="bg-black/40 border border-white/5 p-4 rounded-lg space-y-3">
              <div className="text-emerald-400 font-bold font-mono">🔄 โหมดการทำงานของระบบ (Operation Modes)</div>
              <ul className="list-disc list-inside space-y-2 text-[#a3b3cc]">
                <li>
                  <span className="text-white font-bold">โหมดธรรมดา (Watch Mode):</span> 
                  ระบบจะไม่ออกออเดอร์เองโดยอัตโนมัติ เมื่อวิเคราะห์พบสัญญาณจะส่งมาแสดงที่หน้าต่างบอร์ดหรือ Telegram ผู้ใช้ต้องทำการกดปุ่ม <span className="text-[#10b981] font-bold">"อนุมัติ"</span> ด้วยตนเอง โดยจะซื้อทุกไม้ทันทีตามจำนวนที่กดโดยไม่จำกัดจำนวนไม้เปิดคู่ขนาน (รัวกดได้ทันที)
                </li>
                <li>
                  <span className="text-[#22d3ee] font-bold">โหมดอัตโนมัติ (Auto Mode):</span>
                  ระบบ AI และ Risk Engine จะตรวจสอบเกณฑ์ความปลอดภัยอย่างเข้มงวดและอนุมัติส่งคำสั่งซื้อขายจริง (Auto Execution) ไปยัง Broker ทันทีตามที่บอทประเมินว่าเหมาะสมและผ่านเกณฑ์จำกัดความเสี่ยง
                </li>
              </ul>
            </div>

            <div className="bg-black/40 border border-white/5 p-4 rounded-lg space-y-3">
              <div className="text-[#f87171] font-bold font-mono">🛡️ กฎความเสี่ยง 6 ประการ (Risk Engine Guardrails)</div>
              <ol className="list-decimal list-inside space-y-1 text-[#a3b3cc]">
                <li>มีสัญญาณซื้อขายจริง (<span className="text-white">ไม่ใช่ WAIT</span>)</li>
                <li>ความเสี่ยงต่อไม้ไม่เกิน <span className="text-white">2.0%</span> ของพอร์ต (2% Rule)</li>
                <li>จุดตัดขาดทุนขั้นต่ำ (Stop Loss) <span className="text-white">&ge; 10 pips</span></li>
                <li>ค่าสเปรดโบรกเกอร์ (Spread) <span className="text-white">ไม่กว้างเกินเกณฑ์สูงสุด (3.0)</span></li>
                <li>มูลค่าถือครองสินทรัพย์รวมทั้งพอร์ต <span className="text-white">ไม่เกิน 20%</span></li>
                <li>สถานะระบบความปลอดภัย <span className="text-white">Circuit Breaker</span> ปิดปกติ</li>
              </ol>
            </div>
          </div>

          <div className="bg-black/60 p-4 rounded border border-white/5 text-xs font-mono space-y-2.5 leading-relaxed text-[#c8d8f0]">
            <div className="text-slate-400 border-b border-white/5 pb-1 mb-1 font-bold">🚀 ลำดับขั้นตอนการทำงาน (Safe Execution Flow)</div>
            <div><span className="text-[#fbbf24] font-bold">[1] สั่งการ / ค้นหาสัญญาณ:</span> ระบบสแกนหาทิศทางราคา หรือรับคำสั่งวิเคราะห์ทางเทคนิค</div>
            <div><span className="text-[#fbbf24] font-bold">[2] CEO Agent ประมวลผล:</span> CEO จะสั่งให้ Chart AI (กราฟ), Risk AI (คำนวณความเสี่ยง/Lot), News AI (ดึงข่าวด่วน) ประมวลผลร่วมกัน</div>
            <div><span className="text-[#fbbf24] font-bold">[3] ตัดสินใจ & ขออนุมัติ:</span> ในโหมด Watch บอทส่งสัญญาณมาขอความเห็นชอบบนเว็บ/Telegram หรืออนุมัติยิงตลาดทันทีหากเปิดโหมด Auto</div>
            <div><span className="text-[#fbbf24] font-bold">[4] บันทึกสมุดบัญชี ERP:</span> หลังจากปิดดีลสำเร็จ Finance AI จะยิงข้อมูล P&L และยอดภาษีเข้าระบบ ERP บัญชีแยกประเภททันที</div>
          </div>
        </div>

        {/* 2. ประวัติการเทรดกรองตามวันที่ */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/5 pb-3">
            <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">📅 ประวัติการเทรดแยกตามวันเดือนปี (Historical Trades Calendar)</h3>
                
            {/* Date Picker */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#7a9bbf]">เลือกวันที่:</span>
              <input 
                type="date" 
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                className="bg-black/60 border border-white/10 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-emerald-400 font-mono transition"
              />
              {filterDate && (
                <button 
                  onClick={() => setFilterDate("")}
                  className="text-[10px] text-red-400 hover:text-red-300 px-2 py-1 bg-red-950/20 border border-red-800/30 rounded font-bold"
                >
                  ล้างตัวกรอง
                </button>
              )}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs font-mono">
              <thead>
                <tr className="border-b border-white/10 text-[#7a9bbf]">
                  <th className="py-2.5 px-3">วันเวลา (Opened At)</th>
                  <th className="py-2.5 px-3">สินทรัพย์</th>
                  <th className="py-2.5 px-3">ประเภท</th>
                  <th className="py-2.5 px-3">ขนาด (Lot)</th>
                  <th className="py-2.5 px-3">ราคาเข้า</th>
                  <th className="py-2.5 px-3">SL</th>
                  <th className="py-2.5 px-3">TP</th>
                  <th className="py-2.5 px-3">ราคาปัจจุบัน</th>
                  <th className="py-2.5 px-3">ราคาออก</th>
                  <th className="py-2.5 px-3">กำไร/ขาดทุน (USD)</th>
                  <th className="py-2.5 px-3">สถานะ</th>
                  <th className="py-2.5 px-3 text-center">การจัดการ</th>
                </tr>
              </thead>
              <tbody>
                {(() => {
                  const filtered = filterDate 
                    ? orders.filter(o => o.opened_at && o.opened_at.startsWith(filterDate))
                    : orders;
                      
                  if (filtered.length === 0) {
                    return (
                      <tr>
                        <td colSpan={12} className="py-8 text-center text-slate-500">
                          ไม่พบประวัติการเทรดในวันที่เลือก
                        </td>
                      </tr>
                    );
                  }

                  return filtered.map((ord, idx) => (
                    <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                      <td className="py-2.5 px-3 text-[#a3b3cc]">
                        {ord.opened_at ? parseUTCDate(ord.opened_at).toLocaleString('th-TH') : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-white font-bold">{ord.symbol}</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          ord.action === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                        }`}>
                          {ord.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">{ord.volume}</td>
                      <td className="py-2.5 px-3 text-slate-300">${ord.entry_price.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-red-400">
                        {ord.sl_price > 0 ? `$${ord.sl_price.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-emerald-400">
                        {ord.tp_price > 0 ? `$${ord.tp_price.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-white font-bold">
                        {priceMap[ord.symbol] ? `$${priceMap[ord.symbol].toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {ord.exit_price > 0 ? `$${ord.exit_price.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2.5 px-3">
                        {ord.status === "CLOSED" ? (
                          <span className={`font-bold ${ord.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {ord.pnl >= 0 ? `+$${ord.pnl.toFixed(2)}` : `-$${Math.abs(ord.pnl).toFixed(2)}`}
                          </span>
                        ) : (
                          <span className="text-slate-500 font-bold">Running</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          ord.status === "CLOSED" 
                            ? "bg-slate-800 text-slate-400" 
                            : "bg-emerald-950 text-emerald-400 animate-pulse"
                        }`}>
                          {ord.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {ord.status !== "CLOSED" && ord.status !== "CANCELLED" ? (
                          <button
                            onClick={() => handleCloseOrder(ord.id)}
                            className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30 text-[10px] font-bold transition-all"
                          >
                            ปิดออเดอร์ ❌
                          </button>
                        ) : (
                          <span className="text-[10px] text-slate-600">-</span>
                        )}
                      </td>
                    </tr>
                  ));
                })()}
              </tbody>
            </table>
          </div>
        </div>

        {/* 3. Signal Activity Log */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">
              📊 Auto Mode Signal Activity Log
              {mode === "auto" && <span className="w-2 h-2 rounded-full bg-[#22d3ee] animate-pulse shadow-[0_0_6px_#22d3ee] ml-1" />}
            </h3>
            <button
              onClick={() => setSignalActivity([])}
              className="text-[9px] px-2 py-0.5 bg-red-950/30 hover:bg-red-900 border border-red-800/30 text-red-400 rounded transition"
            >
              ล้าง log
            </button>
          </div>
          <div className="max-h-[320px] overflow-y-auto space-y-1">
            {signalActivity.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs font-mono">
                {mode === "auto"
                  ? "⏳ กำลังรอสัญญาณจาก AI Decision Engine..."
                  : "💤 ระบบอยู่ใน Watch Mode — กด Auto Scan เพื่อเปิด Auto Mode"
                }
              </div>
            ) : (
              signalActivity.map((act) => (
                <div
                  key={act.id}
                  className={`flex items-start gap-2 px-3 py-2 rounded text-[11px] font-mono border-l-2 ${
                    act.status === "APPROVED"
                      ? "border-emerald-500 bg-emerald-950/10"
                      : act.status === "REJECTED"
                      ? "border-red-500 bg-red-950/10"
                      : "border-yellow-500 bg-yellow-950/10"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] text-[#7a9bbf]">
                        {new Date(act.time).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </span>
                      <span className="font-bold text-white">{act.ticker}</span>
                      <span className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                        act.action === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                      }`}>
                        {act.action}
                      </span>
                      {act.status === "APPROVED" && (
                        <span className="text-[9px] text-emerald-400 font-bold">✅ APPROVED</span>
                      )}
                      {act.status === "REJECTED" && (
                        <span className="text-[9px] text-red-400 font-bold">❌ REJECTED</span>
                      )}
                      {act.status === "VOTING" && (
                        <span className="text-[9px] text-yellow-400 font-bold">⏳ VOTING</span>
                      )}
                    </div>
                    {act.status === "APPROVED" && (act.sl || act.tp) && (
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        SL: <span className="text-red-400">${act.sl?.toFixed(2)}</span> &nbsp; TP: <span className="text-emerald-400">${act.tp?.toFixed(2)}</span>
                      </div>
                    )}
                    {act.status === "REJECTED" && act.reason && (
                      <div className="text-[10px] text-red-400/70 mt-0.5 truncate">
                        {act.reason}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
  );
}
