'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import('apexcharts/donut');

export interface SentimentPieChartProps {
  ticker?: string;
}

export function SentimentPieChart({ ticker }: SentimentPieChartProps) {
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

        const sentiment = json.sentiment_breakdown || {};
        setData({
          positiveNews: sentiment.positive_news ?? 0,
          negativeNews: sentiment.negative_news ?? 0,
          neutralNews: sentiment.neutral_news ?? 0,
          socialBull: sentiment.social_bull ?? 0,
          socialBear: sentiment.social_bear ?? 0,
        });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [ticker, retryCount]);

  if (loading) return <ChartSkeleton height={280} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load sentiment breakdown</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button
          onClick={() => setRetryCount(c => c + 1)}
          className="text-xs text-saffron underline mt-1"
        >
          Retry
        </button>
      </div>
    );
  }

  const labels = ['Positive News', 'Negative News', 'Neutral News', 'Social Bullish', 'Social Bearish'];
  const series = [
    data.positiveNews,
    data.negativeNews,
    data.neutralNews,
    data.socialBull,
    data.socialBear,
  ];
  const colors = [CHART_COLORS.bullish, CHART_COLORS.bearish, '#94A3B8', CHART_COLORS.neutral, '#7C3AED'];

  const options: any = {
    chart: {
      type: 'donut',
      background: 'transparent',
      animations: { enabled: true, speed: 600 },
    },
    labels,
    colors,
    dataLabels: {
      enabled: true,
      formatter: (val: number) => `${val.toFixed(1)}%`,
      style: { fontSize: '11px', fontWeight: '600', colors: ['#fff'] },
      dropShadow: { enabled: false },
    },
    plotOptions: {
      pie: {
        donut: {
          size: '65%',
          labels: {
            show: true,
            total: {
              show: true,
              label: 'Total',
              fontSize: '13px',
              fontWeight: '700',
              color: chartTheme.text,
              formatter: () => `${series.reduce((a, b) => a + b, 0)}`,
            },
          },
        },
      },
    },
    legend: {
      position: 'bottom',
      labels: { colors: chartTheme.text },
      fontSize: '11px',
      markers: { width: 8, height: 8, radius: 2 },
    },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      y: { formatter: (val: number) => `${val.toFixed(1)}%` },
    },
    stroke: { width: 2, colors: [chartTheme.bg === 'transparent' ? '#0f172a' : '#fff'] },
  };

  return (
    <div className="w-full">
      <Chart type="donut" series={series} options={options} height={280} />
    </div>
  );
}
