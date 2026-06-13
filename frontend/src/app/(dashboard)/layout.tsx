"use client";

import { DashboardProvider } from "@/context/DashboardContext";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import RightPanel from "@/components/RightPanel";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardProvider>
      <div className="h-screen w-screen bg-[#000000] text-[#c8d8f0] flex overflow-hidden font-sans select-none">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Topbar />
          <main className="flex-1 flex flex-col overflow-hidden relative">{children}</main>
        </div>
        <RightPanel />
      </div>
    </DashboardProvider>
  );
}
