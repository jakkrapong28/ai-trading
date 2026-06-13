"use client";

import type { Indicator, Signal } from "@/types";

// Our in-house answer to Binance's "Trading Data" tab: every number here comes
// from our own backend (indicators + signal engine), not a third-party feed.
export default function AIAnalysisPanel({
  indicators,
  signal,
}: {
  indicators: Indicator | null;
  signal: Signal | null;
}) {
  if (!indicators) {
    return (
      <div className="py-8 text-center text-[10.5px] text-[#5c7a9c] font-mono">
        กำลังรอข้อมูลวิเคราะห์จาก AI…
      </div>
    );
  }

  const action = signal?.action ?? "WAIT";
  const actionColor =
    action === "BUY" ? "#10b981" : action === "SELL" ? "#f87171" : "#7a9bbf";
  const confidence = Math.round((signal?.confidence ?? 0) * 100);
  const buy = signal?.buy_score ?? 0;
  const sell = signal?.sell_score ?? 0;
  const scoreTotal = Math.max(buy + sell, 1);

  const rsi = indicators.rsi ?? 50;
  const rsiState =
    rsi >= 70 ? { t: "Overbought", c: "#f87171" } : rsi <= 30 ? { t: "Oversold", c: "#10b981" } : { t: "Neutral", c: "#7a9bbf" };

  const hist = indicators.macd?.histogram ?? 0;
  const macdBull = hist >= 0;
  const emaBull = (indicators.ema_fast ?? 0) >= (indicators.ema_slow ?? 0);
  const volRatio = indicators.volume?.ratio ?? 0;

  const fmt = (n?: number, d = 2) =>
    n === undefined || n === null ? "-" : n.toLocaleString(undefined, { maximumFractionDigits: d });

  return (
    <div className="space-y-3 font-mono pb-1">
      {/* AI Signal verdict */}
      <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-[#5c7a9c] uppercase">AI Signal</span>
          {signal?.mtf_blocked && (
            <span className="text-[8.5px] bg-amber-950 text-amber-400 px-1.5 py-0.5 rounded font-bold">
              MTF BLOCKED
            </span>
          )}
        </div>
        <div className="flex items-end justify-between">
          <div>
            <div className="text-[20px] font-black leading-none" style={{ color: actionColor }}>
              {action}
            </div>
            <div className="text-[9px] text-[#5c7a9c] mt-1">{signal?.strategy_type ?? "—"}</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-[#5c7a9c]">Confidence</div>
            <div className="text-[16px] font-bold text-white leading-none">{confidence}%</div>
          </div>
        </div>
        {/* buy vs sell score bar */}
        <div className="mt-2.5">
          <div className="flex justify-between text-[8.5px] mb-1">
            <span className="text-[#10b981]">Buy {buy}</span>
            <span className="text-[#f87171]">Sell {sell}</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden bg-[#1a1f29] flex">
            <div className="bg-[#10b981] h-full" style={{ width: `${(buy / scoreTotal) * 100}%` }} />
            <div className="bg-[#f87171] h-full" style={{ width: `${(sell / scoreTotal) * 100}%` }} />
          </div>
        </div>
        {signal?.reason && (
          <div className="text-[9.5px] text-[#7a9bbf] mt-2 leading-snug">{signal.reason}</div>
        )}
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* RSI */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">RSI (14)</span>
            <span className="text-[9px] font-bold" style={{ color: rsiState.c }}>{rsiState.t}</span>
          </div>
          <div className="text-[15px] font-bold text-white">{fmt(rsi, 1)}</div>
          <div className="relative h-1.5 mt-1.5 rounded-full bg-gradient-to-r from-[#10b981]/40 via-[#1a1f29] to-[#f87171]/40">
            <div
              className="absolute top-1/2 -translate-y-1/2 w-1 h-2.5 bg-white rounded-sm"
              style={{ left: `${Math.min(Math.max(rsi, 0), 100)}%` }}
            />
          </div>
        </div>

        {/* MACD */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">MACD</span>
            <span className="text-[9px] font-bold" style={{ color: macdBull ? "#10b981" : "#f87171" }}>
              {macdBull ? "Bullish" : "Bearish"}
            </span>
          </div>
          <div className="text-[15px] font-bold" style={{ color: macdBull ? "#10b981" : "#f87171" }}>
            {hist >= 0 ? "+" : ""}{fmt(hist)}
          </div>
          <div className="text-[8.5px] text-[#5c7a9c] mt-1.5">
            macd {fmt(indicators.macd?.macd)} · sig {fmt(indicators.macd?.signal)}
          </div>
        </div>

        {/* Trend / EMA */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">Trend</span>
            <span className="text-[9px] font-bold" style={{ color: emaBull ? "#10b981" : "#f87171" }}>
              EMA {emaBull ? "↑" : "↓"}
            </span>
          </div>
          <div className="text-[13px] font-bold text-white">{indicators.trend}</div>
          <div className="text-[8.5px] text-[#5c7a9c] mt-1.5">
            f {fmt(indicators.ema_fast)} · s {fmt(indicators.ema_slow)}
          </div>
        </div>

        {/* Volume */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">Volume</span>
            <span className="text-[9px] font-bold" style={{ color: volRatio >= 1 ? "#10b981" : "#7a9bbf" }}>
              {fmt(volRatio)}x
            </span>
          </div>
          <div className="text-[13px] font-bold text-white">{fmt(indicators.volume?.current, 0)}</div>
          <div className="text-[8.5px] text-[#5c7a9c] mt-1.5">avg20 {fmt(indicators.volume?.avg_20, 0)}</div>
        </div>

        {/* Volatility / ATR */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">ATR</span>
            <span className="text-[8px] text-[#5c7a9c]">{indicators.atr_source ?? ""}</span>
          </div>
          <div className="text-[15px] font-bold text-white">{fmt(indicators.atr)}</div>
          <div className="text-[8.5px] text-[#5c7a9c] mt-1.5">โซนแกว่ง ±{fmt(indicators.atr)}</div>
        </div>

        {/* Bollinger width */}
        <div className="bg-[#0b0f16] border border-[#26262b] rounded-lg p-2.5">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-[9px] text-[#5c7a9c] uppercase">Bollinger</span>
          </div>
          <div className="text-[13px] font-bold text-white">{fmt(indicators.bollinger?.width)}</div>
          <div className="text-[8.5px] text-[#5c7a9c] mt-1.5">
            S {fmt(indicators.support)} · R {fmt(indicators.resistance)}
          </div>
        </div>
      </div>
    </div>
  );
}
