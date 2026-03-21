'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPrice } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

interface PayoffChartProps {
  ticker?: string;
}

export function PayoffChart({ ticker = 'NIFTY' }: PayoffChartProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Mock: Generate options payoff diagram
        const currentPrice = 23500;
        const strikeCall = 23500;
        const strikePut = 23200;
        const premiumCall = 150;
        const premiumPut = 100;

        const prices = Array.from({ length: 41 }, (_, i) => currentPrice - 1000 + i * 100);
        const callPayoff = prices.map((p) => Math.max(p - strikeCall - premiumCall, -premiumCall));
        const putPayoff = prices.map((p) => Math.max(strikePut - p - premiumPut, -premiumPut));
        const strategyPayoff = prices.map((p, i) => callPayoff[i] + putPayoff[i]);

        setData({ prices, callPayoff, putPayoff, strategyPayoff, currentPrice, strikeCall, strikePut });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (loading) return <ChartSkeleton height={320} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load payoff diagram</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'Call',
      data: data.callPayoff,
    },
    {
      name: 'Put',
      data: data.putPayoff,
    },
    {
      name: 'Strategy',
      data: data.strategyPayoff,
    },
  ];

  const options: any = {
    chart: { type: 'area', toolbar: { show: false }, background: chartTheme.bg },
    stroke: {
      curve: 'smooth',
      width: [1.5, 1.5, 2.5],
      colors: [CHART_COLORS.neutral, CHART_COLORS.warning, CHART_COLORS.saffron],
    },
    fill: {
      type: 'gradient',
      opacity: [0.1, 0.1, 0.15],
    },
    xaxis: {
      categories: data.prices.map((p: number) => formatPrice(p)),
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => formatPrice(val),
        style: { colors: chartTheme.text },
      },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      xaxis: [
        { x: formatPrice(data.currentPrice), borderColor: CHART_COLORS.saffron, label: { text: 'Current', style: { color: CHART_COLORS.saffron } } },
      ],
      yaxis: [{ y: 0, borderColor: chartTheme.grid, strokeDashArray: 4 }],
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
    legend: { labels: { colors: chartTheme.text } },
  };

  const maxProfit = Math.max(...data.strategyPayoff);
  const maxLoss = Math.min(...data.strategyPayoff);
  const breakeven = data.prices.find((p: number, i: number) => Math.abs(data.strategyPayoff[i]) < 100);

  return (
    <div className="w-full space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">Max Profit</div>
          <div className={`text-lg font-bold ${maxProfit > 0 ? 'text-bullish-green' : 'text-bearish-red'}`}>{formatPrice(maxProfit)}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">Max Loss</div>
          <div className={`text-lg font-bold ${maxLoss < 0 ? 'text-bearish-red' : 'text-bullish-green'}`}>{formatPrice(maxLoss)}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">Breakeven</div>
          <div className="text-lg font-bold text-neutral-blue">{formatPrice(breakeven || data.currentPrice)}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">Current</div>
          <div className="text-lg font-bold text-saffron">{formatPrice(data.currentPrice)}</div>
        </div>
      </div>

      <Chart type="area" series={series} options={options} height={280} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Options Payoff:</strong> Shows profit/loss across price levels at expiration. Strategy = Long Call + Long Put (straddle). Profit if stock moves significantly; loss if stays flat.
      </div>
    </div>
  );
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
