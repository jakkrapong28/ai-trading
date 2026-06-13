"use client";

import { useDashboard } from "@/context/DashboardContext";

export default function Topbar() {
  const { todayPnLSum, pnlPct, totalEquity, closedOrders, activeTradesCount, riskForm } = useDashboard();

  return (
    <header className="bg-[#070a0f] border-b border-[#1e2d45] flex items-center justify-between px-4 h-[52px] flex-shrink-0">
      {/* Left: Portfolio statistics */}
      <div className="flex items-center gap-6 text-xs">
        {/* PnL Today */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">PnL Today</span>
          <div className="flex items-center gap-1.5 font-bold font-mono">
            <span className={todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}>
              {todayPnLSum >= 0 ? "+" : ""}${todayPnLSum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className={`text-[10px] ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
              {todayPnLSum >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
            </span>
          </div>
        </div>

        {/* Equity */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Equity</span>
          <div className="font-bold text-white font-mono">
            ${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        {/* Win Rate */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Win Rate</span>
          <div className="font-bold text-white font-mono">
            {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(1) : "0.0"}%
          </div>
        </div>

        {/* Open Positions */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Open Positions</span>
          <div className="font-bold text-white font-mono">{activeTradesCount}</div>
        </div>

        {/* Risk Level */}
        <div className="flex flex-col gap-0.5">
          <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Risk Level</span>
          <div className="font-bold text-[#10b981] font-mono">
            {riskForm.riskPct > 3 ? "HIGH" : riskForm.riskPct > 1.5 ? "MEDIUM" : "LOW"}
          </div>
        </div>
      </div>

      {/* Right: Status and profile */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 bg-[#0d2a14]/30 border border-[#1a5a28]/40 px-2.5 py-0.5 rounded-full text-[10px] text-[#10b981] font-bold font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981]"></span>
          WS Connected
        </div>

        {/* Bell notification */}
        <button className="relative p-1 text-[#7a9bbf] hover:text-white transition">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-red-500 rounded-full text-[8px] text-white font-extrabold flex items-center justify-center">
            3
          </span>
        </button>

        {/* Profile badge */}
        <div className="w-6 h-6 rounded-full bg-[#0d1520] border border-[#1e2d45] text-[11px] font-bold text-white flex items-center justify-center font-mono">
          C
        </div>
      </div>
    </header>
  );
}
