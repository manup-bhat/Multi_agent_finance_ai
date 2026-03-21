'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import('apexcharts/bar');

export interface CompositeSentimentBarProps {
  ticker?: string;
}

const WEIGHTS: Record<string, string> = {
  GDELT: '20%',
  'Social F/G': '25%',
  'India FinBERT': '20%',
  Institutional: '35%',
};

export function CompositeSentimentBar({ ticker }: CompositeSentimentBarProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analyze`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: ticker || 'NIFTY', horizon: 5, include_fno: false }),
          }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        const cs = json.composite_sentiment || {};
        setData({
          gdelt: cs.gdelt ?? 0,
          social: cs.social ?? 0,
          finbert: cs.finbert ?? 0,
          institutional: cs.institutional ?? 0,
          composite: cs.composite ?? 0,
        });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [ticker, retryCount]);

  if (loading) return <ChartSkeleton height={220} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load composite sentiment</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button onClick={() => setRetryCount(c => c + 1)} className="text-xs text-saffron underline mt-1">Retry</button>
      </div>
    );
  }

  const categories = ['GDELT', 'Social F/G', 'India FinBERT', 'Institutional'];
  const values = [data.gdelt, data.social, data.finbert, data.institutional];
  const barColors = values.map((v: number) =>
    v > 0.2 ? CHART_COLORS.bullish : v < -0.2 ? CHART_COLORS.bearish : '#94A3B8'
  );

  const options: any = {
    chart: {
      type: 'bar',
      toolbar: { show: false },
      background: 'transparent',
      animations: { enabled: true, speed: 500 },
    },
    plotOptions: {
      bar: {
        horizontal: true,
        barHeight: '55%',
        borderRadius: 4,
        distributed: true,
        dataLabels: { position: 'right' },
      },
    },
    colors: barColors,
    dataLabels: {
      enabled: true,
      formatter: (val: number) => val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2),
      style: { fontSize: '11px', fontWeight: '700', colors: [chartTheme.text] },
      offsetX: 6,
    },
    xaxis: {
      categories,
      min: -1,
      max: 1,
      labels: { style: { colors: chartTheme.text, fontSize: '12px' } },
      axisBorder: { color: chartTheme.grid },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: {
        style: { colors: chartTheme.text, fontSize: '12px' },
        formatter: (val: string) => {
          const weight = WEIGHTS[val] || '';
          return weight ? `${val} (${weight})` : val;
        },
      },
    },
    annotations: {
      xaxis: [
        {
          x: 0,
          borderColor: chartTheme.grid,
          strokeDashArray: 3,
          borderWidth: 1.5,
        },
        {
          x: 0.2,
          borderColor: CHART_COLORS.bullish,
          strokeDashArray: 4,
          opacity: 0.4,
          borderWidth: 1,
        },
        {
          x: -0.2,
          borderColor: CHART_COLORS.bearish,
          strokeDashArray: 4,
          opacity: 0.4,
          borderWidth: 1,
        },
      ],
    },
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3, xaxis: { lines: { show: true } } },
    legend: { show: false },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      y: {
        formatter: (val: number) => {
          const zone = val > 0.2 ? 'Bullish' : val < -0.2 ? 'Bearish' : 'Neutral';
          return `${val > 0 ? '+' : ''}${val.toFixed(3)} (${zone})`;
        },
      },
    },
  };

  return (
    <div className="w-full space-y-3">
      {/* Composite score badge */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted">Composite Score:</span>
        <span
          className="text-sm font-bold px-2 py-0.5 rounded"
          style={{
            color: data.composite > 0.2 ? CHART_COLORS.bullish : data.composite < -0.2 ? CHART_COLORS.bearish : '#94A3B8',
          }}
        >
          {data.composite > 0 ? '+' : ''}{data.composite.toFixed(3)}
        </span>
        <span className="text-xs text-text-muted">
          {data.composite > 0.2 ? '● BULLISH' : data.composite < -0.2 ? '● BEARISH' : '● NEUTRAL'}
        </span>
      </div>
      <Chart type="bar" series={[{ name: 'Score', data: values }]} options={options} height={200} />
    </div>
  );
}
