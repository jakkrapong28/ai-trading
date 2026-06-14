"use client";

import { useState } from "react";
import { useDashboard } from "@/context/DashboardContext";

export default function Topbar() {
  const { todayPnLSum, pnlPct, totalEquity, closedOrders, activeTradesCount, riskForm, taxSummary, signalActivity, symbol, dataSources, wsStatus } = useDashboard();
  const [notifOpen, setNotifOpen] = useState(false);
  const notifCount = signalActivity.length;

  // Feed health badge for the active symbol (live/stale/mock/offline).
  const feed = dataSources[symbol];
  const FEED_STYLE: Record<string, { dot: string; text: string; label: string }> = {
    live: { dot: "#10b981", text: "text-[#10b981]", label: "LIVE" },
    stale: { dot: "#fbbf24", text: "text-[#fbbf24]", label: "STALE" },
    mock: { dot: "#a855f7", text: "text-[#a855f7]", label: "MOCK" },
    offline: { dot: "#6b7280", text: "text-[#9ca3af]", label: "OFFLINE" },
  };
  const feedStyle = FEED_STYLE[feed?.status ?? "offline"] ?? FEED_STYLE.offline;
  const wsConnected = wsStatus === "connected";

  return (
    <header className="bg-[#070a0f] border-b border-[#26262b] flex items-center justify-between px-4 h-[52px] flex-shrink-0">
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
        {/* ERP summary — relocated here from the floating chart overlay */}
        {taxSummary && (
          <div className="hidden md:flex items-center gap-4 pr-3 mr-1 border-r border-[#1c1c20]">
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">ERP ภาษี</span>
              <span className="font-bold text-[#f87171] font-mono text-xs">
                -${taxSummary.estimatedIncomeTax.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Net พอร์ต</span>
              <span className="font-bold text-[#10b981] font-mono text-xs">
                ${taxSummary.netAfterTax.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        )}

        {/* Data-source / feed health badge for the active symbol */}
        <div
          className={`flex items-center gap-1.5 bg-black/30 border border-[#26262b] px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono ${feedStyle.text}`}
          title={feed?.source ? `${feed.source}${feed.age != null ? ` · ${feed.age}s ago` : ""}` : "no feed"}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: feedStyle.dot, boxShadow: `0 0 5px ${feedStyle.dot}` }}></span>
          {symbol} {feedStyle.label}
        </div>

        {/* WS connection — reflects real status (was hardcoded) */}
        <div className={`flex items-center gap-1.5 border px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono ${wsConnected ? "bg-[#0d2a14]/30 border-[#1a5a28]/40 text-[#10b981]" : "bg-[#2a0d0d]/30 border-[#5a1a1a]/40 text-[#f87171]"}`}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: wsConnected ? "#10b981" : "#f87171", boxShadow: `0 0 5px ${wsConnected ? "#10b981" : "#f87171"}` }}></span>
          {wsConnected ? "WS Connected" : "WS Offline"}
        </div>

        {/* Bell notification */}
        <button
          onClick={() => setNotifOpen((o) => !o)}
          className={`relative p-1 transition ${notifOpen ? "text-white" : "text-[#7a9bbf] hover:text-white"}`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          {notifCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-3.5 h-3.5 px-0.5 bg-red-500 rounded-full text-[8px] text-white font-extrabold flex items-center justify-center">
              {notifCount > 9 ? "9+" : notifCount}
            </span>
          )}
        </button>

        {/* Notification dropdown — fixed so the overflow-hidden layout can't clip it */}
        {notifOpen && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
            <div className="fixed right-3 top-[54px] z-50 w-[320px] max-h-[420px] overflow-y-auto bg-[#0a0e16] border border-[#26262b] rounded-xl shadow-2xl">
              <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#26262b] sticky top-0 bg-[#0a0e16]">
                <span className="text-[11px] font-bold text-white font-mono">การแจ้งเตือน · สัญญาณ</span>
                <span className="text-[9px] text-[#5c7a9c] font-mono">{notifCount} รายการ</span>
              </div>
              {notifCount === 0 ? (
                <div className="px-3.5 py-8 text-center text-[10.5px] text-[#5c7a9c] font-mono">
                  ยังไม่มีการแจ้งเตือน
                </div>
              ) : (
                <ul className="divide-y divide-[#26262b]/50">
                  {signalActivity.slice(0, 30).map((s) => (
                    <li key={s.id} className="px-3.5 py-2.5 hover:bg-white/5">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="flex items-center gap-1.5 font-mono text-[11px] font-bold">
                          <span className={s.action === "BUY" ? "text-[#10b981]" : s.action === "SELL" ? "text-[#f87171]" : "text-[#7a9bbf]"}>
                            {s.action}
                          </span>
                          <span className="text-white">{s.ticker}</span>
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[8.5px] font-bold font-mono ${
                            s.status === "APPROVED"
                              ? "bg-emerald-950 text-emerald-400"
                              : s.status === "REJECTED"
                                ? "bg-red-950 text-red-400"
                                : "bg-amber-950 text-amber-400"
                          }`}
                        >
                          {s.status}
                        </span>
                      </div>
                      {s.reason && <div className="text-[9.5px] text-[#5c7a9c] font-mono leading-snug">{s.reason}</div>}
                      <div className="text-[8.5px] text-[#3d5a7a] font-mono mt-0.5">{s.time}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}

        {/* Profile badge */}
        <div className="w-6 h-6 rounded-full bg-[#0d1520] border border-[#26262b] text-[11px] font-bold text-white flex items-center justify-center font-mono">
          C
        </div>
      </div>
    </header>
  );
}
