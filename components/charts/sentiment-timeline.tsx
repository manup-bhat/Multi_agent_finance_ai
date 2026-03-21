'use client';

import dynamic from 'next/dynamic';
import { useState, useCallback } from 'react';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={300} />,
});

export interface SentimentTimelineChartProps {
  data?: {
    dates: string[];
    composite: number[];
    institutional?: number[];
    social?: number[];
    gdelt?: number[];
    events?: Array<{ date: string; type: 'RBI' | 'Budget' | 'Expiry'; label: string }>;
  };
  height?: number;
}

const PERIOD_OPTIONS = ['3D', '7D', '30D'];

export function SentimentTimelineChart({ data, height = 300 }: SentimentTimelineChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();
  const [period, setPeriod] = useState('7D');

  if (!data || !data.dates || data.dates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-text-muted text-sm gap-2">
        <span>No sentiment timeline data</span>
        <span className="text-xs">Run an analysis to populate this chart</span>
      </div>
    );
  }

  const periodDays = { '3D': 3, '7D': 7, '30D': 30 }[period] ?? 7;
  const sliceFrom = Math.max(0, data.dates.length - periodDays);

  const sliced = {
    dates: data.dates.slice(sliceFrom),
    composite: data.composite.slice(sliceFrom),
    institutional: (data.institutional || []).slice(sliceFrom),
    social: (data.social || []).slice(sliceFrom),
    gdelt: (data.gdelt || []).slice(sliceFrom),
  };

  const series = [
    { name: 'Composite', data: sliced.composite, color: CHART_COLORS.saffron },
    { name: 'Institutional', data: sliced.institutional, color: CHART_COLORS.neutral },
    { name: 'Social F/G', data: sliced.social, color: '#7C3AED' },
    { name: 'GDELT', data: sliced.gdelt, color: CHART_COLORS.warning },
  ].filter((s) => s.data.length > 0);

  const eventAnnotations = (data.events || []).map((evt) => ({
    x: new Date(evt.date).getTime(),
    borderColor: evt.type === 'RBI' ? '#7C3AED' : evt.type === 'Budget' ? '#DC2626' : CHART_COLORS.warning,
    strokeDashArray: 4,
    label: {
      text: evt.label,
      style: {
        background: evt.type === 'RBI' ? '#7C3AED' : evt.type === 'Budget' ? '#DC2626' : CHART_COLORS.warning,
        color: '#fff',
        fontSize: '10px',
      },
    },
  }));

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'line',
      toolbar: { show: false },
      animations: { enabled: true },
      zoom: { enabled: false },
    },
    stroke: {
      curve: 'smooth',
      width: [2.5, 1.5, 1.5, 1.5],
      dashArray: [0, 0, 0, 5],
    },
    colors: series.map((s) => s.color),
    xaxis: {
      categories: sliced.dates,
      type: 'datetime',
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      min: -1,
      max: 1,
      tickAmount: 4,
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: number) => val.toFixed(2),
      },
    },
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
      yaxis: { lines: { show: true } },
      xaxis: { lines: { show: false } },
    },
    annotations: {
      xaxis: eventAnnotations,
      yaxis: [
        {
          y: 0,
          borderColor: chartTheme.grid,
          strokeDashArray: 4,
          label: { text: 'Zero', style: { color: chartTheme.text, background: chartTheme.tooltipBg, fontSize: '10px' } },
        },
      ],
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      shared: true,
      y: { formatter: (val: number) => (val != null ? val.toFixed(3) : 'N/A') },
    },
    legend: {
      show: true,
      position: 'top' as const,
      horizontalAlign: 'right' as const,
      labels: { colors: chartTheme.text },
    },
    markers: { size: 0 },
  };

  return (
    <div className="w-full">
      {/* Period toggle */}
      <div className="flex gap-1.5 mb-3">
        {PERIOD_OPTIONS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className="text-xs px-2.5 py-1 rounded-btn font-medium transition-all"
            style={{
              background: period === p ? CHART_COLORS.saffron : 'transparent',
              color: period === p ? '#fff' : chartTheme.text,
              border: `1px solid ${period === p ? CHART_COLORS.saffron : chartTheme.grid}`,
            }}
          >
            {p}
          </button>
        ))}
      </div>

      <Chart
        options={options}
        series={series.map((s) => ({ name: s.name, data: s.data }))}
        type="line"
        height={height}
      />
    </div>
  );
}
