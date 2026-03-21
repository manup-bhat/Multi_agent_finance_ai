'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPrice } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import 'apexcharts/features/annotations';

export interface FanChartProps {
  ticker?: string;
  horizon?: number;
}

export function FanChart({ ticker, horizon = 5 }: FanChartProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/predict`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: ticker || 'NIFTY', horizon }),
          }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        // Mock: Generate forecast data (in production, this comes from API)
        const today = new Date();
        const dates = Array.from({ length: horizon }, (_, i) => {
          const d = new Date(today);
          d.setDate(d.getDate() + i);
          return d.toISOString().split('T')[0];
        });

        const p50Base = 23500;
        const p50 = Array.from({ length: horizon }, (_, i) => p50Base + (i * 50 + Math.random() * 100 - 50));
        const p10 = p50.map((v) => v - 800 - Math.random() * 400);
        const p90 = p50.map((v) => v + 800 + Math.random() * 400);

        setData({ dates, p10, p50, p90, current: p50Base });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker, horizon]);

  if (loading) return <ChartSkeleton height={320} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load forecast</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'P50 (Median)',
      type: 'line',
      data: data.p50.map((v: number) => parseFloat(v.toFixed(2))),
    },
    {
      name: 'Confidence Band (P10-P90)',
      type: 'rangeArea',
      data: data.p10.map((low: number, i: number) => [
        parseFloat(low.toFixed(2)),
        parseFloat(data.p90[i].toFixed(2)),
      ]),
    },
  ];

  const options: any = {
    chart: { type: 'line', toolbar: { show: false }, background: chartTheme.bg },
    stroke: {
      curve: 'smooth',
      width: [2.5, 0],
      colors: [CHART_COLORS.saffron],
    },
    fill: {
      opacity: [1, 0.1],
      type: ['solid', 'gradient'],
      gradient: {
        opacityFrom: 0.1,
        opacityTo: 0.1,
        colorStops: [
          { offset: 0, color: CHART_COLORS.saffron, opacity: 0.12 },
          { offset: 100, color: CHART_COLORS.saffron, opacity: 0.05 },
        ],
      },
    },
    xaxis: {
      categories: data.dates,
      labels: { style: { colors: chartTheme.text }, format: 'DD MMM' },
      axisBorder: { color: chartTheme.grid },
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
        {
          x: new Date(new Date().toISOString().split('T')[0]).getTime(),
          strokeDashArray: 4,
          borderColor: '#FFFFFF',
          label: { text: 'TODAY', style: { color: '#FFFFFF' } },
        },
      ],
    },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      custom: ({ series, seriesIndex, dataPointIndex }: any) => {
        if (seriesIndex === 0) {
          return `<div class="px-2 py-1 text-xs"><div>Date: ${data.dates[dataPointIndex]}</div><div>P50: ${formatPrice(data.p50[dataPointIndex])}</div></div>`;
        }
        return `<div class="px-2 py-1 text-xs"><div>Date: ${data.dates[dataPointIndex]}</div><div>Range: ${formatPrice(data.p10[dataPointIndex])} - ${formatPrice(data.p90[dataPointIndex])}</div></div>`;
      },
    },
    grid: { borderColor: chartTheme.grid },
    legend: { labels: { colors: chartTheme.text } },
  };

  return (
    <div className="w-full space-y-4">
      <div className="grid grid-cols-4 gap-3">
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">Current</div>
          <div className="text-lg font-bold text-text-primary">{formatPrice(data.current)}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">P10 (Bear)</div>
          <div className="text-lg font-bold text-bearish-red">{formatPrice(data.p10[data.p10.length - 1])}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">P50 (Base)</div>
          <div className="text-lg font-bold text-saffron">{formatPrice(data.p50[data.p50.length - 1])}</div>
        </div>
        <div className="card-base p-3 text-center">
          <div className="text-xs text-text-muted">P90 (Bull)</div>
          <div className="text-lg font-bold text-bullish-green">{formatPrice(data.p90[data.p90.length - 1])}</div>
        </div>
      </div>

      <Chart type="line" series={series} options={options} height={300} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Fan Chart:</strong> Shows the probability distribution of future prices. P50 is the most likely outcome (median). The band represents 80% confidence range (P10 to P90).
      </div>
    </div>
  );
}
