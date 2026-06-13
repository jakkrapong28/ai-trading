"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDashboard } from "@/context/DashboardContext";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const icon = (d: string) => (
  <svg className="w-3.5 h-3.5 mr-2 text-inherit" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);

const MAIN: NavItem[] = [
  { label: "Office Overview", href: "/", icon: icon("M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z") },
  { label: "Trading Dashboard", href: "/trading", icon: icon("M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z") },
  { label: "Workflow Board", href: "/workflow", icon: icon("M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01") },
];

const TRADING: NavItem[] = [
  { label: "Analytics", href: "/analytics", icon: icon("M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z") },
  { label: "Performance Dashboard", href: "/performance", icon: icon("M13 10V3L4 14h7v7l9-11h-7z") },
  { label: "Risk Monitor", href: "/risk", icon: icon("M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z") },
  { label: "ERP & Reports", href: "/reports", icon: icon("M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4") },
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

  const renderItem = (item: NavItem) => (
    <Link key={item.href} href={item.href} className={linkClass(item.href)}>
      <span className="flex items-center">{item.icon}{item.label}</span>
    </Link>
  );

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
        <div>
          <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">MAIN</div>
          <nav className="space-y-0.5 mt-1 font-semibold">
            {MAIN.slice(0, 2).map(renderItem)}
            {/* Chat Center — resets unread badge on navigate */}
            <Link
              href="/chat"
              onClick={() => setUnreadCount(0)}
              className={linkClass("/chat")}
            >
              <span className="flex items-center">
                {icon("M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z")}
                Chat Center
              </span>
              <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
                {unreadCount > 0 ? unreadCount : 7}
              </span>
            </Link>
            <Link href="/agents" className={linkClass("/agents")}>
              <span className="flex items-center">
                {icon("M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z")}
                AI Agents
              </span>
              <span className="bg-[#10b981] text-white text-[8.5px] px-2 py-0.5 rounded-full font-extrabold shadow-[0_0_5px_rgba(16,185,129,0.3)]">
                9
              </span>
            </Link>
            {MAIN.slice(2).map(renderItem)}
          </nav>
        </div>

        <div>
          <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">TRADING</div>
          <nav className="space-y-0.5 mt-1 font-semibold">{TRADING.map(renderItem)}</nav>
        </div>

        <div>
          <div className="px-3.5 py-1 text-[8.5px] text-[#3d5a7a] tracking-wider uppercase font-bold">SYSTEM</div>
          <nav className="space-y-0.5 mt-1 font-semibold">
            <Link href="/settings" className={linkClass("/settings")}>
              <span className="flex items-center">
                {icon("M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z")}
                Settings
              </span>
            </Link>
          </nav>
        </div>
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
