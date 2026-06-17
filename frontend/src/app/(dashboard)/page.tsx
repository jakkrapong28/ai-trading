"use client";

import { useEffect, useRef, useState } from "react";
import { SYMBOLS_LIST } from "@/config/dashboard";
import { useDashboard } from "@/context/DashboardContext";

const CYAN = "#38e0ff";
const STARTING_BALANCE = 45750;

const fmt = (n: number | null | undefined, d = 2) =>
  n == null ? "—" : n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

const CATS = [
  { key: "Crypto", label: "CRYPTO", dot: "#f7931a" },
  { key: "Forex", label: "METAL / FX", dot: "#e2b714" },
  { key: "Stock", label: "EQUITIES", dot: "#22d3ee" },
] as const;

const biasColor = (action?: string) =>
  action === "BUY" ? "#10b981" : action === "SELL" ? "#ef4444" : CYAN;

export default function OfficeOverviewPage() {
  const {
    symbol, priceMap, indicators, signal,
    totalEquity, todayPnLSum, pnlPct, activeTradesCount,
    handleSymbolChange,
  } = useDashboard();

  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Boot sequence — "entering the system" moment on first mount.
  const [booting, setBooting] = useState(true);
  useEffect(() => {
    const id = setTimeout(() => setBooting(false), 1750);
    return () => clearTimeout(id);
  }, []);

  // Smooth count-up toward the live equity (powering-up feel).
  const displayEquity = useTween(totalEquity);

  // Intraday market pulse — real H1 candles for the active symbol.
  const candles = useCandles(symbol);

  // Real per-symbol tick direction + session-anchored change %.
  const prev = useRef<Record<string, number>>({});
  const anchor = useRef<Record<string, number>>({});
  const dir: Record<string, 1 | -1 | 0> = {};
  const chg: Record<string, number> = {};
  for (const { symbol: s } of SYMBOLS_LIST) {
    const p = priceMap[s];
    if (p == null) { dir[s] = 0; chg[s] = 0; continue; }
    if (anchor.current[s] == null) anchor.current[s] = p;
    const pv = prev.current[s];
    dir[s] = pv == null || p === pv ? 0 : p > pv ? 1 : -1;
    prev.current[s] = p;
    chg[s] = ((p - anchor.current[s]) / anchor.current[s]) * 100;
  }

  const equityPct = Math.max(0, Math.min(1.5, totalEquity / STARTING_BALANCE));
  const pnlUp = todayPnLSum >= 0;
  const sigConf = Math.round((signal?.confidence ?? 0) * 100);
  const rsi = indicators?.rsi ?? 0;

  return (
    <div className="absolute inset-0 overflow-hidden bg-[#000308] text-[#bfe9f7]">
      {/* grid + vignette + scanline */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.18]"
        style={{ backgroundImage: "linear-gradient(#0e3a48 1px,transparent 1px),linear-gradient(90deg,#0e3a48 1px,transparent 1px)", backgroundSize: "46px 46px" }} />
      <div className="pointer-events-none absolute inset-0"
        style={{ background: "radial-gradient(120% 90% at 50% 42%, rgba(10,40,60,0.55) 0%, rgba(0,3,8,0.2) 45%, #000308 80%)" }} />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[3px] hud-scanline"
        style={{ background: "linear-gradient(90deg,transparent,rgba(56,224,255,0.5),transparent)" }} />

      {/* ── boot sequence ── */}
      {booting && (
        <div className="hud-bootscreen absolute inset-0 z-50 flex flex-col items-center justify-center bg-[#000308]">
          <div className="relative mb-6">
            <svg viewBox="0 0 90 90" className="w-20 h-20">
              <circle cx="45" cy="45" r="40" fill="none" stroke={CYAN} strokeWidth="1.5" opacity="0.4" className="hud-spin-30" strokeDasharray="4 6" />
              <circle cx="45" cy="45" r="30" fill="none" stroke={CYAN} strokeWidth="2" opacity="0.7" className="hud-spin-r45" strokeDasharray="30 10" />
              <circle cx="45" cy="45" r="14" fill={CYAN} opacity="0.85" className="hud-core" style={{ filter: `drop-shadow(0 0 10px ${CYAN})` }} />
            </svg>
          </div>
          <div className="text-[13px] font-black tracking-[0.4em] font-mono mb-3" style={{ color: CYAN, textShadow: `0 0 16px ${CYAN}` }}>
            A · I&nbsp; TRADING&nbsp; CORE
          </div>
          <div className="w-[240px] h-[3px] bg-[#0c2c38] rounded-full overflow-hidden">
            <div className="hud-bootbar h-full rounded-full" style={{ background: CYAN, boxShadow: `0 0 10px ${CYAN}` }} />
          </div>
          <div className="text-[9px] tracking-[0.35em] text-[#3f7e93] font-mono mt-3">INITIALISING&nbsp; MARKET&nbsp; LINK…</div>
        </div>
      )}

      <div className="relative h-full w-full overflow-y-auto px-5 py-3">
        {/* ── status bar ── */}
        <div className="flex items-center justify-between border-b border-[#114b5f]/60 pb-2">
          <div className="flex items-center gap-3">
            <CoreGlyph />
            <div>
              <div className="text-[13px] font-black tracking-[0.25em] font-mono" style={{ color: CYAN, textShadow: `0 0 12px ${CYAN}66` }}>
                A · I &nbsp;TRADING&nbsp; CORE
              </div>
              <div className="text-[9px] text-[#3f7e93] tracking-[0.3em] font-mono mt-0.5">MARKET COMMAND · STOCK + CRYPTO</div>
            </div>
          </div>
          <div className="flex items-center gap-6 font-mono">
            <Stat label="UTC SYNC" value={now ? now.toUTCString().slice(17, 25) : "--:--:--"} />
            <Stat label="LOCAL" value={now ? now.toLocaleTimeString([], { hour12: false }) : "--:--:--"} />
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_8px_#10b981] animate-pulse" />
              <span className="text-[10px] text-[#10b981] font-bold tracking-wider">LINK ONLINE</span>
            </div>
          </div>
        </div>

        {/* ── main HUD: vitals | reactor | market ── */}
        <div className="grid grid-cols-1 xl:grid-cols-[260px_1fr_320px] gap-4 mt-3">
          {/* LEFT — vitals */}
          <div className="flex flex-col gap-3 order-2 xl:order-1 hud-reveal" style={{ animationDelay: "0.1s" }}>
            <Panel title="PORTFOLIO VITALS">
              <div className="grid grid-cols-2 gap-2">
                <Gauge label="ACTIVE POS" display={String(activeTradesCount)} value={activeTradesCount} max={8} color={CYAN} />
                <Gauge label="SIGNAL" display={`${sigConf}%`} value={sigConf} max={100} color={biasColor(signal?.action)} />
                <Gauge label="RSI" display={fmt(rsi, 0)} value={rsi} max={100} color={rsi >= 70 ? "#ef4444" : rsi <= 30 ? "#10b981" : CYAN} />
                <Gauge label="DAY P/L" display={`${pnlUp ? "+" : ""}${pnlPct.toFixed(1)}%`} value={Math.min(Math.abs(pnlPct), 100)} max={100} color={pnlUp ? "#10b981" : "#ef4444"} />
              </div>
            </Panel>
            <Panel title="ACTIVE INSTRUMENT">
              <div className="flex items-baseline justify-between">
                <span className="text-[15px] font-black text-white font-mono">{symbol}</span>
                <span className="text-[12px] font-mono font-bold" style={{ color: biasColor(signal?.action) }}>
                  {signal?.action ?? "WAIT"}
                </span>
              </div>
              <div className="text-[18px] font-black text-white font-mono mt-1 leading-none">{fmt(priceMap[symbol])}</div>
              <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono text-[#5c93a8]">
                <Row k="Trend" v={indicators?.trend ?? "—"} />
                <Row k="ATR" v={fmt(indicators?.atr)} />
                <Row k="Support" v={fmt(indicators?.support)} />
                <Row k="Resist" v={fmt(indicators?.resistance)} />
              </div>
            </Panel>
          </div>

          {/* CENTER — reactor core */}
          <div className="order-1 xl:order-2 flex flex-col items-center justify-center min-h-[340px] hud-pop">
            <ReactorCore
              equity={displayEquity}
              pnl={todayPnLSum}
              pnlPct={pnlPct}
              fill={equityPct / 1.5}
              up={pnlUp}
            />
            <div className="mt-3 flex items-center gap-2 text-[10px] font-mono text-[#3f7e93] tracking-[0.25em]">
              <span className="w-8 h-px bg-[#114b5f]" />
              EQUITY CORE · BASE {STARTING_BALANCE.toLocaleString()}
              <span className="w-8 h-px bg-[#114b5f]" />
            </div>
          </div>

          {/* RIGHT — live market feed */}
          <div className="order-3 flex flex-col gap-3 hud-reveal" style={{ animationDelay: "0.18s" }}>
            {CATS.map((cat) => {
              const rows = SYMBOLS_LIST.filter((s) => s.category === cat.key);
              if (!rows.length) return null;
              return (
                <Panel key={cat.key} title={cat.label} dot={cat.dot}>
                  <div className="flex flex-col">
                    {rows.map((s) => (
                      <MarketRow
                        key={s.symbol}
                        sym={s.symbol}
                        name={s.name}
                        price={priceMap[s.symbol]}
                        dir={dir[s.symbol]}
                        chg={chg[s.symbol]}
                        active={s.symbol === symbol}
                        onClick={() => handleSymbolChange(s.symbol)}
                      />
                    ))}
                  </div>
                </Panel>
              );
            })}
          </div>
        </div>

        {/* ── daily market pulse chart ── */}
        <div className="mt-4 hud-reveal" style={{ animationDelay: "0.25s" }}>
          <MarketPulseChart symbol={symbol} candles={candles} up={pnlUp} />
        </div>
      </div>
    </div>
  );
}

/* ─────────── hooks ─────────── */

function useTween(target: number, ms = 900) {
  const [val, setVal] = useState(target);
  const ref = useRef(target);
  useEffect(() => {
    const from = ref.current;
    const start = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / ms);
      const e = 1 - Math.pow(1 - p, 4); // ease-out-quart
      const v = from + (target - from) * e;
      ref.current = v;
      setVal(v);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return val;
}

interface Candle { time: number; open: number; high: number; low: number; close: number; }

function useCandles(symbol: string) {
  const [candles, setCandles] = useState<Candle[]>([]);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/candles?symbol=${symbol}&tf=H1&bars=64`);
        if (!res.ok) return;
        const data = await res.json();
        if (alive && Array.isArray(data?.candles)) setCandles(data.candles);
      } catch { /* feed offline — chart shows empty state */ }
    };
    load();
    const id = setInterval(load, 20000);
    return () => { alive = false; clearInterval(id); };
  }, [symbol]);
  return candles;
}

/* ─────────── pieces ─────────── */

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-right">
      <div className="text-[8px] text-[#3f7e93] tracking-[0.2em]">{label}</div>
      <div className="text-[11px] font-bold text-[#bfe9f7] font-mono leading-none mt-0.5">{value}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[#3f7e93]">{k}</span>
      <span className="text-[#bfe9f7] font-bold">{v}</span>
    </div>
  );
}

function Panel({ title, dot, children }: { title: string; dot?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-[#114b5f]/70 bg-[#04101a]/70 backdrop-blur-[2px] p-3">
      <div className="flex items-center gap-2 mb-2.5">
        <span className="w-1 h-3 rounded-full" style={{ background: dot ?? CYAN, boxShadow: `0 0 8px ${dot ?? CYAN}` }} />
        <h3 className="text-[9.5px] font-bold tracking-[0.22em] text-[#5c93a8]">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function Gauge({ label, display, value, max, color }: { label: string; display: string; value: number; max: number; color: string }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / (max || 1)));
  return (
    <div className="flex flex-col items-center gap-1 py-1">
      <div className="relative w-[74px] h-[74px]">
        <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
          <circle cx="40" cy="40" r={r} fill="none" stroke="#0c2c38" strokeWidth="5" />
          <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
            strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
            style={{ filter: `drop-shadow(0 0 4px ${color}aa)`, transition: "stroke-dashoffset .6s cubic-bezier(.22,1,.36,1)" }} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[13px] font-black font-mono text-white">{display}</span>
        </div>
      </div>
      <span className="text-[8px] tracking-[0.15em] text-[#3f7e93] font-bold">{label}</span>
    </div>
  );
}

function MarketRow({ sym, name, price, dir, chg, active, onClick }: {
  sym: string; name: string; price?: number; dir: 1 | -1 | 0; chg: number; active: boolean; onClick: () => void;
}) {
  const tone = chg > 0 ? "#10b981" : chg < 0 ? "#ef4444" : "#5c93a8";
  return (
    <button onClick={onClick}
      className={`group flex items-center justify-between py-1.5 px-1.5 -mx-1 rounded transition-colors ${active ? "bg-[#0a2b38]" : "hover:bg-[#08222d]"}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="w-1 h-6 rounded-full transition-all" style={{ background: active ? CYAN : "#123a48", boxShadow: active ? `0 0 8px ${CYAN}` : "none" }} />
        <div className="text-left min-w-0">
          <div className="text-[11px] font-bold text-white font-mono leading-none">{sym}</div>
          <div className="text-[8.5px] text-[#3f7e93] truncate max-w-[120px] leading-none mt-1">{name}</div>
        </div>
      </div>
      <div className="text-right font-mono">
        <div className="flex items-center justify-end gap-1 text-[11px] font-bold text-white leading-none">
          {dir !== 0 && (
            <span style={{ color: dir > 0 ? "#10b981" : "#ef4444" }}>{dir > 0 ? "▲" : "▼"}</span>
          )}
          {price == null ? "—" : fmt(price)}
        </div>
        <div className="text-[8.5px] font-bold leading-none mt-1" style={{ color: tone }}>
          {price == null ? "··" : `${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%`}
        </div>
      </div>
    </button>
  );
}

function MarketPulseChart({ symbol, candles, up }: { symbol: string; candles: Candle[]; up: boolean }) {
  const W = 1000, H = 150, pad = 6;
  const closes = candles.map((c) => c.close).filter((n) => typeof n === "number");
  const tone = up ? "#10b981" : CYAN;

  let line = "", area = "", last = 0, first = 0, lo = 0, hi = 0;
  if (closes.length > 1) {
    lo = Math.min(...closes); hi = Math.max(...closes);
    const span = hi - lo || 1;
    const x = (i: number) => pad + (i / (closes.length - 1)) * (W - pad * 2);
    const y = (v: number) => pad + (1 - (v - lo) / span) * (H - pad * 2);
    const pts = closes.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    line = "M" + pts.join(" L");
    area = `${line} L${(W - pad).toFixed(1)},${H - pad} L${pad},${H - pad} Z`;
    first = closes[0]; last = closes[closes.length - 1];
  }
  const dayChg = first ? ((last - first) / first) * 100 : 0;
  const id = `pulse-${symbol}`;

  return (
    <section className="rounded-lg border border-[#114b5f]/70 bg-[#04101a]/70 p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="w-1 h-3 rounded-full" style={{ background: CYAN, boxShadow: `0 0 8px ${CYAN}` }} />
          <h3 className="text-[9.5px] font-bold tracking-[0.22em] text-[#5c93a8]">MARKET PULSE · {symbol} · H1 · ~2.5D</h3>
        </div>
        {closes.length > 1 && (
          <div className="flex items-center gap-3 font-mono text-[10px]">
            <span className="text-[#3f7e93]">H <span className="text-[#bfe9f7] font-bold">{fmt(hi)}</span></span>
            <span className="text-[#3f7e93]">L <span className="text-[#bfe9f7] font-bold">{fmt(lo)}</span></span>
            <span className="font-bold" style={{ color: dayChg >= 0 ? "#10b981" : "#ef4444" }}>
              {dayChg >= 0 ? "+" : ""}{dayChg.toFixed(2)}%
            </span>
          </div>
        )}
      </div>
      {closes.length > 1 ? (
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-[120px]">
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={tone} stopOpacity="0.32" />
              <stop offset="100%" stopColor={tone} stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((g) => (
            <line key={g} x1="0" x2={W} y1={H * g} y2={H * g} stroke="#0e3a48" strokeWidth="1" opacity="0.5" />
          ))}
          <path d={area} fill={`url(#${id})`} />
          <path d={line} fill="none" stroke={tone} strokeWidth="2" vectorEffect="non-scaling-stroke"
            style={{ filter: `drop-shadow(0 0 4px ${tone}aa)` }} />
        </svg>
      ) : (
        <div className="h-[120px] flex items-center justify-center text-[10px] text-[#3f7e93] font-mono">
          กำลังรับสัญญาณราคา… (ต่อ backend :8000)
        </div>
      )}
    </section>
  );
}

function CoreGlyph() {
  return (
    <svg viewBox="0 0 40 40" className="w-7 h-7">
      <circle cx="20" cy="20" r="17" fill="none" stroke={CYAN} strokeWidth="1.4" opacity="0.5" className="hud-spin-60" style={{ strokeDasharray: "6 5" }} />
      <circle cx="20" cy="20" r="11" fill="none" stroke={CYAN} strokeWidth="1.4" opacity="0.8" className="hud-spin-r45" style={{ strokeDasharray: "3 7" }} />
      <circle cx="20" cy="20" r="5" fill={CYAN} opacity="0.9" className="hud-core" style={{ filter: `drop-shadow(0 0 5px ${CYAN})` }} />
    </svg>
  );
}

function ReactorCore({ equity, pnl, pnlPct, fill, up }: { equity: number; pnl: number; pnlPct: number; fill: number; up: boolean }) {
  const R = 120;
  const c = 2 * Math.PI * R;
  const pnlColor = up ? "#10b981" : "#ef4444";
  return (
    <div className="relative w-[300px] h-[300px] flex items-center justify-center">
      <svg viewBox="0 0 300 300" className="absolute inset-0 w-full h-full">
        {/* outer dashed ring */}
        <circle cx="150" cy="150" r="142" fill="none" stroke="#0e3a48" strokeWidth="1" />
        <g className="hud-spin-60">
          <circle cx="150" cy="150" r="134" fill="none" stroke={CYAN} strokeWidth="1.5" opacity="0.45" strokeDasharray="2 12" />
        </g>
        <g className="hud-spin-r45">
          <circle cx="150" cy="150" r="118" fill="none" stroke={CYAN} strokeWidth="2" opacity="0.35" strokeDasharray="40 18" />
        </g>
        {/* equity progress arc */}
        <circle cx="150" cy="150" r={R} fill="none" stroke="#0c2c38" strokeWidth="7" />
        <circle cx="150" cy="150" r={R} fill="none" stroke={CYAN} strokeWidth="7" strokeLinecap="round"
          transform="rotate(-90 150 150)"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(1, fill)))}
          style={{ filter: `drop-shadow(0 0 6px ${CYAN})`, transition: "stroke-dashoffset .8s cubic-bezier(.22,1,.36,1)" }} />
        <g className="hud-spin-30">
          <circle cx="150" cy="150" r="96" fill="none" stroke={CYAN} strokeWidth="1" opacity="0.3" strokeDasharray="1 9" />
        </g>
      </svg>
      {/* radar sweep */}
      <div className="hud-radar absolute w-[240px] h-[240px] rounded-full overflow-hidden opacity-70"
        style={{ background: `conic-gradient(from 0deg, transparent 0deg, ${CYAN}00 300deg, ${CYAN}44 350deg, ${CYAN}77 360deg)`, maskImage: "radial-gradient(circle, #000 60%, transparent 61%)", WebkitMaskImage: "radial-gradient(circle, #000 60%, transparent 61%)" }} />
      {/* inner core glow */}
      <div className="hud-core absolute w-[150px] h-[150px] rounded-full"
        style={{ background: `radial-gradient(circle, ${CYAN}33 0%, ${CYAN}11 45%, transparent 70%)` }} />
      <div className="relative z-10 text-center">
        <div className="text-[9px] tracking-[0.3em] text-[#3f7e93] font-mono">TOTAL EQUITY</div>
        <div className="text-[30px] font-black text-white font-mono leading-none mt-1" style={{ textShadow: `0 0 18px ${CYAN}55` }}>
          {fmt(equity)}
        </div>
        <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border" style={{ borderColor: `${pnlColor}55`, background: `${pnlColor}14` }}>
          <span className="text-[12px] font-black font-mono" style={{ color: pnlColor }}>
            {up ? "+" : ""}{fmt(pnl)}
          </span>
          <span className="text-[10px] font-bold font-mono" style={{ color: pnlColor }}>
            ({up ? "+" : ""}{pnlPct.toFixed(2)}%)
          </span>
        </div>
        <div className="text-[8.5px] tracking-[0.25em] text-[#3f7e93] font-mono mt-1.5">TODAY · REALISED</div>
      </div>
    </div>
  );
}
