'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import('apexcharts/area');

export interface MacroAreaChartProps {
  title: string;
  dataKey: string;
  color: string;
  unit: string;
  height?: number;
  showThreshold?: { value: number; label: string };
}

export function MacroAreaChart({
  title,
  dataKey,
  color,
  unit,
  height = 180,
  showThreshold,
}: MacroAreaChartProps) {
  const [series, setSeries] = useState<any[]>([]);
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
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/macro/india-cues`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        const history = json.history || json;
        const raw: { date: string; value: number }[] = Array.isArray(history[dataKey])
          ? history[dataKey]
          : [];

        setSeries([
          {
            name: title,
            data: raw.map((d) => ({ x: d.date, y: d.value })),
          },
        ]);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [dataKey, title, retryCount]);

  if (loading) return <ChartSkeleton height={height} />;

  if (error || !series[0]?.data?.length) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-4 text-center space-y-1">
        <p className="text-bearish-red font-medium text-sm">Failed to load {title}</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button onClick={() => setRetryCount(c => c + 1)} className="text-xs text-saffron underline">Retry</button>
      </div>
    );
  }

  const annotations: any = { yaxis: [] };
  if (showThreshold) {
    annotations.yaxis.push({
      y: showThreshold.value,
      borderColor: color,
      strokeDashArray: 4,
      label: {
        text: showThreshold.label,
        style: { color, background: chartTheme.tooltipBg, fontSize: '10px' },
      },
    });
  }

  const options: any = {
    chart: {
      type: 'area',
      toolbar: { show: false },
      background: 'transparent',
      sparkline: { enabled: false },
      animations: { enabled: true, speed: 500 },
    },
    stroke: { curve: 'smooth', width: 2, colors: [color] },
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'dark',
        type: 'vertical',
        opacityFrom: 0.25,
        opacityTo: 0.02,
        colorStops: [
          { offset: 0, color, opacity: 0.25 },
          { offset: 100, color, opacity: 0.02 },
        ],
      },
    },
    colors: [color],
    xaxis: {
      type: 'datetime',
      labels: { style: { colors: chartTheme.text, fontSize: '10px' }, datetimeFormatter: { month: 'MMM yy' } },
      axisBorder: { color: chartTheme.grid },
      axisTicks: { color: chartTheme.grid },
    },
    yaxis: {
      labels: {
        style: { colors: chartTheme.text, fontSize: '10px' },
        formatter: (val: number) => `${unit}${val.toLocaleString('en-IN', { maximumFractionDigits: 1 })}`,
      },
    },
    annotations,
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3 },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      y: { formatter: (val: number) => `${unit}${val.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` },
      x: { format: 'dd MMM yyyy' },
    },
    markers: { size: 0 },
  };

  return (
    <div className="w-full">
      <Chart type="area" series={series} options={options} height={height} />
    </div>
  );
}
