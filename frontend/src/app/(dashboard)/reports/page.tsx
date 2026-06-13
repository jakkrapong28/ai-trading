"use client";

import ReportsTab from "@/components/tabs/ReportsTab";
import { useDashboard } from "@/context/DashboardContext";

export default function ReportsPage() {
  const { ledger, taxSummary, handleResetData } = useDashboard();
  return <ReportsTab active ledger={ledger} taxSummary={taxSummary} onResetData={handleResetData} />;
}
