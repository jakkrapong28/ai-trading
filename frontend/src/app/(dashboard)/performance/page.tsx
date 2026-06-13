"use client";

import PerformanceTab from "@/components/tabs/PerformanceTab";
import { useDashboard } from "@/context/DashboardContext";

export default function PerformancePage() {
  const { closedOrders, todayPnLSum, activeTradesCount } = useDashboard();
  return (
    <PerformanceTab
      active
      closedOrders={closedOrders}
      todayPnLSum={todayPnLSum}
      activeTradesCount={activeTradesCount}
    />
  );
}
