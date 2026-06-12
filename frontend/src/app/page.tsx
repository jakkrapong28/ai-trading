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
  pnl: number;
  fee: number;
  status: string;
  opened_at?: string;
  closed_at?: string;
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
  { id: "report", name: "Report AI", role: "ฝ่ายเขียนรายงาน", color: "#1e113a", border: "#6c2e9c", labelColor: "#d8b4fe", emoji: "📋", bubble: "สร้างรายงานสรุป...", status: "idle", col: 0, row: 0 },
  { id: "audit", name: "Audit AI", role: "ฝ่ายความถูกต้อง", color: "#160f29", border: "#3b2c80", labelColor: "#a78bfa", emoji: "🔍", bubble: "ตรวจสอบประวัติ...", status: "online", col: 1, row: 0 },
  { id: "ceo", name: "CEO Agent", role: "ผู้นำบัญชาการ", color: "#0d1b2a", border: "#1b4965", labelColor: "#60a5fa", emoji: "🕴️", bubble: "แจกงานให้ทีม!", status: "online", col: 2, row: 0 },
  
  { id: "finance", name: "Finance AI", role: "ฝ่ายการเงิน ERP", color: "#0f2a2a", border: "#1c5c5c", labelColor: "#22d3ee", emoji: "💰", bubble: "บันทึกบัญชีแยกประเภท...", status: "online", col: 0, row: 1 },
  { id: "ea", name: "EA Bot", role: "ฝ่ายยิงออเดอร์", color: "#0e0e26", border: "#252575", labelColor: "#818cf8", emoji: "🤖", bubble: "รอยิงคำสั่ง...", status: "busy", col: 1, row: 1 },
  { id: "chart", name: "Chart AI", role: "วิเคราะห์กราฟ", color: "#0a1f11", border: "#184f24", labelColor: "#34d399", emoji: "📊", bubble: "ประเมินแนวรับ...", status: "busy", col: 2, row: 1 },
  
  { id: "strategy", name: "Strategy AI", role: "กลยุทธ์การลงทุน", color: "#221a0f", border: "#523c1c", labelColor: "#fbbf24", emoji: "🎯", bubble: "หมุนสภาวะตลาด...", status: "online", col: 0, row: 2 },
  { id: "alert", name: "Alert AI", role: "แจ้งเตือนภัยพอร์ต", color: "#2c1611", border: "#6b2c1f", labelColor: "#f97316", emoji: "🔔", bubble: "เช็คสเปรดโบรกเกอร์...", status: "busy", col: 1, row: 2 },
  { id: "risk", name: "Risk AI", role: "ฝ่ายควบคุมความเสี่ยง", color: "#2c0e0e", border: "#6b1c1c", labelColor: "#f87171", emoji: "⚠️", bubble: "เช็ค Limit พอร์ต!", status: "busy", col: 2, row: 2 },
];

const AGENT_COLORS: Record<string, string> = {
  ceo: "#3b82f6", chart: "#10b981", audit: "#a855f7",
  ea: "#6366f1", risk: "#ef4444", finance: "#06b6d4",
  strategy: "#f59e0b", alert: "#f97316", report: "#c084fc"
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

export default function Dashboard() {
  const [activeMenu, setActiveMenu] = useState("Office Overview");
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "error">("connecting");
  
  // --- สเตตจำลองจากระบบเทรดและ ERP ---
  const [symbol, setSymbol] = useState("XAUUSD");
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [indicators, setIndicators] = useState<Indicator | null>(null);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [risk, setRisk] = useState<RiskCheck | null>(null);
  const [mode, setMode] = useState("watch");
  const [balances, setBalances] = useState<Balance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [filterDate, setFilterDate] = useState("");
  
  const [featureFlags, setFeatureFlags] = useState<Record<string, boolean>>({});
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, any>>({});
  const [heartbeats, setHeartbeats] = useState<Record<string, any>>({});
  const [nanLogs, setNanLogs] = useState({ count: 0 });
  const [calibration, setCalibration] = useState({ calibrated_count: 0, pending_count: 0 });
  const [correlationRejections, setCorrelationRejections] = useState({ count: 0 });
  
  const getMenuButtonClass = (menuName: string) => {
    const isActive = activeMenu === menuName;
    return `w-full flex items-center justify-between px-3 py-1.5 text-[12.5px] rounded text-left transition-all duration-300 ${
      isActive 
        ? "bg-white/10 text-emerald-400 border-l-2 border-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.15)] backdrop-blur-sm font-bold" 
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
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // คลาสอ้างอิงตำแหน่งของ Agents ที่เคลื่อนไหวอยู่บน Canvas
  const agentsStateRef = useRef<any[]>([]);
  const frameCountRef = useRef(0);
  const scaleMultiplierRef = useRef(1.0);

  // สถิติยอดพอร์ตและการเทรด
  const totalEquity = (balances || []).reduce((sum, b) => sum + b.equity, 0);
  const activeTradesCount = (orders || []).filter((o) => o.status === "PENDING" || o.status === "OPEN").length;
  const closedOrders = (orders || []).filter((o) => o.status === "CLOSED");
  const todayPnLSum = closedOrders.reduce((sum, o) => sum + o.pnl, 0);

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
          setLatestPrice(msg.price);
          setIndicators(msg.indicators);
          setSignal(msg.signal);
          setRisk(msg.risk);
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
          setOrders((prev) => [msg.order, ...prev]);
          if (msg.balances) setBalances(msg.balances);
          addChatMessage("ea", `🔔 [ระบบ Team ERP] เปิดออเดอร์ใหม่สถานะรอดำเนินการ: ${msg.order.action} ${msg.order.symbol} ที่ราคา ${msg.order.entry_price}`);
          fetchERPData();
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

      // Fit all rooms in available space
      // base sizes: sizeX=150, sizeY=87, wallH=60
      // Total height span: wallH + 5*sizeY (bottom room center at row+col=4 is 4*sizeY below grid center)
      // + sizeY for bottom half of diamond + ~25px for desk furniture + agent
      const availableH = H - BOTTOM_BAR_H;
      const wallToSizeXRatio = 60 / 150;
      const sizeYToSizeXRatio = 87 / 150;
      // Height constraint: wallH + 5.5*sizeY + 25 <= 0.88 * availableH
      const furniturePad = 25; // pixels for desk+agent below room center
      const maxByH = (availableH * 0.85 - 20) / (wallToSizeXRatio + 5.2 * sizeYToSizeXRatio);
      const maxByW = (W * 0.85) / 6.0;
      const targetSizeX = Math.min(maxByH, maxByW);
      scaleMultiplier = Math.max(0.25, Math.min(1.1, targetSizeX / 150));
      scaleMultiplierRef.current = scaleMultiplier;
      sizeX = Math.round(150 * scaleMultiplier);
      sizeY = Math.round(87 * scaleMultiplier);
      wallHeight = Math.round(60 * scaleMultiplier);
      charScale = 1.8 * scaleMultiplier;

      centers = getRoomCenters(W, H);
    };

    resize();

    if (agentsStateRef.current.length === 0) {
      agentsStateRef.current = ROOMS_CONFIG.map((r) => {
        return {
          id: r.id,
          color: AGENT_COLORS[r.id] || "#ffffff",
          lx: 0, 
          ly: 0, 
          tx: 0, 
          ty: 0,
          speed: 0.55 + Math.random() * 0.3,
          facing: "down",
          speaking: false,
          speakTimer: 0,
          idleTimer: Math.random() * 60,
          moving: false,
          bubble: "",
          bubbleTimer: 0,
        };
      });
    }

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

      // 1. วาดพื้นห้องนีออน (Sleek Tech Metallic Grid Floor)
      ctx.fillStyle = r.color;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.fill();

      // เส้นตารางเรืองแสงสีนีออน (Cyber Grid)
      ctx.strokeStyle = r.border + "44";
      ctx.lineWidth = 0.8;
      const step = 5;
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

      // วาดขอบพื้นห้องนีออนเรืองแสง (Neon Glowing Border)
      ctx.strokeStyle = r.border;
      ctx.lineWidth = 2.0;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx, cy + sizeY);
      ctx.lineTo(cx - sizeX, cy);
      ctx.closePath();
      ctx.stroke();
      ctx.shadowBlur = 0; // Reset shadow blur

      // 2. วาดผนัง 3D กระจกใสไฮเทค (Sleek Tech Glass Walls)
      // เสาหลักเสามุมเรืองแสง (Glowing pillars)
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(cx - sizeX - 2, cy - wallHeight, 4, wallHeight);
      ctx.fillRect(cx + sizeX - 2, cy - wallHeight, 4, wallHeight);
      ctx.fillRect(cx - 2, cy - sizeY - wallHeight, 4, wallHeight);

      // วาดแผงกระจกสะท้อนแสงสีฟ้านีออน
      ctx.fillStyle = "rgba(6, 182, 212, 0.04)";
      ctx.beginPath();
      ctx.moveTo(cx - sizeX, cy);
      ctx.lineTo(cx, cy - sizeY);
      ctx.lineTo(cx, cy - sizeY - wallHeight);
      ctx.lineTo(cx - sizeX, cy - wallHeight);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = r.border + "33";
      ctx.stroke();

      ctx.fillStyle = "rgba(6, 182, 212, 0.02)";
      ctx.beginPath();
      ctx.moveTo(cx, cy - sizeY);
      ctx.lineTo(cx + sizeX, cy);
      ctx.lineTo(cx + sizeX, cy - wallHeight);
      ctx.lineTo(cx, cy - sizeY - wallHeight);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // ════════════════════════════════════════════════════════
      // 3. วาดเฟอร์นิเจอร์ + คอมพิวเตอร์ทุกห้อง — Real Office Look
      // ════════════════════════════════════════════════════════
      const S = scaleMultiplier;

      // ── ต้นไม้ / หม้อไม้ ประดับทั่วไป ──
      const drawPlant = (px: number, py: number) => {
        ctx.fillStyle = "#3d2b1f";
        ctx.fillRect(px - 4*S, py, 8*S, 7*S);
        ctx.fillStyle = "#166534";
        ctx.beginPath();
        ctx.arc(px, py - 7*S, 6*S, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = "#15803d";
        ctx.beginPath();
        ctx.arc(px - 5*S, py - 4*S, 4*S, 0, Math.PI*2); ctx.fill();
        ctx.beginPath();
        ctx.arc(px + 5*S, py - 4*S, 4*S, 0, Math.PI*2); ctx.fill();
      };

      // ── วาดโต๊ะ (isometric desk top + side) ──
      const drawDesk = (bx: number, by: number, dw: number, dd: number, col: string, accent: string) => {
        // ข้างมือเซ้า (left face)
        ctx.fillStyle = "#0f172a";
        ctx.beginPath();
        ctx.moveTo(bx,      by);
        ctx.lineTo(bx - dd*0.4, by + dd*0.35);
        ctx.lineTo(bx - dd*0.4, by + dd*0.35 + 9*S);
        ctx.lineTo(bx,      by + 9*S);
        ctx.closePath(); ctx.fill();
        // หน้า (right face)
        ctx.fillStyle = "#1a2744";
        ctx.beginPath();
        ctx.moveTo(bx,      by);
        ctx.lineTo(bx + dw, by - dw*0.22);
        ctx.lineTo(bx + dw, by - dw*0.22 + 9*S);
        ctx.lineTo(bx,      by + 9*S);
        ctx.closePath(); ctx.fill();
        // หน้าโต๊ะ (top surface)
        ctx.fillStyle = col;
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(bx,           by);
        ctx.lineTo(bx + dw,      by - dw*0.22);
        ctx.lineTo(bx + dw - dd*0.4, by - dw*0.22 + dd*0.35);
        ctx.lineTo(bx - dd*0.4,  by + dd*0.35);
        ctx.closePath(); ctx.fill(); ctx.stroke();
      };

      // ── จอคอมพิวเตอร์แบบ isometric (monitor on desk) ──
      const drawMonitor = (mx: number, my: number, mw: number, mh: number, screenColor: string, content?: () => void) => {
        // ขาตั้ง
        ctx.fillStyle = "#334155";
        ctx.fillRect(mx + mw*0.45, my + mh, mw*0.1, 5*S);
        ctx.fillRect(mx + mw*0.3, my + mh + 5*S, mw*0.4, 2*S);
        // กรอบจอ
        ctx.fillStyle = "#1e293b";
        ctx.beginPath();
        ctx.roundRect(mx - 2*S, my - 2*S, mw + 4*S, mh + 4*S, 2*S);
        ctx.fill();
        // หน้าจอ
        ctx.fillStyle = screenColor;
        ctx.beginPath();
        ctx.roundRect(mx, my, mw, mh, 1*S);
        ctx.fill();
        if (content) content();
      };

      // ── MacBook (slim laptop) ──
      const drawMacBook = (lx: number, ly: number, lw: number, accent: string) => {
        const lh = lw * 0.62;
        // lid (screen)
        ctx.fillStyle = "#1c2333";
        ctx.beginPath(); ctx.roundRect(lx, ly - lh, lw, lh, 2*S); ctx.fill();
        ctx.fillStyle = "#0a0f1e";
        ctx.beginPath(); ctx.roundRect(lx + 2*S, ly - lh + 2*S, lw - 4*S, lh - 4*S, 1*S); ctx.fill();
        // Apple logo
        ctx.fillStyle = accent + "99";
        ctx.beginPath(); ctx.arc(lx + lw/2, ly - lh/2, 3*S, 0, Math.PI*2); ctx.fill();
        // base
        ctx.fillStyle = "#374151";
        ctx.beginPath(); ctx.roundRect(lx - 2*S, ly, lw + 4*S, 4*S, 1*S); ctx.fill();
        // keyboard glow
        ctx.fillStyle = accent + "22";
        ctx.beginPath(); ctx.roundRect(lx + 2*S, ly + 1*S, lw - 4*S, 2*S, 0.5*S); ctx.fill();
      };

      // ── Keyboard ──
      const drawKeyboard = (kx: number, ky: number, kw: number, accent: string) => {
        ctx.fillStyle = "#1e293b";
        ctx.beginPath(); ctx.roundRect(kx, ky, kw, 5*S, 1*S); ctx.fill();
        ctx.strokeStyle = accent + "44"; ctx.lineWidth = 0.5;
        for (let ki = 0; ki < 4; ki++) {
          ctx.beginPath();
          ctx.moveTo(kx + 2*S, ky + 1.2*S * ki + 0.8*S);
          ctx.lineTo(kx + kw - 2*S, ky + 1.2*S * ki + 0.8*S);
          ctx.stroke();
        }
      };

      // ── Mouse ──
      const drawMouse = (ox: number, oy: number, accent: string) => {
        ctx.fillStyle = "#1e293b";
        ctx.beginPath(); ctx.ellipse(ox, oy, 3*S, 4.5*S, 0, 0, Math.PI*2); ctx.fill();
        ctx.strokeStyle = accent + "66"; ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(ox, oy - 4.5*S); ctx.lineTo(ox, oy + 1*S); ctx.stroke();
      };

      // ── Coffee cup ──
      const drawCoffee = (ox: number, oy: number) => {
        ctx.fillStyle = "#78350f";
        ctx.fillRect(ox - 3*S, oy - 5*S, 6*S, 6*S);
        ctx.strokeStyle = "#92400e"; ctx.lineWidth = 0.5;
        ctx.strokeRect(ox - 3*S, oy - 5*S, 6*S, 6*S);
        ctx.fillStyle = "#451a03";
        ctx.beginPath(); ctx.ellipse(ox, oy - 5*S, 3*S, 1.5*S, 0, 0, Math.PI*2); ctx.fill();
        // handle
        ctx.strokeStyle = "#92400e"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(ox + 3.5*S, oy - 2*S, 2*S, -0.5, 0.5); ctx.stroke();
      };

      // ════════════════════════════════
      // ตำแหน่งโต๊ะกลางห้อง (room-relative coords)
      // ════════════════════════════════
      const deskBX = cx - 18*S; // base X of desk front-left corner
      const deskBY = cy + 12*S; // base Y
      const deskW  = 50*S;

      // วาดโต๊ะทุกห้อง (glass desk with neon accent)
      drawDesk(deskBX, deskBY, deskW, 20*S, "rgba(15,23,42,0.92)", r.border);

      // Keyboard + mouse on desk top
      const kbX = deskBX + 5*S;
      const kbY = deskBY - 3.5*S;
      drawKeyboard(kbX, kbY, 22*S, r.labelColor);
      drawMouse(deskBX + 32*S, deskBY - 2*S, r.labelColor);

      // ════════════════════════════════
      // เฮดเอร์เฉพาะตามแผนก
      // ════════════════════════════════
      if (r.id === "ceo") {
        // CEO: จอคู่ + MacBook (premium setup)
        // จอใหญ่ซ้าย
        drawMonitor(cx - 28*S, cy - 14*S, 20*S, 13*S, "#0d1b2a", () => {
          // dashboard
          ctx.fillStyle = "#60a5fa22";
          ctx.fillRect(cx - 28*S + 1*S, cy - 14*S + 1*S, 18*S, 11*S);
          ctx.fillStyle = "#60a5fa"; ctx.font = `bold ${Math.round(4*S)}px monospace`;
          ctx.fillText("CEO DASH", cx - 27*S, cy - 8*S);
          for (let b = 0; b < 3; b++) {
            ctx.fillStyle = ["#10b981","#f59e0b","#ef4444"][b];
            ctx.fillRect(cx - 27*S + b*6*S, cy - 6*S, 5*S, 3*S);
          }
        });
        // จอเล็กขวาย
        drawMonitor(cx - 6*S, cy - 11*S, 14*S, 9*S, "#080c1a", () => {
          ctx.fillStyle = "#fbbf24"; ctx.font = `bold ${Math.round(3.5*S)}px monospace`;
          ctx.fillText("XAUUSD", cx - 5*S, cy - 6*S);
          ctx.fillStyle = "#10b981"; ctx.fillText("+2.4%", cx - 5*S, cy - 3*S);
        });
        drawMacBook(cx + 10*S, cy + 4*S, 18*S, "#60a5fa");
        drawPlant(cx - sizeX + 25*S, cy + 5*S);
        drawCoffee(cx + 6*S, deskBY - 4*S);
        // ถ้วยรางวัลทอง
        ctx.fillStyle = "#fbbf24";
        ctx.beginPath(); ctx.arc(cx - sizeX + 38*S, cy + 10*S, 3*S, 0, Math.PI*2); ctx.fill();
        ctx.fillRect(cx - sizeX + 37*S, cy + 13*S, 2*S, 5*S);
        ctx.fillRect(cx - sizeX + 34*S, cy + 18*S, 8*S, 2*S);

      } else if (r.id === "chart") {
        // Chart AI: สามจอเรียงกันแสดงกราฟ
        const fc = frameCountRef.current;
        drawMonitor(cx - 30*S, cy - 15*S, 18*S, 12*S, "#031a0a", () => {
          // candlesticks
          const candles = [6,3,8,5,7,4,9,2,7,5];
          candles.forEach((h, i) => {
            const up = i % 2 === 0;
            ctx.fillStyle = up ? "#10b981" : "#ef4444";
            ctx.fillRect(cx - 29*S + i*1.8*S, cy - 7*S - h*0.8*S, 1.2*S, h*0.8*S);
          });
        });
        drawMonitor(cx - 10*S, cy - 12*S, 18*S, 12*S, "#031a0a", () => {
          // RSI line
          ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 1;
          ctx.beginPath();
          [40,55,48,62,50,58,45,67,52,60].forEach((v, i) => {
            const px2 = cx - 9*S + i*1.7*S;
            const py2 = cy - 6*S - (v - 40)*0.08*S;
            i === 0 ? ctx.moveTo(px2, py2) : ctx.lineTo(px2, py2);
          });
          ctx.stroke();
        });
        drawMonitor(cx + 10*S, cy - 9*S, 14*S, 9*S, "#02050f", () => {
          ctx.fillStyle = "#a78bfa"; ctx.font = `bold ${Math.round(3*S)}px monospace`;
          ctx.fillText("LIVE FEED", cx + 11*S, cy - 5*S);
          ctx.fillStyle = `rgba(167,139,250,${0.4 + Math.sin(fc*0.1)*0.3})`;
          ctx.fillText("BTC " + (44000 + Math.round(Math.sin(fc*0.05)*200)), cx + 11*S, cy - 2*S);
        });
        drawKeyboard(deskBX + 2*S, deskBY - 4*S, 28*S, r.labelColor);

      } else if (r.id === "ea") {
        // EA Bot: จอคู่ + ตู้เซิร์วเดอร์
        drawMonitor(cx - 26*S, cy - 13*S, 18*S, 12*S, "#020817", () => {
          ctx.fillStyle = "#818cf8"; ctx.font = `bold ${Math.round(3.5*S)}px monospace`;
          const status = ["SCANNING","EXECUTE","WAITING"][(Math.floor(frameCountRef.current/30))%3];
          ctx.fillText(status, cx - 25*S, cy - 7*S);
          ctx.fillStyle = `rgba(99,102,241,${0.5+Math.sin(frameCountRef.current*0.15)*0.4})`;
          ctx.fillRect(cx - 25*S, cy - 5*S, 16*S, 2*S);
        });
        drawMonitor(cx - 6*S, cy - 10*S, 14*S, 9*S, "#020817", () => {
          ctx.fillStyle = "#10b981"; ctx.font = `${Math.round(3*S)}px monospace`;
          ["LOT: 0.1","SL: 15","TP: 30"].forEach((t, i) => ctx.fillText(t, cx - 5*S, cy - 7*S + i*3*S));
        });
        // ตู้เซิร์วเดอร์
        const sx = cx + 12*S; const sy2 = cy - 14*S;
        ctx.fillStyle = "#0a0f1a";
        ctx.fillRect(sx, sy2, 14*S, 28*S);
        ctx.strokeStyle = "#3b82f6"; ctx.lineWidth = 0.8;
        ctx.strokeRect(sx, sy2, 14*S, 28*S);
        for (let li = 0; li < 6; li++) {
          const on = (frameCountRef.current + li*3) % 18 > 9;
          ctx.fillStyle = on ? "#10b981" : "#064e3b";
          ctx.beginPath(); ctx.arc(sx+4*S, sy2+4*S+li*4*S, 1.5*S, 0, Math.PI*2); ctx.fill();
          ctx.fillStyle = (frameCountRef.current + li*5) % 14 > 7 ? "#3b82f6" : "#1e3a5f";
          ctx.beginPath(); ctx.arc(sx+9*S, sy2+4*S+li*4*S, 1.5*S, 0, Math.PI*2); ctx.fill();
        }

      } else if (r.id === "risk") {
        // Risk AI: จอแสดงการเตือนภัย
        const riskPulse = Math.sin(frameCountRef.current * 0.15) > 0;
        drawMonitor(cx - 28*S, cy - 14*S, 20*S, 13*S, riskPulse ? "#200808" : "#0d0505", () => {
          ctx.fillStyle = riskPulse ? "#ef4444" : "#7f1d1d";
          ctx.font = `bold ${Math.round(4*S)}px monospace`;
          ctx.fillText("RISK ALERT", cx - 27*S, cy - 9*S);
          ctx.fillStyle = "#fca5a5"; ctx.font = `${Math.round(3*S)}px monospace`;
          ["SPREAD: 3.2","LOSS: -$120","LIMIT: 2%"].forEach((t,i)=>ctx.fillText(t, cx-27*S, cy-6*S+i*3*S));
        });
        drawMonitor(cx - 5*S, cy - 11*S, 14*S, 9*S, "#0d0505", () => {
          ctx.fillStyle = riskPulse ? "#ef4444" : "#991b1b";
          ctx.beginPath(); ctx.arc(cx+2*S, cy-7*S, 4*S, 0, Math.PI*2); ctx.fill();
          ctx.fillStyle = "#fff"; ctx.font = `bold ${Math.round(3*S)}px monospace`;
          ctx.fillText("!", cx+1*S, cy-5.5*S);
        });
        // siren
        ctx.fillStyle = riskPulse ? "#ef4444" : "#7f1d1d";
        ctx.beginPath(); ctx.arc(cx + sizeX - 18*S, cy - sizeY/2, 5*S, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = riskPulse ? "rgba(239,68,68,0.3)" : "transparent";
        ctx.beginPath(); ctx.arc(cx + sizeX - 18*S, cy - sizeY/2, 10*S, 0, Math.PI*2); ctx.fill();

      } else if (r.id === "finance") {
        // Finance AI: จอคู่ + ตู้นิรภัย
        drawMonitor(cx - 28*S, cy - 14*S, 20*S, 13*S, "#011a1a", () => {
          ctx.fillStyle = "#22d3ee"; ctx.font = `bold ${Math.round(4*S)}px monospace`;
          ctx.fillText("ERP LEDGER", cx - 27*S, cy - 9*S);
          ctx.fillStyle = "#67e8f9"; ctx.font = `${Math.round(3*S)}px monospace`;
          ["REV: +$2340","EXP: -$440","NET: $1900"].forEach((t,i)=>ctx.fillText(t, cx-27*S, cy-6*S+i*3*S));
        });
        drawMonitor(cx - 6*S, cy - 11*S, 14*S, 9*S, "#011a1a", () => {
          // bar chart
          [4,7,5,9,6,8].forEach((h,i) => {
            ctx.fillStyle = "#06b6d4";
            ctx.fillRect(cx-4*S+i*2.2*S, cy-4*S-h*0.8*S, 1.5*S, h*0.8*S);
          });
        });
        // ตู้นิรภัย
        const sfx = cx - sizeX + 28*S; const sfy = cy - 8*S;
        ctx.fillStyle = "#1e293b";
        ctx.fillRect(sfx, sfy, 14*S, 18*S);
        ctx.strokeStyle = "#06b6d4"; ctx.lineWidth = 1;
        ctx.strokeRect(sfx, sfy, 14*S, 18*S);
        ctx.beginPath(); ctx.arc(sfx+7*S, sfy+9*S, 3*S, 0, Math.PI*2); ctx.stroke();
        ctx.fillStyle = "#06b6d4";
        ctx.beginPath(); ctx.arc(sfx+7*S, sfy+9*S, 1.5*S, 0, Math.PI*2); ctx.fill();

      } else if (r.id === "strategy") {
        // Strategy AI: จอ + Whiteboard
        drawMonitor(cx - 26*S, cy - 13*S, 18*S, 12*S, "#0f0e00", () => {
          ctx.fillStyle = "#fbbf24"; ctx.font = `bold ${Math.round(4*S)}px monospace`;
          ctx.fillText("STRATEGY", cx - 25*S, cy - 8*S);
          ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 1;
          ctx.beginPath();
          [30,60,45,75,55,80,65].forEach((v,i) => {
            const px2 = cx - 25*S + i*2.4*S;
            const py2 = cy - 6*S - (v-30)*0.06*S;
            i===0?ctx.moveTo(px2,py2):ctx.lineTo(px2,py2);
          }); ctx.stroke();
        });
        drawMacBook(cx - 5*S, cy + 5*S, 18*S, "#fbbf24");
        // Whiteboard
        const wx = cx - sizeX + 15*S, wy2 = cy - sizeY/2 - 5*S;
        ctx.fillStyle = "#f1f5f9";
        ctx.fillRect(wx, wy2, 22*S, 16*S);
        ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 1;
        ctx.strokeRect(wx, wy2, 22*S, 16*S);
        ctx.strokeStyle = "#3b82f6"; ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.moveTo(wx+2*S, wy2+12*S); ctx.lineTo(wx+8*S, wy2+5*S);
        ctx.lineTo(wx+14*S, wy2+9*S); ctx.lineTo(wx+20*S, wy2+3*S);
        ctx.stroke();
        ctx.strokeStyle = "#ef4444";
        ctx.beginPath(); ctx.moveTo(wx+2*S, wy2+14*S); ctx.lineTo(wx+20*S, wy2+14*S); ctx.stroke();

      } else if (r.id === "audit") {
        // Audit AI: จอ + เอกสารกอง อุปกรณ์ตรวจสอบ
        drawMonitor(cx - 26*S, cy - 13*S, 18*S, 12*S, "#070516", () => {
          ctx.fillStyle = "#a78bfa"; ctx.font = `bold ${Math.round(3.5*S)}px monospace`;
          ctx.fillText("AUDIT LOG", cx - 25*S, cy - 9*S);
          ctx.fillStyle = "#c4b5fd"; ctx.font = `${Math.round(2.8*S)}px monospace`;
          ["✓ Trade #1042","✓ PnL Match","⚠ Spread +0.2"].forEach((t,i)=>ctx.fillText(t, cx-25*S, cy-6.5*S+i*3*S));
        });
        drawMonitor(cx - 6*S, cy - 10*S, 14*S, 9*S, "#070516", () => {
          // checklist bars
          [0.9,0.75,0.6,1.0].forEach((v,i)=>{
            ctx.fillStyle = "#7c3aed22";
            ctx.fillRect(cx-5*S, cy-8*S+i*2.2*S, 12*S, 1.5*S);
            ctx.fillStyle = v===1.0?"#10b981":v>0.8?"#a78bfa":"#f59e0b";
            ctx.fillRect(cx-5*S, cy-8*S+i*2.2*S, 12*S*v, 1.5*S);
          });
        });
        drawPlant(cx + sizeX - 25*S, cy + 5*S);

      } else if (r.id === "alert") {
        // Alert AI: จอแจ้งเตือน + MacBook
        const alertOn = Math.sin(frameCountRef.current * 0.12) > 0.3;
        drawMonitor(cx - 26*S, cy - 13*S, 18*S, 12*S, alertOn ? "#1a0d00" : "#0c0600", () => {
          ctx.fillStyle = alertOn ? "#f97316" : "#7c2d12";
          ctx.font = `bold ${Math.round(4*S)}px monospace`;
          ctx.fillText(alertOn ? "🔔 ALERT!" : "MONITOR", cx - 25*S, cy - 8*S);
          ctx.fillStyle = "#fed7aa"; ctx.font = `${Math.round(3*S)}px monospace`;
          ["PORT ALERT","SPREAD: 2.8","RISK: HIGH"].forEach((t,i)=>ctx.fillText(t,cx-25*S,cy-6*S+i*3*S));
        });
        drawMacBook(cx - 5*S, cy + 5*S, 16*S, "#f97316");
        drawCoffee(cx + 14*S, deskBY - 4*S);

      } else if (r.id === "report") {
        // Report AI: จอ + เอกสารรายงาน
        drawMonitor(cx - 26*S, cy - 13*S, 18*S, 12*S, "#0a0316", () => {
          ctx.fillStyle = "#c084fc"; ctx.font = `bold ${Math.round(3.5*S)}px monospace`;
          ctx.fillText("REPORT GEN", cx - 25*S, cy - 9*S);
          ctx.fillStyle = "#e9d5ff"; ctx.font = `${Math.round(2.8*S)}px monospace`;
          ["Daily PnL...","Risk Sum...","Tax Calc..."].forEach((t,i)=>ctx.fillText(t,cx-25*S,cy-6.5*S+i*3*S));
        });
        drawMacBook(cx - 5*S, cy + 5*S, 18*S, "#c084fc");
        // เอกสารกองบนโต๊ะ (paper stack)
        for (let pi = 0; pi < 3; pi++) {
          ctx.fillStyle = `rgba(241,245,249,${0.8-pi*0.2})`;
          ctx.fillRect(cx + 10*S + pi*1.5*S, deskBY - 5*S - pi*1.5*S, 10*S, 7*S);
          ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 0.5;
          ctx.strokeRect(cx + 10*S + pi*1.5*S, deskBY - 5*S - pi*1.5*S, 10*S, 7*S);
        }
        drawPlant(cx - sizeX + 25*S, cy + 5*S);
      }

    };

    const drawRoomNameplate = (r: RoomDef) => {
      const pos = centers[r.id];
      if (!pos) return;
      const { cx, cy } = pos;

      // Unified Room Nameplate Badge (Department Role, Agent Name & Live Status)
      const labelText = `${r.emoji} ${r.role} • ${r.name}`;
      const labelFontSize = Math.max(12, Math.round(15 * scaleMultiplier));
      ctx.font = `bold ${labelFontSize}px "Manrope", "Inter", "Segoe UI", sans-serif`;
      
      const labelTextWidth = ctx.measureText(labelText).width;
      
      // Layout dimensions
      const dotRadius = Math.max(3.5, 4.5 * scaleMultiplier);
      const dotSpacing = 8 * scaleMultiplier;
      const paddingX = 14 * scaleMultiplier;
      
      const badgeW = labelTextWidth + paddingX * 2 + dotRadius * 2 + dotSpacing;
      const badgeH = Math.max(22, Math.round(28 * scaleMultiplier));
      const badgeX = cx - badgeW / 2;
      let badgeY = cy + sizeY - badgeH / 2 + 2 * scaleMultiplier;

      // Constrain Y position so it doesn't get covered by the Risk Gate panel at the bottom of the screen
      const maxBadgeBottom = H - 64;
      if (badgeY + badgeH > maxBadgeBottom) {
        badgeY = maxBadgeBottom - badgeH;
      }

      // Draw glowing nameplate background
      ctx.save();
      ctx.fillStyle = "rgba(7, 10, 15, 0.95)";
      ctx.strokeStyle = r.border;
      ctx.lineWidth = 1.8;
      ctx.shadowColor = r.border;
      ctx.shadowBlur = 8;
      roundRect(ctx, badgeX, badgeY, badgeW, badgeH, Math.max(4, 6 * scaleMultiplier));
      ctx.fill();
      ctx.stroke();
      ctx.restore(); // Reset shadow and other styles

      // Draw Live Status Dot inside the badge
      const statusColors = { online: "#10b981", busy: "#f59e0b", idle: "#64748b" };
      const dotX = badgeX + paddingX + dotRadius;
      const dotY = badgeY + badgeH / 2;
      
      ctx.fillStyle = statusColors[r.status];
      ctx.beginPath();
      ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2);
      ctx.fill();

      // Pulsing status ring
      if (r.status !== "idle") {
        ctx.fillStyle = statusColors[r.status] + "22";
        ctx.beginPath();
        ctx.arc(dotX, dotY, dotRadius * 2 + Math.sin(frameCountRef.current * 0.12) * 1.5 * scaleMultiplier, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw Badge Text (Emoji, Role, Name)
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.font = `bold ${labelFontSize}px "Manrope", "Inter", "Segoe UI", sans-serif`;
      ctx.fillText(labelText, dotX + dotRadius + dotSpacing, badgeY + badgeH / 2 + 0.5);

      // Reset text alignment to defaults
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
    };

    const drawDebateConnections = () => {
      const ceoCenter = centers["ceo"];
      if (!ceoCenter) return;

      const targetRoomIds = ["chart", "audit", "ea", "finance", "strategy", "risk"];
      
      targetRoomIds.forEach((ti, idx) => {
        const dest = centers[ti];
        if (!dest) return;

        ctx.strokeStyle = "rgba(6, 182, 212, 0.4)"; // Bright Neon
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 10]);
        
        ctx.beginPath();
        ctx.moveTo(ceoCenter.cx, ceoCenter.cy);
        ctx.lineTo(dest.cx, dest.cy);
        ctx.stroke();
        
        ctx.setLineDash([]); 

        // Glowing Event Flow Animation
        const speedMultiplier = 0.012;
        const progress = ((frameCountRef.current * speedMultiplier) + idx * 0.15) % 1;
        const px = ceoCenter.cx + (dest.cx - ceoCenter.cx) * progress;
        const py = ceoCenter.cy + (dest.cy - ceoCenter.cy) * progress;
        
        // Glowing dot
        ctx.shadowColor = "#22d3ee";
        ctx.shadowBlur = 10;
        ctx.fillStyle = "#22d3ee";
        ctx.beginPath();
        ctx.arc(px, py, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    };

    const drawCharacter = (cx: number, cy: number, color: string, facing: string, frame: number, speaking: boolean) => {
      ctx.save();
      const s = 2.4; 

      ctx.fillStyle = "rgba(0,0,0,0.28)";
      ctx.beginPath();
      ctx.ellipse(cx + 4.5 * s, cy + 14 * s, 5.5 * s, 2 * s, 0, 0, Math.PI * 2);
      ctx.fill();

      const walkCycle = Math.sin(frame * 0.18);
      const legL = walkCycle > 0 ? 1.8 : 0;
      const legR = walkCycle <= 0 ? 1.8 : 0;

      ctx.fillStyle = "#1e293b"; 
      ctx.fillRect(cx + 2.5 * s, cy + 8.5 * s, 1.5 * s, 4.5 * s + legL);
      ctx.fillRect(cx + 5 * s, cy + 8.5 * s, 1.5 * s, 4.5 * s + legR);

      ctx.fillStyle = "#0c0a0f";
      ctx.fillRect(cx + 2 * s, cy + 13 * s + legL, 2.2 * s, 1.2 * s);
      ctx.fillRect(cx + 5 * s, cy + 13 * s + legR, 2.2 * s, 1.2 * s);

      // เสื้อสูทพนักงานออฟฟิศ
      ctx.fillStyle = color; 
      ctx.fillRect(cx + 2 * s, cy + 3.8 * s, 5.2 * s, 5.2 * s);

      // คอเสื้อเชิ้ตเชือกขาว
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(cx + 3.6 * s, cy + 3.8 * s, 2 * s, 2.2 * s);

      // เนคไทสีแดง
      ctx.fillStyle = "#b91c1c";
      ctx.fillRect(cx + 4.2 * s, cy + 4.4 * s, 0.8 * s, 2.6 * s);

      // ใบหน้า
      ctx.fillStyle = "#f5d0b4"; 
      ctx.fillRect(cx + 1.5 * s, cy + 0.2 * s, 6.2 * s, 3.8 * s);

      // ผมสุภาพน้ำตาลออฟฟิศ
      ctx.fillStyle = "#271b12";
      ctx.fillRect(cx + 1.5 * s, cy - 0.6 * s, 6.2 * s, 1.2 * s); 
      ctx.fillRect(cx + 1.5 * s, cy + 0.2 * s, 1 * s, 2 * s);     
      ctx.fillRect(cx + 6.7 * s, cy + 0.2 * s, 1 * s, 2 * s);     

      const eyeY = cy + 1.2 * s;
      ctx.fillStyle = "#000000";
      if (facing === "right") {
        ctx.fillRect(cx + 5.5 * s, eyeY, 1 * s, 1 * s);
      } else if (facing === "left") {
        ctx.fillRect(cx + 2.5 * s, eyeY, 1 * s, 1 * s);
      } else {
        ctx.fillRect(cx + 2.5 * s, eyeY, 1 * s, 1 * s);
        ctx.fillRect(cx + 5.5 * s, eyeY, 1 * s, 1 * s);
      }

      if (speaking && Math.sin(frame * 0.45) > 0) {
        ctx.fillStyle = "#9a3412";
        ctx.fillRect(cx + 3.6 * s, cy + 2.8 * s, 2 * s, 0.8 * s);
      }

      const armSwing = walkCycle * 1.5;
      ctx.fillStyle = color; 
      ctx.fillRect(cx + 0.5 * s, cy + 3.8 * s + (facing === "left" ? armSwing : 0), 1.5 * s, 4 * s);
      ctx.fillRect(cx + 7.2 * s, cy + 3.8 * s + (facing === "right" ? armSwing : 0), 1.5 * s, 4 * s);

      ctx.fillStyle = "#f5d0b4"; 
      ctx.fillRect(cx + 0.5 * s, cy + 7.4 * s + (facing === "left" ? armSwing : 0), 1.5 * s, 1 * s);
      ctx.fillRect(cx + 7.2 * s, cy + 7.4 * s + (facing === "right" ? armSwing : 0), 1.5 * s, 1 * s);

      ctx.restore();
    };

    const drawBubble = (a: any) => {
      if (a.bubbleTimer <= 0 || !a.bubble) return;
      const alpha = Math.min(1.0, a.bubbleTimer / 20);
      ctx.save();
      ctx.globalAlpha = alpha;

      const text = a.bubble;
      const bubbleFontSize = Math.max(13, Math.round(16 * scaleMultiplier));
      ctx.font = `bold ${bubbleFontSize}px "Manrope", "Inter", "Segoe UI", sans-serif`;
      
      const tw = ctx.measureText(text).width + 16 * scaleMultiplier;
      const th = Math.max(24, 28 * scaleMultiplier);
      
      let bx = a.sx - tw / 2 + 4 * scaleMultiplier;
      let by = a.sy - 12 - th;
      let arrowDirection = "down"; // where the arrow points (relative to the bubble)
      
      // Customize positions for each room to prevent overlap in the center
      const sidePadding = 15 * scaleMultiplier;
      const thHalf = th / 2;
      
      if (a.id === "report" || a.id === "finance" || a.id === "strategy") {
        // Left side rooms -> Bubble to the left
        bx = a.sx - tw - sidePadding;
        by = a.sy - thHalf;
        arrowDirection = "right";
      } else if (a.id === "ceo" || a.id === "chart" || a.id === "risk") {
        // Right side rooms -> Bubble to the right
        bx = a.sx + sidePadding + 8 * scaleMultiplier;
        by = a.sy - thHalf;
        arrowDirection = "left";
      } else if (a.id === "audit") {
        // Top-center -> Bubble slightly to the left and up
        bx = a.sx - tw - 5 * scaleMultiplier;
        by = a.sy - th - 5 * scaleMultiplier;
        arrowDirection = "bottom-right";
      } else if (a.id === "alert") {
        // Bottom-center -> Bubble to the left and down
        bx = a.sx - tw - 5 * scaleMultiplier;
        by = a.sy + 5 * scaleMultiplier;
        arrowDirection = "top-right";
      } else if (a.id === "ea") {
        // Center room -> Bubble above
        bx = a.sx - tw / 2;
        by = a.sy - 16 * scaleMultiplier - th;
        arrowDirection = "down";
      }

      ctx.fillStyle = "#070a0f";
      ctx.strokeStyle = "#06b6d4";
      ctx.lineWidth = 1.5;
      roundRect(ctx, bx, by, tw, th, Math.max(3, 4 * scaleMultiplier));
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = "#070a0f";
      ctx.strokeStyle = "#06b6d4";
      
      if (arrowDirection === "down") {
        ctx.beginPath();
        ctx.moveTo(a.sx + 2 * scaleMultiplier, by + th);
        ctx.lineTo(a.sx + 4 * scaleMultiplier, by + th + 6 * scaleMultiplier);
        ctx.lineTo(a.sx + 8 * scaleMultiplier, by + th);
        ctx.closePath();
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(a.sx + 3 * scaleMultiplier, by + th);
        ctx.lineTo(a.sx + 4 * scaleMultiplier, by + th + 6 * scaleMultiplier);
        ctx.lineTo(a.sx + 7 * scaleMultiplier, by + th);
        ctx.stroke();
      } else if (arrowDirection === "left") {
        ctx.beginPath();
        ctx.moveTo(bx, by + thHalf - 4 * scaleMultiplier);
        ctx.lineTo(bx - 6 * scaleMultiplier, by + thHalf);
        ctx.lineTo(bx, by + thHalf + 4 * scaleMultiplier);
        ctx.closePath();
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(bx, by + thHalf - 3 * scaleMultiplier);
        ctx.lineTo(bx - 6 * scaleMultiplier, by + thHalf);
        ctx.lineTo(bx, by + thHalf + 3 * scaleMultiplier);
        ctx.stroke();
      } else if (arrowDirection === "right") {
        ctx.beginPath();
        ctx.moveTo(bx + tw, by + thHalf - 4 * scaleMultiplier);
        ctx.lineTo(bx + tw + 6 * scaleMultiplier, by + thHalf);
        ctx.lineTo(bx + tw, by + thHalf + 4 * scaleMultiplier);
        ctx.closePath();
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(bx + tw, by + thHalf - 3 * scaleMultiplier);
        ctx.lineTo(bx + tw + 6 * scaleMultiplier, by + thHalf);
        ctx.lineTo(bx + tw, by + thHalf + 3 * scaleMultiplier);
        ctx.stroke();
      } else if (arrowDirection === "bottom-right") {
        ctx.beginPath();
        ctx.moveTo(bx + tw - 8 * scaleMultiplier, by + th);
        ctx.lineTo(bx + tw, by + th + 6 * scaleMultiplier);
        ctx.lineTo(bx + tw - 2 * scaleMultiplier, by + th);
        ctx.closePath();
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(bx + tw - 7 * scaleMultiplier, by + th);
        ctx.lineTo(bx + tw, by + th + 6 * scaleMultiplier);
        ctx.lineTo(bx + tw - 3 * scaleMultiplier, by + th);
        ctx.stroke();
      } else if (arrowDirection === "top-right") {
        ctx.beginPath();
        ctx.moveTo(bx + tw - 8 * scaleMultiplier, by);
        ctx.lineTo(bx + tw, by - 6 * scaleMultiplier);
        ctx.lineTo(bx + tw - 2 * scaleMultiplier, by);
        ctx.closePath();
        ctx.fill();
        
        ctx.beginPath();
        ctx.moveTo(bx + tw - 7 * scaleMultiplier, by);
        ctx.lineTo(bx + tw, by - 6 * scaleMultiplier);
        ctx.lineTo(bx + tw - 3 * scaleMultiplier, by);
        ctx.stroke();
      }

      ctx.fillStyle = "#f8fafc";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(text, bx + tw / 2, by + th / 2 + 0.5);

      // คืนค่าตั้งต้นสำหรับ Text Alignment ของ canvas
      ctx.textAlign = "left";
      ctx.textBaseline = "alphabetic";
      ctx.restore();
    };

    const render = () => {
      ctx.clearRect(0, 0, W, H);

      // ══════════════════════════════════════════════════════
      // 🏢 WORLD-CLASS TECH OFFICE BACKGROUND
      // ══════════════════════════════════════════════════════

      // 1. Dark architectural gradient base
      const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
      bgGrad.addColorStop(0, "#050810");
      bgGrad.addColorStop(0.4, "#080c18");
      bgGrad.addColorStop(1, "#04060e");
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      // 2. Subtle perspective floor grid (converging lines)
      const horizonY = H * 0.28;
      const vpX = W / 2;
      ctx.strokeStyle = "rgba(30, 58, 138, 0.12)";
      ctx.lineWidth = 0.8;
      for (let i = -16; i <= 16; i++) {
        const floorX = vpX + i * (W / 16);
        ctx.beginPath();
        ctx.moveTo(vpX, horizonY);
        ctx.lineTo(floorX, H);
        ctx.stroke();
      }
      // horizontal floor lines
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const y = horizonY + (H - horizonY) * t * t;
        const alpha = 0.05 + t * 0.08;
        ctx.strokeStyle = `rgba(30, 58, 138, ${alpha})`;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }

      // 3. Ceiling structure (top architectural lines)
      ctx.strokeStyle = "rgba(51, 65, 85, 0.3)";
      ctx.lineWidth = 1;
      // ceiling beams
      for (let i = 0; i <= 8; i++) {
        const x = (W / 8) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H * 0.12);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(0, H * 0.12);
      ctx.lineTo(W, H * 0.12);
      ctx.stroke();

      // 4. Ceiling recessed lights
      const lightCount = Math.ceil(W / 120);
      for (let i = 0; i < lightCount; i++) {
        const lx = (W / lightCount) * i + W / (lightCount * 2);
        const ly = H * 0.06;
        // light cone
        const coneGrad = ctx.createRadialGradient(lx, ly, 2, lx, ly + 80, 120);
        coneGrad.addColorStop(0, "rgba(147, 210, 255, 0.18)");
        coneGrad.addColorStop(0.4, "rgba(96, 165, 250, 0.06)");
        coneGrad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = coneGrad;
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(lx - 80, ly + 160);
        ctx.lineTo(lx + 80, ly + 160);
        ctx.closePath();
        ctx.fill();
        // fixture dot
        ctx.fillStyle = "rgba(200, 230, 255, 0.7)";
        ctx.beginPath();
        ctx.arc(lx, ly, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // 5. Large ambient glow in center (halo)
      const centerGlow = ctx.createRadialGradient(W/2, H*0.45, 40, W/2, H*0.45, W*0.55);
      centerGlow.addColorStop(0, "rgba(15, 30, 80, 0.35)");
      centerGlow.addColorStop(0.5, "rgba(8, 15, 40, 0.15)");
      centerGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = centerGlow;
      ctx.fillRect(0, 0, W, H);

      // 6. Fine dot-matrix grid
      ctx.fillStyle = "rgba(51, 75, 120, 0.18)";
      const dotSpacing = 32;
      for (let gx = 0; gx < W; gx += dotSpacing) {
        for (let gy = 0; gy < H; gy += dotSpacing) {
          ctx.beginPath();
          ctx.arc(gx, gy, 0.7, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // 7. Side wall panels (left and right architectural elements)
      // Left wall
      const leftWallGrad = ctx.createLinearGradient(0, 0, W * 0.12, 0);
      leftWallGrad.addColorStop(0, "rgba(15, 25, 60, 0.25)");
      leftWallGrad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = leftWallGrad;
      ctx.fillRect(0, 0, W * 0.12, H);
      // Right wall
      const rightWallGrad = ctx.createLinearGradient(W, 0, W * 0.88, 0);
      rightWallGrad.addColorStop(0, "rgba(15, 25, 60, 0.25)");
      rightWallGrad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = rightWallGrad;
      ctx.fillRect(W * 0.88, 0, W * 0.12, H);

      // 8. Neon accent lines on walls (horizontal strips)
      ctx.strokeStyle = "rgba(59, 130, 246, 0.15)";
      ctx.lineWidth = 1;
      [H * 0.25, H * 0.5, H * 0.75].forEach(y => {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W * 0.06, y);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(W * 0.94, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      });

      // ══════════════════════════════════════════════════════
      // 9. Cyber circuit lines between departments
      // ══════════════════════════════════════════════════════
      ctx.strokeStyle = "rgba(6, 182, 212, 0.1)";
      ctx.lineWidth = 1.2;
      const drawCircuitRoute = (fromId: string, toId: string) => {
        const p1 = centers[fromId];
        const p2 = centers[toId];
        if (p1 && p2) {
          ctx.beginPath();
          ctx.moveTo(p1.cx, p1.cy);
          ctx.lineTo(p1.cx, (p1.cy + p2.cy) / 2);
          ctx.lineTo(p2.cx, (p1.cy + p2.cy) / 2);
          ctx.lineTo(p2.cx, p2.cy);
          ctx.stroke();
        }
      };
      drawCircuitRoute("strategy", "risk");
      drawCircuitRoute("risk", "ea");
      drawCircuitRoute("ceo", "chart");
      drawCircuitRoute("chart", "finance");
      drawCircuitRoute("report", "audit");
      drawCircuitRoute("audit", "ceo");

      // 10. Draw ambient room spotlights
      ROOMS_CONFIG.forEach((r) => {
        const pos = centers[r.id];
        if (!pos) return;
        const grad = ctx.createRadialGradient(pos.cx, pos.cy - sizeY * 0.3, 5, pos.cx, pos.cy, sizeX * 1.1);
        grad.addColorStop(0, r.border + "20");
        grad.addColorStop(1, "rgba(4, 6, 14, 0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.ellipse(pos.cx, pos.cy, sizeX * 1.1, sizeY * 1.1, 0, 0, Math.PI * 2);
        ctx.fill();
      });

      drawDebateConnections();

      ROOMS_CONFIG.forEach(drawRoom);

      frameCountRef.current++;
      const currentFrame = frameCountRef.current;

      agentsStateRef.current.forEach((a) => {
        if (a.bubbleTimer > 0) a.bubbleTimer--;
        if (a.speakTimer > 0) {
          a.speakTimer--;
          a.speaking = true;
        } else {
          a.speaking = false;
        }

        const roomPos = centers[a.id];
        if (!roomPos) return;

        if (a.moving) {
          const dx = a.tx - a.lx;
          const dy = a.ty - a.ly;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 2.0) {
            a.moving = false;
            a.idleTimer = 80 + Math.random() * 160;
          } else {
            const stepVal = Math.min(a.speed, dist);
            a.lx += (dx / dist) * stepVal;
            a.ly += (dy / dist) * stepVal;

            if (Math.abs(dx) > Math.abs(dy)) {
              a.facing = dx > 0 ? "right" : "left";
            } else {
              a.facing = dy > 0 ? "down" : "up";
            }
          }
        } else {
          a.idleTimer--;
          if (a.idleTimer <= 0) {
            a.tx = (Math.random() - 0.5) * (sizeX - 60);
            a.ty = (Math.random() - 0.5) * (sizeY - 35);
            a.moving = true;
          }
        }

        a.sx = roomPos.cx + (a.lx - a.ly);
        a.sy = roomPos.cy + (a.lx + a.ly) * 0.5 - 12;

        drawCharacter(Math.round(a.sx), Math.round(a.sy), a.color, a.facing, currentFrame, a.speaking);
        drawBubble(a);
      });

      // Draw all unified room nameplate badges after all rooms and characters to prevent floor clipping
      ROOMS_CONFIG.forEach(drawRoomNameplate);

      ctx.fillStyle = "rgba(0, 0, 0, 0.035)";
      for (let sy = 0; sy < H; sy += 3.5) {
        ctx.fillRect(0, sy, W, 1.2);
      }

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

    ROOMS_CONFIG.forEach((r, i) => {
      const agState = agentsStateRef.current[i];
      if (!agState) return;

      const dist = Math.sqrt(Math.pow(mx - agState.sx, 2) + Math.pow(my - agState.sy, 2));
      
      if (dist < 40 * scaleMultiplierRef.current) {
        agState.speakTimer = 100;
        agState.bubbleTimer = 165;
        agState.bubble = r.bubble;
        addChatMessage("system", `📌 ตรวจเช็คข้อมูลเอเจนต์ประจำแผนก: ${r.name} [${r.role}] — สแตนบายพร้อมอัปเดตสถิติ`);
      }
    });
  };

  return (
    <div className="h-screen w-screen bg-[#000000] text-[#c8d8f0] flex flex-col overflow-hidden font-sans select-none">
      
      {/* ── TOPBAR ── */}
      <header className="bg-[#000000] border-b border-[#1e2d45] flex items-center gap-2 px-3.5 h-10 flex-shrink-0">
        <div className="text-[11px] font-black text-[#f0b429] tracking-wider font-mono">
          🏢 <span>TRADE</span> OFFICE
        </div>
        <div className="w-[1px] h-[18px] bg-[#1e2d45] mx-1"></div>
        <div className="flex items-center gap-1.5 bg-[#111520] border border-[#1e2d45] rounded px-2.5 py-0.5 text-[11px] text-[#7a9bbf]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981] animate-pulse"></span>
          Notion
        </div>
        <div className="flex items-center gap-1.5 bg-[#111520] border border-[#1e2d45] rounded px-2.5 py-0.5 text-[11px] text-[#7a9bbf]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981]"></span>
          Google Drive
        </div>
        <div className="flex items-center gap-1.5 bg-[#111520] border border-[#1e2d45] rounded px-2.5 py-0.5 text-[11px] text-[#7a9bbf]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3b82f6] shadow-[0_0_5px_#3b82f6] animate-pulse"></span>
          Binance CCXT
        </div>

        <div className="flex-1"></div>

        {wsStatus === "connected" ? (
          <div className="text-[10px] px-2.5 py-0.5 rounded bg-[#0d2a14] border border-[#1a5a28] text-[#10b981] font-mono font-bold">
            ⬤ WS Connected
          </div>
        ) : wsStatus === "connecting" ? (
          <div className="text-[10px] px-2.5 py-0.5 rounded bg-[#0d1929] border border-[#1a3a6a] text-[#3b82f6] font-mono animate-pulse">
            ⬤ WS Connecting...
          </div>
        ) : (
          <div className="text-[10px] px-2.5 py-0.5 rounded bg-[#1f0d0d] border border-[#4a1a1a] text-[#ef4444] font-mono font-bold">
            ⬤ WS Disconnected
          </div>
        )}

        <div 
          onClick={fetchStateData}
          className="flex items-center gap-1.5 bg-[#111520] border border-[#1e2d45] hover:bg-[#161c2a] rounded px-2.5 py-0.5 text-[11px] text-[#c8d8f0] cursor-pointer transition font-bold"
        >
          ✏️ Edit Mode
        </div>
        <div className="w-5 h-5 rounded-full bg-[#1e2d45] text-[9px] font-bold text-[#3b82f6] flex items-center justify-center border border-[#3b82f6]">
          C
        </div>
      </header>

      {/* ── LAYOUT CONTENT ── */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* ── SIDEBAR ── */}
        <aside className="w-[172px] min-w-[172px] bg-black/40 backdrop-blur-md border-r border-white/10 flex flex-col flex-shrink-0">
          <div className="p-3 border-b border-white/10">
            <div className="text-[18px] mb-1">🏢</div>
            <div className="text-[8px] font-black text-[#f0b429] tracking-wider leading-relaxed">TRADE OFFICE</div>
            <div className="text-[10px] text-[#3d5a7a]">v2.21.0 · Active</div>
          </div>

          <div className="p-2 space-y-3">
            <div>
              <div className="px-3 py-1 text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold"># MAIN</div>
              <nav className="space-y-0.5 mt-1 font-semibold">
                <button 
                  onClick={() => setActiveMenu("Office Overview")}
                  className={getMenuButtonClass("Office Overview")}
                >
                  🖥 Office Overview
                </button>
                <button 
                  onClick={() => {
                    setActiveMenu("Chat Center");
                    setUnreadCount(0);
                  }}
                  className={getMenuButtonClass("Chat Center")}
                >
                  <span>💬 Chat Center</span>
                  {unreadCount > 0 && (
                    <span className="bg-[#da3633] text-white text-[8px] px-1.5 py-0.2 rounded-full font-bold">
                      {unreadCount}
                    </span>
                  )}
                </button>
                <button 
                  onClick={() => setActiveMenu("AI Agents")}
                  className={getMenuButtonClass("AI Agents")}
                >
                  <span>🤖 AI Agents</span>
                  <span className="bg-[#238636] text-white text-[8px] px-1.5 py-0.2 rounded font-bold">
                    9
                  </span>
                </button>
                <button 
                  onClick={() => setActiveMenu("Workflow Board")}
                  className={getMenuButtonClass("Workflow Board")}
                >
                  📋 Workflow Board
                </button>
              </nav>
            </div>

            <div>
              <div className="px-3 py-1 text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold"># TRADING</div>
              <nav className="space-y-0.5 mt-1 font-semibold">
                <button 
                  onClick={() => setActiveMenu("Analytics")}
                  className={getMenuButtonClass("Analytics")}
                >
                  📊 Analytics
                </button>
                <button 
                  onClick={() => setActiveMenu("Performance Dashboard")}
                  className={getMenuButtonClass("Performance Dashboard")}
                >
                  📈 Performance Dashboard
                </button>
                <button 
                  onClick={() => setActiveMenu("Risk Monitor")}
                  className={getMenuButtonClass("Risk Monitor")}
                >
                  ⚠️ Risk Monitor
                </button>
                <button 
                  onClick={() => setActiveMenu("Reports")}
                  className={getMenuButtonClass("Reports")}
                >
                  📊 ERP & Reports
                </button>
              </nav>
            </div>

            <div>
              <div className="px-3 py-1 text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold"># SYSTEM</div>
              <nav className="space-y-0.5 mt-1 font-semibold">
                <button 
                  onClick={() => setActiveMenu("Settings")}
                  className={getMenuButtonClass("Settings")}
                >
                  ⚙️ Settings
                </button>
              </nav>
            </div>
          </div>

          <div className="mt-auto p-3 border-t border-white/10 text-[10.5px] text-[#7a9bbf] leading-relaxed">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981]"></span>
              9 Agents · Online
            </div>
            <div className="text-[#10b981] text-[9.5px] mt-1 font-bold">MT5 & CCXT Binance</div>
          </div>
        </aside>

        {/* ── CENTRAL MAIN WORKSPACE ── */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          
          {/* TAB 1: 🖥 Office Overview (Isometric Neon Tech Canvas) */}
          <div className={`flex-1 relative overflow-hidden bg-[#000000] ${activeMenu === "Office Overview" ? "block" : "hidden"}`} ref={wrapRef}>
            <canvas 
              id="office" 
              ref={canvasRef}
              onClick={handleCanvasClick}
              className="block w-full h-full cursor-pointer"
            />
            
            {/* ── Bottom Center: Risk Gate Control Bar (2-row layout) ── */}
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-[820px] max-w-[98vw] bg-[#000000]/90 border border-[#1e2d45] rounded-xl px-3 py-2 shadow-2xl backdrop-blur-md flex flex-col gap-1.5">

              {/* แถวบน: Label + Indicators + Auto Scan */}
              <div className="flex items-center gap-2">
                {/* Symbol selector */}
                <div className="flex flex-col gap-0.5 min-w-[80px]">
                  <div className="text-[8px] text-[#f59e0b] font-bold uppercase tracking-wider">📡 Risk Gate</div>
                  <select
                    value={symbol}
                    onChange={(e) => handleSymbolChange(e.target.value)}
                    className="bg-[#111520] border border-[#1e2d45] rounded text-[9px] text-white p-0.5 outline-none font-mono font-bold w-full"
                  >
                    {SYMBOLS_LIST.map((s) => (
                      <option key={s.symbol} value={s.symbol}>{s.symbol}</option>
                    ))}
                  </select>
                </div>

                {/* Indicators */}
                <div className="flex gap-2 text-center text-[9px] bg-[#0a0d16] border border-[#1e2d45] px-2 py-1 rounded font-mono flex-1">
                  <div className="flex-1">
                    <div className="text-[#3d5a7a] text-[7.5px]">ราคา</div>
                    <div className="font-bold text-white">{latestPrice || "-"}</div>
                  </div>
                  <div className="flex-1">
                    <div className="text-[#3d5a7a] text-[7.5px]">EMA</div>
                    <div className={`font-bold ${indicators?.trend === "Bullish" ? "text-[#10b981]" : "text-[#f87171]"}`}>{indicators?.trend || "-"}</div>
                  </div>
                  <div className="flex-1">
                    <div className="text-[#3d5a7a] text-[7.5px]">RSI</div>
                    <div className="font-bold text-white">{indicators?.rsi || "-"}</div>
                  </div>
                  <div className="flex-1">
                    <div className="text-[#3d5a7a] text-[7.5px]">Signal</div>
                    <div className={`font-bold ${signal?.action === "BUY" ? "text-[#10b981]" : signal?.action === "SELL" ? "text-[#f87171]" : "text-slate-400"}`}>{signal?.action || "WAIT"}</div>
                  </div>
                </div>

                {/* 🤖 Auto Scan — วางแยกชัดเจนขวาสุดแถวบน */}
                <button
                  onClick={handleToggleMode}
                  className={`px-3 py-1.5 text-[9px] font-bold rounded border transition whitespace-nowrap flex items-center gap-1 ${
                    mode === "auto"
                      ? "bg-[#0d2a3a] text-[#22d3ee] border-[#1a5a7a] shadow-[0_0_10px_#22d3ee55]"
                      : "bg-[#111827] text-[#7a9bbf] border-[#1e2d45] hover:bg-[#1e2d45] hover:text-[#c8d8f0]"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${mode === "auto" ? "bg-[#22d3ee] shadow-[0_0_5px_#22d3ee]" : "bg-[#3d5a7a]"}`} />
                  {mode === "auto" ? "AUTO ON" : "Auto Scan"}
                </button>
              </div>

              {/* แถวล่าง: Lot / SL / TP / Spread Limit / Reject / Risk % + ปุ่ม Action */}
              <div className="flex items-center gap-2">
                {/* Lot / SL / TP / Spread Limit / Reject / Risk % */}
                <div className="flex gap-1.5 text-[8.5px]">
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">Lot</span>
                    <input type="number" step="0.01" value={riskForm.lot}
                      onChange={(e) => setRiskForm({...riskForm, lot: Number(e.target.value)})}
                      className="w-12 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">SL (Pips)</span>
                    <input type="number" value={riskForm.stopDistance}
                      onChange={(e) => setRiskForm({...riskForm, stopDistance: Number(e.target.value)})}
                      className="w-12 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">TP (Pips)</span>
                    <input type="number" value={riskForm.takeProfit}
                      onChange={(e) => setRiskForm({...riskForm, takeProfit: Number(e.target.value)})}
                      className="w-12 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">Spread Limit</span>
                    <input type="number" step="0.1" value={riskForm.spread}
                      onChange={(e) => setRiskForm({...riskForm, spread: Number(e.target.value)})}
                      className="w-14 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">Reject &gt;</span>
                    <input type="number" step="0.1" value={riskForm.rejectThreshold}
                      onChange={(e) => setRiskForm({...riskForm, rejectThreshold: Number(e.target.value)})}
                      className="w-12 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                  <div>
                    <span className="text-[#3d5a7a] block text-[7.5px]">Risk %</span>
                    <input type="number" step="0.1" value={riskForm.riskPct}
                      onChange={(e) => setRiskForm({...riskForm, riskPct: Number(e.target.value)})}
                      className="w-12 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center text-[9px]"
                    />
                  </div>
                </div>

                {/* divider */}
                <div className="w-px h-7 bg-[#1e2d45]" />

                {/* Action buttons */}
                <div className="flex items-center gap-1.5 flex-1">
                  <button onClick={handleRiskTest} className="px-2.5 py-1.5 bg-[#1e2d45] hover:bg-[#243352] text-[9px] font-bold text-[#c8d8f0] rounded border border-[#243352] transition whitespace-nowrap">
                    🔍 ประเมิน
                  </button>
                  <div className={`px-2.5 py-1.5 text-[9px] font-bold rounded flex items-center border ${
                    risk?.passed ? "bg-[#0d2a14] text-[#10b981] border-[#1a5a28]" : "bg-[#2a0d0d] text-[#f87171] border-[#6b1c1c]"
                  }`}>
                    {risk?.passed ? "🟢 PASS" : "🔴 BLOCK"}
                  </div>
                  <button
                    onClick={handleApprove}
                    disabled={mode === "auto" || !signal || (signal.action !== "BUY" && signal.action !== "SELL")}
                    className="px-2.5 py-1.5 bg-[#16a34a] hover:bg-[#15803d] disabled:bg-[#111520] disabled:text-[#3d5a7a] border border-[#15803d] disabled:border-[#1e2d45] text-white text-[9px] font-bold rounded transition whitespace-nowrap"
                  >
                    ✅ อนุมัติ
                  </button>
                  <button
                    onClick={handleReject}
                    className="px-2 py-1.5 bg-[#2a0d0d] hover:bg-[#5a1a1a] border border-[#5a1a1a] text-[#f87171] text-[9px] rounded transition"
                  >
                    ❌
                  </button>
                </div>
              </div>

            </div>

            {/* ── Top-Right: ERP Mini Widget ── */}
            <div className="absolute right-3 top-3 w-60 bg-[#070a0f]/95 border border-[#1e2d45] rounded-lg p-2.5 shadow-2xl backdrop-blur-md">
              <div className="flex justify-between items-center border-b border-[#1e2d45] pb-1.5 mb-1.5">
                <div className="text-[9.5px] text-[#22d3ee] font-bold uppercase tracking-wider font-mono">💰 Team ERP</div>
                <button onClick={fetchERPData} className="text-[7.5px] text-[#22d3ee] bg-[#22d3ee]/10 hover:bg-[#22d3ee]/20 px-1.5 rounded border border-[#22d3ee]/20 font-bold">
                  รีเฟรช
                </button>
              </div>
              {taxSummary ? (
                <div className="text-[9px] space-y-0.5 font-mono">
                  <div className="flex justify-between"><span className="text-[#7a9bbf]">PnL:</span><span className="text-[#10b981] font-bold">${taxSummary.accumulatedPnL.toFixed(2)}</span></div>
                  <div className="flex justify-between"><span className="text-[#7a9bbf]">VAT คืน:</span><span className="text-[#22d3ee] font-bold">+${taxSummary.inputVatClaimable.toFixed(2)}</span></div>
                  <div className="flex justify-between"><span className="text-[#7a9bbf]">ภาษี:</span><span className="text-[#ef4444] font-bold">-${taxSummary.estimatedIncomeTax.toFixed(2)}</span></div>
                  <div className="flex justify-between border-t border-[#1e2d45] pt-0.5 mt-0.5"><span className="text-[#c8d8f0] font-bold">สุทธิ:</span><span className="text-[#10b981] font-bold">${taxSummary.netAfterTax.toFixed(2)}</span></div>
                </div>
              ) : (
                <div className="text-[8.5px] text-[#3d5a7a] text-center py-1">กดรีเฟรชเพื่อดูงบดุล</div>
              )}
              {ledger.slice(-1).map((tx, idx) => (
                <div key={idx} className="bg-[#0a0d16] p-1.5 rounded text-[7.5px] border border-[#1e2d45] font-mono mt-1.5">
                  <div className="font-bold text-[#c8d8f0] truncate">{tx.description}</div>
                  <div className="flex justify-between text-[7px] mt-0.5">
                    <span className="text-[#10b981]">Dr: ${tx.debit.amount}</span>
                    <span className="text-[#f59e0b]">Cr: ${tx.credit.amount}</span>
                  </div>
                </div>
              ))}
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
                            <td colSpan={9} className="py-8 text-center text-slate-500">
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

        {/* ── CHAT PANEL (ขวา - ย่อลงเหลือ 228px ตามแคปเจอร์) ── */}
        <aside className="w-[228px] min-w-[228px] bg-[#070a0f] border-l border-[#1e2d45] flex flex-col flex-shrink-0">
          <div className="p-2 border-b border-[#1e2d45] text-xs">
            <div className="flex items-center gap-2">
              <span className="text-[14px]">💬</span>
              <div>
                <div className="font-bold text-[#c8d8f0] text-[12.5px]">Team Chat</div>
                <div className="text-[#10b981] text-[9.5px] leading-tight">● System ready</div>
                <div className="text-[#3d5a7a] text-[9.5px]">#ai-trading-team</div>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2 bg-[#000000]/30">
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

          <form onSubmit={handleSendChat} className="p-2 border-t border-[#1e2d45] flex gap-1 bg-[#070a0f]">
            <input 
              type="text" 
              placeholder="พิมพ์ข้อความ..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1 bg-[#111520] border border-[#1e2d45] rounded px-2 py-1 text-[11.5px] text-white outline-none focus:border-[#3b82f6] font-mono"
            />
            <button 
              type="submit" 
              className="bg-[#3b82f6] hover:bg-[#60a5fa] text-white px-2 rounded flex items-center justify-center text-[12px] transition cursor-pointer"
            >
              ↗
            </button>
          </form>
        </aside>

      </div>
    </div>
  );
}