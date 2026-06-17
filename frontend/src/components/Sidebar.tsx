"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDashboard } from "@/context/DashboardContext";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: "unread" | number;
}

const icon = (d: string) => (
  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);

// Three balanced groups so the rail reads as an organized workspace rather than
// a flat 10-item dump. (Settings removed — secrets live server-side in .env.)
const GROUPS: { title: string; items: NavItem[] }[] = [
  {
    title: "WORKSPACE",
    items: [
      { label: "Office Overview", href: "/", icon: icon("M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z") },
      { label: "Trading Dashboard", href: "/trading", icon: icon("M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z") },
      { label: "Chat Center", href: "/chat", icon: icon("M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"), badge: "unread" },
    ],
  },
  {
    title: "INTELLIGENCE",
    items: [
      { label: "AI Agents", href: "/agents", icon: icon("M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"), badge: 9 },
      { label: "Analytics", href: "/analytics", icon: icon("M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z") },
      { label: "Workflow & Guide", href: "/workflow", icon: icon("M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01") },
    ],
  },
  {
    title: "PORTFOLIO",
    items: [
      { label: "Performance", href: "/performance", icon: icon("M13 10V3L4 14h7v7l9-11h-7z") },
      { label: "Risk Monitor", href: "/risk", icon: icon("M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z") },
      { label: "ERP & Reports", href: "/reports", icon: icon("M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4") },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { unreadCount, setUnreadCount } = useDashboard();

  const linkClass = (href: string) =>
    `w-full flex items-center justify-between px-3.5 py-2 text-[12px] rounded-md transition-all duration-200 ${
      pathname === href
        ? "bg-[#131d27]/80 text-white font-bold"
        : "text-[#7a9bbf] hover:bg-white/5 hover:text-white"
    }`;

  const badgeFor = (item: NavItem) => {
    if (item.badge === "unread") return unreadCount > 0 ? unreadCount : 7;
    return item.badge;
  };

  const renderItem = (item: NavItem) => {
    const badge = badgeFor(item);
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={item.badge === "unread" ? () => setUnreadCount(0) : undefined}
        className={linkClass(item.href)}
      >
        <span className="flex items-center">{item.icon}{item.label}</span>
        {badge != null && (
          <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
            {badge}
          </span>
        )}
      </Link>
    );
  };

  return (
    <aside className="w-[172px] min-w-[172px] bg-[#070a0f] border-r border-[#26262b] flex flex-col flex-shrink-0">
      <div className="p-4 border-b border-[#26262b] flex items-center gap-2">
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
        {GROUPS.map((group) => (
          <div key={group.title}>
            <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">{group.title}</div>
            <nav className="space-y-0.5 mt-1 font-semibold">{group.items.map(renderItem)}</nav>
          </div>
        ))}
      </div>

      <div className="mt-auto p-2">
        <div className="border border-[#26262b] bg-[#070b11]/80 rounded-lg p-2.5 flex flex-col gap-1">
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
  );
}
