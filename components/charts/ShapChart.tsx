'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPct } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

interface ShapChartProps {
  ticker?: string;
}

export function ShapChart({ ticker = 'NIFTY' }: ShapChartProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Mock: Generate SHAP feature importance
        const features = ['RSI(14)', 'EMA_20/50 Ratio', 'MACD Hist', 'Volume Momentum', 'VIX Level', 'FII Flow', 'PCR Ratio', 'ATR %'];
        const importance = [0.28, 0.22, 0.15, 0.12, 0.10, -0.08, 0.07, 0.06];

        setData({ features, importance });
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
        <p className="text-bearish-red font-medium">Failed to load SHAP values</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'Feature Importance',
      data: data.importance,
    },
  ];

  const options: any = {
    chart: { type: 'bar', toolbar: { show: false }, background: chartTheme.bg },
    plotOptions: {
      bar: {
        horizontal: true,
        borderRadius: 4,
        barHeight: '60%',
        colors: {
          ranges: data.importance.map((val: number) => ({
            from: val,
            to: val,
            color: val > 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish,
          })),
        },
        dataLabels: { position: 'right' },
      },
    },
    dataLabels: {
      enabled: true,
      formatter: (val: number) => formatPct(val * 100, 1),
      offsetX: 10,
      style: { fontSize: '11px', colors: [chartTheme.text] },
    },
    xaxis: {
      categories: data.features,
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: { style: { colors: chartTheme.text } },
    },
    annotations: {
      xaxis: [{ x: 0, borderColor: chartTheme.grid }],
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
  };

  return (
    <div className="w-full space-y-4">
      <Chart type="bar" series={series} options={options} height={300} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>SHAP Feature Importance:</strong> Shows which technical indicators have the most influence on the model's prediction. Positive = bullish impact, Negative = bearish impact.
      </div>
    </div>
  );
}
