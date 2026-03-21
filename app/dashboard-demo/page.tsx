'use client';

import dynamic from 'next/dynamic';
import {
  ChartSkeleton,
  FearGreedGauge,
  RiskGauge,
  FiiDiiChart,
  VixChart,
  SectorHeatmap,
  SentimentTimelineChart,
  SparklineBar,
} from '@/components/charts';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { formatCrore, formatINR, formatPct } from '@/lib/format-india';
import { useTheme } from 'next-themes';

export default function DashboardDemo() {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  // Demo data
  const mockFiiDiiData = [
    { date: '2024-03-01', fiiNetCrore: 2500, diiNetCrore: 1200 },
    { date: '2024-03-02', fiiNetCrore: -1800, diiNetCrore: 900 },
    { date: '2024-03-03', fiiNetCrore: 3200, diiNetCrore: -500 },
    { date: '2024-03-04', fiiNetCrore: 1500, diiNetCrore: 2100 },
    { date: '2024-03-05', fiiNetCrore: 4100, diiNetCrore: 1800 },
  ];

  const mockVixData = [
    { date: '2024-03-01', value: 18.5 },
    { date: '2024-03-02', value: 20.2 },
    { date: '2024-03-03', value: 19.8 },
    { date: '2024-03-04', value: 17.3 },
    { date: '2024-03-05', value: 16.9 },
  ];

  const mockSectorData = [
    { sector: 'IT', marketCap: 450000, rs5d: 2.5 },
    { sector: 'BANK', marketCap: 420000, rs5d: 1.8 },
    { sector: 'AUTO', marketCap: 280000, rs5d: -1.2 },
    { sector: 'PHARMA', marketCap: 200000, rs5d: 0.5 },
    { sector: 'METAL', marketCap: 180000, rs5d: -2.8 },
    { sector: 'INFRA', marketCap: 160000, rs5d: 3.2 },
    { sector: 'REALTY', marketCap: 140000, rs5d: -0.5 },
    { sector: 'FMCG', marketCap: 120000, rs5d: 1.1 },
    { sector: 'ENERGY', marketCap: 100000, rs5d: -3.5 },
    { sector: 'TELECOM', marketCap: 80000, rs5d: 0.8 },
  ];

  const mockSentimentData = [
    { date: '2024-03-01', composite: 0.25, institutional: 0.3, socialFg: 0.2, gdelt: 0.15 },
    { date: '2024-03-02', composite: 0.3, institutional: 0.25, socialFg: 0.35, gdelt: 0.2 },
    { date: '2024-03-03', composite: 0.28, institutional: 0.32, socialFg: 0.25, gdelt: 0.25 },
    { date: '2024-03-04', composite: 0.22, institutional: 0.2, socialFg: 0.18, gdelt: 0.1 },
    { date: '2024-03-05', composite: 0.35, institutional: 0.4, socialFg: 0.3, gdelt: 0.3 },
  ];

  const mockSparklineData = [10, -5, 8, 15, -3, 12, 6];

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-text-primary mb-2">Financial Dashboard</h1>
          <p className="text-text-secondary">Comprehensive market analysis with proper color contrast</p>
        </header>

        {/* KPI Section */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Market Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <KPICard
              label="Nifty 50"
              value="23,450.25"
              change="+2.35%"
              changeColor={CHART_COLORS.bullish}
              sparkline={mockSparklineData}
            />
            <KPICard
              label="FII Net (5D)"
              value={formatCrore(5200, 0)}
              change="+1,200 Cr"
              changeColor={CHART_COLORS.bullish}
              sparkline={[10, 15, 8, 12, 9]}
            />
            <KPICard
              label="India VIX"
              value="16.9"
              change="-1.3"
              changeColor={CHART_COLORS.bullish}
              sparkline={[18.5, 20.2, 19.8, 17.3, 16.9]}
            />
            <KPICard
              label="Market Sentiment"
              value="Bullish"
              change="+35%"
              changeColor={CHART_COLORS.bullish}
              sparkline={[20, 30, 28, 22, 35]}
            />
          </div>
        </section>

        {/* Main Charts Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Fear & Greed */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card">
            <FearGreedGauge value={65} label="Market Sentiment" height={280} />
          </div>

          {/* Risk Assessment */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card">
            <RiskGauge riskLevel="MODERATE" riskScore={55} positionSize={1.2} height={280} />
          </div>

          {/* FII/DII Flow */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card lg:col-span-1">
            <FiiDiiChart data={mockFiiDiiData} height={300} />
          </div>

          {/* VIX Index */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card lg:col-span-1">
            <VixChart variant="full" height={300} />
          </div>
        </section>

        {/* Full Width Charts */}
        <section className="space-y-6">
          {/* Sector Heatmap */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card">
            <SectorHeatmap
              data={mockSectorData}
              height={400}
              onSectorClick={(sector) => console.log('Clicked sector:', sector)}
            />
          </div>

          {/* Sentiment Timeline */}
          <div className="bg-surface rounded-lg border border-border p-6 shadow-card">
            <SentimentTimelineChart
              data={{
                dates: mockSentimentData.map(d => d.date),
                composite: mockSentimentData.map(d => d.composite),
                institutional: mockSentimentData.map(d => d.institutional),
                social: mockSentimentData.map(d => d.socialFg),
                gdelt: mockSentimentData.map(d => d.gdelt),
              }}
              height={300}
            />
          </div>
        </section>

        {/* Color Contrast Validation Section */}
        <section className="mt-12 p-6 bg-surface rounded-lg border border-border shadow-card">
          <h3 className="text-lg font-semibold text-text-primary mb-4">Color Contrast Reference</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <ColorBox bg={CHART_COLORS.bullish} fg="#FFFFFF" label="Bullish" />
            <ColorBox bg={CHART_COLORS.bearish} fg="#FFFFFF" label="Bearish" />
            <ColorBox bg={CHART_COLORS.neutral} fg="#FFFFFF" label="Neutral" />
            <ColorBox bg={CHART_COLORS.warning} fg="#FFFFFF" label="Warning" />
            <ColorBox bg={CHART_COLORS.bullishBg} fg={CHART_COLORS.bullish} label="Bullish BG" />
            <ColorBox bg={CHART_COLORS.bearishBg} fg={CHART_COLORS.bearish} label="Bearish BG" />
            <ColorBox bg={CHART_COLORS.neutralBg} fg={CHART_COLORS.neutral} label="Neutral BG" />
            <ColorBox bg={CHART_COLORS.warningBg} fg={CHART_COLORS.warning} label="Warning BG" />
          </div>
        </section>

        {/* Typography Reference */}
        <section className="mt-8 p-6 bg-surface rounded-lg border border-border shadow-card">
          <h3 className="text-lg font-semibold text-text-primary mb-4">Typography & Contrast</h3>
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-text-muted uppercase tracking-widest">Section Label</p>
              <p className="text-text-primary">Primary Text (17:1 contrast)</p>
              <p className="text-text-secondary">Secondary Text (9:1 contrast)</p>
              <p className="text-text-muted">Muted Text (7:1 contrast)</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function KPICard({
  label,
  value,
  change,
  changeColor,
  sparkline,
}: {
  label: string;
  value: string;
  change: string;
  changeColor: string;
  sparkline: number[];
}) {
  return (
    <div className="bg-surface-raised rounded-lg p-4 border border-border">
      <p className="text-xs font-medium text-text-muted uppercase tracking-widest mb-3">{label}</p>
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-2xl font-bold text-text-primary tabular-nums">{value}</div>
        <div style={{ color: changeColor }} className="text-sm font-semibold">
          {change}
        </div>
      </div>
      <SparklineBar data={sparkline} height={40} />
    </div>
  );
}

function ColorBox({ bg, fg, label }: { bg: string; fg: string; label: string }) {
  return (
    <div
      className="p-4 rounded-lg text-center flex flex-col items-center justify-center min-h-24 border border-border"
      style={{ backgroundColor: bg }}
    >
      <div style={{ color: fg }} className="text-sm font-semibold mb-2">
        {label}
      </div>
      <div style={{ color: fg }} className="text-xs opacity-75">
        {bg}
      </div>
    </div>
  );
}
