'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={280} />,
});

export interface AccuracyChartProps {
  data: {
    dates: string[];
    accuracy: number[];
    regimes?: Array<{ start: string; end: string; type: 'bull' | 'bear' | 'sideways' }>;
  };
  threshold?: number;       // default 55%
  height?: number;
}

export function AccuracyChart({ data, threshold = 55, height = 280 }: AccuracyChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.dates.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No model accuracy data available
      </div>
    );
  }

  // Gradient fill: above threshold → green, below → red
  const colorStops = [
    { offset: 0, color: CHART_COLORS.bullish, opacity: 0.45 },
    { offset: 100, color: CHART_COLORS.bullish, opacity: 0.05 },
  ];

  // Build regime background annotations
  const regimeAnnotations = (data.regimes || []).map((r) => ({
    x: new Date(r.start).getTime(),
    x2: new Date(r.end).getTime(),
    fillColor:
      r.type === 'bull'
        ? 'rgba(5,150,105,0.07)'
        : r.type === 'bear'
        ? 'rgba(220,38,38,0.07)'
        : 'rgba(217,119,6,0.05)',
    label: {
      text: r.type.charAt(0).toUpperCase() + r.type.slice(1),
      style: { color: chartTheme.text, fontSize: '10px', background: 'transparent' },
    },
  }));

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'area',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
      zoom: { enabled: false },
    },
    stroke: {
      curve: 'smooth',
      width: 2.5,
      colors: [CHART_COLORS.bullish],
    },
    fill: {
      type: 'gradient',
      gradient: {
        shade: isDark ? 'dark' : 'light',
        type: 'vertical',
        colorStops: [colorStops],
      },
    },
    colors: [CHART_COLORS.bullish],
    xaxis: {
      categories: data.dates,
      type: 'datetime',
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      min: 40,
      max: 85,
      tickAmount: 5,
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: number) => `${val.toFixed(0)}%`,
      },
    },
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
    },
    annotations: {
      xaxis: regimeAnnotations,
      yaxis: [
        {
          y: threshold,
          borderColor: CHART_COLORS.warning,
          strokeDashArray: 4,
          borderWidth: 2,
          label: {
            text: `Min threshold (${threshold}%)`,
            style: {
              color: CHART_COLORS.warning,
              background: chartTheme.tooltipBg,
              fontSize: '11px',
              fontWeight: '600',
            },
            position: 'right',
          },
        },
      ],
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val: number) => `${val.toFixed(1)}% accuracy`,
      },
    },
    markers: { size: 3, strokeWidth: 0 },
    legend: { show: false },
  };

  const avgAccuracy =
    data.accuracy.length > 0
      ? (data.accuracy.reduce((a, b) => a + b, 0) / data.accuracy.length).toFixed(1)
      : '—';

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-3">
        <span className="text-xs text-text-muted">Directional Accuracy Over Time</span>
        <div className="text-right">
          <span className="text-sm font-bold tabular-nums" style={{ color: CHART_COLORS.bullish }}>
            {avgAccuracy}%
          </span>
          <span className="text-xs text-text-muted ml-1">avg</span>
        </div>
      </div>
      <Chart
        options={options}
        series={[{ name: 'Accuracy', data: data.accuracy }]}
        type="area"
        height={height}
      />
    </div>
  );
}
