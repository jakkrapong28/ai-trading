// --- อินเตอร์เฟสโครงสร้างข้อมูล ---
// Shared data structures for the trading dashboard.

export interface Balance {
  source: string;
  equity: number;
  balance: number;
  free_margin: number;
}

export interface Indicator {
  latest: number;
  rsi: number;
  atr: number;
  trend: string;
  support: number;
  resistance: number;
  // Extended fields returned by /api/state (optional for backward-compat).
  atr_source?: string;
  ema_fast?: number;
  ema_slow?: number;
  macd?: { macd: number; signal: number; histogram: number; prev_histogram?: number };
  bollinger?: { upper: number; middle: number; lower: number; width: number };
  volume?: { current: number; avg_20: number; ratio: number };
}

export interface Signal {
  action: string;
  reason: string;
  confidence?: number;
  strategy_type?: string;
  buy_score?: number;
  sell_score?: number;
  confirmations?: string[];
  statistical_score?: number;
  mtf_blocked?: boolean;
}

export interface RiskCheck {
  passed: boolean;
  checks: { name: string; pass: boolean }[];
  riskDollars: number;
  riskPct: number;
  exposurePct: number;
}

export interface Order {
  id: string;
  symbol: string;
  action: string;
  volume: number;
  entry_price: number;
  exit_price: number;
  sl_price: number;
  tp_price: number;
  pnl: number;
  fee: number;
  status: string;
  opened_at?: string;
  closed_at?: string;
}

export interface SignalActivity {
  id: string;
  ticker: string;
  action: string;
  status: "VOTING" | "APPROVED" | "REJECTED";
  reason?: string;
  sl?: number;
  tp?: number;
  time: string;
}

export interface ChatMessage {
  name: string;
  color: string;
  bg: string;
  init: string;
  text: string;
  time?: string;
}

export interface LedgerEntry {
  id: string;
  timestamp: string;
  event: string;
  description: string;
  debit: { account: string; amount: number };
  credit: { account: string; amount: number };
}

export interface TaxSummary {
  accumulatedPnL: number;
  accumulatedFees: number;
  taxableIncome: number;
  vatRate: string;
  inputVatClaimable: number;
  corporateTaxRate: string;
  estimatedIncomeTax: number;
  netAfterTax: number;
}

// ── รายการห้องจำลองในระบบบัญชาการ 3D (9 แผนก Neon Tech style) ──
export interface RoomDef {
  id: string;
  name: string;
  role: string;
  color: string;
  border: string;
  labelColor: string;
  emoji: string;
  bubble: string;
  status: "online" | "busy" | "idle";
  col: number;
  row: number;
}
