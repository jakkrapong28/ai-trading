"use client";

import { useEffect, useState } from "react";

interface DailyPlan {
  symbol: string;
  asof: string;
  ready: boolean;
  reason?: string;
  price?: number;
  atr?: number;
  bias?: { h1: string; regime: string };
  setup?: "BUY" | "SELL" | "WAIT";
  tier?: "A" | "B" | "C" | null;
  levels?: { resistance: number[]; support: number[] };
  entry_zone?: [number, number] | null;
  stop_loss?: number | null;
  take_profits?: number[];
  rr?: number | null;
}

const fmt = (n?: number | null) =>
  n == null ? "—" : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const SETUP_STYLE: Record<string, { text: string; bg: string; border: string; label: string }> = {
  BUY: { text: "#10b981", bg: "rgba(16,185,129,0.10)", border: "#10b981", label: "BUY ON DIP" },
  SELL: { text: "#f87171", bg: "rgba(248,113,113,0.10)", border: "#f87171", label: "SELL ON RALLY" },
  WAIT: { text: "#7a9bbf", bg: "rgba(122,155,191,0.08)", border: "#26262b", label: "STAND ASIDE" },
};

const biasTone = (s?: string) =>
  s === "Bullish" || s === "BULL" ? "#10b981" : s === "Bearish" || s === "BEAR" ? "#f87171" : "#fbbf24";

export default function DailyPlanCard({ symbol }: { symbol: string }) {
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/daily-plan?symbol=${symbol}`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        if (alive) { setPlan(data); setErr(false); }
      } catch {
        if (alive) setErr(true);
      }
    };
    load();
    const id = setInterval(load, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [symbol]);

  const setup = plan?.setup ?? "WAIT";
  const st = SETUP_STYLE[setup] ?? SETUP_STYLE.WAIT;
  const tps = plan?.take_profits ?? [];

  return (
    <div className="bg-[#070a0f] border border-[#26262b] rounded-xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#26262b] bg-gradient-to-r from-[#0a0f17] to-[#070a0f]">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#fbbf24]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          <div>
            <div className="text-[12.5px] font-black text-white tracking-wide leading-none font-mono">แผนเทรดรายวัน · {symbol}</div>
            <div className="text-[9px] text-[#5c7a9c] mt-1 leading-none font-mono">DAILY PLAN · อิงโครงสร้าง SMC + H1 bias</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[15px] font-black text-white font-mono leading-none">{fmt(plan?.price)}</div>
          <div className="text-[9px] text-[#5c7a9c] mt-1 leading-none font-mono">ATR {fmt(plan?.atr)}</div>
        </div>
      </div>

      {err && !plan && (
        <div className="px-4 py-6 text-center text-[11px] text-[#5c7a9c] font-mono">ต่อ backend ไม่ได้ — เริ่ม FastAPI ที่ :8000 ก่อน</div>
      )}
      {plan && !plan.ready && (
        <div className="px-4 py-6 text-center text-[11px] text-[#7a9bbf] font-mono">{plan.reason || "ยังไม่พร้อม"}</div>
      )}

      {plan?.ready && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-px bg-[#26262b]">
          {/* ── Col 1: Bias + setup ── */}
          <div className="bg-[#070a0f] p-4 flex flex-col gap-3">
            <div className="text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold">ภาพรวม / Bias</div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-[#5c7a9c]">แนวโน้ม H1</span>
              <span className="font-bold" style={{ color: biasTone(plan.bias?.h1) }}>{plan.bias?.h1}</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-[#5c7a9c]">Regime</span>
              <span className="font-bold" style={{ color: biasTone(plan.bias?.regime) }}>{plan.bias?.regime}</span>
            </div>
            <div
              className="mt-1 rounded-lg px-3 py-2.5 flex items-center justify-between"
              style={{ background: st.bg, border: `1px solid ${st.border}` }}
            >
              <div>
                <div className="text-[9px] text-[#5c7a9c] uppercase tracking-wide font-bold">Setup</div>
                <div className="text-[13px] font-black font-mono" style={{ color: st.text }}>{st.label}</div>
              </div>
              {plan.tier && (
                <div className="text-center">
                  <div className="text-[8px] text-[#5c7a9c] uppercase">Tier</div>
                  <div className="text-[18px] font-black font-mono leading-none" style={{ color: st.text }}>{plan.tier}</div>
                </div>
              )}
            </div>
            <div className="text-[9.5px] text-[#7a9bbf] leading-snug font-mono">{plan.reason}</div>
          </div>

          {/* ── Col 2: Plan (entry/SL/TP) ── */}
          <div className="bg-[#070a0f] p-4 flex flex-col gap-2">
            <div className="text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold mb-1">แผนการเทรด / Setup</div>
            {setup === "WAIT" ? (
              <div className="flex-1 flex items-center justify-center text-[11px] text-[#7a9bbf] font-mono text-center py-4">
                รอจังหวะชัดเจน — ยังไม่มี setup ที่ผ่าน TIER
              </div>
            ) : (
              <>
                <PlanRow label="Entry Zone" value={plan.entry_zone ? `${fmt(plan.entry_zone[0])} – ${fmt(plan.entry_zone[1])}` : "—"} tone="#cbd5e1" />
                <PlanRow label="Stop Loss" value={fmt(plan.stop_loss)} tone="#f87171" />
                <div className="h-px bg-[#26262b] my-1" />
                {tps.map((tp, i) => (
                  <PlanRow key={i} label={`Take Profit ${i + 1}`} value={fmt(tp)} tone="#10b981" />
                ))}
                <PlanRow label="Risk : Reward" value={`1 : ${plan.rr}`} tone="#fbbf24" />
              </>
            )}
          </div>

          {/* ── Col 3: Key levels ── */}
          <div className="bg-[#070a0f] p-4 flex flex-col gap-2">
            <div className="text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold mb-1">ระดับราคาสำคัญ</div>
            <div className="text-[9px] text-[#f87171] font-bold uppercase mb-0.5">แนวต้าน / Resistance</div>
            {(plan.levels?.resistance ?? []).length ? (
              plan.levels!.resistance.map((r, i) => (
                <PlanRow key={`r${i}`} label={`R${i + 1}`} value={fmt(r)} tone="#f87171" />
              ))
            ) : <div className="text-[10px] text-[#5c7a9c] font-mono">—</div>}
            <div className="text-[9px] text-[#10b981] font-bold uppercase mt-2 mb-0.5">แนวรับ / Support</div>
            {(plan.levels?.support ?? []).length ? (
              plan.levels!.support.map((s, i) => (
                <PlanRow key={`s${i}`} label={`S${i + 1}`} value={fmt(s)} tone="#10b981" />
              ))
            ) : <div className="text-[10px] text-[#5c7a9c] font-mono">—</div>}
          </div>
        </div>
      )}

      <div className="px-4 py-1.5 border-t border-[#26262b] text-[8.5px] text-[#3d5a7a] font-mono text-center">
        ⚠️ แผนช่วยวิเคราะห์ ไม่ใช่คำสั่งเทรด — บริหารความเสี่ยง 1–2% เสมอ
      </div>
    </div>
  );
}

function PlanRow({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex items-center justify-between text-[11px] font-mono">
      <span className="text-[#5c7a9c]">{label}</span>
      <span className="font-bold" style={{ color: tone }}>{value}</span>
    </div>
  );
}
