"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useDashboard } from "@/context/DashboardContext";

const API = "http://localhost:8000";

interface MT5Account {
  login: number;
  server: string;
  name: string;
  balance: number;
  equity: number;
  currency: string;
  leverage: number;
  company: string;
}

interface MT5Status {
  connected: boolean;
  bridge_running?: boolean;
  bridge_url?: string;
  login?: number | null;
  server?: string | null;
  terminal_build?: number | null;
  account?: MT5Account;
  error?: string;
}

// Common Exness MT5 servers for the dropdown; the field below is also free-typeable.
const SERVER_GROUPS: { label: string; servers: string[] }[] = [
  { label: "Demo / ทดลอง", servers: [
    "Exness-MT5Trial", "Exness-MT5Trial7", "Exness-MT5Trial9", "Exness-MT5Trial14",
  ]},
  { label: "Real / จริง", servers: [
    "Exness-MT5Real", "Exness-MT5Real8", "Exness-MT5Real14", "Exness-MT5Real15",
    "Exness-MT5Real20", "Exness-MT5Real26", "Exness-MT5Real27", "Exness-MT5Real28",
    "Exness-MT5Real33",
  ]},
];

export default function MT5Page() {
  const [form, setForm] = useState({ login: "", password: "", server: "Exness-MT5Trial7" });
  const [status, setStatus] = useState<MT5Status | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [serverOpen, setServerOpen] = useState(false);
  const serverRef = useRef<HTMLDivElement>(null);
  // Refresh the global dashboard (HUD equity, balances, history) after connect/disconnect.
  const { fetchStateData } = useDashboard();

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/mt5/status`);
      const data: MT5Status = await res.json();
      setStatus(data);
      if (data.login && !form.login) {
        setForm((f) => ({ ...f, login: String(data.login), server: data.server || f.server }));
      }
    } catch {
      setStatus({ connected: false, bridge_running: false });
    }
  }, [form.login]);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 4000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  // Close the server dropdown when clicking outside of it.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (serverRef.current && !serverRef.current.contains(e.target as Node)) setServerOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const handleConnect = async () => {
    if (!form.login || !form.password || !form.server) {
      setMsg({ kind: "err", text: "กรอก Login / Password / Server ให้ครบ" });
      return;
    }
    setLoading(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/mt5/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: Number(form.login), password: form.password, server: form.server }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMsg({ kind: "err", text: data.detail || "เชื่อมต่อไม่สำเร็จ" });
      } else if (data.status === "success" || data.connected) {
        setMsg({ kind: "ok", text: "เชื่อมต่อ MT5 สำเร็จ ✅" });
        setForm((f) => ({ ...f, password: "" }));
      } else {
        setMsg({ kind: "err", text: data.message || "เชื่อมต่อไม่สำเร็จ (ตรวจ login/รหัส/server)" });
      }
      await fetchStatus();
      await fetchStateData();   // push the new MT5 account onto the HUD immediately
    } catch (e: any) {
      setMsg({ kind: "err", text: `ผิดพลาด: ${e.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("ตัดการเชื่อมต่อ MT5?")) return;
    setLoading(true);
    setMsg(null);
    try {
      const res = await fetch(`${API}/api/mt5/disconnect`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) setMsg({ kind: "err", text: data.detail || "ตัดการเชื่อมต่อไม่สำเร็จ" });
      else setMsg({ kind: "ok", text: "ตัดการเชื่อมต่อแล้ว" });
      await fetchStatus();
      await fetchStateData();   // revert HUD back to the simulated account
    } catch (e: any) {
      setMsg({ kind: "err", text: `ผิดพลาด: ${e.message}` });
    } finally {
      setLoading(false);
    }
  };

  const connected = !!status?.connected;
  const bridgeDown = status?.bridge_running === false;
  const acct = status?.account;

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6">
      <div className="border-b border-[#26262b] pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">🔌 การเชื่อมต่อ MetaTrader 5 (MT5 Connection)</h2>
          <p className="text-xs text-[#7a9bbf] mt-1">
            ล็อกอินบัญชี MT5 เพื่อดึงราคาทอง (XAUUSD) สดเข้าระบบ — ทำงานผ่าน bridge บนเครื่อง Windows
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-[#10b981] shadow-[0_0_8px_#10b981] animate-pulse" : "bg-[#ef4444] shadow-[0_0_8px_#ef4444]"}`} />
          <span className={`text-[11px] font-bold tracking-wider ${connected ? "text-[#10b981]" : "text-[#f87171]"}`}>
            {connected ? "CONNECTED" : "DISCONNECTED"}
          </span>
        </div>
      </div>

      {bridgeDown && (
        <div className="bg-[#2a1a05] border border-[#6b4a1c] text-[#fbbf24] rounded-xl p-4 text-xs">
          ⚠️ ยังไม่พบ Bridge server — เปิดก่อนด้วยคำสั่ง:
          <code className="block mt-2 bg-black/40 px-2 py-1 rounded font-mono text-[#fde68a]">
            powershell -ExecutionPolicy Bypass -File tools\run_mt5_bridge.ps1
          </code>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection form */}
        <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-5">
          <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4">ข้อมูลเข้าสู่ระบบ</div>
          <div className="space-y-3">
            <label className="block">
              <span className="text-[11px] text-[#7a9bbf]">Login (เลขบัญชี)</span>
              <input
                type="text" inputMode="numeric" value={form.login}
                onChange={(e) => setForm({ ...form, login: e.target.value })}
                placeholder="433787236"
                className="w-full mt-1 bg-[#000000] border border-[#26262b] rounded px-3 py-2 text-white text-sm outline-none focus:border-[#3b82f6]"
              />
            </label>
            <label className="block">
              <span className="text-[11px] text-[#7a9bbf]">Master Password (รหัสเทรด)</span>
              <input
                type="password" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                className="w-full mt-1 bg-[#000000] border border-[#26262b] rounded px-3 py-2 text-white text-sm outline-none focus:border-[#3b82f6]"
              />
            </label>
            <label className="block">
              <span className="text-[11px] text-[#7a9bbf]">Server</span>
              <div className="relative mt-1" ref={serverRef}>
                <input
                  type="text" value={form.server}
                  onChange={(e) => { setForm({ ...form, server: e.target.value }); setServerOpen(true); }}
                  onFocus={() => setServerOpen(true)}
                  placeholder="เลือกหรือพิมพ์ เช่น Exness-MT5Trial7"
                  className="w-full bg-[#000000] border border-[#26262b] rounded px-3 py-2 pr-9 text-white text-sm outline-none focus:border-[#3b82f6] font-mono"
                />
                <button
                  type="button" tabIndex={-1}
                  onClick={() => setServerOpen((o) => !o)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#7a9bbf] hover:text-white"
                >
                  <svg className={`w-4 h-4 transition-transform ${serverOpen ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {serverOpen && (
                  <div className="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto bg-[#0a0e16] border border-[#26262b] rounded shadow-lg shadow-black/50">
                    {SERVER_GROUPS.map((g) => {
                      const q = form.server.trim().toLowerCase();
                      const shown = q === "" ? g.servers : g.servers.filter((s) => s.toLowerCase().includes(q));
                      if (shown.length === 0) return null;
                      return (
                        <div key={g.label}>
                          <div className="px-3 py-1 text-[9px] uppercase tracking-wider text-[#3d5a7a] bg-[#070b11] sticky top-0">{g.label}</div>
                          {shown.map((s) => (
                            <button
                              key={s} type="button"
                              onClick={() => { setForm({ ...form, server: s }); setServerOpen(false); }}
                              className={`w-full text-left px-3 py-1.5 text-sm font-mono hover:bg-[#131d27] ${form.server === s ? "text-[#10b981]" : "text-white"}`}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </label>

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleConnect} disabled={loading || connected}
                className="flex-1 py-2 bg-[#0e3a1f] hover:bg-[#14532d] disabled:bg-[#111520] disabled:text-[#3d5a7a] border border-[#166534] disabled:border-[#26262b] text-[#10b981] disabled:text-[#3d5a7a] text-sm font-bold rounded transition"
              >
                {loading ? "กำลังเชื่อม..." : connected ? "เชื่อมต่ออยู่แล้ว" : "เชื่อมต่อ MT5"}
              </button>
              <button
                onClick={handleDisconnect} disabled={loading || !connected}
                className="px-4 py-2 bg-[#2a0d0d] hover:bg-[#450a0a] disabled:bg-[#111520] disabled:text-[#3d5a7a] border border-[#6b1c1c] disabled:border-[#26262b] text-[#f87171] disabled:text-[#3d5a7a] text-sm font-bold rounded transition"
              >
                ตัดการเชื่อมต่อ
              </button>
            </div>

            {msg && (
              <div className={`mt-1 text-xs font-medium px-3 py-2 rounded border ${
                msg.kind === "ok"
                  ? "bg-[#0d2a14] text-[#10b981] border-[#1a5a28]"
                  : "bg-[#2a0d0d] text-[#f87171] border-[#6b1c1c]"
              }`}>
                {msg.text}
              </div>
            )}

            <p className="text-[10px] text-slate-500 leading-relaxed pt-1">
              ⚠️ ต้องใช้ <b>รหัสเทรด (Master password)</b> + <b>เลขบัญชี</b> — login ด้วย email ใช้กับ API ไม่ได้
              · บัญชีทดลอง (demo) ก็ดึงราคาทองได้เหมือนกัน · server demo เป็นแนว <code>Exness-MT5Trialxx</code>
            </p>
          </div>
        </div>

        {/* Status card */}
        <div className="bg-[#070a0f] border border-[#26262b] rounded-xl p-5">
          <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4">สถานะบัญชี</div>
          {connected && acct ? (
            <div className="space-y-3 text-sm">
              <Row label="บัญชี (Login)" value={String(acct.login)} mono />
              <Row label="ชื่อ" value={acct.name || "-"} />
              <Row label="โบรกเกอร์" value={acct.company || "-"} />
              <Row label="Server" value={acct.server} mono />
              <Row label="Balance" value={`${acct.balance.toLocaleString()} ${acct.currency}`} highlight />
              <Row label="Equity" value={`${acct.equity.toLocaleString()} ${acct.currency}`} />
              <Row label="Leverage" value={`1:${acct.leverage}`} />
              <Row label="Terminal build" value={String(status?.terminal_build ?? "-")} mono />
              <div className="mt-4 pt-3 border-t border-[#26262b] text-[11px] text-[#10b981] flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" />
                ราคาทอง XAUUSD กำลังไหลเข้าระบบจาก MT5 แล้ว
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-center py-10 text-sm">
              {bridgeDown ? "Bridge ยังไม่ทำงาน" : "ยังไม่ได้เชื่อมต่อบัญชี"}
              <div className="text-[11px] mt-2 text-slate-600">กรอกข้อมูลด้านซ้ายแล้วกด “เชื่อมต่อ MT5”</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono, highlight }: { label: string; value: string; mono?: boolean; highlight?: boolean }) {
  return (
    <div className="flex justify-between items-center border-b border-white/5 pb-2 last:border-0">
      <span className="text-slate-400 text-xs">{label}</span>
      <span className={`${mono ? "font-mono" : ""} ${highlight ? "text-[#e2b714] font-bold" : "text-white"} text-sm`}>{value}</span>
    </div>
  );
}
