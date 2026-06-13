"use client";

import { useDashboard } from "@/context/DashboardContext";

export default function RightPanel() {
  const { activityLogs, chatMsgs, chatInput, setChatInput, chatEndRef, handleSendChat } = useDashboard();
  return (
      <aside className="w-[260px] min-w-[260px] bg-[#070a0f] border-l border-[#1e2d45] flex flex-col flex-shrink-0 h-full">
        {/* --- TEAM CHAT (TOP 55%) --- */}
        <div className="h-[55%] min-h-[55%] flex flex-col border-b border-[#1e2d45]">
          <div className="p-2 border-b border-[#1e2d45]/60 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-[14px]">💬</span>
              <div>
                <div className="font-bold text-[#c8d8f0] text-[12.5px] leading-none">Team Chat</div>
                <div className="text-[#10b981] text-[9px] mt-0.5 leading-tight flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                  System ready
                </div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2 bg-[#000000]/10">
            {chatMsgs.map((msg, idx) => (
              <div key={idx} className="bg-[#111520] border border-[#1e2d45] rounded p-2 space-y-1">
                <div className="flex items-center gap-1.5">
                  <div 
                    className="w-4 h-4 rounded-full flex items-center justify-center text-[7.5px] font-bold flex-shrink-0"
                    style={{ backgroundColor: msg.bg, color: msg.color }}
                  >
                    {msg.init}
                  </div>
                  <div className="text-[10.5px] font-bold font-mono" style={{ color: msg.color }}>
                    {msg.name}
                  </div>
                  {msg.time && (
                    <div className="text-[8.5px] text-[#3d5a7a] ml-auto">
                      {msg.time}
                    </div>
                  )}
                </div>
                <div className="text-[11px] text-[#a8c0d8] leading-relaxed break-words font-mono">
                  {msg.text}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleSendChat} className="p-2 border-t border-[#1e2d45]/60 flex gap-1 bg-[#070a0f]">
            <input 
              type="text" 
              placeholder="พิมพ์ข้อความ..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1 bg-[#111520] border border-[#1e2d45] rounded px-2 py-1 text-[11.5px] text-white outline-none focus:border-[#3b82f6] font-mono"
            />
            <button 
              type="submit" 
              className="bg-[#10b881]/10 hover:bg-[#10b881]/20 border border-[#10b881]/30 text-emerald-400 px-3 rounded flex items-center justify-center transition cursor-pointer"
            >
              <svg className="w-3.5 h-3.5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </form>
        </div>

        {/* --- AI ACTIVITY LOG (BOTTOM 45%) --- */}
        <div className="h-[45%] min-h-[45%] flex flex-col">
          <div className="p-2 border-b border-[#1e2d45]/60 text-xs bg-[#070a0f]">
            <div className="flex items-center gap-2">
              <span className="text-[14px]">⚡</span>
              <div>
                <div className="font-bold text-[#c8d8f0] text-[12.5px] leading-none">AI Activity Log</div>
                <div className="text-[#3d5a7a] text-[9.5px] mt-0.5">Live System Stream</div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1.5 bg-[#000000]/30 font-mono text-[10.5px]">
            {activityLogs.map((log, idx) => (
              <div key={idx} className="border-b border-[#1e2d45]/20 pb-1.5 last:border-b-0">
                <div className="flex items-center gap-1.5 text-[9.5px]">
                  <span 
                    className="w-1.5 h-1.5 rounded-full" 
                    style={{ backgroundColor: log.dotColor || "#10b981", boxShadow: `0 0 4px ${log.dotColor || "#10b981"}` }} 
                  />
                  <span className="font-bold" style={{ color: log.color }}>
                    {log.agent}
                  </span>
                  <span className="text-[#3d5a7a] ml-auto">{log.time}</span>
                </div>
                <div className="text-[#a8c0d8] text-[10px] leading-tight mt-0.5 break-words pl-3">
                  {log.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>
  );
}
