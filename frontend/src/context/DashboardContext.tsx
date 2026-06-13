"use client";

import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import type {
  Balance,
  Indicator,
  Signal,
  RiskCheck,
  Order,
  SignalActivity,
  ChatMessage,
  LedgerEntry,
  TaxSummary,
} from "@/types";
import { AGENT_CHAT_MAP, ROOMS_CONFIG } from "@/config/dashboard";

/**
 * Owns ALL shared dashboard state: the live WebSocket connection, trading/market
 * state, ERP ledger, chat, settings, and the agent canvas refs. Lives in the
 * dashboard layout so it survives route navigation between tabs.
 */
function useDashboardState() {
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
    // Optimistically switch the UI immediately so the chart/symbol changes on
    // selection, regardless of backend latency or response. Backend is synced after.
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

    try {
      const res = await fetch("http://localhost:8000/api/change-symbol", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: newSym })
      });
      const data = await res.json();
      if (data.status === "success") {
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
  return {
    wsStatus,
    setWsStatus,
    symbol,
    setSymbol,
    latestPrice,
    setLatestPrice,
    priceMap,
    setPriceMap,
    indicators,
    setIndicators,
    signal,
    setSignal,
    risk,
    setRisk,
    mode,
    setMode,
    balances,
    setBalances,
    orders,
    setOrders,
    activeTab,
    setActiveTab,
    filterDate,
    setFilterDate,
    featureFlags,
    setFeatureFlags,
    circuitBreakers,
    setCircuitBreakers,
    heartbeats,
    setHeartbeats,
    nanLogs,
    setNanLogs,
    calibration,
    setCalibration,
    correlationRejections,
    setCorrelationRejections,
    signalActivity,
    setSignalActivity,
    activityLogs,
    setActivityLogs,
    ledger,
    setLedger,
    taxSummary,
    setTaxSummary,
    chatMsgs,
    setChatMsgs,
    chatInput,
    setChatInput,
    unreadCount,
    setUnreadCount,
    settingsForm,
    setSettingsForm,
    riskForm,
    setRiskForm,
    newsFeed,
    setNewsFeed,
    canvasRef,
    wrapRef,
    chatEndRef,
    wsRef,
    symbolRef,
    agentsStateRef,
    frameCountRef,
    scaleMultiplierRef,
    totalEquity,
    activeTradesCount,
    closedOrders,
    todayPnLSum,
    pnlPct,
    addActivityLog,
    addSignalActivity,
    fetchERPData,
    fetchNewsData,
    fetchStateData,
    handleCloseOrder,
    addChatMessage,
    handleSendChat,
    handleSymbolChange,
    handleRiskTest,
    handleToggleMode,
    handleApprove,
    handleReject,
    handleResetData,
    handleSaveSettings,
  };
}

export type DashboardContextValue = ReturnType<typeof useDashboardState>;

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const value = useDashboardState();
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within a DashboardProvider");
  return ctx;
}
