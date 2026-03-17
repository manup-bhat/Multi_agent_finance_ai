"use client";
import { useApp } from "@/lib/app-context";
import { AnalyzeCard } from "@/components/dashboard/analyze-card";
import { VerdictHero } from "@/components/dashboard/verdict-hero";
import { KPICards } from "@/components/dashboard/kpi-cards";
import { PriceChart } from "@/components/dashboard/price-chart";
import { AgentAccordion } from "@/components/dashboard/agent-accordion";
import { RiskMeter } from "@/components/dashboard/risk-meter";
import { SocialSentiment } from "@/components/dashboard/social-sentiment";
import { KeyLevels } from "@/components/dashboard/key-levels";
import { EmptyState } from "@/components/dashboard/empty-state";

export default function DashboardPage() {
  const { analysisData } = useApp();

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      {/* Analyze Card */}
      <AnalyzeCard />

      {!analysisData ? (
        <EmptyState />
      ) : (
        <>
          {/* Verdict Hero */}
          <VerdictHero />

          {/* KPI Cards */}
          <KPICards />

          {/* Main 2-col grid */}
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
            {/* Left — 60% */}
            <div className="xl:col-span-3 space-y-6">
              <PriceChart />
              <AgentAccordion />
            </div>

            {/* Right — 40% */}
            <div className="xl:col-span-2 space-y-6">
              <RiskMeter />
              <SocialSentiment />
              <KeyLevels />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
