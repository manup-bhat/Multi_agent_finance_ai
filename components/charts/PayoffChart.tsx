'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={280} />,
});

export interface PayoffChartProps {
  data: {
    prices: number[];       // X axis: underlying prices at expiry
    pnl: number[];          // Y axis: P&L at each price
    currentPrice?: number;
    breakevens?: number[];
    maxProfit?: number;
    maxLoss?: number;
    strategyName?: string;
  };
  height?: number;
}

export function PayoffChart({ data, height = 280 }: PayoffChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.prices.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No strategy data available
      </div>
    );
  }

  // Split into profit (green) and loss (red) zones
  const profitData = data.prices.map((price, i) => ({
    x: price,
    y: data.pnl[i] >= 0 ? data.pnl[i] : 0,
  }));
  const lossData = data.prices.map((price, i) => ({
    x: price,
    y: data.pnl[i] < 0 ? data.pnl[i] : 0,
  }));

  const annotations: ApexCharts.ApexOptions['annotations'] = {
    xaxis: [
      ...(data.currentPrice
        ? [
            {
              x: data.currentPrice,
              borderColor: CHART_COLORS.saffron,
              strokeDashArray: 0,
              borderWidth: 2,
              label: {
                text: `CMP ₹${data.currentPrice.toLocaleString('en-IN')}`,
                style: { color: '#fff', background: CHART_COLORS.saffron, fontSize: '10px', fontWeight: '600' },
              },
            },
          ]
        : []),
      ...(data.breakevens || []).map((be, i) => ({
        x: be,
        borderColor: CHART_COLORS.warning,
        strokeDashArray: 4,
        label: {
          text: `BE${i + 1}: ₹${be.toLocaleString('en-IN')}`,
          style: { color: CHART_COLORS.warning, background: chartTheme.tooltipBg, fontSize: '10px' },
        },
      })),
    ],
    yaxis: [
      {
        y: 0,
        borderColor: chartTheme.grid,
        strokeDashArray: 0,
        borderWidth: 1,
      },
    ],
  };

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'area',
      toolbar: { show: false },
      animations: { enabled: true, speed: 400 },
      stacked: false,
    },
    stroke: { curve: 'straight', width: 2 },
    fill: { type: 'solid', opacity: 0.3 },
    colors: [CHART_COLORS.bullish, CHART_COLORS.bearish],
    xaxis: {
      type: 'numeric',
      title: { text: 'Underlying Price at Expiry (₹)', style: { color: chartTheme.text, fontSize: '11px' } },
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: string) => `₹${Number(val).toLocaleString('en-IN')}`,
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      title: { text: 'P&L (₹)', style: { color: chartTheme.text, fontSize: '11px' } },
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (val: number) => (val >= 0 ? `+₹${val.toLocaleString('en-IN')}` : `-₹${Math.abs(val).toLocaleString('en-IN')}`),
      },
    },
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3 },
    annotations,
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val: number) =>
          val >= 0 ? `+₹${val.toLocaleString('en-IN')}` : `-₹${Math.abs(val).toLocaleString('en-IN')}`,
      },
    },
    legend: { show: false },
    markers: { size: 0 },
  };

  return (
    <div className="w-full space-y-3">
      <Chart
        options={options}
        series={[
          { name: 'Profit Zone', data: profitData },
          { name: 'Loss Zone', data: lossData },
        ]}
        type="area"
        height={height}
      />

      {/* Strategy metrics */}
      {(data.maxProfit !== undefined || data.maxLoss !== undefined || data.breakevens) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {data.maxProfit !== undefined && (
            <div className="rounded-card p-3 bg-bullish-bg/30 border border-bullish-green/30">
              <p className="text-xs text-text-muted">Max Profit</p>
              <p className="text-sm font-bold text-bullish-green tabular-nums">
                {data.maxProfit === Infinity ? 'Unlimited' : `+₹${data.maxProfit.toLocaleString('en-IN')}`}
              </p>
            </div>
          )}
          {data.maxLoss !== undefined && (
            <div className="rounded-card p-3 bg-bearish-bg/30 border border-bearish-red/30">
              <p className="text-xs text-text-muted">Max Loss</p>
              <p className="text-sm font-bold text-bearish-red tabular-nums">
                {data.maxLoss === -Infinity ? 'Unlimited' : `-₹${Math.abs(data.maxLoss).toLocaleString('en-IN')}`}
              </p>
            </div>
          )}
          {(data.breakevens || []).map((be, i) => (
            <div key={i} className="rounded-card p-3 bg-warning-bg/30 border border-warning-amber/30">
              <p className="text-xs text-text-muted">Breakeven {i + 1}</p>
              <p className="text-sm font-bold text-warning-amber tabular-nums">
                ₹{be.toLocaleString('en-IN')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
