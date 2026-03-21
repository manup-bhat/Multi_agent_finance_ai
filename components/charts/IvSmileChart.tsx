'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={280} />,
});

export interface IvSmileChartProps {
  data: {
    strikes: number[];
    currentIv: number[];     // Current IV values (%)
    avgIv30d?: number[];     // 30-day average IV values (%)
    atmStrike?: number;      // ATM strike price
  };
  height?: number;
}

export function IvSmileChart({ data, height = 280 }: IvSmileChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.strikes.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No IV data available — run F&O analysis first
      </div>
    );
  }

  const atmAnnotation = data.atmStrike
    ? [
        {
          x: data.atmStrike,
          borderColor: CHART_COLORS.saffron,
          strokeDashArray: 4,
          borderWidth: 2,
          label: {
            text: `ATM ₹${data.atmStrike.toLocaleString('en-IN')}`,
            style: {
              color: '#fff',
              background: CHART_COLORS.saffron,
              fontSize: '11px',
              fontWeight: '700',
            },
          },
        },
      ]
    : [];

  const series: ApexCharts.ApexOptions['series'] = [
    {
      name: 'Current IV',
      data: data.currentIv.map((iv, i) => ({ x: data.strikes[i], y: +iv.toFixed(2) })),
    },
    ...(data.avgIv30d
      ? [
          {
            name: 'Avg IV 30d',
            data: data.avgIv30d.map((iv, i) => ({ x: data.strikes[i], y: +iv.toFixed(2) })),
          },
        ]
      : []),
  ];

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'line',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
    },
    stroke: {
      width: [2.5, 1.5],
      dashArray: [0, 5],
      curve: 'smooth',
    },
    colors: [CHART_COLORS.saffron, '#94A3B8'],
    markers: { size: [4, 0], strokeWidth: 0 },
    xaxis: {
      type: 'numeric' as const,
      title: {
        text: 'Strike Price (₹)',
        style: { color: chartTheme.text, fontSize: '11px' },
      },
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: string) => `₹${Number(val).toLocaleString('en-IN')}`,
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      title: { text: 'IV (%)', style: { color: chartTheme.text, fontSize: '11px' } },
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: number) => `${val.toFixed(1)}%`,
      },
    },
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
    },
    annotations: {
      xaxis: atmAnnotation,
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      shared: true,
      y: { formatter: (val: number) => `${val.toFixed(2)}%` },
    },
    legend: {
      position: 'top',
      horizontalAlign: 'right',
      labels: { colors: chartTheme.text },
    },
  };

  return (
    <div className="w-full">
      <Chart options={options} series={series} type="line" height={height} />
    </div>
  );
}
