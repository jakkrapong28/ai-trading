"use client";

import { SYMBOLS_LIST } from "@/config/dashboard";
import { useDashboard } from "@/context/DashboardContext";

export default function AnalyticsPage() {
  const { symbol, newsFeed, handleSymbolChange } = useDashboard();
  return (
      <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6`}>
        <div className="border-b border-[#1e2d45] pb-4">
          <h2 className="text-xl font-bold text-white">📊 ศูนย์วิเคราะห์ตลาดแบบบูรณาการ (Analytics Desk)</h2>
          <p className="text-xs text-[#7a9bbf] mt-1">ฟีดราคาสดจากโบรกเกอร์ MT5 และ Binance CEX พร้อมสรุปข่าวจริงทั่วโลก</p>
        </div>

        {/* รายการตลาดตราสาร */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {SYMBOLS_LIST.map((s) => (
            <div 
              key={s.symbol}
              onClick={() => handleSymbolChange(s.symbol)}
              className={`p-3 rounded-lg border cursor-pointer transition flex flex-col justify-between ${
                symbol === s.symbol 
                  ? "bg-[#0d2a14] border-[#10b981] text-[#34d399]" 
                  : "bg-[#111520] border-[#1e2d45] hover:border-[#3d5a7a] text-slate-300"
              }`}
            >
              <div className="text-[10px] text-slate-400 font-bold">{s.category.toUpperCase()}</div>
              <div className="text-sm font-bold mt-1 font-mono">{s.symbol}</div>
              <div className="text-[10px] text-slate-500 mt-0.5 truncate">{s.name}</div>
            </div>
          ))}
        </div>

        {/* บอร์ดข่าวกรองเศรษฐกิจ (Real Macro News Terminal) */}
        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-3">
          <div className="text-xs text-[#fbbf24] font-bold uppercase tracking-wider">🚨 ข่าวเศรษฐกิจมหภาคและการเงินล่าสุด (Macro Financial Feed)</div>
          <div className="divide-y divide-slate-800">
            {newsFeed.map((item, idx) => (
              <div key={idx} className="py-2.5 flex items-start gap-3 text-xs">
                <span className="text-[#7a9bbf] font-mono font-bold bg-[#070a0f] px-1.5 py-0.5 rounded">{item.time}</span>
                <div className="flex-1 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">{item.source}</span>
                    <span className={`text-[8.5px] px-1 rounded font-bold ${item.impact === "HIGH" ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-yellow-500/10 text-yellow-400"}`}>
                      {item.impact} IMPACT
                    </span>
                  </div>
                  <p className="text-slate-300 leading-relaxed">{item.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
  );
}
