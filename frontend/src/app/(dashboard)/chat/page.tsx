"use client";

import { useDashboard } from "@/context/DashboardContext";

export default function ChatPage() {
  const { chatMsgs, setChatMsgs, chatInput, setChatInput, handleSendChat } = useDashboard();
  return (
      <div className={`flex-1 flex flex-col overflow-hidden bg-[#000000]`}>
        <div className="p-4 border-b border-[#26262b] bg-[#0f172a]/40 flex justify-between items-center">
          <div>
            <h2 className="text-md font-bold text-white">💬 ห้องเสวนากลุ่มวิเคราะห์สะสม (Team Chat Terminal)</h2>
            <p className="text-[11px] text-[#7a9bbf]">เก็บบันทึกทรานแซกชั่นการโต้เถียงของ AI และ Telegram Bot แบบสมบูรณ์</p>
          </div>
          <button 
            onClick={() => setChatMsgs([{ name: "EA Bot", color: "#6366f1", bg: "#0d0d22", init: "EA", text: "ล้างประวัติแชทจำลองสำเร็จ พร้อมตรวจสอบข้อมูลใหม่ครับ" }])}
            className="text-[10px] px-2 py-1 bg-red-950/40 hover:bg-red-900 border border-red-800/40 text-red-400 rounded transition"
          >
            ล้างแชทหน้าจอ
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {chatMsgs.map((msg, idx) => (
            <div key={idx} className="flex gap-3 max-w-2xl bg-[#111520] border border-[#26262b] rounded-xl p-3 shadow">
              <div 
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 border"
                style={{ backgroundColor: msg.bg, color: msg.color, borderColor: msg.color }}
              >
                {msg.init}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-xs" style={{ color: msg.color }}>{msg.name}</span>
                  {msg.time && <span className="text-[9px] text-[#3d5a7a]">{msg.time}</span>}
                </div>
                <p className="text-xs text-[#c8d8f0] leading-relaxed break-words whitespace-pre-wrap">{msg.text}</p>
              </div>
            </div>
          ))}
        </div>

        {/* ช่องป้อนแชทล่าง */}
        <form onSubmit={handleSendChat} className="p-4 border-t border-[#26262b] bg-[#070a0f] flex gap-2">
          <input 
            type="text" 
            placeholder="พิมพ์ข้อความแชท หรือรันคำสั่งจำลอง เช่น /analyze BTCUSDT..."
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            className="flex-1 bg-[#111520] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
          />
          <button type="submit" className="bg-[#3b82f6] hover:bg-blue-600 text-white px-4 rounded-lg text-xs font-bold transition">
            ส่งข้อความ
          </button>
        </form>
      </div>
  );
}
