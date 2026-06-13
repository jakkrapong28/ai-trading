"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  LineStyle,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type CandlestickData,
  type LineData,
  type UTCTimestamp,
} from "lightweight-charts";
import { useDashboard } from "@/context/DashboardContext";

const API = "http://localhost:8000";

type RawCandle = { time: number; open: number; high: number; low: number; close: number };

// Which AI line groups are visible. The chart is ours, so every line is drawn
// from our own backend data (no TradingView overlay possible on the iframe).
type LineToggles = { sr: boolean; trade: boolean; atr: boolean; ema: boolean };

// EMA overlays (like Binance MA 7/25/99), computed client-side from closes.
const EMA_CONFIG = [
  { period: 7, color: "#fbbf24" },
  { period: 25, color: "#f472b6" },
  { period: 99, color: "#a78bfa" },
];

function computeEMA(
  candles: CandlestickData<UTCTimestamp>[],
  period: number,
): LineData<UTCTimestamp>[] {
  if (candles.length < period) return [];
  const k = 2 / (period + 1);
  const out: LineData<UTCTimestamp>[] = [];
  let ema = candles.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
  out.push({ time: candles[period - 1].time, value: ema });
  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k);
    out.push({ time: candles[i].time, value: ema });
  }
  return out;
}

export default function AIChartWidget({ symbol, tf = "H1" }: { symbol: string; tf?: string }) {
  const { latestPrice, indicators, orders } = useDashboard();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const lastCandleRef = useRef<CandlestickData<UTCTimestamp> | null>(null);

  const [toggles, setToggles] = useState<LineToggles>({ sr: true, trade: true, atr: false, ema: true });
  const [loading, setLoading] = useState(true);

  // ── Create chart once ──────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#7a9bbf",
        fontFamily: "ui-monospace, monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(38,38,43,0.35)" },
        horzLines: { color: "rgba(38,38,43,0.35)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#26262b" },
      timeScale: {
        borderColor: "#26262b",
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 9, // zoomed enough that the axis labels read hourly
        rightOffset: 6,
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    chartRef.current = chart;
    seriesRef.current = series;

    emaSeriesRef.current = EMA_CONFIG.map(({ color }) =>
      chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      }),
    );

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      emaSeriesRef.current = [];
      priceLinesRef.current = [];
      lastCandleRef.current = null;
    };
  }, []);

  // ── Load candles (and poll) for the active symbol ──────────────────
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`${API}/api/candles?symbol=${symbol}&tf=${tf}&bars=300`);
        const json = await res.json();
        if (!alive || !seriesRef.current) return;
        // lightweight-charts renders the time axis in UTC. Shift timestamps by
        // the viewer's local offset so the axis reads local time (e.g. Bangkok
        // UTC+7) instead of being 7h behind. Also dedupe (Yahoo bootstrap can
        // overlap the forming candle) and sort — the lib requires strictly
        // ascending, unique times.
        const tzOffsetSec = -new Date().getTimezoneOffset() * 60;
        const byTime = new Map<number, CandlestickData<UTCTimestamp>>();
        for (const c of json.candles as RawCandle[]) {
          const t = (c.time + tzOffsetSec) as UTCTimestamp;
          byTime.set(c.time + tzOffsetSec, {
            time: t,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          });
        }
        const data = [...byTime.values()].sort(
          (a, b) => (a.time as number) - (b.time as number),
        );
        seriesRef.current.setData(data);
        lastCandleRef.current = data[data.length - 1] ?? null;

        // EMA overlays from the same candle closes (visibility handled below).
        emaSeriesRef.current.forEach((s, i) => {
          s.setData(computeEMA(data, EMA_CONFIG[i].period));
        });

        // Zoom to a recent, hourly-detailed window (like TradingView) and
        // follow the latest bar — fitContent would cram all 300 bars and the
        // axis would only label every ~6h.
        if (data.length) chartRef.current?.timeScale().scrollToRealTime();
        setLoading(false);
      } catch {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [symbol, tf]);

  // ── Live-update the forming candle from the streamed last price ─────
  useEffect(() => {
    const series = seriesRef.current;
    const last = lastCandleRef.current;
    if (!series || !last || !latestPrice) return;
    const updated: CandlestickData<UTCTimestamp> = {
      ...last,
      close: latestPrice,
      high: Math.max(last.high, latestPrice),
      low: Math.min(last.low, latestPrice),
    };
    lastCandleRef.current = updated;
    series.update(updated);
  }, [latestPrice]);

  // ── Toggle EMA overlay visibility ──────────────────────────────────
  useEffect(() => {
    emaSeriesRef.current.forEach((s) => s.applyOptions({ visible: toggles.ema }));
  }, [toggles.ema]);

  // ── Redraw AI price lines when data or toggles change ──────────────
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    priceLinesRef.current.forEach((l) => series.removePriceLine(l));
    priceLinesRef.current = [];

    const add = (price: number, color: string, title: string, dashed = false) => {
      if (!price || !isFinite(price)) return;
      priceLinesRef.current.push(
        series.createPriceLine({
          price,
          color,
          lineWidth: 1,
          lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
          axisLabelVisible: true,
          title,
        }),
      );
    };

    if (toggles.sr && indicators) {
      add(indicators.resistance, "#f87171", "R แนวต้าน");
      add(indicators.support, "#34d399", "S แนวรับ");
    }
    if (toggles.atr && indicators?.latest && indicators?.atr) {
      add(indicators.latest + indicators.atr, "#fbbf24", "ATR+", true);
      add(indicators.latest - indicators.atr, "#fbbf24", "ATR-", true);
    }
    if (toggles.trade) {
      const open = orders.find(
        (o) => o.symbol === symbol && ["OPEN", "RUNNING", "PARTIAL"].includes(o.status),
      );
      if (open) {
        add(open.entry_price, "#60a5fa", "Entry");
        add(open.sl_price, "#ef4444", "SL");
        add(open.tp_price, "#10b981", "TP");
      }
    }
  }, [toggles, indicators, orders, symbol]);

  const lineButtons: { k: keyof LineToggles; label: string }[] = [
    { k: "sr", label: "แนวรับ/ต้าน" },
    { k: "trade", label: "Entry/SL/TP" },
    { k: "ema", label: "EMA" },
    { k: "atr", label: "ATR" },
  ];

  return (
    <div className="relative w-full h-full">
      {/* AI line toggles */}
      <div className="absolute z-10 left-2 top-2 flex items-center gap-1.5 bg-[#070a0f]/85 backdrop-blur-sm border border-[#26262b] rounded-lg px-1.5 py-1">
        <span className="text-[9px] text-[#5c7a9c] font-mono px-1">AI เส้น</span>
        {lineButtons.map(({ k, label }) => (
          <button
            key={k}
            onClick={() => setToggles((t) => ({ ...t, [k]: !t[k] }))}
            className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border transition ${
              toggles[k]
                ? "bg-[#10b981]/15 border-[#10b981]/40 text-[#10b981]"
                : "bg-transparent border-[#26262b] text-[#5c7a9c] hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {loading && (
        <div className="absolute z-10 inset-0 flex items-center justify-center text-[11px] text-[#5c7a9c] font-mono">
          กำลังโหลดแท่งเทียนจาก AI…
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  );
}
