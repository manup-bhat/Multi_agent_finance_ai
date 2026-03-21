'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPct } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

export interface ShapChartProps {
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
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/predict`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker: ticker || 'NIFTY', horizon: 5 }),
          }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        const shapRaw: { feature: string; value: number }[] = json.shap_values || [];
        if (!shapRaw.length) throw new Error('No SHAP values in response');
        // Sort by |value| descending, take top 8
        const sorted = [...shapRaw].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 8);
        setData({ features: sorted.map((s) => s.feature), importance: sorted.map((s) => s.value) });
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
