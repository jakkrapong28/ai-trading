"use client";

import { useState } from "react";
import { SYMBOLS_LIST } from "@/config/dashboard";
import TradingViewWidget from "@/components/TradingViewWidget";
import AIChartWidget from "@/components/AIChartWidget";
import AIAnalysisPanel from "@/components/AIAnalysisPanel";
import { useDashboard } from "@/context/DashboardContext";

export default function TradingPage() {
  const { symbol, latestPrice, priceMap, indicators, signal, risk, mode, balances, orders, activeTab, setActiveTab, signalActivity, ledger, riskForm, setRiskForm, newsFeed, closedOrders, todayPnLSum, pnlPct, handleCloseOrder, handleSymbolChange, handleRiskTest, handleToggleMode, handleApprove, handleReject } = useDashboard();
  const [chartMode, setChartMode] = useState<"ai" | "tv">("ai");
  const [tf, setTf] = useState<"M15" | "H1" | "H4" | "D1">("H1");
  return (
      <div className={`flex-1 flex flex-col p-4 gap-4 bg-[#000000] overflow-y-auto`}>
            
        {/* ── ROW 1: CANDLESTICK CHART ── */}
        <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col gap-2.5 h-[360px] min-h-[360px] shadow-lg">
          {/* Chart Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="font-bold text-white text-[14px] font-mono">{symbol}</span>
                  <svg className="w-3.5 h-3.5 text-[#fbbf24] cursor-pointer" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.24.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.176 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.768-.57-.37-1.81.588-1.81h4.907a1 1 0 00.95-.69l1.519-4.674z" /></svg>
                </div>
                <span className="text-[10px] text-[#5c7a9c] font-medium leading-none mt-0.5 font-mono">
                  {SYMBOLS_LIST.find(s => s.symbol === symbol)?.name || "Binance Asset"}
                </span>
              </div>
              <div className="h-6 w-[1px] bg-[#26262b]" />
              <div className="flex flex-col">
                <span className="text-[14px] font-black text-white font-mono leading-none">
                  {latestPrice ? latestPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : "-"}
                </span>
                <span className="text-[9.5px] font-mono text-[#f87171] leading-none mt-1">
                  -327.85 (-0.51%)
                </span>
              </div>
            </div>

            {/* Right specs */}
            <div className="flex items-center gap-6 text-[10px] font-mono text-[#7a9bbf]">
              <div>
                <span className="text-[#5c7a9c]">High</span> <span className="font-bold text-white">{(latestPrice ? latestPrice * 1.01 : 64872.10).toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
              </div>
              <div>
                <span className="text-[#5c7a9c]">Low</span> <span className="font-bold text-white">{(latestPrice ? latestPrice * 0.99 : 62980.45).toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
              </div>
              <div>
                <span className="text-[#5c7a9c]">Volume</span> <span className="font-bold text-white">12.43K</span>
              </div>
            </div>
          </div>

          {/* Chart Toolbar */}
          <div className="flex items-center justify-between border-t border-b border-[#26262b]/40 py-1 text-[10.5px]">
            <div className="flex items-center gap-1 font-semibold text-[#7a9bbf] font-mono">
              {([
                { label: "15m", tf: "M15" },
                { label: "1h", tf: "H1" },
                { label: "4h", tf: "H4" },
                { label: "D", tf: "D1" },
              ] as const).map(({ label, tf: t }) => (
                <span
                  key={label}
                  onClick={() => setTf(t)}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    tf === t ? "bg-[#131d27] text-white" : "hover:bg-white/5"
                  }`}
                >
                  {label}
                </span>
              ))}
              <div className="w-[1px] h-3 bg-[#26262b] mx-1" />
              <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer flex items-center gap-1 text-[#22d3ee]">
                📊 Indicators
              </span>
              <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer flex items-center gap-1">
                🔔 Alert
              </span>
            </div>

            {/* Chart source toggle: our AI chart vs TradingView */}
            <div className="flex items-center gap-1 bg-[#0b0f16] border border-[#26262b] rounded-md p-0.5">
              <button
                onClick={() => setChartMode("ai")}
                className={`px-2.5 py-0.5 rounded text-[10px] font-bold font-mono transition ${
                  chartMode === "ai" ? "bg-[#10b981]/20 text-[#10b981]" : "text-[#5c7a9c] hover:text-white"
                }`}
              >
                AI Chart
              </button>
              <button
                onClick={() => setChartMode("tv")}
                className={`px-2.5 py-0.5 rounded text-[10px] font-bold font-mono transition ${
                  chartMode === "tv" ? "bg-[#22d3ee]/15 text-[#22d3ee]" : "text-[#5c7a9c] hover:text-white"
                }`}
              >
                TradingView
              </button>
            </div>
          </div>

          {/* Chart Container — AI chart (our data + AI lines) or TradingView embed */}
          <div className="flex-1 rounded-lg overflow-hidden border border-[#26262b]/50 relative">
            {chartMode === "ai" ? <AIChartWidget symbol={symbol} tf={tf} /> : <TradingViewWidget symbol={symbol} />}
          </div>
        </div>

        {/* ── ROW 2: WORKFORCE AGENTS ── */}
        <div className="grid grid-cols-6 gap-3">
          {/* Risk AI */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#ef4444]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">🛡️</span>
                <span className="font-bold text-white text-[11px] font-mono">Risk AI</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">Risk Score</span>
                <span className="text-[#10b981] font-bold">32/100</span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">Status</span>
                <span className="text-[#10b981] font-bold">Normal</span>
              </div>
            </div>
          </div>

          {/* Strategy AI */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#fbbf24]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">🎯</span>
                <span className="font-bold text-white text-[11px] font-mono">Strategy AI</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">Signals Today</span>
                <span className="text-white font-bold">{signalActivity.length}</span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">Run Rate</span>
                <span className="text-white font-bold">66.7%</span>
              </div>
            </div>
          </div>

          {/* EA Bot */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#818cf8]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">🤖</span>
                <span className="font-bold text-white text-[11px] font-mono">EA Bot</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Active
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">Trades Today</span>
                <span className="text-white font-bold">{(orders || []).filter(o => o.status === "CLOSED").length}</span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">Win Rate</span>
                <span className="text-white font-bold">
                  {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(0) : "0"}%
                </span>
              </div>
            </div>
          </div>

          {/* Finance AI */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#06b6d4]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">💰</span>
                <span className="font-bold text-white text-[11px] font-mono">Finance AI</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">PnL Today</span>
                <span className={`font-bold ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                  ${todayPnLSum.toFixed(0)}
                </span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">ROI</span>
                <span className="text-white font-bold">{pnlPct.toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {/* Audit AI */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#a855f7]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">🔍</span>
                <span className="font-bold text-white text-[11px] font-mono">Audit AI</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">Checks Today</span>
                <span className="text-white font-bold">{ledger.length}</span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">Issues</span>
                <span className="text-[#10b981] font-bold">0</span>
              </div>
            </div>
          </div>

          {/* CEO Agent */}
          <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#10b981]/30 transition">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-[14px]">🕴️</span>
                <span className="font-bold text-white text-[11px] font-mono">CEO Agent</span>
              </div>
              <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Active
              </span>
            </div>
            <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
              <div>
                <span className="text-[#5c7a9c] block text-[8px]">Reports</span>
                <span className="text-white font-bold">3</span>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] text-right">Alerts</span>
                <span className="text-white font-bold">1</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── ROW 3: POSITIONS TABS & RISK GATE ── */}
        <div className="flex gap-4">
          {/* Tabbed Positions Table (Left) */}
          <div className="flex-1 bg-[#070a0f] border border-[#26262b] rounded-xl p-3.5 shadow-lg flex flex-col h-[280px] min-h-[280px]">
            {/* Tab selector */}
            <div className="flex gap-5 border-b border-[#26262b]/40 pb-2 text-[11px] font-bold text-[#7a9bbf] font-mono cursor-pointer">
              {["POSITIONS", "ORDERS", "PORTFOLIO", "SIGNALS", "ALERTS", "AI ANALYSIS"].map((tab) => {
                const isTabActive = tab === activeTab;
                return (
                  <span 
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`${isTabActive ? "text-white border-b-2 border-[#fbbf24] pb-2" : "hover:text-white"}`}
                  >
                    {tab}
                  </span>
                );
              })}
            </div>

            {/* Table contents */}
            <div className="flex-1 overflow-y-auto mt-2 pr-1">
              {activeTab === "POSITIONS" && (
                <table className="w-full text-left text-[10.5px] font-mono">
                  <thead>
                    <tr className="text-[#5c7a9c] border-b border-[#26262b]/30">
                      <th className="py-2">Symbol</th>
                      <th className="py-2">Side</th>
                      <th className="py-2">Size</th>
                      <th className="py-2">Entry Price</th>
                      <th className="py-2">Mark Price</th>
                      <th className="py-2">PnL (USDT)</th>
                      <th className="py-2">PnL %</th>
                      <th className="py-2">Risk</th>
                      <th className="py-2 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#26262b]/20 text-white">
                    {(() => {
                      const openOrders = (orders || []).filter(o => o.status === "OPEN" || o.status === "PENDING");
                      if (openOrders.length === 0) {
                        return (
                          <tr>
                            <td colSpan={9} className="py-8 text-center text-slate-500 text-[10px]">
                              ไม่พบข้อมูลออเดอร์ที่กำลังทำงาน (Active Positions)
                            </td>
                          </tr>
                        );
                      }
                      return openOrders.map((ord) => {
                        const markPrice = priceMap[ord.symbol] || latestPrice || ord.entry_price;
                        const pnlValue = (markPrice - ord.entry_price) * ord.volume * (ord.action === "BUY" ? 1 : -1);
                        const pnlPctValue = ord.entry_price > 0 ? (pnlValue / (ord.entry_price * ord.volume)) * 100 : 0;
                        return (
                          <tr key={ord.id} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(ord.symbol)}>
                            <td className="py-2 font-bold">{ord.symbol}</td>
                            <td className="py-2">
                              <span className={ord.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{ord.action}</span>
                            </td>
                            <td className="py-2">{ord.volume}</td>
                            <td className="py-2">${ord.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                            <td className="py-2">${markPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                            <td className={`py-2 font-bold ${pnlValue >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                              {pnlValue >= 0 ? "+" : ""}${pnlValue.toFixed(2)}
                            </td>
                            <td className={`py-2 font-bold ${pnlValue >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                              {pnlValue >= 0 ? "+" : ""}{pnlPctValue.toFixed(2)}%
                            </td>
                            <td className="py-2 text-[#10b981]">Low</td>
                            <td className="py-2 text-center">
                              <button 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCloseOrder(ord.id);
                                }}
                                className="text-[9px] px-2 py-0.5 rounded bg-[#ef4444]/10 border border-[#ef4444]/30 text-[#f87171] hover:bg-[#ef4444]/30"
                              >
                                Close
                              </button>
                            </td>
                          </tr>
                        );
                      });
                    })()}
                  </tbody>
                </table>
              )}

              {activeTab === "ORDERS" && (
                <table className="w-full text-left text-[10.5px] font-mono">
                  <thead>
                    <tr className="text-[#5c7a9c] border-b border-[#26262b]/30">
                      <th className="py-2">ID</th>
                      <th className="py-2">Symbol</th>
                      <th className="py-2">Side</th>
                      <th className="py-2">Size</th>
                      <th className="py-2">Entry</th>
                      <th className="py-2">Exit</th>
                      <th className="py-2">PnL</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#26262b]/20 text-white">
                    {orders.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-8 text-center text-slate-500 text-[10px]">
                          ไม่พบประวัติออเดอร์
                        </td>
                      </tr>
                    ) : (
                      orders.map((ord) => (
                        <tr key={ord.id} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(ord.symbol)}>
                          <td className="py-2 text-[#5c7a9c] max-w-[60px] truncate" title={ord.id}>
                            {ord.id.slice(0, 8)}...
                          </td>
                          <td className="py-2 font-bold">{ord.symbol}</td>
                          <td className="py-2">
                            <span className={ord.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{ord.action}</span>
                          </td>
                          <td className="py-2">{ord.volume}</td>
                          <td className="py-2">${ord.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                          <td className="py-2">
                            {ord.exit_price ? `$${ord.exit_price.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "-"}
                          </td>
                          <td className={`py-2 font-bold ${ord.pnl >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                            {ord.pnl >= 0 ? "+" : ""}${ord.pnl.toFixed(2)}
                          </td>
                          <td className="py-2">
                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                              ord.status === "CLOSED" ? "bg-[#26262b] text-[#7a9bbf]" : "bg-emerald-950 text-emerald-400"
                            }`}>
                              {ord.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {activeTab === "PORTFOLIO" && (
                <table className="w-full text-left text-[10.5px] font-mono">
                  <thead>
                    <tr className="text-[#5c7a9c] border-b border-[#26262b]/30">
                      <th className="py-2">Source</th>
                      <th className="py-2">Equity</th>
                      <th className="py-2">Balance</th>
                      <th className="py-2">Free Margin</th>
                      <th className="py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#26262b]/20 text-white">
                    {balances.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-500 text-[10px]">
                          ไม่พบข้อมูลพอร์ตโฟลิโอ
                        </td>
                      </tr>
                    ) : (
                      balances.map((bal, idx) => (
                        <tr key={idx} className="hover:bg-white/5">
                          <td className="py-2 font-bold text-[#22d3ee]">{bal.source}</td>
                          <td className="py-2 font-mono">${bal.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                          <td className="py-2 font-mono">${bal.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                          <td className="py-2 font-mono">${bal.free_margin.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                          <td className="py-2">
                            <span className="text-[#10b981] font-bold">● Connected</span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {activeTab === "SIGNALS" && (
                <table className="w-full text-left text-[10.5px] font-mono">
                  <thead>
                    <tr className="text-[#5c7a9c] border-b border-[#26262b]/30">
                      <th className="py-2">Symbol</th>
                      <th className="py-2">Action</th>
                      <th className="py-2">Status</th>
                      <th className="py-2">Reason</th>
                      <th className="py-2 text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#26262b]/20 text-white">
                    {signalActivity.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-500 text-[10px]">
                          ไม่พบประวัติสัญญาณการเทรดวันนี้
                        </td>
                      </tr>
                    ) : (
                      signalActivity.map((sig, idx) => (
                        <tr key={sig.id || idx} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(sig.ticker)}>
                          <td className="py-2 font-bold">{sig.ticker}</td>
                          <td className="py-2">
                            <span className={sig.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{sig.action}</span>
                          </td>
                          <td className="py-2">
                            <span className={`px-1.5 py-0.2 rounded text-[8.5px] font-bold ${
                              sig.status === "APPROVED" ? "bg-emerald-950 text-emerald-400" :
                              sig.status === "REJECTED" ? "bg-red-950 text-red-400" : "bg-amber-950 text-amber-400"
                            }`}>
                              {sig.status}
                            </span>
                          </td>
                          <td className="py-2 text-slate-400 max-w-[150px] truncate" title={sig.reason || ""}>
                            {sig.reason || "-"}
                          </td>
                          <td className="py-2 text-[#5c7a9c] text-[9.5px] text-right">
                            {new Date(sig.time).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {activeTab === "ALERTS" && (
                <table className="w-full text-left text-[10.5px] font-mono">
                  <thead>
                    <tr className="text-[#5c7a9c] border-b border-[#26262b]/30">
                      <th className="py-2">Time</th>
                      <th className="py-2">Source</th>
                      <th className="py-2">Summary</th>
                      <th className="py-2">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#26262b]/20 text-white">
                    {newsFeed.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-slate-500 text-[10px]">
                          ไม่พบข้อมูลข่าวสารหรือการแจ้งเตือน
                        </td>
                      </tr>
                    ) : (
                      newsFeed.map((news, idx) => (
                        <tr key={idx} className="hover:bg-white/5">
                          <td className="py-2 text-[#5c7a9c] text-[9.5px]">{news.time}</td>
                          <td className="py-2 font-bold text-[#fbbf24]">{news.source}</td>
                          <td className="py-2 max-w-[200px] truncate" title={news.text}>{news.text}</td>
                          <td className="py-2">
                            <span className={`px-1.5 py-0.5 rounded text-[8.5px] font-bold ${
                              news.impact === "HIGH" ? "bg-red-950 text-red-400" : "bg-amber-950 text-amber-400"
                            }`}>
                              {news.impact}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {activeTab === "AI ANALYSIS" && (
                <AIAnalysisPanel indicators={indicators} signal={signal} />
              )}
            </div>
          </div>

          {/* RISK GATE (Right) */}
          <div className="w-[360px] bg-[#070a0f] border border-[#26262b] rounded-xl p-3.5 shadow-lg flex flex-col h-[280px] min-h-[280px] justify-between">
                
            {/* แถวบน: Title + Auto Scan */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[11px] text-[#fbbf24] font-extrabold uppercase tracking-wider font-mono">
                <svg className="w-4 h-4 text-[#fbbf24]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                RISK GATE
              </div>
                  
              <div className="flex items-center gap-2">
                <button
                  onClick={handleToggleMode}
                  className={`px-2 py-1 text-[9px] font-bold rounded-full border transition flex items-center gap-1 ${
                    mode === "auto"
                      ? "bg-[#0d2a3a]/80 text-[#22d3ee] border-[#1a5a7a] shadow-[0_0_8px_#22d3ee44]"
                      : "bg-[#111827] text-[#7a9bbf] border-[#26262b] hover:bg-[#26262b] hover:text-[#c8d8f0]"
                  }`}
                >
                  <span className={`w-1 h-1 rounded-full ${mode === "auto" ? "bg-[#22d3ee] shadow-[0_0_4px_#22d3ee]" : "bg-[#64748b]"}`} />
                  Auto Scan
                </button>
              </div>
            </div>

            {/* Indicators Row */}
            <div className="flex gap-2 text-center text-[10px] bg-[#000000]/40 border border-[#26262b] px-2.5 py-1.5 rounded-lg font-mono items-center justify-around">
              <div>
                <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">ราคา</span>
                <div className="font-bold text-white mt-0.5 text-[9.5px]">{latestPrice ? latestPrice.toLocaleString() : "-"}</div>
              </div>
              <div className="w-[1px] h-3.5 bg-[#26262b]" />
              <div>
                <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">EMA</span>
                <div className={`font-bold mt-0.5 text-[9.5px] ${indicators?.trend === "Bullish" ? "text-[#10b981]" : indicators?.trend === "Bearish" ? "text-[#f87171]" : "text-[#fbbf24]"}`}>{indicators?.trend || "-"}</div>
              </div>
              <div className="w-[1px] h-3.5 bg-[#26262b]" />
              <div>
                <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">RSI</span>
                <div className="font-bold text-white mt-0.5 text-[9.5px]">{indicators?.rsi || "-"}</div>
              </div>
              <div className="w-[1px] h-3.5 bg-[#26262b]" />
              <div>
                <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">Signal</span>
                <div className={`font-bold mt-0.5 text-[9.5px] ${signal?.action === "BUY" ? "text-[#10b981]" : signal?.action === "SELL" ? "text-[#f87171]" : "text-slate-400"}`}>{signal?.action || "WAIT"}</div>
              </div>
            </div>

            {/* Parameters block */}
            <div className="grid grid-cols-3 gap-2 text-[9px] font-mono border-t border-[#26262b]/40 pt-2">
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">คู่เหรียญ</span>
                <select
                  value={symbol}
                  onChange={(e) => handleSymbolChange(e.target.value)}
                  className="bg-[#000000] border border-[#26262b] rounded text-[10px] text-white px-1 py-0.5 outline-none font-mono font-bold w-full h-[22px] cursor-pointer"
                >
                  {SYMBOLS_LIST.map((s) => (
                    <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                  ))}
                </select>
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Lot</span>
                <input type="number" step="0.01" value={riskForm.lot}
                  onChange={(e) => setRiskForm({...riskForm, lot: Number(e.target.value)})}
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">SL (Pips)</span>
                <input type="number" value={riskForm.stopDistance}
                  onChange={(e) => setRiskForm({...riskForm, stopDistance: Number(e.target.value)})}
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">TP (Pips)</span>
                <input type="number" value={riskForm.takeProfit}
                  onChange={(e) => setRiskForm({...riskForm, takeProfit: Number(e.target.value)})}
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Spread Limit</span>
                <input type="number" step="0.1" value={riskForm.spread}
                  onChange={(e) => setRiskForm({...riskForm, spread: Number(e.target.value)})}
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                />
              </div>
              <div>
                <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Risk %</span>
                <input type="number" step="0.1" value={riskForm.riskPct}
                  onChange={(e) => setRiskForm({...riskForm, riskPct: Number(e.target.value)})}
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                />
              </div>
            </div>

            {/* Actions row */}
            <div className="flex items-center gap-1.5 border-t border-[#26262b]/40 pt-2 justify-between">
              <button onClick={handleRiskTest} className="px-2.5 py-1 bg-[#161f30] hover:bg-[#202d44] text-[9.5px] font-bold text-[#c8d8f0] rounded border border-[#243352] transition flex items-center gap-1 h-6">
                ประเมิน
              </button>
                  
              <div className={`px-2 py-1 text-[9.5px] font-bold rounded flex items-center gap-1 border h-6 ${
                risk?.passed ? "bg-[#0d2a14] text-[#10b981] border-[#1a5a28]" : "bg-[#2a0d0d] text-[#f87171] border-[#6b1c1c]"
              }`}>
                <span className={`w-1 h-1 rounded-full ${risk?.passed ? "bg-[#10b981] shadow-[0_0_4px_#10b981]" : "bg-[#ef4444] shadow-[0_0_4px_#ef4444]"}`} />
                {risk?.passed ? "PASS" : "BLOCK"}
              </div>
                  
              <button
                onClick={() => handleApprove()}
                disabled={mode === "auto" || !signal || (signal.action !== "BUY" && signal.action !== "SELL")}
                className="px-3.5 py-1 bg-[#0e3a1f] hover:bg-[#14532d] disabled:bg-[#111520] disabled:text-[#3d5a7a] border border-[#166534] disabled:border-[#26262b] text-[#10b981] disabled:text-[#3d5a7a] text-[10px] font-bold rounded transition flex items-center gap-1.5 h-7"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                อนุมัติ
              </button>
                  
              <button
                onClick={handleReject}
                className="px-2.5 py-1 bg-[#2a0d0d] hover:bg-[#450a0a] border border-[#6b1c1c] text-[#f87171] text-[10px] font-bold rounded transition flex items-center justify-center h-7"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </div>

        </div>
      </div>
  );
}
