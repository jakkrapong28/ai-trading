// TAB: 📈 Performance Dashboard — live KPI cards and recent executions table.
import type { Order } from "@/types";

interface PerformanceTabProps {
  active: boolean;
  closedOrders: Order[];
  todayPnLSum: number;
  activeTradesCount: number;
}

const PerformanceTab = ({ active, closedOrders, todayPnLSum, activeTradesCount }: PerformanceTabProps) => {
  return (
    <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${active ? "block" : "hidden"}`}>
      <div className="border-b border-[#1e2d45] pb-4">
        <h2 className="text-xl font-bold text-white">📈 AI Trading Performance Dashboard</h2>
        <p className="text-xs text-[#7a9bbf] mt-1">Live metrics from the trading engines.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
          <div className="text-xs text-slate-400">Total Trades</div>
          <div className="text-3xl font-bold text-white mt-2">{closedOrders.length}</div>
        </div>

        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
          <div className="text-xs text-slate-400">Win Rate</div>
          <div className="text-3xl font-bold text-[#10b981] mt-2">
            {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(1) : 0}%
          </div>
        </div>

        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
          <div className="text-xs text-slate-400">Total PnL</div>
          <div className={`text-3xl font-bold mt-2 ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
            ${todayPnLSum.toFixed(2)}
          </div>
        </div>

        <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
          <div className="text-xs text-slate-400">Active Positions</div>
          <div className="text-3xl font-bold text-[#3b82f6] mt-2">{activeTradesCount}</div>
        </div>
      </div>

      {/* Recent Trades Table */}
      <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 mt-6">
        <div className="text-xs text-white font-bold uppercase tracking-wider mb-4">Recent Executions</div>
        <table className="w-full text-left text-xs text-slate-300">
            <thead>
              <tr className="border-b border-[#1e2d45] text-slate-400 font-mono">
                <th className="py-2">ID</th>
                <th className="py-2">Symbol</th>
                <th className="py-2">Action</th>
                <th className="py-2">Status</th>
                <th className="py-2 text-right">Entry Price</th>
                <th className="py-2 text-right">PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {closedOrders.map((ord, idx) => (
                <tr key={idx} className="hover:bg-[#070a0f]/40">
                  <td className="py-2 text-slate-500 truncate max-w-[100px]">{ord.id}</td>
                  <td className="py-2 font-bold text-white">{ord.symbol}</td>
                  <td className={`py-2 font-bold ${ord.action === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>{ord.action}</td>
                  <td className="py-2">{ord.status}</td>
                  <td className="py-2 text-right">{ord.entry_price}</td>
                  <td className={`py-2 text-right font-bold ${ord.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{ord.pnl.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
        </table>
      </div>

    </div>
  );
};

export default PerformanceTab;
