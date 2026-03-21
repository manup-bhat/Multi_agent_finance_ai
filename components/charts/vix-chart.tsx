'use client';
import type { ApexOptions } from 'apexcharts';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={250} />,
});

export interface VixChartProps {
  data: Array<{ date: string; value: number }>;
  variant?: 'sparkline' | 'full';
  height?: number;
}

function getVixColor(value: number): string {
  if (value < 13) return CHART_COLORS.bullish; // Complacency - Green
  if (value < 18) return CHART_COLORS.neutral; // Normal - Blue
  if (value < 25) return CHART_COLORS.warning; // Elevated - Amber
  return CHART_COLORS.bearish; // High Fear - Red
}

function getVixRegime(value: number): string {
  if (value < 13) return 'Complacency';
  if (value < 18) return 'Normal';
  if (value < 25) return 'Elevated';
  return 'High Fear';
}

export function VixChart({ data, variant = 'full', height = 250 }: VixChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.length === 0) {
    return <div className="text-text-muted text-sm p-4">No VIX data available</div>;
  }

  const latestValue = data[data.length - 1]?.value || 0;
  const latestColor = getVixColor(latestValue);
  const latestRegime = getVixRegime(latestValue);

  const series = [
    {
      name: 'VIX',
      data: data.map((d) => ({
        x: d.date,
        y: d.value,
      })),
    },
  ];

  const options: ApexOptions = {
    chart: {
      type: 'area' as const,
      sparkline: variant === 'sparkline' ? { enabled: true } : { enabled: false },
      toolbar: variant === 'sparkline' ? { show: false } : { show: true },
      animations: { enabled: true },
    },
    stroke: {
      curve: 'smooth',
      width: variant === 'sparkline' ? 1.5 : 2,
      colors: [latestColor],
    },
    fill: {
      type: 'gradient',
      gradient: {
        opacityFrom: 0.45,
        opacityTo: 0.05,
        colorStops: [
          { offset: 0, color: latestColor, opacity: 0.3 },
          { offset: 100, color: latestColor, opacity: 0.01 },
        ],
      },
    },
    xaxis: {
      type: 'datetime' as const,
      labels: {
        style: { colors: chartTheme.text, fontSize: '12px' },
        show: variant !== 'sparkline',
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      show: variant !== 'sparkline',
      labels: {
        style: { colors: chartTheme.text, fontSize: '12px' },
      },
      min: 0,
    },
    annotations: variant !== 'sparkline' ? {
      yaxis: [
        { y: 13, borderColor: '#ECFDF5', fillColor: '#ECFDF5', opacity: 0.1, label: { text: 'Complacency', style: { color: '#0F172A', background: '#ECFDF5' } } },
        { y: 18, borderColor: '#EFF6FF', fillColor: '#EFF6FF', opacity: 0.1, label: { text: 'Normal', style: { color: '#0F172A', background: '#EFF6FF' } } },
        { y: 25, borderColor: '#FFFBEB', fillColor: '#FFFBEB', opacity: 0.1, label: { text: 'Elevated', style: { color: '#0F172A', background: '#FFFBEB' } } },
        { y: 30, borderColor: '#FEF2F2', fillColor: '#FEF2F2', opacity: 0.15, label: { text: 'High Fear', style: { color: '#0F172A', background: '#FEF2F2' } } },
      ],
    } : undefined,
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val: number) => `VIX: ${val.toFixed(2)}`,
      },
    },
    colors: [latestColor],
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
      show: variant !== 'sparkline',
    },
    markers: variant === 'sparkline' ? { size: 0 } : { size: 4, strokeWidth: 0 },
    states: {
      hover: { filter: { type: 'none' } },
      active: { filter: { type: 'none' } },
    },
  };

  return (
    <div className="w-full">
      {variant === 'full' && (
        <div className="mb-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest">India VIX</h3>
            <div className="text-right">
              <div className="text-2xl font-bold" style={{ color: latestColor }}>
                {latestValue.toFixed(2)}
              </div>
              <div className="text-xs text-text-secondary">{latestRegime}</div>
            </div>
          </div>
        </div>
      )}

      <Chart
        options={options}
        series={series}
        type="area"
        height={height}
      />
    </div>
  );
}
