'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import('apexcharts/bar');

export interface ErrorHistogramProps {
  errors?: number[];
}

function binErrors(errors: number[], bins = 20): { x: number; y: number }[] {
  if (!errors.length) return [];
  const min = Math.min(...errors);
  const max = Math.max(...errors);
  const step = (max - min) / bins || 0.01;
  const buckets = Array.from({ length: bins }, (_, i) => ({
    x: parseFloat((min + i * step + step / 2).toFixed(3)),
    y: 0,
  }));
  errors.forEach((e) => {
    const idx = Math.min(Math.floor((e - min) / step), bins - 1);
    buckets[idx].y += 1;
  });
  return buckets;
}

export function ErrorHistogram({ errors: externalErrors }: ErrorHistogramProps) {
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
        if (externalErrors && externalErrors.length > 0) {
          setData(externalErrors);
          return;
        }
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/model-performance`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        setData(json.prediction_errors || []);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [externalErrors, retryCount]);

  if (loading) return <ChartSkeleton height={240} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load error distribution</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button onClick={() => setRetryCount(c => c + 1)} className="text-xs text-saffron underline mt-1">Retry</button>
      </div>
    );
  }

  const bins = binErrors(data, 20);
  const mean = data.length > 0 ? data.reduce((a: number, b: number) => a + b, 0) / data.length : 0;

  const seriesData = bins.map((b) => b.y);
  const categories = bins.map((b) => `${b.x > 0 ? '+' : ''}${(b.x * 100).toFixed(1)}%`);
  const barColors = bins.map((b) =>
    b.x < -0.005 ? CHART_COLORS.bearish : b.x > 0.005 ? CHART_COLORS.neutral : CHART_COLORS.bullish
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
        columnWidth: '95%',
        borderRadius: 0,
        distributed: true,
      },
    },
    colors: barColors,
    xaxis: {
      categories,
      labels: {
        style: { colors: chartTheme.text, fontSize: '10px' },
        rotate: -45,
      },
      axisBorder: { color: chartTheme.grid },
    },
    yaxis: {
      title: { text: 'Count', style: { color: chartTheme.text, fontSize: '11px' } },
      labels: { style: { colors: chartTheme.text } },
    },
    annotations: {
      xaxis: [
        {
          x: `${(0).toFixed(1)}%`,
          borderColor: chartTheme.text,
          strokeDashArray: 3,
          label: {
            text: 'Zero Error',
            style: { color: chartTheme.text, background: chartTheme.tooltipBg, fontSize: '10px' },
          },
        },
        {
          x: `${mean > 0 ? '+' : ''}${(mean * 100).toFixed(1)}%`,
          borderColor: CHART_COLORS.warning,
          strokeDashArray: 4,
          label: {
            text: `Mean: ${mean > 0 ? '+' : ''}${(mean * 100).toFixed(2)}%`,
            style: { color: CHART_COLORS.warning, background: chartTheme.tooltipBg, fontSize: '10px' },
          },
        },
      ],
    },
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3 },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      y: { formatter: (val: number) => `${val} predictions` },
    },
  };

  return (
    <div className="w-full">
      <Chart type="bar" series={[{ name: 'Count', data: seriesData }]} options={options} height={240} />
      <p className="text-xs text-text-muted text-center mt-1">
        Distribution of {data.length} prediction errors • Mean: {mean > 0 ? '+' : ''}{(mean * 100).toFixed(2)}%
      </p>
    </div>
  );
}
