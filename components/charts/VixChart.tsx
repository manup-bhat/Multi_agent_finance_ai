'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

export interface VixChartProps {
  variant?: 'sparkline' | 'full';
  height?: number;
}

export function VixChart({ variant = 'full', height = 280 }: VixChartProps) {
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
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/macro/india-cues`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        const vixHistory: { date: string; vix: number }[] = json.vix_history || json.india_vix_history || [];
        if (!vixHistory.length) throw new Error('No VIX history data');
        const vixValues = vixHistory.map((v) => v.vix);
        setData({
          dates: vixHistory.map((v) => v.date),
          vix: vixValues,
          current: vixValues[vixValues.length - 1],
        });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <ChartSkeleton height={height} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load VIX data</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const getVixColor = (vix: number) => {
    if (vix < 13) return CHART_COLORS.bullish;
    if (vix < 18) return CHART_COLORS.neutral;
    if (vix < 25) return CHART_COLORS.warning;
    return CHART_COLORS.bearish;
  };

  const getVixRegime = (vix: number) => {
    if (vix < 13) return 'Complacency';
    if (vix < 18) return 'Elevated';
    if (vix < 25) return 'High Fear';
    return 'Crisis';
  };

  const series = [
    {
      name: 'India VIX',
      data: data.vix,
    },
  ];

  if (variant === 'sparkline') {
    const sparklineOptions: any = {
      chart: { type: 'area', sparkline: { enabled: true } },
      stroke: { curve: 'smooth', width: 1.5, colors: [getVixColor(data.current)] },
      fill: {
        type: 'gradient',
        gradient: { opacityFrom: 0.45, opacityTo: 0.05 },
      },
      tooltip: {
        theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
        fixed: { enabled: false },
      },
    };

    return (
      <div className="w-full">
        <Chart type="area" series={series} options={sparklineOptions} height={height} />
      </div>
    );
  }

  // Full variant
  const fullOptions: any = {
    chart: { type: 'area', toolbar: { show: false }, background: chartTheme.bg },
    stroke: { curve: 'smooth', width: 2, colors: [getVixColor(data.current)] },
    fill: {
      type: 'gradient',
      gradient: {
        opacityFrom: 0.1,
        opacityTo: 0.05,
        colorStops:
          data.current < 13
            ? [
                { offset: 0, color: CHART_COLORS.bullish, opacity: 0.08 },
                { offset: 100, color: CHART_COLORS.bullish, opacity: 0.02 },
              ]
            : data.current < 18
            ? [
                { offset: 0, color: CHART_COLORS.neutral, opacity: 0.08 },
                { offset: 100, color: CHART_COLORS.neutral, opacity: 0.02 },
              ]
            : data.current < 25
            ? [
                { offset: 0, color: CHART_COLORS.warning, opacity: 0.08 },
                { offset: 100, color: CHART_COLORS.warning, opacity: 0.02 },
              ]
            : [
                { offset: 0, color: CHART_COLORS.bearish, opacity: 0.08 },
                { offset: 100, color: CHART_COLORS.bearish, opacity: 0.02 },
              ],
      },
    },
    xaxis: {
      type: 'datetime',
      categories: data.dates,
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => val.toFixed(1),
        style: { colors: chartTheme.text },
      },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      yaxis: [
        { y: 13, borderColor: CHART_COLORS.bullish, label: { text: 'Low', style: { color: CHART_COLORS.bullish } } },
        { y: 18, borderColor: CHART_COLORS.neutral, label: { text: 'Normal', style: { color: CHART_COLORS.neutral } } },
        { y: 25, borderColor: CHART_COLORS.warning, label: { text: 'High', style: { color: CHART_COLORS.warning } } },
      ],
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
  };

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-text-muted">India VIX</div>
          <div className="text-3xl font-bold" style={{ color: getVixColor(data.current) }}>
            {data.current.toFixed(1)}
          </div>
          <div className="text-xs font-medium" style={{ color: getVixColor(data.current) }}>
            {getVixRegime(data.current)}
          </div>
        </div>
      </div>

      <Chart type="area" series={series} options={fullOptions} height={height - 80} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>India VIX:</strong> Volatility index measuring market fear. Low VIX (&lt;13) = complacency. High VIX (&gt;25) = fear/crisis. Inverse correlation with stock prices.
      </div>
    </div>
  );
}
