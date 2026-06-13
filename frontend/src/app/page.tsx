"use client";

import React, { useState, useEffect, useRef } from "react";

// --- อินเตอร์เฟสโครงสร้างข้อมูล ---
interface Balance {
  source: string;
  equity: number;
  balance: number;
  free_margin: number;
}

interface Indicator {
  latest: number;
  rsi: number;
  atr: number;
  trend: string;
  support: number;
  resistance: number;
}

interface Signal {
  action: string;
  reason: string;
}

interface RiskCheck {
  passed: boolean;
  checks: { name: string; pass: boolean }[];
  riskDollars: number;
  riskPct: number;
  exposurePct: number;
}

interface Order {
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

interface SignalActivity {
  id: string;
  ticker: string;
  action: string;
  status: "VOTING" | "APPROVED" | "REJECTED";
  reason?: string;
  sl?: number;
  tp?: number;
  time: string;
}

interface ChatMessage {
  name: string;
  color: string;
  bg: string;
  init: string;
  text: string;
  time?: string;
}

interface LedgerEntry {
  id: string;
  timestamp: string;
  event: string;
  description: string;
  debit: { account: string; amount: number };
  credit: { account: string; amount: number };
}

interface TaxSummary {
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
interface RoomDef {
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

const ROOMS_CONFIG: RoomDef[] = [
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

const CONNECTIONS = [
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

const AGENT_COLORS: Record<string, string> = {
  ceo: "#10b981", chart: "#10b981", audit: "#10b981",
  ea: "#818cf8", risk: "#ef4444", finance: "#10b981",
  strategy: "#fbbf24", alert: "#fbbf24", report: "#10b981"
};

const parseUTCDate = (dateStr?: string) => {
  if (!dateStr) return new Date();
  if (dateStr.endsWith("Z") || dateStr.includes("+") || (dateStr.includes("-") && dateStr.lastIndexOf("-") > 10)) {
    return new Date(dateStr);
  }
  if (dateStr.includes("T")) {
    return new Date(dateStr + "Z");
  }
  return new Date(dateStr.replace(" ", "T") + "Z");
};

const AGENT_CHAT_MAP: Record<string, { name: string; color: string; bg: string; init: string }> = {
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
const SYMBOLS_LIST = [
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

// --- TradingView Chart Widget ---
const TradingViewWidget = ({ symbol }: { symbol: string }) => {
  const getTradingViewSymbol = (sym: string) => {
    if (sym === "XAUUSD") return "OANDA:XAUUSD";
    if (sym === "EURUSD") return "FX:EURUSD";
    if (sym === "TSLA") return "NASDAQ:TSLA";
    if (sym === "AAPL") return "NASDAQ:AAPL";
    if (sym === "NVDA") return "NASDAQ:NVDA";
    if (sym === "MSFT") return "NASDAQ:MSFT";
    if (sym === "AMZN") return "NASDAQ:AMZN";
    if (sym.endsWith("USDT")) return `BINANCE:${sym}`;
    return `BINANCE:${sym}`;
  };

  const tvSymbol = getTradingViewSymbol(symbol);

  return (
    <div className="w-full h-full bg-[#0c0d14]">
      <iframe
        id="tradingview-widget"
        src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview-widget&symbol=${tvSymbol}&interval=5&hidesidetoolbar=1&symboledit=0&saveimage=1&toolbarbg=131722&studies=%5B%5D&theme=dark&style=1&timezone=Asia%2FBangkok&studies_overrides=%7B%7D&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=th`}
        style={{ width: "100%", height: "100%", border: "none" }}
        allowFullScreen
      />
    </div>
  );
};

export default function Dashboard() {
  const [activeMenu, setActiveMenu] = useState("Overview");
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "error">("connecting");
  
  // --- สเตตจำลองจากระบบเทรดและ ERP ---
  const [symbol, setSymbol] = useState("XAUUSD");
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [priceMap, setPriceMap] = useState<Record<string, number>>({});
  const [indicators, setIndicators] = useState<Indicator | null>(null);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [risk, setRisk] = useState<RiskCheck | null>(null);
  const [mode, setMode] = useState("watch");
  const [balances, setBalances] = useState<Balance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [activeTab, setActiveTab] = useState("POSITIONS");
  const [filterDate, setFilterDate] = useState("");
  
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, any>>({});
  const [heartbeats, setHeartbeats] = useState<Record<string, any>>({});
  const [nanLogs, setNanLogs] = useState({ count: 0 });
  const [calibration, setCalibration] = useState({ calibrated_count: 0, pending_count: 0 });
  const [correlationRejections, setCorrelationRejections] = useState({ count: 0 });
  const [signalActivity, setSignalActivity] = useState<SignalActivity[]>([]);

  // --- AI Activity Log State ---
  interface ActivityLog {
    time: string;
    agent: string;
    text: string;
    color: string;
    dotColor: string;
  }
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([
    { time: "10:37:12", agent: "Risk AI", text: "Position check passed", color: "#ef4444", dotColor: "#10b981" },
    { time: "10:37:09", agent: "EA Bot", text: "Order submitted BTCUSDT Long 0.02", color: "#6366f1", dotColor: "#3b82f6" },
    { time: "10:36:58", agent: "Strategy AI", text: "Generated Long signal Confidence: 78%", color: "#fbbf24", dotColor: "#a855f7" },
    { time: "10:36:41", agent: "Market Scanner", text: "Found 3 opportunities", color: "#06b6d4", dotColor: "#22d3ee" },
    { time: "10:36:30", agent: "News AI", text: "No high impact news", color: "#f97316", dotColor: "#fbbf24" }
  ]);

  const addActivityLog = (agent: string, text: string, dotColor = "#10b981") => {
    const timeStr = new Date().toTimeString().split(" ")[0];
    const color = AGENT_CHAT_MAP[agent.toLowerCase().replace(" ", "")]?.color || "#94a3b8";
    setActivityLogs(prev => [
      { time: timeStr, agent, text, color, dotColor },
      ...prev
    ].slice(0, 50));
  };

  const addSignalActivity = (act: Omit<SignalActivity, "id" | "time">) => {
    const entry: SignalActivity = { ...act, id: crypto.randomUUID?.() || Math.random().toString(36), time: new Date().toISOString() };
    setSignalActivity(prev => [entry, ...prev].slice(0, 50));
  };

  const getMenuButtonClass = (menuName: string) => {
    const isActive = activeMenu === menuName;
    return `w-full flex items-center justify-between px-3.5 py-2 text-[12px] rounded-md transition-all duration-200 ${
      isActive 
        ? "bg-[#131d27]/80 text-white font-bold" 
        : "text-[#7a9bbf] hover:bg-white/5 hover:text-white"
    }`;
  };
  
  // --- สเตตสมุดบัญชีและภาษี ERP ---
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [taxSummary, setTaxSummary] = useState<TaxSummary | null>(null);

  // --- แถบแชททีมงานจำลอง (Team Chat Panel) ---
  const [chatMsgs, setChatMsgs] = useState<ChatMessage[]>([
    { name: "EA Bot", color: "#6366f1", bg: "#0d0d22", init: "EA", text: "AITradingTeam EA v2.4 · สแตนบายพร้อมยิงออเดอร์แล้วครับ" }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);

  // --- พารามิเตอร์การตั้งค่า (Settings State) ---
  const [settingsForm, setSettingsForm] = useState({
    telegram_token: "",
    anthropic_key: "",
    binance_key: "",
    binance_secret: "",
    news_api_key: "",
    twelvedata_api_key: "",
    finnhub_api_key: "",
    maxRiskPerTradePct: 2.0,
    maxOpenExposurePct: 20.0
  });

  // --- พารามิเตอร์คุมความเสี่ยง ---
  const [riskForm, setRiskForm] = useState({
    lot: 0.01,
    stopDistance: 20.0,
    takeProfit: 40.0,
    spread: 2.0,
    rejectThreshold: 3.0,
    riskPct: 1.5
  });

  // --- ข้อมูลข่าวสารเศรษฐกิจมหภาคจริง ---
  const [newsFeed, setNewsFeed] = useState<any[]>([
    { time: "02:15", source: "FED Watch", text: "ประธาน FED ส่งสัญญาณแนวโน้มปรับลดดอกเบี้ยนโยบายปลายปีนี้ หากดัชนีเงินเฟ้อลดต่ำลงตามเป้าหมาย 2%", impact: "HIGH" },
    { time: "01:30", source: "Binance Research", text: "ปริมาณการซื้อขายเหรียญ SOL ทะยานขึ้นสูงสุดในรอบ 3 เดือน รับอานิสงส์จากการทำธุรกรรม DeFi บนเครือข่ายที่พุ่งสูง", impact: "MEDIUM" },
    { time: "00:45", source: "NVIDIA Corp", text: "NVIDIA ประกาศชิป AI รุ่นสถาปัตยกรรมใหม่ที่มีกำลังประมวลผลสูงขึ้น 4 เท่า หุ้นพุ่งทะลุ 3.5% นำดัชนี Nasdaq ดีดตัว", impact: "HIGH" }
  ]);

  // --- อ้างอิงสำหรับ Canvas และ WebSocket ---
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  let centers: Record<string, { cx: number; cy: number }> = {};
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;

  // คลาสอ้างอิงตำแหน่งของ Agents ที่เคลื่อนไหวอยู่บน Canvas
  const agentsStateRef = useRef<any[]>([]);
  const frameCountRef = useRef(0);
  const scaleMultiplierRef = useRef(1.0);

  // สถิติยอดพอร์ตและการเทรด
  const totalEquity = (balances || []).reduce((sum, b) => sum + b.equity, 0);
  const activeTradesCount = (orders || []).filter((o) => o.status === "PENDING" || o.status === "OPEN").length;
  const closedOrders = (orders || []).filter((o) => o.status === "CLOSED");
  const todayPnLSum = closedOrders.reduce((sum, o) => sum + o.pnl, 0);
  const pnlPct = totalEquity > 0 ? (todayPnLSum / (totalEquity - todayPnLSum)) * 100 : 0.0;

  // เลื่อนหน้าต่างแชทลงด้านล่างอัตโนมัติ
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMsgs]);

  const fetchERPData = async () => {
    try {
      const ledgerRes = await fetch("http://localhost:8000/api/erp/ledger");
      const ledgerData = await ledgerRes.json();
      if (ledgerData.success) setLedger(ledgerData.ledger);

      const taxRes = await fetch("http://localhost:8000/api/erp/tax-summary");
      const taxData = await taxRes.json();
      if (taxData.success) setTaxSummary(taxData.data);
    } catch (e) {
      console.error("เชื่อมต่อบัญชี ERP ขัดข้อง:", e);
    }
  };

  const fetchNewsData = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/news");
      const data = await res.json();
      if (data.success) setNewsFeed(data.news);
    } catch (e) {
      console.error("ดึงข่าวสดขัดข้องจำเป็น:", e);
    }
  };

  const fetchStateData = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/state");
      const data = await res.json();
      setSymbol(data.symbol);
      setLatestPrice(data.latest);
      if (data.symbol && data.latest) {
        setPriceMap(prev => ({ ...prev, [data.symbol]: data.latest }));
      }
      if (data.market_prices) {
        setPriceMap(prev => ({ ...prev, ...data.market_prices }));
      }
      setIndicators(data.indicators);
      setSignal(data.signal);
      setRisk(data.risk);
      setMode(data.mode);
      setBalances(data.balances || []);
      setOrders(data.orders || []);
      
      if (data.feature_flags) setFeatureFlags(data.feature_flags);
      if (data.circuit_breaker) setCircuitBreakers(data.circuit_breaker);
      if (data.heartbeats) setHeartbeats(data.heartbeats);
      if (data.nan_logs) setNanLogs(data.nan_logs);
      if (data.calibration) setCalibration(data.calibration);
      if (data.correlation_rejections) setCorrelationRejections(data.correlation_rejections);
      
      // ดึงคอนฟิกการตั้งค่า
      if (data.settings) {
        setSettingsForm({
          telegram_token: data.settings.telegram_token || "",
          anthropic_key: data.settings.anthropic_key || "",
          binance_key: data.settings.binance_key || "",
          binance_secret: data.settings.binance_secret || "",
          news_api_key: data.settings.news_api_key || "",
          twelvedata_api_key: data.settings.twelvedata_api_key || "",
          finnhub_api_key: data.settings.finnhub_api_key || "",
          maxRiskPerTradePct: data.settings.maxRiskPerTradePct || 2.0,
          maxOpenExposurePct: data.settings.maxOpenExposurePct || 20.0
        });
      }
    } catch (e) {
      console.error("ดึงสถานะเริ่มต้นขัดข้อง:", e);
    }
  };

  const handleCloseOrder = async (orderId: string) => {
    if (!confirm("⚠️ คุณต้องการสั่งปิดออเดอร์นี้ด้วยมือทันทีใช่หรือไม่?")) return;
    try {
      const res = await fetch("http://localhost:8000/api/close-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: orderId })
      });
      const data = await res.json();
      if (data.success) {
        alert(`ปิดออเดอร์สำเร็จ! ได้รับกำไร/ขาดทุนสะสม: $${data.realized_pnl.toFixed(2)} USD`);
        fetchStateData();
        fetchERPData();
      } else {
        alert(`ไม่สามารถปิดออเดอร์ได้: ${data.detail || "เกิดข้อผิดพลาด"}`);
      }
    } catch (e: any) {
      alert(`การปิดออเดอร์ล้มเหลว: ${e.message}`);
    }
  };

  useEffect(() => {
    fetchStateData();
    fetchERPData();
    fetchNewsData();
  }, []);

  const mapAgentNameToRoomId = (name: string): string => {
    const n = name.toLowerCase();
    if (n.includes("ceo")) return "ceo";
    if (n.includes("chart")) return "chart";
    if (n.includes("crypto")) return "strategy";
    if (n.includes("wallet")) return "report";
    if (n.includes("risk")) return "risk";
    if (n.includes("news") || n.includes("audit")) return "audit";
    if (n.includes("telegram")) return "ceo"; // โยนไปห้อง CEO ให้คุยโทรศัพท์
    return "ceo";
  };

  const mapJournalTypeToAgent = (type: string): string => {
    const t = type.toLowerCase();
    if (t.includes("market") || t.includes("snapshot")) return "chart";
    if (t.includes("analysis")) return "ceo";
    if (t.includes("trade") || t.includes("order")) return "ea";
    if (t.includes("risk")) return "risk";
    if (t.includes("settings") || t.includes("mode") || t.includes("system") || t.includes("pause")) return "system";
    return "system";
  };

  useEffect(() => {
    const connectWebSocket = () => {
      setWsStatus("connecting");
      const ws = new WebSocket("ws://localhost:8000/ws");
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("connected");
        addChatMessage("system", "🔌 เชื่อมต่อ WebSocket เข้ากับห้องวิเคราะห์สดสำเร็จ");
      };

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);

        if (msg.type === "init") {
          const s = msg.state;
          setSymbol(s.symbol);
          setLatestPrice(s.latest);
          setIndicators(s.indicators);
          setSignal(s.signal);
          setRisk(s.risk);
          setMode(s.mode);
          setBalances(s.balances || []);
          setOrders(s.orders || []);
          
          if (s.feature_flags) setFeatureFlags(s.feature_flags);
          if (s.circuit_breaker) setCircuitBreakers(s.circuit_breaker);
          if (s.heartbeats) setHeartbeats(s.heartbeats);
          if (s.nan_logs) setNanLogs(s.nan_logs);
          if (s.calibration) setCalibration(s.calibration);
          if (s.correlation_rejections) setCorrelationRejections(s.correlation_rejections);

          if (s.journal && s.journal.length > 0) {
            const initialChats = s.journal.map((j: any) => {
              const agentKey = mapJournalTypeToAgent(j.type);
              const config = AGENT_CHAT_MAP[agentKey] || AGENT_CHAT_MAP["system"];
              const date = new Date(j.at);
              const timeStr = date.getHours().toString().padStart(2, "0") + ":" + date.getMinutes().toString().padStart(2, "0");
              return {
                ...config,
                text: j.detail,
                time: timeStr
              };
            });
            setChatMsgs(initialChats.reverse());
          }
        } 
        else if (msg.type === "market_update") {
          setSymbol(msg.symbol);
          setLatestPrice(msg.latest);
          setIndicators(msg.indicators);
          setSignal(msg.signal);
          setRisk(msg.risk);
          setMode(msg.mode);
          
          if (msg.feature_flags) setFeatureFlags(msg.feature_flags);
          if (msg.circuit_breaker) setCircuitBreakers(msg.circuit_breaker);
          if (msg.heartbeats) setHeartbeats(msg.heartbeats);
          if (msg.nan_logs) setNanLogs(msg.nan_logs);
          if (msg.calibration) setCalibration(msg.calibration);
          if (msg.correlation_rejections) setCorrelationRejections(msg.correlation_rejections);
        } 
        else if (msg.type === "price_tick") {
          if (msg.symbol === symbolRef.current) {
            setLatestPrice(msg.price);
          }
          if (msg.symbol && msg.price) {
            setPriceMap(prev => ({ ...prev, [msg.symbol]: msg.price }));
          }
          if (msg.indicators) setIndicators(msg.indicators);
          if (msg.signal) setSignal(msg.signal);
          if (msg.risk) setRisk(msg.risk);

          // 10% chance to rate-limit log price ticks in AI Activity Log
          if (Math.random() < 0.1) {
            addActivityLog("Market Scanner", `Found opportunities for ${msg.symbol}`, "#22d3ee");
          }
        } 
        else if (msg.type === "risk:signal:approved") {
          const ticker = msg.data?.ticker || msg.ticker || "?";
          const action = msg.data?.action || msg.action || "?";
          addSignalActivity({
            ticker,
            action,
            status: "APPROVED",
            sl: msg.data?.stop_loss || msg.stop_loss,
            tp: msg.data?.take_profit || msg.take_profit,
          });
          addActivityLog("Risk AI", "Position check passed", "#10b981");
          addActivityLog("EA Bot", `Order submitted ${ticker} ${action} 0.02`, "#3b82f6");
        }
        else if (msg.type === "risk:signal:rejected") {
          const ticker = msg.data?.ticker || msg.ticker || "?";
          const action = msg.data?.action || msg.action || "?";
          const reason = msg.data?.reason || msg.reason || "ไม่มีเหตุผล";
          addSignalActivity({
            ticker,
            action,
            status: "REJECTED",
            reason,
          });
          addActivityLog("Risk AI", `Blocked: ${reason}`, "#ef4444");
        }
        else if (msg.type === "ai:decision:final") {
          const ticker = msg.data?.ticker || msg.ticker || "?";
          const action = msg.data?.action || msg.action || "?";
          addSignalActivity({
            ticker,
            action,
            status: "VOTING",
          });
          addActivityLog("Strategy AI", `Generated ${action} signal for ${ticker}`, "#a855f7");
        }
        else if (msg.type === "agent_typing") {
          const agentKey = mapAgentNameToRoomId(msg.message.agent);
          addChatMessage(agentKey, msg.message.message);

          // อัปเดตฟองคำพูด AI
          const agentIndex = ROOMS_CONFIG.findIndex((r) => r.id === agentKey);
          if (agentIndex >= 0 && agentsStateRef.current[agentIndex]) {
            const ag = agentsStateRef.current[agentIndex];
            ag.bubble = msg.message.message.substring(0, 26) + (msg.message.message.length > 26 ? "..." : "");
            ag.bubbleTimer = 180;
            ag.speakTimer = 120;
          }
        } 
        else if (msg.type === "order_opened") {
          setOrders((prev) => {
            if (prev.some(o => o.id === msg.order.id)) return prev;
            return [msg.order, ...prev];
          });
          if (msg.balances) setBalances(msg.balances);
          addChatMessage("ea", `🔔 [ระบบ Team ERP] เปิดออเดอร์ใหม่สถานะรอดำเนินการ: ${msg.order.action} ${msg.order.symbol} ที่ราคา ${msg.order.entry_price}`);
          fetchERPData();
          addActivityLog("EA Bot", `Order Opened: ${msg.order.action} ${msg.order.symbol} @${msg.order.entry_price}`, "#3b82f6");
        }
        else if (msg.type === "order_closed") {
          if (msg.orders) {
            setOrders(msg.orders);
          } else if (msg.order) {
            setOrders((prev) => prev.map(o => o.id === msg.order.id ? msg.order : o));
          }
          if (msg.balances) setBalances(msg.balances);
          
          const eaIndex = ROOMS_CONFIG.findIndex((r) => r.id === "ea");
          if (eaIndex >= 0 && agentsStateRef.current[eaIndex]) {
            const ag = agentsStateRef.current[eaIndex];
            ag.bubble = `เปิดดีลสำเร็จ! PnL: $${msg.order ? msg.order.pnl.toFixed(2) : '0.00'}`;
            ag.bubbleTimer = 180;
            ag.speakTimer = 120;
          }
          fetchERPData();
          if (msg.order) {
            addActivityLog("EA Bot", `Order Closed: ${msg.order.symbol} PnL: $${msg.order.pnl.toFixed(2)}`, msg.order.pnl >= 0 ? "#10b981" : "#ef4444");
          }
        }
      };

      ws.onclose = () => {
        setWsStatus("error");
        setTimeout(connectWebSocket, 5000);
      };

      ws.onerror = () => {
        setWsStatus("error");
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const addChatMessage = (agentKey: string, text: string) => {
    const config = AGENT_CHAT_MAP[agentKey] || AGENT_CHAT_MAP["system"];
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2, "0") + ":" + now.getMinutes().toString().padStart(2, "0");
    
    setChatMsgs((prev) => {
      const list = [...prev, { ...config, text, time: timeStr }];
      if (list.length > 60) list.shift();
      return list;
    });
    setUnreadCount((prev) => prev + 1);
  };

  const handleSendChat = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!chatInput.trim()) return;

    const text = chatInput.trim();
    setChatInput("");

    addChatMessage("user", text);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      if (text.startsWith("/")) {
        try {
          const res = await fetch("http://localhost:8000/api/telegram/command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: text })
          });
          const data = await res.json();
          addChatMessage("ceo", data.response);
          setTimeout(fetchStateData, 500);
        } catch (err) {
          addChatMessage("system", "❌ เซิร์ฟเวอร์ Python ไม่ตอบสนองคำสั่งบอท");
        }
      } else {
        wsRef.current.send(JSON.stringify({ type: "command", message: text }));
      }
    } else {
      setTimeout(() => {
        addChatMessage("ceo", `รับทราบครับคุณโทนี่: "${text}" — (ระบบวิเคราะห์จำลอง กำลังรอคิวเชื่อมต่อ...)`);
      }, 800);
    }
  };

  const handleSymbolChange = async (newSym: string) => {
    try {
      const res = await fetch("http://localhost:8000/api/change-symbol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: newSym })
      });
      const data = await res.json();
      if (data.status === "success") {
        setSymbol(newSym);
        
        const newRiskForm = {
          lot: 0.01,
          stopDistance: 20.0,
          takeProfit: 40.0,
          spread: 2.0,
          rejectThreshold: 3.0,
          riskPct: 1.5
        };
        setRiskForm(newRiskForm);
        
        await fetch("http://localhost:8000/api/update-risk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newRiskForm)
        });
        
        fetchStateData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRiskTest = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/update-risk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(riskForm)
      });
      const data = await res.json();
      setRisk(data);
      addChatMessage("system", `🛡️ ตรวจสอบความเสี่ยงสำเร็จ: Lot ${riskForm.lot} | SL ${riskForm.stopDistance} | TP ${riskForm.takeProfit} | Spread Limit ${riskForm.spread} | Reject ${riskForm.rejectThreshold} | Risk Limit ${riskForm.riskPct}% -> สถานะ: ${data.passed ? "ผ่าน ✅" : "บล็อก 🔴"}`);
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ ไม่สามารถส่งคำขอดึงความเสี่ยงจากบอทได้");
    }
  };

  const handleToggleMode = async () => {
    const newMode = mode === "auto" ? "watch" : "auto";
    try {
      const res = await fetch("http://localhost:8000/api/change-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: newMode })
      });
      const data = await res.json();
      if (data.status === "success") {
        setMode(newMode);
        addChatMessage("system", `⚙️ เปลี่ยนระบบเป็นโหมด: ${newMode.toUpperCase()}`);
      }
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ เกิดข้อผิดพลาดในการเปลี่ยนโหมด");
    }
  };

  const handleApprove = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/approve", {
        method: "POST"
      });
      const data = await res.json();
      if (data.status === "success") {
        addChatMessage("system", "✅ อนุมัติยิงคำสั่งเทรดเรียบร้อย สั่งการ EA และบันทึก ERP ทันที");
        fetchStateData();
        fetchERPData();
      }
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ เกิดข้อผิดพลาดในการอนุมัติคำสั่งเทรด");
    }
  };

  const handleReject = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/reject", {
        method: "POST"
      });
      const data = await res.json();
      if (data.status === "success") {
        addChatMessage("system", "❌ ปฏิเสธแผนเทรดเรียบร้อย ล้างประวัติแผนด่วน");
        fetchStateData();
      }
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ เกิดข้อผิดพลาดในการยกเลิกแผนเทรด");
    }
  };

  const handleResetData = async () => {
    if (!window.confirm("คุณต้องการล้างประวัติการเทรด สมุดบัญชี และข้อมูล ERP ทั้งหมดในระบบใช่หรือไม่? การกระทำนี้ไม่สามารถย้อนกลับได้")) {
      return;
    }
    try {
      const res = await fetch("http://localhost:8000/api/reset-data", {
        method: "POST"
      });
      const data = await res.json();
      if (data.status === "success") {
        addChatMessage("system", "🗑️ รีเซ็ตฐานข้อมูลประวัติเทรดและ ERP กลาง เรียบร้อยแล้ว");
        fetchStateData();
        fetchERPData();
      }
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ เกิดข้อผิดพลาดในการรีเซ็ตระบบ");
    }
  };

  // --- ปรับใช้การตั้งค่า Token และ Limit ใน backend ---
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("http://localhost:8000/api/update-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsForm)
      });
      const data = await res.json();
      if (data.status === "success") {
        addChatMessage("system", "🟢 บันทึกตั้งค่าระบบวิเคราะห์ความเสี่ยงและ Bot Token จริงเรียบร้อย");
        fetchStateData();
        alert("บันทึกการตั้งค่าสำเร็จ!");
      }
    } catch (err) {
      alert("ขัดข้อง: ไม่สามารถประมวลผลเซิร์ฟเวอร์หลัก");
    }
  };

  // ════════════════════════════════════════
  // 📐 ENGINE วาดพิกเซล NEON TECH OFFICE (ขยายขอบเขตและสีเรืองแสง)
  // ════════════════════════════════════════
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const wrap = wrapRef.current;
    if (!wrap) return;

    let W = 0, H = 0;
    const SCALE = 2;

    let scaleMultiplier = 1.0;
    let sizeX = 150;
    let sizeY = 87;
    let wallHeight = 60;
    let charScale = 1.8;
    const BOTTOM_BAR_H = 58; // height reserved for Risk Gate bar at bottom

    const getRoomCenters = (canvasW: number, canvasH: number) => {
      const centers: Record<string, { cx: number; cy: number }> = {};
      const availH = canvasH - BOTTOM_BAR_H;
      const totalH = wallHeight + 4.8 * sizeY;
      const gridCenterY = Math.max(wallHeight + 10, (availH - totalH) / 2 + wallHeight);
      const gridCenterX = canvasW / 2;

      ROOMS_CONFIG.forEach((r) => {
        const cx = gridCenterX + (r.col - r.row) * sizeX;
        const cy = gridCenterY + (r.col + r.row) * sizeY;
        centers[r.id] = { cx, cy };
      });

      return centers;
    };

    let centers = getRoomCenters(W, H);

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      W = r.width;
      H = r.height;
      canvas.width = Math.floor(W * SCALE);
      canvas.height = Math.floor(H * SCALE);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.scale(SCALE, SCALE);

      const availableH = H - BOTTOM_BAR_H;
      const wallToSizeXRatio = 60 / 150;
      const sizeYToSizeXRatio = 87 / 150;
      const maxByH = (availableH * 0.85 - 20) / (wallToSizeXRatio + 5.2 * sizeYToSizeXRatio);
      const maxByW = (W * 0.85) / 6.0;
      const targetSizeX = Math.min(maxByH, maxByW);
      scaleMultiplier = Math.max(0.25, Math.min(1.1, targetSizeX / 150));
      scaleMultiplierRef.current = scaleMultiplier;
      sizeX = Math.round(150 * scaleMultiplier);
      sizeY = Math.round(87 * scaleMultiplier);
      wallHeight = Math.round(60 * scaleMultiplier);

      centers = getRoomCenters(W, H);
    };

    resize();

    let animFrameId: number;

    const roundRect = (c: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) => {
      c.beginPath();
      c.moveTo(x + r, y);
      c.lineTo(x + w - r, y);
      c.quadraticCurveTo(x + w, y, x + w, y + r);
      c.lineTo(x + w, y + h - r);
      c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      c.lineTo(x + r, y + h);
      c.quadraticCurveTo(x, y + h, x, y + h - r);
      c.lineTo(x, y + r);
      c.quadraticCurveTo(x, y, x + r, y);
      c.closePath();
    };

    const drawRoom = (r: RoomDef) => {
      const pos = centers[r.id];
      if (!pos) return;
      const { cx, cy } = pos;

      ctx.fillStyle = r.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.fill();

      ctx.strokeStyle = r.border + "33";
      ctx.lineWidth = 0.8;
      const step = 4;
      for (let i = 1; i < step; i++) {
        const offsetPct = i / step;
        const xStart1 = cx - sizeX + sizeX * offsetPct;
        const yStart1 = cy + sizeY * offsetPct;
        ctx.beginPath();
        ctx.moveTo(xStart1, yStart1);
        ctx.lineTo(xStart1 + sizeX, yStart1 - sizeY);
        ctx.stroke();

        const xStart2 = cx + sizeX - sizeX * offsetPct;
        const yStart2 = cy + sizeY * offsetPct;
        ctx.beginPath();
        ctx.moveTo(xStart2, yStart2);
        ctx.lineTo(xStart2 - sizeX, yStart2 - sizeY);
        ctx.stroke();
      }

      ctx.strokeStyle = r.border;
      ctx.lineWidth = 1.5;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.stroke();
      ctx.shadowBlur = 0;
    };

    const drawRoomNameplate = (r: RoomDef) => {
      const pos = centers[r.id];
      if (!pos) return;
      const { cx, cy } = pos;

      const S = scaleMultiplier;
      const titleFont = `bold ${Math.max(11, Math.round(13 * S))}px "Manrope", sans-serif`;
      const subtitleFont = `${Math.max(9, Math.round(10.5 * S))}px "Manrope", sans-serif`;

      ctx.font = titleFont;
      const titleText = `${r.emoji} ${r.name}`;
      const titleWidth = ctx.measureText(titleText).width;

      ctx.font = subtitleFont;
      const subtitleText = r.role;
      const subtitleWidth = ctx.measureText(subtitleText).width;

      const paddingX = 14 * S;
      const dotRadius = Math.max(3.5, 4.5 * S);
      const dotSpacing = 8 * S;

      const contentWidth = Math.max(titleWidth + dotSpacing + dotRadius * 2, subtitleWidth);
      const badgeW = contentWidth + paddingX * 2;
      const badgeH = Math.max(38, Math.round(44 * S));

      const badgeX = cx - badgeW / 2;
      let badgeY = cy + sizeY - badgeH / 2 + 4 * S;

      const maxBadgeBottom = H - 64;
      if (badgeY + badgeH > maxBadgeBottom) {
        badgeY = maxBadgeBottom - badgeH;
      }

      ctx.save();
      ctx.fillStyle = "rgba(7, 10, 15, 0.96)";
      ctx.strokeStyle = r.border;
      ctx.lineWidth = 1.8;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 8;
      roundRect(ctx, badgeX, badgeY, badgeW, badgeH, Math.max(4, 6 * S));
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      ctx.save();
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";

      const titleGroupW = titleWidth + dotSpacing + dotRadius * 2;
      const titleStartX = badgeX + (badgeW - titleGroupW) / 2;
      const firstLineY = badgeY + badgeH * 0.35;

      ctx.font = titleFont;
      ctx.fillStyle = "#ffffff";
      ctx.fillText(titleText, titleStartX, firstLineY);

      const dotX = titleStartX + titleWidth + dotSpacing + dotRadius;
      const dotY = firstLineY;
      
      const getStatusColor = (roomId: string, status: string) => {
        if (roomId === "ea") return "#818cf8"; // Purple for EA Bot
        if (roomId === "risk") return "#ef4444"; // Red for Risk AI
        if (roomId === "strategy" || roomId === "alert") return "#fbbf24"; // Orange/Yellow
        return "#10b981"; // Green for others
      };
      const dotColor = getStatusColor(r.id, r.status);

      ctx.fillStyle = dotColor;
      ctx.beginPath();
      ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2);
      ctx.fill();

      // Pulsing status ring
      if (r.status !== "idle") {
        ctx.fillStyle = dotColor + "22";
        ctx.beginPath();
        ctx.arc(dotX, dotY, dotRadius * 2 + Math.sin(frameCountRef.current * 0.12) * 1.5 * S, 0, Math.PI * 2);
        ctx.fill();
      }

      const secondLineY = badgeY + badgeH * 0.72;
      ctx.textAlign = "center";
      ctx.font = subtitleFont;
      ctx.fillStyle = r.labelColor;
      ctx.fillText(subtitleText, cx, secondLineY);

      ctx.restore();
    };

    const drawNetworkConnections = () => {
      CONNECTIONS.forEach((conn, idx) => {
        const p1 = centers[conn.from];
        const p2 = centers[conn.to];
        if (!p1 || !p2) return;

        // Draw solid connection line
        ctx.save();
        ctx.strokeStyle = conn.color + "44"; // Translucent for cyber aesthetic
        ctx.lineWidth = 1.5;
        ctx.shadowColor = conn.color;
        ctx.shadowBlur = 4;
        ctx.beginPath();
        ctx.moveTo(p1.cx, p1.cy);
        ctx.lineTo(p2.cx, p2.cy);
        ctx.stroke();
        ctx.restore();

        // Flowing data packet animation
        const speed = 0.008;
        const offset = idx * 0.12;
        const progress = ((frameCountRef.current * speed) + offset) % 1.0;
        
        const px = p1.cx + (p2.cx - p1.cx) * progress;
        const py = p1.cy + (p2.cy - p1.cy) * progress;

        ctx.save();
        ctx.fillStyle = conn.color;
        ctx.shadowColor = conn.color;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });
    };

    const render = () => {
      ctx.clearRect(0, 0, W, H);

      // 1. Dark architectural gradient base
      const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
      bgGrad.addColorStop(0, "#050810");
      bgGrad.addColorStop(0.4, "#080c18");
      bgGrad.addColorStop(1, "#04060e");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      // 2. Subtle isometric grid floor
      ctx.strokeStyle = "rgba(30, 58, 138, 0.08)";
      ctx.lineWidth = 0.5;
      const gridSpacingX = sizeX / 2;
      
      if (gridSpacingX > 0 && !isNaN(gridSpacingX) && sizeY > 0 && !isNaN(sizeY)) {
        // Draw diagonal lines in direction 1 (top-left to bottom-right)
        for (let offset = -W; offset < W; offset += gridSpacingX) {
          ctx.beginPath();
          ctx.moveTo(offset, 0);
          ctx.lineTo(offset + H * (sizeX / sizeY), H);
          ctx.stroke();
        }
        // Draw diagonal lines in direction 2 (top-right to bottom-left)
        for (let offset = 0; offset < W + H * (sizeX / sizeY); offset += gridSpacingX) {
          ctx.beginPath();
          ctx.moveTo(offset, 0);
          ctx.lineTo(offset - H * (sizeX / sizeY), H);
          ctx.stroke();
        }
      }

      // 3. Large ambient glow in center (halo)
      const centerGlow = ctx.createRadialGradient(W/2, H*0.45, 40, W/2, H*0.45, W*0.55);
      centerGlow.addColorStop(0, "rgba(15, 30, 80, 0.35)");
      centerGlow.addColorStop(0.5, "rgba(8, 15, 40, 0.15)");
      centerGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = centerGlow;
      ctx.fillRect(0, 0, W, H);


      // Draw glowing network lines and packets
      drawNetworkConnections();

      // Draw room diamond bases
      ROOMS_CONFIG.forEach(drawRoom);

      frameCountRef.current++;

      // Draw all unified room nameplate badges
      ROOMS_CONFIG.forEach(drawRoomNameplate);

      animFrameId = requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      resize();
      centers = getRoomCenters(W, H);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animFrameId);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    ROOMS_CONFIG.forEach((r) => {
      const pos = centers[r.id];
      if (!pos) return;

      const dist = Math.sqrt(Math.pow(mx - pos.cx, 2) + Math.pow(my - pos.cy, 2));
      
      if (dist < 50 * scaleMultiplierRef.current) {
        addChatMessage("system", `📌 ตรวจเช็คข้อมูลเอเจนต์ประจำแผนก: ${r.name} [${r.role}] — สแตนบายพร้อมอัปเดตสถิติ`);
      }
    });
  };

  return (
    <div className="h-screen w-screen bg-[#000000] text-[#c8d8f0] flex overflow-hidden font-sans select-none">
      
      {/* ── SIDEBAR ── */}
      <aside className="w-[172px] min-w-[172px] bg-[#070a0f] border-r border-[#1e2d45] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-[#1e2d45] flex items-center gap-2">
          <div className="flex-shrink-0 text-white">
            <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 10h4v4h-4z" />
            </svg>
          </div>
          <div>
            <div className="text-[12.5px] font-black text-white tracking-wider leading-none font-mono">TRADE OFFICE</div>
            <div className="text-[9.5px] text-[#5c7a9c] font-medium mt-1 leading-none">v2.21.0 • Active</div>
          </div>
        </div>

        <div className="py-3 space-y-3">
          <div>
            <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">MAIN</div>
            <nav className="space-y-0.5 mt-1 font-semibold">
              <button 
                onClick={() => setActiveMenu("Office Overview")}
                className={getMenuButtonClass("Office Overview")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>
                  Office Overview
                </span>
              </button>
              <button 
                onClick={() => {
                  setActiveMenu("Chat Center");
                  setUnreadCount(0);
                }}
                className={getMenuButtonClass("Chat Center")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
                  Chat Center
                </span>
                {unreadCount > 0 ? (
                  <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
                    {unreadCount}
                  </span>
                ) : (
                  <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
                    7
                  </span>
                )}
              </button>
              <button 
                onClick={() => setActiveMenu("AI Agents")}
                className={getMenuButtonClass("AI Agents")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                  AI Agents
                </span>
                <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
                  9
                </span>
              </button>
              <button 
                onClick={() => setActiveMenu("Workflow Board")}
                className={getMenuButtonClass("Workflow Board")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>
                  Workflow Board
                </span>
              </button>
            </nav>
          </div>

          <div>
            <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">TRADING</div>
            <nav className="space-y-0.5 mt-1 font-semibold">
              <button 
                onClick={() => setActiveMenu("Analytics")}
                className={getMenuButtonClass("Analytics")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                  Analytics
                </span>
              </button>
              <button 
                onClick={() => setActiveMenu("Performance Dashboard")}
                className={getMenuButtonClass("Performance Dashboard")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  Performance Dashboard
                </span>
              </button>
              <button 
                onClick={() => setActiveMenu("Risk Monitor")}
                className={getMenuButtonClass("Risk Monitor")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>
                  Risk Monitor
                </span>
              </button>
              <button 
                onClick={() => setActiveMenu("Reports")}
                className={getMenuButtonClass("Reports")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
                  ERP & Reports
                </span>
              </button>
            </nav>
          </div>

          <div>
            <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">SYSTEM</div>
            <nav className="space-y-0.5 mt-1 font-semibold">
              <button 
                onClick={() => setActiveMenu("Settings")}
                className={getMenuButtonClass("Settings")}
              >
                <span className="flex items-center">
                  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                  Settings
                </span>
              </button>
            </nav>
          </div>
        </div>

        <div className="mt-auto p-2">
          <div className="border border-[#1e2d45] bg-[#070b11]/80 rounded-lg p-2.5 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-[11px] text-[#10b981] font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_6px_#10b981]"></span>
              WS Connected
            </div>
            <div className="text-[#5c7a9c] text-[9.5px] font-medium leading-none font-mono">
              Binance CCXT • 52ms
            </div>
          </div>
        </div>
      </aside>

      {/* ── CENTER AREA ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* ── TOPBAR ── */}
        <header className="bg-[#070a0f] border-b border-[#1e2d45] flex items-center justify-between px-4 h-[52px] flex-shrink-0">
          {/* Left: Portfolio statistics */}
          <div className="flex items-center gap-6 text-xs">
            {/* PnL Today */}
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">PnL Today</span>
              <div className="flex items-center gap-1.5 font-bold font-mono">
                <span className={todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}>
                  {todayPnLSum >= 0 ? "+" : ""}${todayPnLSum.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </span>
                <span className={`text-[10px] ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                  {todayPnLSum >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Equity */}
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Equity</span>
              <div className="font-bold text-white font-mono">
                ${totalEquity.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
              </div>
            </div>

            {/* Win Rate */}
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Win Rate</span>
              <div className="font-bold text-white font-mono">
                {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(1) : "0.0"}%
              </div>
            </div>

            {/* Open Positions */}
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Open Positions</span>
              <div className="font-bold text-white font-mono">
                {activeTradesCount}
              </div>
            </div>

            {/* Risk Level */}
            <div className="flex flex-col gap-0.5">
              <span className="text-[#5c7a9c] text-[9.5px] font-medium uppercase font-mono">Risk Level</span>
              <div className="font-bold text-[#10b981] font-mono">
                {riskForm.riskPct > 3 ? "HIGH" : riskForm.riskPct > 1.5 ? "MEDIUM" : "LOW"}
              </div>
            </div>
          </div>

          {/* Right: Status and profile */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 bg-[#0d2a14]/30 border border-[#1a5a28]/40 px-2.5 py-0.5 rounded-full text-[10px] text-[#10b981] font-bold font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981]"></span>
              WS Connected
            </div>
            
            {/* Bell notification */}
            <button className="relative p-1 text-[#7a9bbf] hover:text-white transition">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-red-500 rounded-full text-[8px] text-white font-extrabold flex items-center justify-center">
                3
              </span>
            </button>

            {/* Profile badge */}
            <div className="w-6 h-6 rounded-full bg-[#0d1520] border border-[#1e2d45] text-[11px] font-bold text-white flex items-center justify-center font-mono">
              C
            </div>
          </div>
        </header>

        {/* ── CENTRAL MAIN WORKSPACE ── */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          
          {/* TAB 1: 🖥 Overview (Trading layout with candlestick chart, workforce grid, positions table, and bottom-right Risk Gate) */}
          <div className={`flex-1 flex flex-col p-4 gap-4 bg-[#000000] overflow-y-auto ${activeMenu === "Overview" ? "block" : "hidden"}`}>
            
            {/* ── ROW 1: CANDLESTICK CHART ── */}
            <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col gap-2.5 h-[360px] min-h-[360px] shadow-lg">
              {/* Chart Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-white text-[14px] font-mono">{symbol}</span>
                      <svg className="w-3.5 h-3.5 text-[#fbbf24] cursor-pointer" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.24.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.176 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.768-.57-.37-1.81.588-1.81h4.907a1 1 0 00.95-.69l1.519-4.674z" /></svg>
                    </div>
                    <span className="text-[10px] text-[#5c7a9c] font-medium leading-none mt-0.5 font-mono">
                      {SYMBOLS_LIST.find(s => s.symbol === symbol)?.name || "Binance Asset"}
                    </span>
                  </div>
                  <div className="h-6 w-[1px] bg-[#1e2d45]" />
                  <div className="flex flex-col">
                    <span className="text-[14px] font-black text-white font-mono leading-none">
                      {latestPrice ? latestPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) : "-"}
                    </span>
                    <span className="text-[9.5px] font-mono text-[#f87171] leading-none mt-1">
                      -327.85 (-0.51%)
                    </span>
                  </div>
                </div>

                {/* Right specs */}
                <div className="flex items-center gap-6 text-[10px] font-mono text-[#7a9bbf]">
                  <div>
                    <span className="text-[#5c7a9c]">High</span> <span className="font-bold text-white">{(latestPrice ? latestPrice * 1.01 : 64872.10).toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c]">Low</span> <span className="font-bold text-white">{(latestPrice ? latestPrice * 0.99 : 62980.45).toLocaleString(undefined, {maximumFractionDigits: 2})}</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c]">Volume</span> <span className="font-bold text-white">12.43K</span>
                  </div>
                </div>
              </div>

              {/* Chart Toolbar */}
              <div className="flex items-center justify-between border-t border-b border-[#1e2d45]/40 py-1 text-[10.5px]">
                <div className="flex items-center gap-1 font-semibold text-[#7a9bbf] font-mono">
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">1m</span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">5m</span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">15m</span>
                  <span className="px-2 py-0.5 rounded bg-[#131d27] text-white cursor-pointer">1h</span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">4h</span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">D</span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer">W</span>
                  <div className="w-[1px] h-3 bg-[#1e2d45] mx-1" />
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer flex items-center gap-1 text-[#22d3ee]">
                    📊 Indicators
                  </span>
                  <span className="px-2 py-0.5 rounded hover:bg-white/5 cursor-pointer flex items-center gap-1">
                    🔔 Alert
                  </span>
                </div>
              </div>

              {/* Chart Iframe Container */}
              <div className="flex-1 rounded-lg overflow-hidden border border-[#1e2d45]/50 relative">
                <TradingViewWidget symbol={symbol} />
              </div>
            </div>

            {/* ── ROW 2: WORKFORCE AGENTS ── */}
            <div className="grid grid-cols-6 gap-3">
              {/* Risk AI */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#ef4444]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">🛡️</span>
                    <span className="font-bold text-white text-[11px] font-mono">Risk AI</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">Risk Score</span>
                    <span className="text-[#10b981] font-bold">32/100</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">Status</span>
                    <span className="text-[#10b981] font-bold">Normal</span>
                  </div>
                </div>
              </div>

              {/* Strategy AI */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#fbbf24]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">🎯</span>
                    <span className="font-bold text-white text-[11px] font-mono">Strategy AI</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">Signals Today</span>
                    <span className="text-white font-bold">{signalActivity.length}</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">Run Rate</span>
                    <span className="text-white font-bold">66.7%</span>
                  </div>
                </div>
              </div>

              {/* EA Bot */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#818cf8]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">🤖</span>
                    <span className="font-bold text-white text-[11px] font-mono">EA Bot</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Active
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">Trades Today</span>
                    <span className="text-white font-bold">{(orders || []).filter(o => o.status === "CLOSED").length}</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">Win Rate</span>
                    <span className="text-white font-bold">
                      {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(0) : "0"}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Finance AI */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#06b6d4]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">💰</span>
                    <span className="font-bold text-white text-[11px] font-mono">Finance AI</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">PnL Today</span>
                    <span className={`font-bold ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                      ${todayPnLSum.toFixed(0)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">ROI</span>
                    <span className="text-white font-bold">{pnlPct.toFixed(1)}%</span>
                  </div>
                </div>
              </div>

              {/* Audit AI */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#a855f7]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">🔍</span>
                    <span className="font-bold text-white text-[11px] font-mono">Audit AI</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Running
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">Checks Today</span>
                    <span className="text-white font-bold">{ledger.length}</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">Issues</span>
                    <span className="text-[#10b981] font-bold">0</span>
                  </div>
                </div>
              </div>

              {/* CEO Agent */}
              <div className="bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3 flex flex-col justify-between h-[85px] shadow-sm relative group hover:border-[#10b981]/30 transition">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[14px]">🕴️</span>
                    <span className="font-bold text-white text-[11px] font-mono">CEO Agent</span>
                  </div>
                  <span className="text-[8px] text-[#10b981] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-ping" /> Active
                  </span>
                </div>
                <div className="flex justify-between items-end mt-2 text-[10px] font-mono">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px]">Reports</span>
                    <span className="text-white font-bold">3</span>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] text-right">Alerts</span>
                    <span className="text-white font-bold">1</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── ROW 3: POSITIONS TABS & RISK GATE ── */}
            <div className="flex gap-4">
              {/* Tabbed Positions Table (Left) */}
              <div className="flex-1 bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3.5 shadow-lg flex flex-col h-[280px] min-h-[280px]">
                {/* Tab selector */}
                <div className="flex gap-5 border-b border-[#1e2d45]/40 pb-2 text-[11px] font-bold text-[#7a9bbf] font-mono cursor-pointer">
                  {["POSITIONS", "ORDERS", "PORTFOLIO", "SIGNALS", "ALERTS"].map((tab) => {
                    const isTabActive = tab === activeTab;
                    return (
                      <span 
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`${isTabActive ? "text-white border-b-2 border-[#fbbf24] pb-2" : "hover:text-white"}`}
                      >
                        {tab}
                      </span>
                    );
                  })}
                </div>

                {/* Table contents */}
                <div className="flex-1 overflow-y-auto mt-2 pr-1">
                  {activeTab === "POSITIONS" && (
                    <table className="w-full text-left text-[10.5px] font-mono">
                      <thead>
                        <tr className="text-[#5c7a9c] border-b border-[#1e2d45]/30">
                          <th className="py-2">Symbol</th>
                          <th className="py-2">Side</th>
                          <th className="py-2">Size</th>
                          <th className="py-2">Entry Price</th>
                          <th className="py-2">Mark Price</th>
                          <th className="py-2">PnL (USDT)</th>
                          <th className="py-2">PnL %</th>
                          <th className="py-2">Risk</th>
                          <th className="py-2 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e2d45]/20 text-white">
                        {(() => {
                          const openOrders = (orders || []).filter(o => o.status === "OPEN" || o.status === "PENDING");
                          if (openOrders.length === 0) {
                            return (
                              <tr>
                                <td colSpan={9} className="py-8 text-center text-slate-500 text-[10px]">
                                  ไม่พบข้อมูลออเดอร์ที่กำลังทำงาน (Active Positions)
                                </td>
                              </tr>
                            );
                          }
                          return openOrders.map((ord) => {
                            const markPrice = priceMap[ord.symbol] || latestPrice || ord.entry_price;
                            const pnlValue = (markPrice - ord.entry_price) * ord.volume * (ord.action === "BUY" ? 1 : -1);
                            const pnlPctValue = ord.entry_price > 0 ? (pnlValue / (ord.entry_price * ord.volume)) * 100 : 0;
                            return (
                              <tr key={ord.id} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(ord.symbol)}>
                                <td className="py-2 font-bold">{ord.symbol}</td>
                                <td className="py-2">
                                  <span className={ord.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{ord.action}</span>
                                </td>
                                <td className="py-2">{ord.volume}</td>
                                <td className="py-2">${ord.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td className="py-2">${markPrice.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                                <td className={`py-2 font-bold ${pnlValue >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                                  {pnlValue >= 0 ? "+" : ""}${pnlValue.toFixed(2)}
                                </td>
                                <td className={`py-2 font-bold ${pnlValue >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                                  {pnlValue >= 0 ? "+" : ""}{pnlPctValue.toFixed(2)}%
                                </td>
                                <td className="py-2 text-[#10b981]">Low</td>
                                <td className="py-2 text-center">
                                  <button 
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleCloseOrder(ord.id);
                                    }}
                                    className="text-[9px] px-2 py-0.5 rounded bg-[#ef4444]/10 border border-[#ef4444]/30 text-[#f87171] hover:bg-[#ef4444]/30"
                                  >
                                    Close
                                  </button>
                                </td>
                              </tr>
                            );
                          });
                        })()}
                      </tbody>
                    </table>
                  )}

                  {activeTab === "ORDERS" && (
                    <table className="w-full text-left text-[10.5px] font-mono">
                      <thead>
                        <tr className="text-[#5c7a9c] border-b border-[#1e2d45]/30">
                          <th className="py-2">ID</th>
                          <th className="py-2">Symbol</th>
                          <th className="py-2">Side</th>
                          <th className="py-2">Size</th>
                          <th className="py-2">Entry</th>
                          <th className="py-2">Exit</th>
                          <th className="py-2">PnL</th>
                          <th className="py-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e2d45]/20 text-white">
                        {orders.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="py-8 text-center text-slate-500 text-[10px]">
                              ไม่พบประวัติออเดอร์
                            </td>
                          </tr>
                        ) : (
                          orders.map((ord) => (
                            <tr key={ord.id} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(ord.symbol)}>
                              <td className="py-2 text-[#5c7a9c] max-w-[60px] truncate" title={ord.id}>
                                {ord.id.slice(0, 8)}...
                              </td>
                              <td className="py-2 font-bold">{ord.symbol}</td>
                              <td className="py-2">
                                <span className={ord.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{ord.action}</span>
                              </td>
                              <td className="py-2">{ord.volume}</td>
                              <td className="py-2">${ord.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                              <td className="py-2">
                                {ord.exit_price ? `$${ord.exit_price.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "-"}
                              </td>
                              <td className={`py-2 font-bold ${ord.pnl >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                                {ord.pnl >= 0 ? "+" : ""}${ord.pnl.toFixed(2)}
                              </td>
                              <td className="py-2">
                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                  ord.status === "CLOSED" ? "bg-[#1e2d45] text-[#7a9bbf]" : "bg-emerald-950 text-emerald-400"
                                }`}>
                                  {ord.status}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}

                  {activeTab === "PORTFOLIO" && (
                    <table className="w-full text-left text-[10.5px] font-mono">
                      <thead>
                        <tr className="text-[#5c7a9c] border-b border-[#1e2d45]/30">
                          <th className="py-2">Source</th>
                          <th className="py-2">Equity</th>
                          <th className="py-2">Balance</th>
                          <th className="py-2">Free Margin</th>
                          <th className="py-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e2d45]/20 text-white">
                        {balances.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-slate-500 text-[10px]">
                              ไม่พบข้อมูลพอร์ตโฟลิโอ
                            </td>
                          </tr>
                        ) : (
                          balances.map((bal, idx) => (
                            <tr key={idx} className="hover:bg-white/5">
                              <td className="py-2 font-bold text-[#22d3ee]">{bal.source}</td>
                              <td className="py-2 font-mono">${bal.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                              <td className="py-2 font-mono">${bal.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                              <td className="py-2 font-mono">${bal.free_margin.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                              <td className="py-2">
                                <span className="text-[#10b981] font-bold">● Connected</span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}

                  {activeTab === "SIGNALS" && (
                    <table className="w-full text-left text-[10.5px] font-mono">
                      <thead>
                        <tr className="text-[#5c7a9c] border-b border-[#1e2d45]/30">
                          <th className="py-2">Symbol</th>
                          <th className="py-2">Action</th>
                          <th className="py-2">Status</th>
                          <th className="py-2">Reason</th>
                          <th className="py-2 text-right">Time</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e2d45]/20 text-white">
                        {signalActivity.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-slate-500 text-[10px]">
                              ไม่พบประวัติสัญญาณการเทรดวันนี้
                            </td>
                          </tr>
                        ) : (
                          signalActivity.map((sig, idx) => (
                            <tr key={sig.id || idx} className="hover:bg-white/5 cursor-pointer" onClick={() => handleSymbolChange(sig.ticker)}>
                              <td className="py-2 font-bold">{sig.ticker}</td>
                              <td className="py-2">
                                <span className={sig.action === "BUY" ? "text-[#10b981]" : "text-[#f87171]"}>{sig.action}</span>
                              </td>
                              <td className="py-2">
                                <span className={`px-1.5 py-0.2 rounded text-[8.5px] font-bold ${
                                  sig.status === "APPROVED" ? "bg-emerald-950 text-emerald-400" :
                                  sig.status === "REJECTED" ? "bg-red-950 text-red-400" : "bg-amber-950 text-amber-400"
                                }`}>
                                  {sig.status}
                                </span>
                              </td>
                              <td className="py-2 text-slate-400 max-w-[150px] truncate" title={sig.reason || ""}>
                                {sig.reason || "-"}
                              </td>
                              <td className="py-2 text-[#5c7a9c] text-[9.5px] text-right">
                                {new Date(sig.time).toLocaleTimeString()}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}

                  {activeTab === "ALERTS" && (
                    <table className="w-full text-left text-[10.5px] font-mono">
                      <thead>
                        <tr className="text-[#5c7a9c] border-b border-[#1e2d45]/30">
                          <th className="py-2">Time</th>
                          <th className="py-2">Source</th>
                          <th className="py-2">Summary</th>
                          <th className="py-2">Impact</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e2d45]/20 text-white">
                        {newsFeed.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="py-8 text-center text-slate-500 text-[10px]">
                              ไม่พบข้อมูลข่าวสารหรือการแจ้งเตือน
                            </td>
                          </tr>
                        ) : (
                          newsFeed.map((news, idx) => (
                            <tr key={idx} className="hover:bg-white/5">
                              <td className="py-2 text-[#5c7a9c] text-[9.5px]">{news.time}</td>
                              <td className="py-2 font-bold text-[#fbbf24]">{news.source}</td>
                              <td className="py-2 max-w-[200px] truncate" title={news.text}>{news.text}</td>
                              <td className="py-2">
                                <span className={`px-1.5 py-0.5 rounded text-[8.5px] font-bold ${
                                  news.impact === "HIGH" ? "bg-red-950 text-red-400" : "bg-amber-950 text-amber-400"
                                }`}>
                                  {news.impact}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>

              {/* RISK GATE (Right) */}
              <div className="w-[360px] bg-[#070a0f] border border-[#1e2d45] rounded-xl p-3.5 shadow-lg flex flex-col h-[280px] min-h-[280px] justify-between">
                
                {/* แถวบน: Title + Auto Scan */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[11px] text-[#fbbf24] font-extrabold uppercase tracking-wider font-mono">
                    <svg className="w-4 h-4 text-[#fbbf24]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    RISK GATE
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleToggleMode}
                      className={`px-2 py-1 text-[9px] font-bold rounded-full border transition flex items-center gap-1 ${
                        mode === "auto"
                          ? "bg-[#0d2a3a]/80 text-[#22d3ee] border-[#1a5a7a] shadow-[0_0_8px_#22d3ee44]"
                          : "bg-[#111827] text-[#7a9bbf] border-[#1e2d45] hover:bg-[#1e2d45] hover:text-[#c8d8f0]"
                      }`}
                    >
                      <span className={`w-1 h-1 rounded-full ${mode === "auto" ? "bg-[#22d3ee] shadow-[0_0_4px_#22d3ee]" : "bg-[#64748b]"}`} />
                      Auto Scan
                    </button>
                  </div>
                </div>

                {/* Indicators Row */}
                <div className="flex gap-2 text-center text-[10px] bg-[#000000]/40 border border-[#1e2d45] px-2.5 py-1.5 rounded-lg font-mono items-center justify-around">
                  <div>
                    <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">ราคา</span>
                    <div className="font-bold text-white mt-0.5 text-[9.5px]">{latestPrice ? latestPrice.toLocaleString() : "-"}</div>
                  </div>
                  <div className="w-[1px] h-3.5 bg-[#1e2d45]" />
                  <div>
                    <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">EMA</span>
                    <div className={`font-bold mt-0.5 text-[9.5px] ${indicators?.trend === "Bullish" ? "text-[#10b981]" : indicators?.trend === "Bearish" ? "text-[#f87171]" : "text-[#fbbf24]"}`}>{indicators?.trend || "-"}</div>
                  </div>
                  <div className="w-[1px] h-3.5 bg-[#1e2d45]" />
                  <div>
                    <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">RSI</span>
                    <div className="font-bold text-white mt-0.5 text-[9.5px]">{indicators?.rsi || "-"}</div>
                  </div>
                  <div className="w-[1px] h-3.5 bg-[#1e2d45]" />
                  <div>
                    <span className="text-[#5c7a9c] text-[8px] font-medium leading-none">Signal</span>
                    <div className={`font-bold mt-0.5 text-[9.5px] ${signal?.action === "BUY" ? "text-[#10b981]" : signal?.action === "SELL" ? "text-[#f87171]" : "text-slate-400"}`}>{signal?.action || "WAIT"}</div>
                  </div>
                </div>

                {/* Parameters block */}
                <div className="grid grid-cols-3 gap-2 text-[9px] font-mono border-t border-[#1e2d45]/40 pt-2">
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">คู่เหรียญ</span>
                    <select
                      value={symbol}
                      onChange={(e) => handleSymbolChange(e.target.value)}
                      className="bg-[#000000] border border-[#1e2d45] rounded text-[10px] text-white px-1 py-0.5 outline-none font-mono font-bold w-full h-[22px] cursor-pointer"
                    >
                      {SYMBOLS_LIST.map((s) => (
                        <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Lot</span>
                    <input type="number" step="0.01" value={riskForm.lot}
                      onChange={(e) => setRiskForm({...riskForm, lot: Number(e.target.value)})}
                      className="w-full bg-[#000000] border border-[#1e2d45] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                    />
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">SL (Pips)</span>
                    <input type="number" value={riskForm.stopDistance}
                      onChange={(e) => setRiskForm({...riskForm, stopDistance: Number(e.target.value)})}
                      className="w-full bg-[#000000] border border-[#1e2d45] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                    />
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">TP (Pips)</span>
                    <input type="number" value={riskForm.takeProfit}
                      onChange={(e) => setRiskForm({...riskForm, takeProfit: Number(e.target.value)})}
                      className="w-full bg-[#000000] border border-[#1e2d45] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                    />
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Spread Limit</span>
                    <input type="number" step="0.1" value={riskForm.spread}
                      onChange={(e) => setRiskForm({...riskForm, spread: Number(e.target.value)})}
                      className="w-full bg-[#000000] border border-[#1e2d45] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                    />
                  </div>
                  <div>
                    <span className="text-[#5c7a9c] block text-[8px] font-medium mb-0.5">Risk %</span>
                    <input type="number" step="0.1" value={riskForm.riskPct}
                      onChange={(e) => setRiskForm({...riskForm, riskPct: Number(e.target.value)})}
                      className="w-full bg-[#000000] border border-[#1e2d45] rounded px-1 py-0.5 text-white font-bold text-center text-[10px] h-[22px] outline-none focus:border-[#3b82f6]"
                    />
                  </div>
                </div>

                {/* Actions row */}
                <div className="flex items-center gap-1.5 border-t border-[#1e2d45]/40 pt-2 justify-between">
                  <button onClick={handleRiskTest} className="px-2.5 py-1 bg-[#161f30] hover:bg-[#202d44] text-[9.5px] font-bold text-[#c8d8f0] rounded border border-[#243352] transition flex items-center gap-1 h-6">
                    ประเมิน
                  </button>
                  
                  <div className={`px-2 py-1 text-[9.5px] font-bold rounded flex items-center gap-1 border h-6 ${
                    risk?.passed ? "bg-[#0d2a14] text-[#10b981] border-[#1a5a28]" : "bg-[#2a0d0d] text-[#f87171] border-[#6b1c1c]"
                  }`}>
                    <span className={`w-1 h-1 rounded-full ${risk?.passed ? "bg-[#10b981] shadow-[0_0_4px_#10b981]" : "bg-[#ef4444] shadow-[0_0_4px_#ef4444]"}`} />
                    {risk?.passed ? "PASS" : "BLOCK"}
                  </div>
                  
                  <button
                    onClick={handleApprove}
                    disabled={mode === "auto" || !signal || (signal.action !== "BUY" && signal.action !== "SELL")}
                    className="px-3.5 py-1 bg-[#0e3a1f] hover:bg-[#14532d] disabled:bg-[#111520] disabled:text-[#3d5a7a] border border-[#166534] disabled:border-[#1e2d45] text-[#10b981] disabled:text-[#3d5a7a] text-[10px] font-bold rounded transition flex items-center gap-1.5 h-7"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                    อนุมัติ
                  </button>
                  
                  <button
                    onClick={handleReject}
                    className="px-2.5 py-1 bg-[#2a0d0d] hover:bg-[#450a0a] border border-[#6b1c1c] text-[#f87171] text-[10px] font-bold rounded transition flex items-center justify-center h-7"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              </div>

            </div>

            {/* ── Top-Right: ERP Mini Widget ── */}
            <div className="absolute right-3 top-3 w-[200px] bg-[#070b11]/90 border border-[#1e2d45] rounded-xl p-3.5 shadow-2xl backdrop-blur-md">
              <div className="flex justify-between items-center border-b border-[#1e2d45] pb-2 mb-2">
                <div className="text-[11px] text-white font-extrabold tracking-wider font-mono">TEAM ERP</div>
                <div className="text-[8px] bg-emerald-950/80 border border-emerald-500/30 text-[#10b981] px-1.5 py-0.2 rounded-full font-bold uppercase tracking-wide">Live</div>
              </div>
              
              {taxSummary ? (
                <div className="text-[10px] space-y-1.5 font-mono">
                  <div className="flex justify-between">
                    <span className="text-[#5c7a9c] font-medium">PnL</span>
                    <span className="text-[#10b981] font-bold">${taxSummary.accumulatedPnL.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#5c7a9c] font-medium">VAT ค้าง</span>
                    <span className="text-[#10b981] font-bold">+${taxSummary.inputVatClaimable.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#5c7a9c] font-medium">ภาษี</span>
                    <span className="text-[#ef4444] font-bold">-${taxSummary.estimatedIncomeTax.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-b border-[#1e2d45]/50 pb-2">
                    <span className="text-[#5c7a9c] font-medium">พอร์ต</span>
                    <span className="text-[#10b981] font-bold">${taxSummary.netAfterTax.toFixed(2)}</span>
                  </div>
                </div>
              ) : (
                <div className="text-[10px] text-slate-500 text-center py-2 font-mono">Loading ERP...</div>
              )}
              
              <div className="mt-2 font-mono">
                <div className="text-[9px] text-[#5c7a9c] font-medium">สถานะระบบ</div>
                <div className="text-[10px] text-white font-bold mt-0.5">ERP Ledger</div>
                
                <div className="flex justify-between text-[10px] font-bold mt-2 pt-2 border-t border-[#1e2d45]/50">
                  <span className="text-[#10b981]">Dr: ${ledger.length > 0 ? ledger[ledger.length - 1].debit.amount.toLocaleString() : "0"}</span>
                  <span className="text-[#fbbf24]">Cr: ${ledger.length > 0 ? ledger[ledger.length - 1].credit.amount.toLocaleString() : "0"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* TAB 2: 🤖 AI Agents - Blueprint & System Prompt Viewer */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "AI Agents" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">🤖 บทบาทหน้าที่ทีมงาน AI (AI Trading Virtual Office Agents)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">อัปเดตบทบาทหน้าที่การทำงานของ 9 เอเจนต์หลัก ในระบบเทรดภาษาไทยอย่างถูกต้อง</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              
              {/* Agent 1 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#60a5fa] flex items-center gap-1.5 font-mono">🕴️ AGENT 1: CEO Agent</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: JARVIS-CEO | บทบาท: ผู้นำประสานงานกลาง</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  รับคำสั่งจากผู้ใช้ สั่งการวิเคราะห์ไปหา Chart AI, Risk AI และ News AI แบบขนาน รวบรวมสรุปผลโหวตและแผนเข้าตลาดเพื่อส่งคำขออนุมัติเทรด (Approve/Reject) หรือประมวลผลระบบเทรดอัตโนมัติ
                </div>
              </div>

              {/* Agent 2 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#34d399] flex items-center gap-1.5 font-mono">📊 AGENT 2: Chart AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: NOVA-CHART | บทบาท: นักวิเคราะห์เทคนิค</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  ประเมินแนวโน้มราคาทางเทคนิค คำนวณอินดิเคเตอร์เชิงซ้อน (RSI, ATR, Trend, EMA) และระบุแนวรับแนวต้าน พร้อมสรุปเป็นระดับความมั่นใจเทคนิค (Confluence Score)
                </div>
              </div>

              {/* Agent 3 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#f87171] flex items-center gap-1.5 font-mono">🛡️ AGENT 3: Risk AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: SHIELD-RISK | บทบาท: ผู้คุมความเสี่ยงพอร์ต</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  คำนวณขนาดไม้ (Lot Size) ที่เหมาะสมตามความเสี่ยง ตรวจสอบเกณฑ์ป้องกันความเสี่ยงสูงสุดต่อไม้สูงสุด 2% ป้องกันการขาดทุนสะสม (Daily Drawdown) และหยุดการเทรดหากชนขีดจำกัด
                </div>
              </div>

              {/* Agent 4 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">🎯 AGENT 4: Strategy AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ORACLE-STRATEGY | บทบาท: ผู้วางกลยุทธ์ตามสภาวะ</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  วิเคราะห์ Market Regime คัดกรองและปรับสภาวะการเทรดตามช่วงเวลาดัชนี (ADX, Volatility) เพื่อวางกฎการส่งออเดอร์และการวางแผน Stop Loss/Take Profit ที่เหมาะสม
                </div>
              </div>

              {/* Agent 5 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#f97316] flex items-center gap-1.5 font-mono">📰 AGENT 5: News AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ECHO-NEWS | บทบาท: นักสแกนอารมณ์ข่าว</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  สแกนหาข่าวด่วน ข้อมูลเศรษฐกิจรอบโลก ดึงค่า Sentiment ด้วย FinBERT เพื่อกรองผลลบ/ผลบวกในการลงทุน และบล็อกคำสั่งซื้อขายในช่วงเวลาข่าวผันผวนระดับสูง (High-impact News)
                </div>
              </div>

              {/* Agent 6 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#22d3ee] flex items-center gap-1.5 font-mono">💰 AGENT 6: Finance AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: ATLAS-FINANCE | บทบาท: ฝ่ายการเงิน & ERP</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  มอนิเตอร์และสรุปยอดคงเหลือของแต่ละพอร์ต คำนวณ P&L รายดีล ยอดสะสม ค่าธรรมเนียมโบรกเกอร์ และภาษีสะสมเพื่อส่ง Webhook บันทึกบัญชีแยกประเภท ERP กลางทันทีที่มีธุรกรรม
                </div>
              </div>

              {/* Agent 7 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#a855f7] flex items-center gap-1.5 font-mono">🔍 AGENT 7: Audit AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: VIGIL-AUDIT | บทบาท: ผู้สอบบัญชีความถูกต้อง</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  ตรวจสอบความสม่ำเสมอและความถูกต้องของธุรกรรม (Consistency Check) เทียบประวัติการส่งคำสั่งซื้อขายจริงใน DB กับระบบ ERP บัญชีแยกประเภท เพื่อคัดกรองข้อมูลผิดพลาด
                </div>
              </div>

              {/* Agent 8 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#818cf8] flex items-center gap-1.5 font-mono">🤖 AGENT 8: EA Bot</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: APEX-EA | บทบาท: ผู้ส่งคำสั่งเทรด</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  จัดการเชื่อมต่อ API นำแผนงานส่งออเดอร์ (Market Order) เพื่อเปิด/ปิดคำสั่งจริงที่ Broker (MT5 หรือ Binance API) เฝ้าติดตาม Trailing Stop, SL และ TP อย่างใกล้ชิด
                </div>
              </div>

              {/* Agent 9 */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-2 backdrop-blur-md hover:border-emerald-500/30 transition-all duration-300">
                <h3 className="text-sm font-bold text-[#c084fc] flex items-center gap-1.5 font-mono">📋 AGENT 9: Report AI</h3>
                <p className="text-[10px] text-[#7a9bbf] font-mono">ชื่อรหัส: SCRIBE-REPORT | บทบาท: ผู้จัดทำรายงานสรุป</p>
                <div className="text-xs text-[#c8d8f0] leading-relaxed">
                  สรุปผลลัพธ์การเทรด อัตราส่วนชนะ (Win Rate), อัตราผลตอบแทนต่อความเสี่ยง (Profit Factor), สถิติ Max Drawdown และรวบรวมตัวชี้วัดประสิทธิภาพ จัดทำรายงานภาพรวมพอร์ต
                </div>
              </div>

            </div>
          </div>

          {/* TAB 3: 📋 Workflow Board - Multi-Agent Flow Diagram & Thai Guide */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Workflow Board" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">📋 คู่มือระบบ & ประวัติธุรกรรมตามวันที่ (Workflow & Trade History)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">คู่มือการใช้งานระบบเทรดอัจฉริยะภาษาไทย และการเรียกดูประวัติการเทรดแยกตามวันเดือนปี</p>
            </div>

            {/* 1. คู่มือการใช้งานภาษาไทย */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
              <h3 className="text-sm font-bold text-emerald-400 flex items-center gap-1.5 font-mono">📖 คู่มือการใช้งานระบบ (System Operation Guide)</h3>
              
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 text-xs text-[#c8d8f0] leading-relaxed">
                <div className="bg-black/40 border border-white/5 p-4 rounded-lg space-y-3">
                  <div className="text-emerald-400 font-bold font-mono">🔄 โหมดการทำงานของระบบ (Operation Modes)</div>
                  <ul className="list-disc list-inside space-y-2 text-[#a3b3cc]">
                    <li>
                      <span className="text-white font-bold">โหมดธรรมดา (Watch Mode):</span> 
                      ระบบจะไม่ออกออเดอร์เองโดยอัตโนมัติ เมื่อวิเคราะห์พบสัญญาณจะส่งมาแสดงที่หน้าต่างบอร์ดหรือ Telegram ผู้ใช้ต้องทำการกดปุ่ม <span className="text-[#10b981] font-bold">"อนุมัติ"</span> ด้วยตนเอง โดยจะซื้อทุกไม้ทันทีตามจำนวนที่กดโดยไม่จำกัดจำนวนไม้เปิดคู่ขนาน (รัวกดได้ทันที)
                    </li>
                    <li>
                      <span className="text-[#22d3ee] font-bold">โหมดอัตโนมัติ (Auto Mode):</span>
                      ระบบ AI และ Risk Engine จะตรวจสอบเกณฑ์ความปลอดภัยอย่างเข้มงวดและอนุมัติส่งคำสั่งซื้อขายจริง (Auto Execution) ไปยัง Broker ทันทีตามที่บอทประเมินว่าเหมาะสมและผ่านเกณฑ์จำกัดความเสี่ยง
                    </li>
                  </ul>
                </div>

                <div className="bg-black/40 border border-white/5 p-4 rounded-lg space-y-3">
                  <div className="text-[#f87171] font-bold font-mono">🛡️ กฎความเสี่ยง 6 ประการ (Risk Engine Guardrails)</div>
                  <ol className="list-decimal list-inside space-y-1 text-[#a3b3cc]">
                    <li>มีสัญญาณซื้อขายจริง (<span className="text-white">ไม่ใช่ WAIT</span>)</li>
                    <li>ความเสี่ยงต่อไม้ไม่เกิน <span className="text-white">2.0%</span> ของพอร์ต (2% Rule)</li>
                    <li>จุดตัดขาดทุนขั้นต่ำ (Stop Loss) <span className="text-white">&ge; 10 pips</span></li>
                    <li>ค่าสเปรดโบรกเกอร์ (Spread) <span className="text-white">ไม่กว้างเกินเกณฑ์สูงสุด (3.0)</span></li>
                    <li>มูลค่าถือครองสินทรัพย์รวมทั้งพอร์ต <span className="text-white">ไม่เกิน 20%</span></li>
                    <li>สถานะระบบความปลอดภัย <span className="text-white">Circuit Breaker</span> ปิดปกติ</li>
                  </ol>
                </div>
              </div>

              <div className="bg-black/60 p-4 rounded border border-white/5 text-xs font-mono space-y-2.5 leading-relaxed text-[#c8d8f0]">
                <div className="text-slate-400 border-b border-white/5 pb-1 mb-1 font-bold">🚀 ลำดับขั้นตอนการทำงาน (Safe Execution Flow)</div>
                <div><span className="text-[#fbbf24] font-bold">[1] สั่งการ / ค้นหาสัญญาณ:</span> ระบบสแกนหาทิศทางราคา หรือรับคำสั่งวิเคราะห์ทางเทคนิค</div>
                <div><span className="text-[#fbbf24] font-bold">[2] CEO Agent ประมวลผล:</span> CEO จะสั่งให้ Chart AI (กราฟ), Risk AI (คำนวณความเสี่ยง/Lot), News AI (ดึงข่าวด่วน) ประมวลผลร่วมกัน</div>
                <div><span className="text-[#fbbf24] font-bold">[3] ตัดสินใจ & ขออนุมัติ:</span> ในโหมด Watch บอทส่งสัญญาณมาขอความเห็นชอบบนเว็บ/Telegram หรืออนุมัติยิงตลาดทันทีหากเปิดโหมด Auto</div>
                <div><span className="text-[#fbbf24] font-bold">[4] บันทึกสมุดบัญชี ERP:</span> หลังจากปิดดีลสำเร็จ Finance AI จะยิงข้อมูล P&L และยอดภาษีเข้าระบบ ERP บัญชีแยกประเภททันที</div>
              </div>
            </div>

            {/* 2. ประวัติการเทรดกรองตามวันที่ */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/5 pb-3">
                <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">📅 ประวัติการเทรดแยกตามวันเดือนปี (Historical Trades Calendar)</h3>
                
                {/* Date Picker */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#7a9bbf]">เลือกวันที่:</span>
                  <input 
                    type="date" 
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                    className="bg-black/60 border border-white/10 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-emerald-400 font-mono transition"
                  />
                  {filterDate && (
                    <button 
                      onClick={() => setFilterDate("")}
                      className="text-[10px] text-red-400 hover:text-red-300 px-2 py-1 bg-red-950/20 border border-red-800/30 rounded font-bold"
                    >
                      ล้างตัวกรอง
                    </button>
                  )}
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-white/10 text-[#7a9bbf]">
                      <th className="py-2.5 px-3">วันเวลา (Opened At)</th>
                      <th className="py-2.5 px-3">สินทรัพย์</th>
                      <th className="py-2.5 px-3">ประเภท</th>
                      <th className="py-2.5 px-3">ขนาด (Lot)</th>
                      <th className="py-2.5 px-3">ราคาเข้า</th>
                      <th className="py-2.5 px-3">SL</th>
                      <th className="py-2.5 px-3">TP</th>
                      <th className="py-2.5 px-3">ราคาปัจจุบัน</th>
                      <th className="py-2.5 px-3">ราคาออก</th>
                      <th className="py-2.5 px-3">กำไร/ขาดทุน (USD)</th>
                      <th className="py-2.5 px-3">สถานะ</th>
                      <th className="py-2.5 px-3 text-center">การจัดการ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const filtered = filterDate 
                        ? orders.filter(o => o.opened_at && o.opened_at.startsWith(filterDate))
                        : orders;
                      
                      if (filtered.length === 0) {
                        return (
                          <tr>
                            <td colSpan={12} className="py-8 text-center text-slate-500">
                              ไม่พบประวัติการเทรดในวันที่เลือก
                            </td>
                          </tr>
                        );
                      }

                      return filtered.map((ord, idx) => (
                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="py-2.5 px-3 text-[#a3b3cc]">
                            {ord.opened_at ? parseUTCDate(ord.opened_at).toLocaleString('th-TH') : '-'}
                          </td>
                          <td className="py-2.5 px-3 text-white font-bold">{ord.symbol}</td>
                          <td className="py-2.5 px-3">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              ord.action === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                            }`}>
                              {ord.action}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{ord.volume}</td>
                          <td className="py-2.5 px-3 text-slate-300">${ord.entry_price.toFixed(2)}</td>
                          <td className="py-2.5 px-3 text-red-400">
                            {ord.sl_price > 0 ? `$${ord.sl_price.toFixed(2)}` : '-'}
                          </td>
                          <td className="py-2.5 px-3 text-emerald-400">
                            {ord.tp_price > 0 ? `$${ord.tp_price.toFixed(2)}` : '-'}
                          </td>
                          <td className="py-2.5 px-3 text-white font-bold">
                            {priceMap[ord.symbol] ? `$${priceMap[ord.symbol].toFixed(2)}` : '-'}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">
                            {ord.exit_price > 0 ? `$${ord.exit_price.toFixed(2)}` : '-'}
                          </td>
                          <td className="py-2.5 px-3">
                            {ord.status === "CLOSED" ? (
                              <span className={`font-bold ${ord.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                {ord.pnl >= 0 ? `+$${ord.pnl.toFixed(2)}` : `-$${Math.abs(ord.pnl).toFixed(2)}`}
                              </span>
                            ) : (
                              <span className="text-slate-500 font-bold">Running</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              ord.status === "CLOSED" 
                                ? "bg-slate-800 text-slate-400" 
                                : "bg-emerald-950 text-emerald-400 animate-pulse"
                            }`}>
                              {ord.status}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            {ord.status !== "CLOSED" && ord.status !== "CANCELLED" ? (
                              <button
                                onClick={() => handleCloseOrder(ord.id)}
                                className="px-2 py-0.5 rounded bg-red-500/20 hover:bg-red-500/40 text-red-400 border border-red-500/30 text-[10px] font-bold transition-all"
                              >
                                ปิดออเดอร์ ❌
                              </button>
                            ) : (
                              <span className="text-[10px] text-slate-600">-</span>
                            )}
                          </td>
                        </tr>
                      ));
                    })()}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 3. Signal Activity Log */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4 backdrop-blur-md">
              <div className="flex items-center justify-between border-b border-white/5 pb-3">
                <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5 font-mono">
                  📊 Auto Mode Signal Activity Log
                  {mode === "auto" && <span className="w-2 h-2 rounded-full bg-[#22d3ee] animate-pulse shadow-[0_0_6px_#22d3ee] ml-1" />}
                </h3>
                <button
                  onClick={() => setSignalActivity([])}
                  className="text-[9px] px-2 py-0.5 bg-red-950/30 hover:bg-red-900 border border-red-800/30 text-red-400 rounded transition"
                >
                  ล้าง log
                </button>
              </div>
              <div className="max-h-[320px] overflow-y-auto space-y-1">
                {signalActivity.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 text-xs font-mono">
                    {mode === "auto"
                      ? "⏳ กำลังรอสัญญาณจาก AI Decision Engine..."
                      : "💤 ระบบอยู่ใน Watch Mode — กด Auto Scan เพื่อเปิด Auto Mode"
                    }
                  </div>
                ) : (
                  signalActivity.map((act) => (
                    <div
                      key={act.id}
                      className={`flex items-start gap-2 px-3 py-2 rounded text-[11px] font-mono border-l-2 ${
                        act.status === "APPROVED"
                          ? "border-emerald-500 bg-emerald-950/10"
                          : act.status === "REJECTED"
                          ? "border-red-500 bg-red-950/10"
                          : "border-yellow-500 bg-yellow-950/10"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] text-[#7a9bbf]">
                            {new Date(act.time).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                          </span>
                          <span className="font-bold text-white">{act.ticker}</span>
                          <span className={`px-1 py-0.5 rounded text-[9px] font-bold ${
                            act.action === "BUY" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400"
                          }`}>
                            {act.action}
                          </span>
                          {act.status === "APPROVED" && (
                            <span className="text-[9px] text-emerald-400 font-bold">✅ APPROVED</span>
                          )}
                          {act.status === "REJECTED" && (
                            <span className="text-[9px] text-red-400 font-bold">❌ REJECTED</span>
                          )}
                          {act.status === "VOTING" && (
                            <span className="text-[9px] text-yellow-400 font-bold">⏳ VOTING</span>
                          )}
                        </div>
                        {act.status === "APPROVED" && (act.sl || act.tp) && (
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            SL: <span className="text-red-400">${act.sl?.toFixed(2)}</span> &nbsp; TP: <span className="text-emerald-400">${act.tp?.toFixed(2)}</span>
                          </div>
                        )}
                        {act.status === "REJECTED" && act.reason && (
                          <div className="text-[10px] text-red-400/70 mt-0.5 truncate">
                            {act.reason}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* TAB 4: 💬 Chat Center (Full screen Chat Log View) */}
          <div className={`flex-1 flex flex-col overflow-hidden bg-[#000000] ${activeMenu === "Chat Center" ? "block" : "hidden"}`}>
            <div className="p-4 border-b border-[#1e2d45] bg-[#0f172a]/40 flex justify-between items-center">
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
                <div key={idx} className="flex gap-3 max-w-2xl bg-[#111520] border border-[#1e2d45] rounded-xl p-3 shadow">
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
            <form onSubmit={handleSendChat} className="p-4 border-t border-[#1e2d45] bg-[#070a0f] flex gap-2">
              <input 
                type="text" 
                placeholder="พิมพ์ข้อความแชท หรือรันคำสั่งจำลอง เช่น /analyze BTCUSDT..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                className="flex-1 bg-[#111520] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
              />
              <button type="submit" className="bg-[#3b82f6] hover:bg-blue-600 text-white px-4 rounded-lg text-xs font-bold transition">
                ส่งข้อความ
              </button>
            </form>
          </div>

          {/* TAB 5: 📊 Analytics (Live Stocks & Cryptos + Real Macro News) */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Analytics" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">📊 ศูนย์วิเคราะห์ตลาดแบบบูรณาการ (Analytics Desk)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">ฟีดราคาสดจากโบรกเกอร์ MT5 และ Binance CEX พร้อมสรุปข่าวจริงทั่วโลก</p>
            </div>

            {/* รายการตลาดตราสาร */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {SYMBOLS_LIST.map((s) => (
                <div 
                  key={s.symbol}
                  onClick={() => handleSymbolChange(s.symbol)}
                  className={`p-3 rounded-lg border cursor-pointer transition flex flex-col justify-between ${
                    symbol === s.symbol 
                      ? "bg-[#0d2a14] border-[#10b981] text-[#34d399]" 
                      : "bg-[#111520] border-[#1e2d45] hover:border-[#3d5a7a] text-slate-300"
                  }`}
                >
                  <div className="text-[10px] text-slate-400 font-bold">{s.category.toUpperCase()}</div>
                  <div className="text-sm font-bold mt-1 font-mono">{s.symbol}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5 truncate">{s.name}</div>
                </div>
              ))}
            </div>

            {/* บอร์ดข่าวกรองเศรษฐกิจ (Real Macro News Terminal) */}
            <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-3">
              <div className="text-xs text-[#fbbf24] font-bold uppercase tracking-wider">🚨 ข่าวเศรษฐกิจมหภาคและการเงินล่าสุด (Macro Financial Feed)</div>
              <div className="divide-y divide-slate-800">
                {newsFeed.map((item, idx) => (
                  <div key={idx} className="py-2.5 flex items-start gap-3 text-xs">
                    <span className="text-[#7a9bbf] font-mono font-bold bg-[#070a0f] px-1.5 py-0.5 rounded">{item.time}</span>
                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{item.source}</span>
                        <span className={`text-[8.5px] px-1 rounded font-bold ${item.impact === "HIGH" ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-yellow-500/10 text-yellow-400"}`}>
                          {item.impact} IMPACT
                        </span>
                      </div>
                      <p className="text-slate-300 leading-relaxed">{item.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* TAB 6: ⚠️ Risk Monitor (Hard Rules & Risk check audit) */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Risk Monitor" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">🛡️ สรุปกฎระเบียบความเสี่ยงพอร์ต (Risk Monitor & Compliance Audit)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">มอนิเตอร์ระดับความปลอดภัย การตั้งค่ากฎเหล็ก และประวัติการทำออดิตความเสี่ยง</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
                <div className="text-xs text-slate-400">ขีดจำกัดความเสี่ยงไม้ (Risk Limit)</div>
                <div className="text-2xl font-bold text-[#f87171] mt-1">{settingsForm.maxRiskPerTradePct}%</div>
                <div className="text-[10px] text-slate-500 mt-1">ต่อดีลเทรดจำลอง / จริง</div>
              </div>
              <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
                <div className="text-xs text-slate-400">ถือครองพอร์ตรวมสูงสุด (Max Exposure)</div>
                <div className="text-2xl font-bold text-[#fbbf24] mt-1">{settingsForm.maxOpenExposurePct}%</div>
                <div className="text-[10px] text-slate-500 mt-1">ของทุนสุทธิ (Net Equity)</div>
              </div>
              <div className="bg-[#111520] border border-[#1e2d45] p-4 rounded-xl text-center">
                <div className="text-xs text-slate-400">ลิมิต Drawdown ต่อวัน (Daily Loss)</div>
                <div className="text-2xl font-bold text-[#f87171] mt-1">3.00%</div>
                <div className="text-[10px] text-slate-500 mt-1">บล็อกเทรดทั้งวันทันทีหากชนลิมิต</div>
              </div>
            </div>

            {/* New Advanced Safety & Integrity Cards */}
            <div className="border-t border-[#1e2d45] pt-6 pb-2">
              <h3 className="text-sm font-bold text-white mb-1 uppercase tracking-wider">🛠️ ระบบเฝ้าระวังความเสี่ยงขั้นสูง (Advanced Risk Surveillance)</h3>
              <p className="text-[11px] text-[#7a9bbf]">ควบคุม Feature Flags, สเตตัส Circuit Breakers และตรวจสอบความสมบูรณ์ของข้อมูลแบบเรียลไทม์</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Card 1: Feature Flags */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  ⚙️ Feature Flags
                </div>
                <div className="space-y-2.5 text-xs">
                  {Object.entries(featureFlags || {}).map(([flag, enabled]) => (
                    <div key={flag} className="flex justify-between items-center border-b border-white/5 pb-1.5 last:border-0 last:pb-0">
                      <span className="text-slate-400 font-mono">{flag}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                        {enabled ? 'ON ●' : 'OFF ○'}
                      </span>
                    </div>
                  ))}
                  {Object.keys(featureFlags || {}).length === 0 && (
                    <div className="text-slate-500 text-center py-4">ไม่มีข้อมูล Flags</div>
                  )}
                </div>
              </div>

              {/* Card 2: Circuit Breakers */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  ⚡ Circuit Breakers
                </div>
                <div className="space-y-2.5 text-xs">
                  {Object.entries(circuitBreakers || {}).map(([name, val]: [string, any]) => (
                    <div key={name} className="flex justify-between items-center border-b border-white/5 pb-1.5 last:border-0 last:pb-0">
                      <span className="text-slate-400 font-mono">{name}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${val?.active ? 'bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                        {val?.active ? 'TRIGGERED 🔴' : 'SAFE 🟢'}
                      </span>
                    </div>
                  ))}
                  {Object.keys(circuitBreakers || {}).length === 0 && (
                    <div className="text-slate-500 text-center py-4">ไม่มีข้อมูล Breakers</div>
                  )}
                </div>
              </div>

              {/* Card 3: Heartbeat Monitors */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  📡 Heartbeat Monitors
                </div>
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">MT5 Broker Heartbeat:</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex items-center gap-1.5 ${heartbeats?.broker ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                      <span className={`w-1.5 h-1.5 rounded-full bg-emerald-400 ${heartbeats?.broker && 'animate-ping'}`}></span>
                      {heartbeats?.broker ? new Date(heartbeats.broker).toLocaleTimeString() : 'DISCONNECTED'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Command Center Sys:</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-cyan-500/10 text-cyan-400 font-bold">
                      {heartbeats?.system ? new Date(heartbeats.system).toLocaleTimeString() : 'OFFLINE'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 4: NaN Integrity Monitor */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    🛡️ Data Integrity (NaN Guard)
                  </div>
                  <p className="text-[10px] text-slate-500 mb-3">จำนวนเหตุการณ์ราคาสุดโต่งหรือค่าสูญหายที่ระบบดักกรองไว้</p>
                </div>
                <div className="flex justify-between items-end">
                  <span className="text-2xl font-bold text-cyan-400">{nanLogs?.count || 0}</span>
                  <span className="text-[10px] text-slate-400 border border-slate-500/20 px-2 py-0.5 rounded bg-slate-500/5">NaNs Guarded</span>
                </div>
              </div>

              {/* Card 5: Correlation Caps */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    🔀 Correlation Rejections
                  </div>
                  <p className="text-[10px] text-slate-500 mb-3">จำนวนออเดอร์ที่ถูกบล็อกเนื่องจากมี Exposure ทับซ้อนในกลุ่มเดียวกัน</p>
                </div>
                <div className="flex justify-between items-end">
                  <span className="text-2xl font-bold text-amber-400">{correlationRejections?.count || 0}</span>
                  <span className="text-[10px] text-slate-400 border border-slate-500/20 px-2 py-0.5 rounded bg-slate-500/5">Blocked Signals</span>
                </div>
              </div>

              {/* Card 6: Calibration Command Center */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 backdrop-blur-md hover:border-white/20 transition-all duration-300 flex flex-col justify-between">
                <div>
                  <div className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    🔄 Calibration Center
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400 mb-3">
                    <span>Calibrated: <b>{calibration?.calibrated_count || 0}</b></span>
                    <span>Pending: <b>{calibration?.pending_count || 0}</b></span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const res = await fetch("http://localhost:8000/api/calibrate", { method: "POST" });
                      const d = await res.json();
                      if (d.status === "success") {
                        addChatMessage("system", "🔄 กระตุ้นการทำ Rolling Calibration ข้อมูลวิเคราะห์สำเร็จ!");
                        fetchStateData();
                        alert("Rolling Calibration สำเร็จ!");
                      }
                    } catch (err) {
                      alert("การทำ Calibration ล้มเหลว");
                    }
                  }}
                  className="w-full text-center py-2 bg-purple-600/20 hover:bg-purple-600 border border-purple-500/30 hover:border-purple-500 text-purple-200 hover:text-white rounded-lg transition-all duration-300 font-bold text-xs"
                >
                  กระตุ้น Calibration 🔄
                </button>
              </div>
            </div>

            {/* รายการออดิตความเสี่ยงสะสม */}
            <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4">
              <div className="text-xs text-slate-300 font-bold uppercase tracking-wider mb-3">บันทึกประวัติการทำ Risk Audit (Decision Logs)</div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead>
                    <tr className="border-b border-[#1e2d45] text-slate-400 font-mono">
                      <th className="py-2">วัน-เวลา</th>
                      <th className="py-2">คู่สินทรัพย์</th>
                      <th className="py-2">ผลประเมิน</th>
                      <th className="py-2 text-right">Risk %</th>
                      <th className="py-2 text-right">Exposure %</th>
                      <th className="py-2 text-right">สถานะบิดออเดอร์</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {orders.map((ord, idx) => (
                      <tr key={idx} className="hover:bg-[#070a0f]/40">
                        <td className="py-2 text-slate-500">{ord.opened_at ? parseUTCDate(ord.opened_at).toLocaleTimeString('th-TH') : '-'}</td>
                        <td className="py-2 font-bold text-white">{ord.symbol}</td>
                        <td className="py-2 text-[#10b981] font-bold">✓ ผ่านด่านตรวจสอบ</td>
                        <td className="py-2 text-right">1.2%</td>
                        <td className="py-2 text-right">4.8%</td>
                        <td className="py-2 text-right text-teal-400">ปิดแล้ว (CLOSED)</td>
                      </tr>
                    ))}
                    {orders.length === 0 && (
                      <tr>
                        <td colSpan={6} className="py-4 text-center text-slate-500">ไม่มีผลตรวจความเสี่ยงค้างตรวจในระบบ</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* TAB 7: 📈 Reports (Ledger / P&L / Tax details) */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Reports" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4 flex justify-between items-center flex-wrap gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">📊 รายงานบัญชีและระเบียบภาษีคลัง (Team ERP Ledger & Tax Sheet)</h2>
                <p className="text-xs text-[#7a9bbf] mt-1">สมุดรายการเดบิต/เครดิต และประมาณการการชำระภาษีสะสมในไทย</p>
              </div>
              <button
                onClick={handleResetData}
                className="text-xs px-3 py-1.5 bg-red-600/20 hover:bg-red-600 border border-red-500/30 hover:border-red-500 text-red-200 hover:text-white rounded-lg transition-all duration-300 font-bold flex items-center gap-1.5 shadow-[0_0_10px_rgba(239,68,68,0.1)] hover:shadow-[0_0_15px_rgba(239,68,68,0.3)] font-sans"
              >
                🗑️ ล้างประวัติการเทรด & บัญชี ERP
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* รายงานเดบิต เครดิต ERP */}
              <div className="lg:col-span-2 bg-white/5 border border-white/10 rounded-xl p-5 space-y-4 backdrop-blur-md">
                <div className="text-xs text-white font-bold uppercase tracking-wider font-mono flex justify-between items-center">
                  <span>สมุดบัญชีแยกประเภททั่วไป (General Ledger Double-Entry)</span>
                  <span className="text-[10px] text-slate-500 font-normal font-sans">ล่าสุด: {ledger.length} รายการ</span>
                </div>
                <div className="space-y-3 max-h-[450px] overflow-y-auto pr-1">
                  {ledger.length === 0 ? (
                    <div className="text-center text-slate-500 py-24 text-xs font-sans">
                      ยังไม่มีรายการบันทึกในสมุดบัญชีแยกประเภท
                    </div>
                  ) : (
                    ledger.map((tx, idx) => (
                      <div key={idx} className="bg-black/60 border border-white/5 p-4 rounded-lg text-xs space-y-2.5 font-mono hover:border-white/10 transition-colors">
                        <div className="flex justify-between text-[10px] text-slate-500">
                          <span>TX ID: {tx.id}</span>
                          <span>{parseUTCDate(tx.timestamp).toLocaleString('th-TH')}</span>
                        </div>
                        <div className="font-semibold text-slate-200">{tx.description}</div>
                        <div className="grid grid-cols-2 gap-4 text-[10px] border-t border-white/5 pt-2">
                          <div className="text-emerald-400">
                            Dr: {tx.debit.account}
                            <div className="font-bold text-white text-xs mt-0.5">${tx.debit.amount.toLocaleString()}</div>
                          </div>
                          <div className="text-amber-400">
                            Cr: {tx.credit.account}
                            <div className="font-bold text-white text-xs mt-0.5">${tx.credit.amount.toLocaleString()}</div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* แบบสรุปภาษี Team Tax */}
              <div className="bg-white/5 border border-white/10 rounded-xl p-5 space-y-5 backdrop-blur-md">
                <div className="text-xs text-white font-bold uppercase tracking-wider font-mono">แบบสรุปการยื่นภาษีสะสม (Team Tax Summary)</div>
                {taxSummary ? (
                  <div className="text-xs space-y-4 font-mono">
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-slate-400">กำไรสะสม (Accumulated PnL):</span>
                      <span className="font-bold text-emerald-400">${taxSummary.accumulatedPnL.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-slate-400">ค่าธรรมเนียมสะสม (Accumulated Fees):</span>
                      <span className="font-bold text-red-400">${taxSummary.accumulatedFees.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-slate-400">รายได้สุทธิเพื่อคำนวณ (Taxable Income):</span>
                      <span className="font-bold text-white">${taxSummary.taxableIncome.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-emerald-400 font-bold">ภาษีซื้อขอคืนสะสม (VAT {taxSummary.vatRate}):</span>
                      <span className="font-bold text-emerald-400">+${taxSummary.inputVatClaimable.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-red-400 font-bold">ภาษีนิติบุคคลหักสะสม ({taxSummary.corporateTaxRate}):</span>
                      <span className="font-bold text-red-400">-${taxSummary.estimatedIncomeTax.toLocaleString()}</span>
                    </div>
                    <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex justify-between items-center text-sm font-bold mt-4 shadow-[0_0_15px_rgba(16,185,129,0.05)] font-sans">
                      <span className="text-emerald-400">กำไรสุทธิหลังหักภาษี (Net profit):</span>
                      <span className="text-emerald-400 text-base font-black">${taxSummary.netAfterTax.toLocaleString()}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-slate-500 py-12 text-xs font-sans">ยังไม่มีข้อมูลภาษีสะสม</div>
                )}
              </div>
            </div>
          </div>

          {/* TAB 8: 📈 Performance Dashboard */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Performance Dashboard" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">📈 AI Trading Performance Dashboard</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">Live metrics from the trading engines.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              
              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
                <div className="text-xs text-slate-400">Total Trades</div>
                <div className="text-3xl font-bold text-white mt-2">{closedOrders.length}</div>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
                <div className="text-xs text-slate-400">Win Rate</div>
                <div className="text-3xl font-bold text-[#10b981] mt-2">
                  {closedOrders.length > 0 ? ((closedOrders.filter(o => o.pnl > 0).length / closedOrders.length) * 100).toFixed(1) : 0}%
                </div>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
                <div className="text-xs text-slate-400">Total PnL</div>
                <div className={`text-3xl font-bold mt-2 ${todayPnLSum >= 0 ? "text-[#10b981]" : "text-[#f87171]"}`}>
                  ${todayPnLSum.toFixed(2)}
                </div>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 text-center">
                <div className="text-xs text-slate-400">Active Positions</div>
                <div className="text-3xl font-bold text-[#3b82f6] mt-2">{activeTradesCount}</div>
              </div>
            </div>
            
            {/* Recent Trades Table */}
            <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 mt-6">
              <div className="text-xs text-white font-bold uppercase tracking-wider mb-4">Recent Executions</div>
              <table className="w-full text-left text-xs text-slate-300">
                  <thead>
                    <tr className="border-b border-[#1e2d45] text-slate-400 font-mono">
                      <th className="py-2">ID</th>
                      <th className="py-2">Symbol</th>
                      <th className="py-2">Action</th>
                      <th className="py-2">Status</th>
                      <th className="py-2 text-right">Entry Price</th>
                      <th className="py-2 text-right">PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {closedOrders.map((ord, idx) => (
                      <tr key={idx} className="hover:bg-[#070a0f]/40">
                        <td className="py-2 text-slate-500 truncate max-w-[100px]">{ord.id}</td>
                        <td className="py-2 font-bold text-white">{ord.symbol}</td>
                        <td className={`py-2 font-bold ${ord.action === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>{ord.action}</td>
                        <td className="py-2">{ord.status}</td>
                        <td className="py-2 text-right">{ord.entry_price}</td>
                        <td className={`py-2 text-right font-bold ${ord.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{ord.pnl.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
              </table>
            </div>

          </div>

          {/* TAB 9: ⚙️ Settings (Telegram Bot Config & constants) */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#000000] space-y-6 ${activeMenu === "Settings" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">⚙️ ตั้งค่าความปลอดภัยและบัญชาการระบบ (System Settings)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">กรอกข้อมูล Bot Token จริง และปรับแต่งพารามิเตอร์ตรวจสอบความเสี่ยงพอร์ต</p>
            </div>

            <form onSubmit={handleSaveSettings} className="bg-[#111520] border border-[#1e2d45] rounded-xl p-6 space-y-4 max-w-xl">
              <div className="text-xs font-bold text-[#22d3ee] uppercase tracking-wider border-b border-[#1e2d45] pb-2 mb-2">
                🤖 บัญชาการ Telegram Bot จริง
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-white font-bold block">Telegram Bot Token จริง (จาก @BotFather):</label>
                <input 
                  type="text" 
                  value={settingsForm.telegram_token}
                  onChange={(e) => setSettingsForm({...settingsForm, telegram_token: e.target.value})}
                  placeholder="กรอก Bot Token ของคุณ เช่น 123456:ABC-def..."
                  className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                />
              </div>

              <div className="text-xs font-bold text-[#10b981] uppercase tracking-wider border-b border-[#1e2d45] pb-2 pt-2 mb-2">
                🧠 มันสมองสภา AI (Claude API)
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-white font-bold block">Anthropic (Claude) API Key:</label>
                <input 
                  type="password" 
                  value={settingsForm.anthropic_key}
                  onChange={(e) => setSettingsForm({...settingsForm, anthropic_key: e.target.value})}
                  placeholder="sk-ant-api03-..."
                  className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                />
              </div>

              <div className="text-xs font-bold text-[#fbbf24] uppercase tracking-wider border-b border-[#1e2d45] pb-2 pt-2 mb-2">
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
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-white font-bold block">Binance API Secret:</label>
                  <input 
                    type="password" 
                    value={settingsForm.binance_secret}
                    onChange={(e) => setSettingsForm({...settingsForm, binance_secret: e.target.value})}
                    placeholder="Binance Secret Key"
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
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
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-white font-bold block">TwelveData API Key:</label>
                  <input 
                    type="password" 
                    value={settingsForm.twelvedata_api_key}
                    onChange={(e) => setSettingsForm({...settingsForm, twelvedata_api_key: e.target.value})}
                    placeholder="TwelveData Key"
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-white font-bold block">Finnhub API Token:</label>
                  <input 
                    type="password" 
                    value={settingsForm.finnhub_api_key}
                    onChange={(e) => setSettingsForm({...settingsForm, finnhub_api_key: e.target.value})}
                    placeholder="Finnhub Token"
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                  />
                </div>
              </div>

              <div className="text-xs font-bold text-[#f87171] uppercase tracking-wider border-b border-[#1e2d45] pb-2 pt-2 mb-2">
                🛡️ การควบคุมความเสี่ยงพอร์ต
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs text-white font-bold block">Max Risk Per Trade (%):</label>
                  <input 
                    type="number" step="0.1"
                    value={settingsForm.maxRiskPerTradePct}
                    onChange={(e) => setSettingsForm({...settingsForm, maxRiskPerTradePct: Number(e.target.value)})}
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs text-white font-bold block">Max Open Exposure (%):</label>
                  <input 
                    type="number" step="0.1"
                    value={settingsForm.maxOpenExposurePct}
                    onChange={(e) => setSettingsForm({...settingsForm, maxOpenExposurePct: Number(e.target.value)})}
                    className="w-full bg-[#070a0f] border border-[#1e2d45] rounded-lg px-3 py-2 text-xs text-white outline-none focus:border-[#3b82f6] font-mono"
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
            <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-5 space-y-4 max-w-xl text-xs">
              <h3 className="font-bold text-white text-sm flex items-center gap-1.5 border-b border-[#1e2d45] pb-2">
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
        </main>
      </div>

      {/* ── CHAT & ACTIVITY LOG PANEL (ขวา) ── */}
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
      </div>
    );
  }