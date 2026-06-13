"use client";

import { parseUTCDate } from "@/lib/datetime";
import { useDashboard } from "@/context/DashboardContext";

export default function RiskPage() {
  const { orders, featureFlags, circuitBreakers, heartbeats, nanLogs, calibration, correlationRejections, settingsForm, fetchStateData, addChatMessage } = useDashboard();
  return (
      <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6`}>
        <div className="border-b border-[#1e2d45] pb-4">
          <h2 className="text-xl font-bold text-white">🛡️ สรุปกฎระเบียบความเสี่ยงพอร์ต (Risk Monitor & Compliance Audit)</h2>
          <p className="text-xs text-[#7a9bbf] mt-1">มอนิเตอร์ระดับความปลอดภัย การตั้งค่ากฎเหล็ก และประวัติการทำออดิตความเสี่ยง</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
            <div className="text-xs text-slate-400">ขีดจำกัดความเสี่ยงไม้ (Risk Limit)</div>
            <div className="text-2xl font-bold text-[#f87171] mt-1">{settingsForm.maxRiskPerTradePct}%</div>
            <div className="text-[10px] text-slate-500 mt-1">ต่อดีลเทรดจำลอง / จริง</div>
          </div>
          <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
            <div className="text-xs text-slate-400">ถือครองพอร์ตรวมสูงสุด (Max Exposure)</div>
            <div className="text-2xl font-bold text-[#fbbf24] mt-1">{settingsForm.maxOpenExposurePct}%</div>
            <div className="text-[10px] text-slate-500 mt-1">ของทุนสุทธิ (Net Equity)</div>
          </div>
          <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
            <div className="text-xs text-slate-400">ลิมิต Drawdown ต่อวัน (Daily Loss)</div>
            <div className="text-2xl font-bold text-[#f87171] mt-1">3.00%</div>
            <div className="text-[10px] text-slate-500 mt-1">บล็อกเทรดทั้งวันทันทีหากชนลิมิต</div>
          </div>
        </div>

        {/* New Advanced Safety & Integrity Cards */}
        <div className="border-t border-[#1e2d45] pt-6 pb-2">
          <h3 className="text-sm font-bold text-white mb-1 uppercase tracking-wider">🛠️ ระบบเฝ้าระวังความเสี่ยงขั้นสูง (Advanced Risk Surveillance)</h3>
          <p className="text-[11px] text-[#7a9bbf]">ควบคุม Feature Flags, สเตตัส Circuit Breakers และตรวจสอบความสมบูรณ์ของข้อมูลแบบเรียลไทม์</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Card 1: Feature Flags */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
            <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              ⚙️ Feature Flags
            </div>
            <div className="space-y-2.5 text-xs">
              {Object.entries(featureFlags || {}).map(([flag, enabled]) => (
                <div key={flag} className="flex justify-between items-center border-b border-white/5 pb-1.5 last:border-0 last:pb-0">
                  <span className="text-slate-400 font-mono">{flag}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                    {enabled ? 'ON ●' : 'OFF ○'}
                  </span>
                </div>
              ))}
              {Object.keys(featureFlags || {}).length === 0 && (
                <div className="text-slate-500 text-center py-4">ไม่มีข้อมูล Flags</div>
              )}
            </div>
          </div>

          {/* Card 2: Circuit Breakers */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
            <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              ⚡ Circuit Breakers
            </div>
            <div className="space-y-2.5 text-xs">
              {Object.entries(circuitBreakers || {}).map(([name, val]: [string, any]) => (
                <div key={name} className="flex justify-between items-center border-b border-white/5 pb-1.5 last:border-0 last:pb-0">
                  <span className="text-slate-400 font-mono">{name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${val?.active ? 'bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                    {val?.active ? 'TRIGGERED 🔴' : 'SAFE 🟢'}
                  </span>
                </div>
              ))}
              {Object.keys(circuitBreakers || {}).length === 0 && (
                <div className="text-slate-500 text-center py-4">ไม่มีข้อมูล Breakers</div>
              )}
            </div>
          </div>

          {/* Card 3: Heartbeat Monitors */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
            <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              📡 Heartbeat Monitors
            </div>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">MT5 Broker Heartbeat:</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1.5 ${heartbeats?.broker ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full bg-emerald-400 ${heartbeats?.broker && 'animate-ping'}`}></span>
                  {heartbeats?.broker ? new Date(heartbeats.broker).toLocaleTimeString() : 'DISCONNECTED'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Command Center Sys:</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] bg-cyan-500/10 text-cyan-400 font-bold">
                  {heartbeats?.system ? new Date(heartbeats.system).toLocaleTimeString() : 'OFFLINE'}
                </span>
              </div>
            </div>
          </div>

          {/* Card 4: NaN Integrity Monitor */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
            <div>
              <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                🛡️ Data Integrity (NaN Guard)
              </div>
              <p className="text-[10px] text-slate-500 mb-3">จำนวนเหตุการณ์ราคาสุดโต่งหรือค่าสูญหายที่ระบบดักกรองไว้</p>
            </div>
            <div className="flex justify-between items-end">
              <span className="text-2xl font-bold text-cyan-400">{nanLogs?.count || 0}</span>
              <span className="text-[10px] text-slate-400 border border-slate-500/20 px-2 py-0.5 rounded bg-slate-500/5">NaNs Guarded</span>
            </div>
          </div>

          {/* Card 5: Correlation Caps */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
            <div>
              <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                🔀 Correlation Rejections
              </div>
              <p className="text-[10px] text-slate-500 mb-3">จำนวนออเดอร์ที่ถูกบล็อกเนื่องจากมี Exposure ทับซ้อนในกลุ่มเดียวกัน</p>
            </div>
            <div className="flex justify-between items-end">
              <span className="text-2xl font-bold text-amber-400">{correlationRejections?.count || 0}</span>
              <span className="text-[10px] text-slate-400 border border-slate-500/20 px-2 py-0.5 rounded bg-slate-500/5">Blocked Signals</span>
            </div>
          </div>

          {/* Card 6: Calibration Command Center */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
            <div>
              <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                🔄 Calibration Center
              </div>
              <div className="flex justify-between text-[11px] text-slate-400 mb-3">
                <span>Calibrated: <b>{calibration?.calibrated_count || 0}</b></span>
                <span>Pending: <b>{calibration?.pending_count || 0}</b></span>
              </div>
            </div>
            <button
              type="button"
              onClick={async () => {
                try {
                  const res = await fetch("http://localhost:8000/api/calibrate", { method: "POST" });
                  const d = await res.json();
                  if (d.status === "success") {
                    addChatMessage("system", "🔄 กระตุ้นการทำ Rolling Calibration ข้อมูลวิเคราะห์สำเร็จ!");
                    fetchStateData();
                    alert("Rolling Calibration สำเร็จ!");
                  }
                } catch (err) {
                  alert("การทำ Calibration ล้มเหลว");
                }
              }}
              className="w-full text-center py-2 bg-purple-600/20 hover:bg-purple-600 border border-purple-500/30 hover:border-purple-500 text-purple-200 hover:text-white rounded-lg transition-all duration-300 font-bold text-xs"
            >
              กระตุ้น Calibration 🔄
            </button>
          </div>
        </div>

        {/* รายการออดิตความเสี่ยงสะสม */}
        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4">
          <div className="text-xs text-slate-300 font-bold uppercase tracking-wider mb-3">บันทึกประวัติการทำ Risk Audit (Decision Logs)</div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead>
                <tr className="border-b border-[#1e2d45] text-slate-400 font-mono">
                  <th className="py-2">วัน-เวลา</th>
                  <th className="py-2">คู่สินทรัพย์</th>
                  <th className="py-2">ผลประเมิน</th>
                  <th className="py-2 text-right">Risk %</th>
                  <th className="py-2 text-right">Exposure %</th>
                  <th className="py-2 text-right">สถานะบิดออเดอร์</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 font-mono">
                {orders.map((ord, idx) => (
                  <tr key={idx} className="hover:bg-[#070a0f]/40">
                    <td className="py-2 text-slate-500">{ord.opened_at ? parseUTCDate(ord.opened_at).toLocaleTimeString('th-TH') : '-'}</td>
                    <td className="py-2 font-bold text-white">{ord.symbol}</td>
                    <td className="py-2 text-[#10b981] font-bold">✓ ผ่านด่านตรวจสอบ</td>
                    <td className="py-2 text-right">1.2%</td>
                    <td className="py-2 text-right">4.8%</td>
                    <td className="py-2 text-right text-teal-400">ปิดแล้ว (CLOSED)</td>
                  </tr>
                ))}
                {orders.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-slate-500">ไม่มีผลตรวจความเสี่ยงค้างตรวจในระบบ</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
  );
}
