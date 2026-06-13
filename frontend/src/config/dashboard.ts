import type { RoomDef } from "@/types";

export const ROOMS_CONFIG: RoomDef[] = [
  { id: "report", name: "Report AI", role: "ฝ่ายเขียนรายงาน", color: "rgba(16, 185, 129, 0.05)", border: "#10b981", labelColor: "#10b981", emoji: "📋", bubble: "", status: "online", col: 0, row: 0 },
  { id: "audit", name: "Audit AI", role: "ฝ่ายตรวจสอบ", color: "rgba(16, 185, 129, 0.05)", border: "#10b981", labelColor: "#10b981", emoji: "🔍", bubble: "", status: "online", col: 1, row: 0 },
  { id: "ceo", name: "CEO Agent", role: "ผู้บัญชาการ", color: "rgba(16, 185, 129, 0.05)", border: "#10b981", labelColor: "#10b981", emoji: "👤", bubble: "", status: "online", col: 2, row: 0 },

  { id: "finance", name: "Finance AI", role: "ฝ่ายการเงิน ERP", color: "rgba(16, 185, 129, 0.05)", border: "#10b981", labelColor: "#10b981", emoji: "💰", bubble: "", status: "online", col: 0, row: 1 },
  { id: "ea", name: "EA Bot", role: "ฝ่ายอัลกอริทึม", color: "rgba(129, 140, 248, 0.05)", border: "#818cf8", labelColor: "#818cf8", emoji: "🤖", bubble: "", status: "busy", col: 1, row: 1 },
  { id: "chart", name: "Chart AI", role: "วิเคราะห์กราฟ", color: "rgba(16, 185, 129, 0.05)", border: "#10b981", labelColor: "#10b981", emoji: "📊", bubble: "", status: "online", col: 2, row: 1 },

  { id: "strategy", name: "Strategy AI", role: "กลยุทธ์การลงทุน", color: "rgba(251, 191, 36, 0.05)", border: "#fbbf24", labelColor: "#fbbf24", emoji: "🎯", bubble: "", status: "busy", col: 0, row: 2 },
  { id: "alert", name: "Alert AI", role: "แจ้งเตือนภัยพอร์ต", color: "rgba(251, 191, 36, 0.05)", border: "#fbbf24", labelColor: "#fbbf24", emoji: "🔔", bubble: "", status: "busy", col: 1, row: 2 },
  { id: "risk", name: "Risk AI", role: "ควบคุมความเสี่ยง", color: "rgba(239, 68, 68, 0.05)", border: "#ef4444", labelColor: "#ef4444", emoji: "⚠️", bubble: "", status: "busy", col: 2, row: 2 },
];

export const CONNECTIONS = [
  // Outer Ring
  { from: "report", to: "finance", color: "#10b981" },
  { from: "report", to: "audit", color: "#10b981" },
  { from: "audit", to: "ceo", color: "#10b981" },
  { from: "finance", to: "strategy", color: "#10b981" },
  { from: "ceo", to: "chart", color: "#10b981" },
  { from: "strategy", to: "alert", color: "#fbbf24" },
  { from: "chart", to: "risk", color: "#ef4444" },
  { from: "alert", to: "risk", color: "#ef4444" },
  // Core to Outer Connections
  { from: "ea", to: "report", color: "#10b981" },
  { from: "ea", to: "audit", color: "#10b981" },
  { from: "ea", to: "ceo", color: "#10b981" },
  { from: "ea", to: "finance", color: "#10b981" },
  { from: "ea", to: "chart", color: "#10b981" },
  { from: "ea", to: "strategy", color: "#fbbf24" },
  { from: "ea", to: "alert", color: "#fbbf24" },
  { from: "ea", to: "risk", color: "#ef4444" },
];

export const AGENT_COLORS: Record<string, string> = {
  ceo: "#10b981", chart: "#10b981", audit: "#10b981",
  ea: "#818cf8", risk: "#ef4444", finance: "#10b981",
  strategy: "#fbbf24", alert: "#fbbf24", report: "#10b981"
};

export const AGENT_CHAT_MAP: Record<string, { name: string; color: string; bg: string; init: string }> = {
  ceo: { name: "CEO Agent", color: "#3b82f6", bg: "#0d1929", init: "CEO" },
  chart: { name: "Chart AI", color: "#10b981", bg: "#0d1e10", init: "CH" },
  risk: { name: "Risk AI", color: "#ef4444", bg: "#220d0d", init: "RK" },
  ea: { name: "EA Bot", color: "#6366f1", bg: "#0d0d22", init: "EA" },
  finance: { name: "Finance AI", color: "#06b6d4", bg: "#0d1e1e", init: "FN" },
  audit: { name: "Audit AI", color: "#a855f7", bg: "#1a0d28", init: "AU" },
  alert: { name: "Alert AI", color: "#f97316", bg: "#220d0d", init: "AL" },
  strategy: { name: "Strategy AI", color: "#f59e0b", bg: "#1e1a0d", init: "ST" },
  report: { name: "Report AI", color: "#c084fc", bg: "#160d22", init: "RP" },
  system: { name: "System", color: "#94a3b8", bg: "#1e293b", init: "SYS" },
  user: { name: "คุณโทนี่ (Tony)", color: "#3b82f6", bg: "#0d1929", init: "TN" }
};

// ข้อมูลคู่เหรียญ Binance และหุ้นยอดนิยมระดับโลก
export const SYMBOLS_LIST = [
  { symbol: "XAUUSD", name: "ทองคำ (Gold / US Dollar)", category: "Forex" },
  { symbol: "EURUSD", name: "ยูโร / ดอลลาร์สหรัฐ", category: "Forex" },
  { symbol: "BTCUSDT", name: "Bitcoin / Tether (Binance)", category: "Crypto" },
  { symbol: "ETHUSDT", name: "Ethereum / Tether (Binance)", category: "Crypto" },
  { symbol: "SOLUSDT", name: "Solana / Tether (Binance)", category: "Crypto" },
  { symbol: "TSLA", name: "Tesla Motors, Inc.", category: "Stock" },
  { symbol: "AAPL", name: "Apple Inc.", category: "Stock" },
  { symbol: "NVDA", name: "NVIDIA Corporation", category: "Stock" },
  { symbol: "MSFT", name: "Microsoft Corporation", category: "Stock" },
  { symbol: "AMZN", name: "Amazon.com, Inc.", category: "Stock" }
];
