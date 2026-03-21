'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';
import { formatCrore, formatPct } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={320} />,
});

export interface EquityCurveChartProps {
  data: {
    dates: string[];
    strategy: number[];
    benchmark?: number[];
    drawdown?: number[];
    foldBoundaries?: string[];
  };
  height?: number;
}

export function EquityCurveChart({ data, height = 280 }: EquityCurveChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.dates.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No backtest data available
      </div>
    );
  }

  const minDrawdown = data.drawdown ? Math.min(...data.drawdown) : 0;

  const equityOptions: ApexCharts.ApexOptions = {
    chart: {
      id: 'equity-chart',
      group: 'equityCurve',
      type: 'area',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
      zoom: { enabled: true },
    },
    stroke: {
      curve: 'smooth',
      width: [2.5, 1.5],
      dashArray: [0, 5],
    },
    fill: {
      type: 'gradient',
      gradient: {
        shade: isDark ? 'dark' : 'light',
        type: 'vertical',
        opacityFrom: 0.35,
        opacityTo: 0.02,
        colorStops: [
          [
            { offset: 0, color: CHART_COLORS.saffron, opacity: 0.3 },
            { offset: 100, color: CHART_COLORS.saffron, opacity: 0 },
          ],
          [
            { offset: 0, color: '#94A3B8', opacity: 0 },
            { offset: 100, color: '#94A3B8', opacity: 0 },
          ],
        ],
      },
    },
    colors: [CHART_COLORS.saffron, '#94A3B8'],
    xaxis: {
      categories: data.dates,
      type: 'datetime',
      labels: { show: false },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: chartTheme.text, fontSize: '10px' },
        formatter: (val: number) => `${val.toFixed(1)}%`,
      },
    },
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
      padding: { bottom: 0 },
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
    markers: { size: 0 },
  };

  const drawdownOptions: ApexCharts.ApexOptions = {
    chart: {
      id: 'drawdown-chart',
      group: 'equityCurve',
      type: 'area',
      toolbar: { show: false },
      animations: { enabled: false },
      zoom: { enabled: true },
    },
    stroke: { curve: 'stepline', width: 1, colors: [CHART_COLORS.bearish] },
    fill: { colors: ['#FEF2F2'], type: 'solid', opacity: 0.7 },
    colors: [CHART_COLORS.bearish],
    xaxis: {
      categories: data.dates,
      type: 'datetime',
      labels: { style: { colors: chartTheme.text, fontSize: '10px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      max: 0,
      labels: {
        style: { colors: chartTheme.text, fontSize: '10px' },
        formatter: (val: number) => `${val.toFixed(1)}%`,
      },
    },
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3 },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: { formatter: (val: number) => `DD: ${val.toFixed(2)}%` },
    },
    legend: { show: false },
    annotations: {
      yaxis: [
        {
          y: minDrawdown,
          borderColor: CHART_COLORS.bearish,
          label: {
            text: `Max DD: ${minDrawdown.toFixed(2)}%`,
            style: { color: '#fff', background: CHART_COLORS.bearish, fontSize: '10px' },
          },
        },
      ],
    },
    markers: { size: 0 },
  };

  const equitySeries = [
    { name: 'Strategy', data: data.strategy },
    ...(data.benchmark ? [{ name: 'Nifty TRI', data: data.benchmark }] : []),
  ];

  const drawdownSeries = [{ name: 'Drawdown', data: data.drawdown || [] }];

  return (
    <div className="w-full">
      <Chart
        options={equityOptions}
        series={equitySeries}
        type="area"
        height={height}
      />
      {data.drawdown && data.drawdown.length > 0 && (
        <Chart
          options={drawdownOptions}
          series={drawdownSeries}
          type="area"
          height={100}
        />
      )}
    </div>
  );
}
