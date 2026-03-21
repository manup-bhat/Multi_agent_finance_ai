'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

export interface IvSmileChartProps {
  ticker?: string;
}

export function IvSmileChart({ ticker = 'NIFTY' }: IvSmileChartProps) {
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
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/fno/analyze`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: ticker }),
          }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        // Mock: Generate IV smile (in production, this comes from API)
        const strikes = Array.from({ length: 11 }, (_, i) => 23000 + (i - 5) * 500);
        const atmStrike = 23000;
        const currentIV = Array.from({ length: 11 }, (_, i) => {
          const distance = Math.abs(strikes[i] - atmStrike) / atmStrike;
          return 18 + distance * distance * 100;
        });
        const avgIV = Array.from({ length: 11 }, () => 16 + Math.random() * 4);

        setData({ strikes, currentIV, avgIV, atmStrike });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (loading) return <ChartSkeleton height={300} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load IV smile</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'Current IV',
      type: 'line',
      data: data.currentIV,
    },
    {
      name: 'Avg IV 30d',
      type: 'line',
      data: data.avgIV,
    },
  ];

  const options: any = {
    chart: { type: 'line', toolbar: { show: false }, background: chartTheme.bg },
    stroke: {
      curve: 'smooth',
      width: [2.5, 1.5],
      dashArray: [0, 5],
      colors: [CHART_COLORS.saffron, '#94A3B8'],
    },
    fill: {
      type: ['solid', 'gradient'],
      opacity: [1, 0.3],
      gradient: {
        opacityFrom: 0.3,
        opacityTo: 0.05,
        colorStops: [
          { offset: 0, color: CHART_COLORS.saffron, opacity: 0.15 },
          { offset: 100, color: CHART_COLORS.saffron, opacity: 0.05 },
        ],
      },
    },
    xaxis: {
      categories: data.strikes.map((s: number) => `₹${s}`),
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => `${val.toFixed(1)}%`,
        style: { colors: chartTheme.text },
      },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      xaxis: [
        {
          x: `₹${data.atmStrike}`,
          strokeDashArray: 4,
          borderColor: CHART_COLORS.saffron,
          label: { text: `ATM ₹${data.atmStrike}`, style: { color: CHART_COLORS.saffron, background: 'transparent' } },
        },
      ],
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
    legend: { labels: { colors: chartTheme.text } },
  };

  return (
    <div className="w-full space-y-4">
      <Chart type="line" series={series} options={options} height={300} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>IV Smile:</strong> Shows implied volatility across different strike prices. The U-shaped "smile" is typical. Current IV above average suggests elevated uncertainty. Useful for assessing skew risk.
      </div>
    </div>
  );
}
