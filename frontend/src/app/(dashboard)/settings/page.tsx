"use client";

import { useDashboard } from "@/context/DashboardContext";

export default function SettingsPage() {
  const { settingsForm, setSettingsForm, handleSaveSettings } = useDashboard();
  return (
                <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6`}>
                  <div className="border-b border-[#26262b] pb-4">
                    <h2 className="text-xl font-bold text-white">⚙️ ตั้งค่าความปลอดภัยและบัญชาการระบบ (System Settings)</h2>
                    <p className="text-xs text-[#7a9bbf] mt-1">กรอกข้อมูล Bot Token จริง และปรับแต่งพารามิเตอร์ตรวจสอบความเสี่ยงพอร์ต</p>
                  </div>

                  <form onSubmit={handleSaveSettings} className="bg-[#111520] border border-[#26262b] rounded-xl p-6 space-y-4 max-w-xl">
                    <div className="text-xs font-bold text-[#22d3ee] uppercase tracking-wider border-b border-[#26262b] pb-2 mb-2">
                      🤖 บัญชาการ Telegram Bot จริง
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-white font-bold block">Telegram Bot Token จริง (จาก @BotFather):</label>
                      <input 
                        type="text" 
                        value={settingsForm.telegram_token}
                        onChange={(e) => setSettingsForm({...settingsForm, telegram_token: e.target.value})}
                        placeholder="กรอก Bot Token ของคุณ เช่น 123456:ABC-def..."
                        className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                      />
                    </div>

                    <div className="text-xs font-bold text-[#10b981] uppercase tracking-wider border-b border-[#26262b] pb-2 pt-2 mb-2">
                      🧠 มันสมองสภา AI (Claude API)
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-white font-bold block">Anthropic (Claude) API Key:</label>
                      <input 
                        type="password" 
                        value={settingsForm.anthropic_key}
                        onChange={(e) => setSettingsForm({...settingsForm, anthropic_key: e.target.value})}
                        placeholder="sk-ant-api03-..."
                        className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                      />
                    </div>

                    <div className="text-xs font-bold text-[#fbbf24] uppercase tracking-wider border-b border-[#26262b] pb-2 pt-2 mb-2">
                      💰 การเชื่อมต่อคริปโต & หุ้นยอดนิยม (Binance, TwelveData, Finnhub, NewsAPI)
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">Binance API Key:</label>
                        <input 
                          type="text" 
                          value={settingsForm.binance_key}
                          onChange={(e) => setSettingsForm({...settingsForm, binance_key: e.target.value})}
                          placeholder="Binance API Key"
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">Binance API Secret:</label>
                        <input 
                          type="password" 
                          value={settingsForm.binance_secret}
                          onChange={(e) => setSettingsForm({...settingsForm, binance_secret: e.target.value})}
                          placeholder="Binance Secret Key"
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">NewsAPI Key:</label>
                        <input 
                          type="password" 
                          value={settingsForm.news_api_key}
                          onChange={(e) => setSettingsForm({...settingsForm, news_api_key: e.target.value})}
                          placeholder="NewsAPI Key"
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">TwelveData API Key:</label>
                        <input 
                          type="password" 
                          value={settingsForm.twelvedata_api_key}
                          onChange={(e) => setSettingsForm({...settingsForm, twelvedata_api_key: e.target.value})}
                          placeholder="TwelveData Key"
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">Finnhub API Token:</label>
                        <input 
                          type="password" 
                          value={settingsForm.finnhub_api_key}
                          onChange={(e) => setSettingsForm({...settingsForm, finnhub_api_key: e.target.value})}
                          placeholder="Finnhub Token"
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                    </div>

                    <div className="text-xs font-bold text-[#f87171] uppercase tracking-wider border-b border-[#26262b] pb-2 pt-2 mb-2">
                      🛡️ การควบคุมความเสี่ยงพอร์ต
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">Max Risk Per Trade (%):</label>
                        <input 
                          type="number" step="0.1"
                          value={settingsForm.maxRiskPerTradePct}
                          onChange={(e) => setSettingsForm({...settingsForm, maxRiskPerTradePct: Number(e.target.value)})}
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-xs text-white font-bold block">Max Open Exposure (%):</label>
                        <input 
                          type="number" step="0.1"
                          value={settingsForm.maxOpenExposurePct}
                          onChange={(e) => setSettingsForm({...settingsForm, maxOpenExposurePct: Number(e.target.value)})}
                          className="w-full bg-[#070a0f] border border-[#26262b] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                        />
                      </div>
                    </div>

                    <button 
                      type="submit" 
                      className="w-full py-2.5 bg-[#16a34a] hover:bg-[#15803d] text-white font-bold text-xs rounded-lg transition shadow-md pt-2"
                    >
                      💾 บันทึกและซิงค์การตั้งค่าบอทจริง
                    </button>
                  </form>

                  {/* กล่องคู่มือสอนสร้างและเชื่อมต่อบอท Telegram จริง */}
                  <div className="bg-[#111520] border border-[#26262b] rounded-xl p-5 space-y-4 max-w-xl text-xs">
                    <h3 className="font-bold text-white text-sm flex items-center gap-1.5 border-b border-[#26262b] pb-2">
                      📱 คู่มือการเปิดใช้งาน Telegram Bot และควบคุมจากมือถือ
                    </h3>
                    <div className="space-y-3 text-[#c8d8f0] leading-relaxed font-mono">
                      <p>
                        เพื่อให้บอทส่งสัญญาณเทรดและรอปุ่มกดอนุมัติการเปิดออเดอร์จากคุณโทนี่โดยตรงผ่านมือถือ กรุณาทำตามขั้นตอนต่อไปนี้:
                      </p>
                      <ol className="list-decimal list-inside space-y-2">
                        <li>
                          <strong>สร้างบอทผ่าน @BotFather:</strong>
                          <br />
                          - เปิดแอป Telegram ในมือถือแล้วค้นหาบอทชื่อ <code className="text-[#3b82f6]">@BotFather</code>
                          <br />
                          - พิมพ์คำสั่ง <code>/newbot</code> แล้วทำตามขั้นตอนเพื่อตั้งชื่อบอท
                          <br />
                          - เมื่อทำสำเร็จ คุณจะได้รับ <strong>HTTP API Token</strong> (Bot Token) ให้คัดลอกมาใส่ในช่องกรอกด้านบน
                        </li>
                        <li>
                          <strong>เริ่มต้นใช้งานบอท:</strong>
                          <br />
                          - ค้นหาชื่อบอทของคุณที่คุณเพิ่งสร้างขึ้นมาใน Telegram แล้วกดปุ่ม <code>Start</code> เพื่อเปิดใช้งานบอท
                        </li>
                        <li>
                          <strong>คำสั่งควบคุมบนมือถือ:</strong>
                          <br />
                          - คุณโทนี่สามารถพิมพ์คำสั่งต่อไปนี้ในช่องแชทของบอทเพื่อควบคุมและสั่งงาน:
                          <br />
                          &nbsp;&nbsp;• <code>/analyze XAUUSD</code> &rarr; สั่งให้สภา AI โต้วาทะและวางแผนเทรดทองคำ (หรือคู่หุ้นอื่นๆ เช่น <code>AAPL</code>, <code>NVDA</code>, <code>BTCUSDT</code>)
                          <br />
                          &nbsp;&nbsp;• <code>/status</code> &rarr; เช็คยอดเงิน พอร์ตการลงทุน และสถานะระบบ
                          <br />
                          &nbsp;&nbsp;• <code>/help</code> &rarr; แสดงรายการคำสั่งทั้งหมด
                        </li>
                        <li>
                          <strong>กดอนุมัติการเทรดผ่านปุ่มกด (Inline Keyboards):</strong>
                          <br />
                          - เมื่อใช้คำสั่งวิเคราะห์ บอทจะโต้วาทีและส่งปุ่มกด <code>[✅ อนุมัติการเทรด]</code> หรือ <code>[❌ ปฏิเสธแผนการ]</code> ไปยังแชทมือถือของคุณโทนี่
                          <br />
                          - เมื่อกดปุ่มในมือถือ บอทจะส่งสัญญาณยื่นคำสั่งอนุมัติเปิดออเดอร์เข้ามายังห้องทำงานจริงในหน้าเว็บ Dashboard แบบ Real-Time ทันที!
                        </li>
                      </ol>
                    </div>
                  </div>

                  {/* แผงแก้ไขข้อขัดข้องเซิร์ฟเวอร์ */}
                  <div className="bg-[#181120] border border-[#6b2a47]/30 rounded-xl p-4 max-w-xl space-y-2 text-xs text-slate-300">
                    <h4 className="font-bold text-[#f472b6] flex items-center gap-1.5">💡 คำแนะนำความเสถียรและการเปิดเซิร์ฟเวอร์ Python:</h4>
                    <p className="leading-relaxed">
                      หากขึ้นข้อความ <strong className="text-red-400">"❌ เซิร์ฟเวอร์ Python ไม่ตอบสนองคำสั่งบอท"</strong> แปลว่าเซิร์ฟเวอร์ FastAPI ในเทอร์มินัลของคุณรันค้างอยู่ตั้งแต่ช่วงก่อนติดตั้งไลบรารี ให้เข้าไปที่หน้าต่างนั้น กดปุ่ม <kbd className="bg-[#070a0f] px-1 py-0.5 border border-slate-700 rounded">Ctrl + C</kbd> เพื่อหยุดการทำงานของเซิร์ฟเวอร์เดิม จากนั้นพิมพ์คำสั่งรันระบบอีกครั้งดังนี้:
                    </p>
                    <pre className="bg-[#070a0f] p-2 rounded border border-slate-700 text-teal-400 font-mono text-[10px]">
      {`cd backend
      source venv/bin/activate
      python main.py`}
                    </pre>
                  </div>
                </div>
  );
}
