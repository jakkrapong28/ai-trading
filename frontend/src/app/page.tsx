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
    lot: 0.1,
    stopDistance: 15.0,
    spread: 1.8
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
  const totalEquity = balances.reduce((sum, b) => sum + b.equity, 0);
  const activeTradesCount = orders.filter((o) => o.status === "PENDING" || o.status === "OPEN").length;
  const todayPnLSum = orders.reduce((sum, o) => sum + o.pnl, 0);

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
      console.error("ดึงข่าวสดขัดข้อง:", e);
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
      setBalances(data.balances);
      setOrders(data.orders);
      
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
          setBalances(s.balances);
          setOrders(s.orders);

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
          setBalances(msg.balances);
          addChatMessage("ea", `🔔 [ระบบ Team ERP] เปิดออเดอร์ใหม่สถานะรอดำเนินการ: ${msg.order.action} ${msg.order.symbol} ที่ราคา ${msg.order.entry_price}`);
        }
        else if (msg.type === "order_closed") {
          if (msg.orders) {
            setOrders(msg.orders);
          } else if (msg.order) {
            setOrders((prev) => prev.map(o => o.id === msg.order.id ? msg.order : o));
          }
          setBalances(msg.balances);
          
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
      addChatMessage("system", `🛡️ ตรวจสอบความเสี่ยงสำเร็จ: Lot ${riskForm.lot} | SL ${riskForm.stopDistance} | Spread ${riskForm.spread} -> สถานะ: ${data.passed ? "ผ่าน ✅" : "บล็อก 🔴"}`);
    } catch (e) {
      console.error(e);
      addChatMessage("system", "❌ ไม่สามารถส่งคำขอดึงความเสี่ยงจากบอทได้");
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
      // Grid is 3 col x 3 row isometric
      // col-row range: -2 to +2 (X axis)
      // col+row range: 0 to 4   (Y axis)
      // Vertical span: wallHeight (top of wall above top room) + 5 * sizeY (5 diamonds)
      // Center point at col+row=2 => middle row
      const availH = canvasH - BOTTOM_BAR_H;
      // Position grid center so top room (col+row=0) start above wallHeight
      // and bottom room (col+row=4) fits before BOTTOM_BAR_H
      // Total height: wallH + 5*sizeY; center of middle band at (col+row=2) => place at availH*0.5 roughly
      const totalGridH = wallHeight + 5 * sizeY;
      // เลื่อนกริดขึ้น: topMargin เล็กมากเพื่อให้กริดเต็มพื้นที่ available
      // ห้องล่างสุด (col+row=4) อยู่ที่ gridCenterY + 4*sizeY
      // ปลายล่างสุดของห้องนั้นอยู่ที่ gridCenterY + 5*sizeY + 15 (furniture)
      // ดังนั้น gridCenterY + 5*sizeY + 15 <= availH => gridCenterY <= availH - 5*sizeY - 15
      // gridCenterY = topMargin + wallHeight + 2*sizeY
      // => topMargin = availH - 5*sizeY - 15 - wallHeight - 2*sizeY = availH - 7*sizeY - wallHeight - 15
      const maxGridCenterY = availH - 5 * sizeY - 20;
      const minTopMargin = 4;
      const topMargin = Math.max(minTopMargin, (maxGridCenterY - wallHeight - 2 * sizeY) * 0.1);
      const gridCenterY = topMargin + wallHeight + 2 * sizeY;
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
      const maxByH = (availableH * 0.88 - furniturePad) / (wallToSizeXRatio + 5.5 * sizeYToSizeXRatio);
      const maxByW = (W * 0.83) / 5;
      const targetSizeX = Math.min(maxByH, maxByW);
      scaleMultiplier = Math.max(0.40, Math.min(1.1, targetSizeX / 150));
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

      const targetRoomIds = ["chart", "audit", "ea"];
      
      targetRoomIds.forEach((ti, idx) => {
        const dest = centers[ti];
        if (!dest) return;

        ctx.strokeStyle = "rgba(6, 182, 212, 0.22)"; // นีออนฟ้าเข้มข้น
        ctx.lineWidth = 1.2;
        ctx.setLineDash([5, 5]);
        
        ctx.beginPath();
        ctx.moveTo(ceoCenter.cx, ceoCenter.cy);
        ctx.lineTo(dest.cx, dest.cy);
        ctx.stroke();
        
        ctx.setLineDash([]); 

        const speedMultiplier = 0.008;
        const progress = ((frameCountRef.current * speedMultiplier) + idx * 0.33) % 1;
        const px = ceoCenter.cx + (dest.cx - ceoCenter.cx) * progress;
        const py = ceoCenter.cy + (dest.cy - ceoCenter.cy) * progress;
        
        ctx.fillStyle = "#22d3ee";
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
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
      const bx = a.sx - tw / 2 + 4 * scaleMultiplier;
      const by = a.sy - 12 - th;

      ctx.fillStyle = "#070a0f";
      ctx.strokeStyle = "#06b6d4";
      ctx.lineWidth = 1.5;
      roundRect(ctx, bx, by, tw, th, Math.max(3, 4 * scaleMultiplier));
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = "#070a0f";
      ctx.strokeStyle = "#06b6d4";
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
    <div className="h-screen w-screen bg-[#0b0e14] text-[#c8d8f0] flex flex-col overflow-hidden font-sans select-none">
      
      {/* ── TOPBAR ── */}
      <header className="bg-[#070a0f] border-b border-[#1e2d45] flex items-center gap-2 px-3.5 h-10 flex-shrink-0">
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

        <div className="flex items-center gap-1.5 bg-[#111520] border border-[#3a1a6a] rounded px-2.5 py-0.5 text-[11px] text-[#c084fc]">
          🔑 Claude API ✓
        </div>
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
        <aside className="w-[172px] min-w-[172px] bg-[#070a0f] border-r border-[#1e2d45] flex flex-col flex-shrink-0">
          <div className="p-3 border-b border-[#1e2d45]">
            <div className="text-[18px] mb-1">🏢</div>
            <div className="text-[8px] font-black text-[#f0b429] tracking-wider leading-relaxed">TRADE OFFICE</div>
            <div className="text-[10px] text-[#3d5a7a]">v2.21.0 · Claude API</div>
          </div>

          <div className="p-2 space-y-3">
            <div>
              <div className="px-3 py-1 text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold"># MAIN</div>
              <nav className="space-y-0.5 mt-1 font-semibold">
                <button 
                  onClick={() => setActiveMenu("Office Overview")}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Office Overview" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  🖥 Office Overview
                </button>
                <button 
                  onClick={() => {
                    setActiveMenu("Chat Center");
                    setUnreadCount(0);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Chat Center" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
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
                  className={`w-full flex items-center justify-between px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "AI Agents" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  <span>🤖 AI Agents</span>
                  <span className="bg-[#238636] text-white text-[8px] px-1.5 py-0.2 rounded font-bold">
                    8
                  </span>
                </button>
                <button 
                  onClick={() => setActiveMenu("Workflow Board")}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Workflow Board" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
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
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Analytics" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  📊 Analytics
                </button>
                <button 
                  onClick={() => setActiveMenu("Risk Monitor")}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Risk Monitor" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  ⚠️ Risk Monitor
                </button>
                <button 
                  onClick={() => setActiveMenu("Reports")}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Reports" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  📈 Reports
                </button>
              </nav>
            </div>

            <div>
              <div className="px-3 py-1 text-[9px] text-[#3d5a7a] tracking-wider uppercase font-bold"># SYSTEM</div>
              <nav className="space-y-0.5 mt-1 font-semibold">
                <button 
                  onClick={() => setActiveMenu("Settings")}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-[12.5px] rounded text-left transition ${
                    activeMenu === "Settings" ? "bg-[#0d2a14] text-[#10b981] border-l-2 border-[#10b981]" : "text-[#7a9bbf] hover:bg-[#111520] hover:text-white"
                  }`}
                >
                  ⚙️ Settings
                </button>
              </nav>
            </div>
          </div>

          <div className="mt-auto p-3 border-t border-[#1e2d45] text-[10.5px] text-[#7a9bbf] leading-relaxed">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_5px_#10b981]"></span>
              8 Agents · Online
            </div>
            <div className="text-[#10b981] text-[9.5px] mt-1 font-bold">MT5 & CCXT Binance</div>
          </div>
        </aside>

        {/* ── CENTRAL MAIN WORKSPACE ── */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          
          {/* TAB 1: 🖥 Office Overview (Isometric Neon Tech Canvas) */}
          <div className={`flex-1 relative overflow-hidden bg-[#06090e] ${activeMenu === "Office Overview" ? "block" : "hidden"}`} ref={wrapRef}>
            <canvas 
              id="office" 
              ref={canvasRef}
              onClick={handleCanvasClick}
              className="block w-full h-full cursor-pointer"
            />
            
            {/* ── Bottom Center: Risk Gate Control Bar ── */}
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-[700px] max-w-[96vw] bg-[#070a0f]/96 border border-[#1e2d45] rounded-xl p-2.5 shadow-2xl backdrop-blur-md flex items-center gap-3">
              {/* Symbol selector + price row */}
              <div className="flex flex-col gap-1 min-w-[90px]">
                <div className="text-[8.5px] text-[#f59e0b] font-bold uppercase tracking-wider">📡 Risk Gate</div>
                <select 
                  value={symbol}
                  onChange={(e) => handleSymbolChange(e.target.value)}
                  className="bg-[#111520] border border-[#1e2d45] rounded text-[9px] text-white p-0.5 outline-none font-mono font-bold w-full"
                >
                  {SYMBOLS_LIST.map((s) => (
                    <option key={s.symbol} value={s.symbol}>
                      {s.symbol}
                    </option>
                  ))}
                </select>
              </div>

              {/* Indicators row */}
              <div className="flex gap-2 text-center text-[9px] bg-[#0a0d16] border border-[#1e2d45] p-1.5 rounded font-mono flex-1">
                <div className="flex-1">
                  <div className="text-[#3d5a7a] text-[8px]">ราคา</div>
                  <div className="font-bold text-white">{latestPrice || "-"}</div>
                </div>
                <div className="flex-1">
                  <div className="text-[#3d5a7a] text-[8px]">EMA</div>
                  <div className={`font-bold ${indicators?.trend === "Bullish" ? "text-[#10b981]" : "text-[#f87171]"}`}>{indicators?.trend || "-"}</div>
                </div>
                <div className="flex-1">
                  <div className="text-[#3d5a7a] text-[8px]">RSI</div>
                  <div className="font-bold text-white">{indicators?.rsi || "-"}</div>
                </div>
                <div className="flex-1">
                  <div className="text-[#3d5a7a] text-[8px]">Signal</div>
                  <div className={`font-bold ${signal?.action === "BUY" ? "text-[#10b981]" : signal?.action === "SELL" ? "text-[#f87171]" : "text-slate-400"}`}>{signal?.action || "WAIT"}</div>
                </div>
              </div>

              {/* Lot / SL / Spread */}
              <div className="flex gap-1.5 text-[8.5px]">
                <div>
                  <span className="text-[#3d5a7a] block">Lot</span>
                  <input type="number" step="0.01" value={riskForm.lot} 
                    onChange={(e) => setRiskForm({...riskForm, lot: Number(e.target.value)})}
                    className="w-14 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center"
                  />
                </div>
                <div>
                  <span className="text-[#3d5a7a] block">SL (Pips)</span>
                  <input type="number" value={riskForm.stopDistance} 
                    onChange={(e) => setRiskForm({...riskForm, stopDistance: Number(e.target.value)})}
                    className="w-14 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center"
                  />
                </div>
                <div>
                  <span className="text-[#3d5a7a] block">Spread</span>
                  <input type="number" step="0.1" value={riskForm.spread} 
                    onChange={(e) => setRiskForm({...riskForm, spread: Number(e.target.value)})}
                    className="w-14 bg-[#111520] border border-[#1e2d45] rounded p-0.5 text-white font-mono text-center"
                  />
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-1.5">
                <button onClick={handleRiskTest} className="px-2.5 py-1.5 bg-[#1e2d45] hover:bg-[#243352] text-[9px] font-bold text-[#c8d8f0] rounded border border-[#243352] transition whitespace-nowrap">
                  🔍 ประเมิน
                </button>
                <div className={`px-2 py-1.5 text-[9px] font-bold rounded flex items-center ${
                  risk?.passed ? "bg-[#0d2a14] text-[#10b981] border border-[#1a5a28]" : "bg-[#2a0d0d] text-[#f87171] border border-[#6b1c1c]"
                }`}>
                  {risk?.passed ? "🟢 PASS" : "🔴 BLOCK"}
                </div>
                <button 
                  onClick={handleApprove}
                  disabled={!risk?.passed}
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
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "AI Agents" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">🏢 AI Trading Virtual Office — Master Prompt Blueprint</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">Version 2.21.0 | Claude API | MT5 + Crypto | Thai Language</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#60a5fa] flex items-center gap-1.5">🕴️ AGENT 1: CEO Agent (Orchestrator)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: JARVIS-CEO | บทบาท: ผู้ประสานงานและอนุมัติหลัก</p>
                <div className="text-xs text-[#94a3b8]">รับคำสั่ง แปลงงาน มอนิเตอร์ Risk และสรุปส่งผล Telegram ขอการคอนเฟิร์มแบบ Approve/Reject</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`Orchestrator: CEO Agent
1. parallel dispatch Chart & Risk
2. สรุปแผนเข้าพอร์ตใน 5 บรรทัด`}
                </pre>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#34d399] flex items-center gap-1.5">📊 AGENT 2: Chart AI (Technical Analyst)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: NOVA-CHART | บทบาท: วิเคราะห์แนวโน้มราคา</p>
                <div className="text-xs text-[#94a3b8]">Top-down analysis, คำนวณ RSI, EMA50 vs EMA200 และ Confluence score ต่ำกว่า 3/5 ห้ามปล่อยสัญญาณ</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`Technical Analysis:
- Confluence < 3/5 = WAIT
- RSI > 80 ห้ามสั่ง BUY`}
                </pre>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#f87171] flex items-center gap-1.5">🛡️ AGENT 3: Risk AI (The Guardian)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: SHIELD-RISK | บทบาท: ผู้คุมเกณฑ์เสี่ยงพอร์ต</p>
                <div className="text-xs text-[#94a3b8]">คำนวณ Lot size, ป้องกันการขาดทุนสะสม Drawdown เกิน 3% ต่อวัน และบริหาร Risk Limit ไม้ละ 2%</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`Risk Controls:
- Risk > 2% per trade = BLOCK
- ไม่มี Stop loss = BLOCK`}
                </pre>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#22d3ee] flex items-center gap-1.5">💰 AGENT 4: Finance AI (CFO)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: ATLAS-FINANCE | บทบาท: บัญชีและสรุปพอร์ตรวม</p>
                <div className="text-xs text-[#94a3b8]">ประมวลผล P&L รายดีล ยอดเงินคงคลังสินทรัพย์ และแปลงข้อมูลยิง Webhook สมุดรายวัน ERP</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`ERP Integration:
- Sync event: trade.closed | pnl_realized
- Sync Net Worth MT5 + Binance`}
                </pre>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#f97316] flex items-center gap-1.5">🔔 AGENT 5: Alert AI (Sentinel)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: SENTINEL-ALERT | บทบาท: เฝ้าระวังฉุกเฉินและดัชนีข่าว</p>
                <div className="text-xs text-[#94a3b8]">ตรวจจับระดับวอลลุ่มผันผวนรุนแรง, ข่าว High-impact ใน 30 นาที และ Margin level วิกฤติ ต่ำกว่า 200%</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`High-impact Alert:
- Margin < 200% = HIGH ALERT
- แจ้งปิดออเดอร์ด่วน`}
                </pre>
              </div>

              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-2">
                <h3 className="text-sm font-bold text-[#fbbf24] flex items-center gap-1.5">🎯 AGENT 6: Strategy AI (Oracle)</h3>
                <p className="text-[10px] text-[#7a9bbf]">ชื่อรหัส: ORACLE-STRATEGY | บทบาท: วางสภาวะระบบเทรด</p>
                <div className="text-xs text-[#94a3b8]">ประเมินและคัดกรองระบบเทรดตามค่าดัชนี ADX (Trending market / Sideways / Volatile pre-news)</div>
                <pre className="bg-[#070a0f] border border-[#1e2d45] p-2 text-[10px] text-emerald-400 max-h-24 overflow-y-auto font-mono">
{`Trending (ADX > 25): Crossover/Pullback
Sideways (ADX < 20): Range/Rebound`}
                </pre>
              </div>
            </div>
          </div>

          {/* TAB 3: 📋 Workflow Board - Multi-Agent Flow Diagram */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "Workflow Board" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">🔄 สถิติกระบวนการ Multi-Agent Flow แบบสมบูรณ์</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">เส้นทางประมวลผลสัญญาณเทรดและส่งคืนบัญชี Team ERP</p>
            </div>

            <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-6 space-y-4">
              <div className="text-xs text-[#94a3b8]">
                ขั้นตอนทำงานอย่างเป็นระบบ (Safe Execution Flow) จากข้อความ /analyze หรือปุ่มกดยืนยันใน Telegram:
              </div>
              <div className="bg-[#070a0f] p-4 rounded border border-[#1e2d45] text-xs font-mono space-y-2.5 leading-relaxed text-[#c8d8f0]">
                <div><span className="text-[#fbbf24] font-bold">[1]</span> สั่งการผ่านบอทเทเลแกรมจริง / analyze XAUUSD</div>
                <div><span className="text-[#fbbf24] font-bold">[2]</span> CEO Agent ประมวลผลและแจกงานขนานไปหา Chart AI (วิเคราะห์เทคนิค), Risk AI (คำนวณความเสี่ยง), และ News AI (สแกนข่าวเศรษฐกิจ)</div>
                <div><span className="text-[#fbbf24] font-bold">[3]</span> CEO Agent ส่งสรุปแผนการเทรดกลับไปที่แชทเทเลแกรม พร้อมสร้างปุ่ม [✅ อนุมัติ] / [❌ ปฏิเสธ]</div>
                <div><span className="text-[#fbbf24] font-bold">[4]</span> ผู้ใช้กดปุ่มอนุมัติ &rarr; บอทตรวจ Callback query ยิงสัญญาจริงเข้าตลาดผ่าน EA Bot (MT5) หรือ Binance API</div>
                <div><span className="text-[#fbbf24] font-bold">[5]</span> ดีลปิด &rarr; Finance AI บันทึกกำไรขาดทุนสะสม และประมาณภาษี Team Tax เข้าคลัง ERP อัตโนมัติ</div>
              </div>
            </div>
          </div>

          {/* TAB 4: 💬 Chat Center (Full screen Chat Log View) */}
          <div className={`flex-1 flex flex-col overflow-hidden bg-[#080c12] ${activeMenu === "Chat Center" ? "block" : "hidden"}`}>
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
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "Analytics" ? "block" : "hidden"}`}>
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
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "Risk Monitor" ? "block" : "hidden"}`}>
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
                        <td className="py-2 text-slate-500">{new Date(ord.id ? Number(ord.id.replace("ord_", "")) : Date.now()).toLocaleTimeString()}</td>
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
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "Reports" ? "block" : "hidden"}`}>
            <div className="border-b border-[#1e2d45] pb-4">
              <h2 className="text-xl font-bold text-white">📊 รายงานบัญชีและระเบียบภาษีคลัง (Team ERP Ledger & Tax Sheet)</h2>
              <p className="text-xs text-[#7a9bbf] mt-1">สมุดรายการเดบิต/เครดิต และประมาณการการชำระภาษีสะสมในไทย</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* รายงานเดบิต เครดิต ERP */}
              <div className="lg:col-span-2 bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-3">
                <div className="text-xs text-white font-bold uppercase tracking-wider">สมุดบัญชีแยกประเภททั่วไป (General Ledger Double-Entry)</div>
                <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                  {ledger.map((tx, idx) => (
                    <div key={idx} className="bg-[#070a0f] border border-[#1e2d45] p-3 rounded-lg text-xs space-y-2 font-mono">
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>TX: {tx.id}</span>
                        <span>{new Date(tx.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="font-semibold text-slate-200">{tx.description}</div>
                      <div className="grid grid-cols-2 gap-2 text-[10px] border-t border-slate-800 pt-1.5">
                        <div className="text-emerald-400">
                          Dr: {tx.debit.account}
                          <div className="font-bold text-white mt-0.5">${tx.debit.amount.toLocaleString()}</div>
                        </div>
                        <div className="text-[#fbbf24]">
                          Cr: {tx.credit.account}
                          <div className="font-bold text-white mt-0.5">${tx.credit.amount.toLocaleString()}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* แบบสรุปภาษี Team Tax */}
              <div className="bg-[#111520] border border-[#1e2d45] rounded-xl p-4 space-y-4">
                <div className="text-xs text-white font-bold uppercase tracking-wider">แบบสรุปการยื่นภาษีสะสม (Team Tax Summary)</div>
                {taxSummary ? (
                  <div className="text-xs space-y-3 font-mono">
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">กำไรการลงทุนสะสม:</span>
                      <span className="font-bold text-[#10b981]">${taxSummary.accumulatedPnL.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">ค่าธรรมเนียมธุรกรรมสะสม:</span>
                      <span className="font-bold text-[#ef4444]">${taxSummary.accumulatedFees.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-slate-400">รายได้สุทธิรอคำนวณ:</span>
                      <span className="font-bold text-white">${taxSummary.taxableIncome.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-[#22d3ee] font-bold">ภาษีซื้อเคลมคืน (VAT 7%):</span>
                      <span className="font-bold text-[#22d3ee]">+${taxSummary.inputVatClaimable.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800">
                      <span className="text-[#ef4444]">ภาษีนิติบุคคลหักสะสม (20%):</span>
                      <span className="font-bold text-[#ef4444]">-${taxSummary.estimatedIncomeTax.toFixed(2)}</span>
                    </div>
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/25 rounded-lg flex justify-between items-center text-sm font-bold">
                      <span className="text-[#34d399]">กำไรสุทธิหลังหักภาษี:</span>
                      <span className="text-[#34d399] font-bold">${taxSummary.netAfterTax.toFixed(2)}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-slate-500 py-10 text-xs">ยังไม่มีข้อมูลภาษีสะสม</div>
                )}
              </div>
            </div>
          </div>

          {/* TAB 8: ⚙️ Settings (Telegram Bot Config & constants) */}
          <div className={`flex-1 overflow-y-auto p-6 md:p-8 bg-[#080c12] space-y-6 ${activeMenu === "Settings" ? "block" : "hidden"}`}>
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

          <div className="flex-1 overflow-y-auto p-2 space-y-2 bg-[#080c12]/30">
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
