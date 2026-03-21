'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatCrore } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import 'apexcharts/features/annotations';
import 'apexcharts/features/toolbar';
import 'apexcharts/features/legend';

interface FIIDIIData {
  dates: string[];
  fii: number[];
  dii: number[];
}

interface FiiDiiChartProps {
  days?: number;
}

export function FiiDiiChart({ days = 30 }: FiiDiiChartProps) {
  const [data, setData] = useState<FIIDIIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDays, setSelectedDays] = useState(days);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/fii-dii/latest?days=${selectedDays}`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        const flows: { date: string; fii: number; dii: number }[] = json.flows || json.data || [];
        if (!flows.length) throw new Error('No flow data returned');
        setData({
          dates: flows.map((f) => f.date),
          fii: flows.map((f) => f.fii),
          dii: flows.map((f) => f.dii),
        });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedDays]);

  if (loading) return <ChartSkeleton height={350} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load FII/DII data</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'FII Flow',
      data: data.fii.map((value, i) => ({
        x: data.dates[i],
        y: value,
        fillColor: value >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish,
      })),
    },
    {
      name: 'DII Flow',
      data: data.dii.map((value, i) => ({
        x: data.dates[i],
        y: value,
        fillColor: value >= 0 ? CHART_COLORS.neutral : '#7C3AED',
      })),
    },
  ];

  const options: any = {
    chart: {
      type: 'bar',
      toolbar: { show: false },
      background: chartTheme.bg,
    },
    plotOptions: {
      bar: {
        columnWidth: '60%',
        borderRadius: 3,
        dataLabels: { position: 'top' },
      },
    },
    stroke: { show: true, width: 0, colors: ['transparent'] },
    xaxis: {
      type: 'datetime',
      categories: data.dates,
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: {
        formatter: (val: number) => formatCrore(val, 0),
        style: { colors: chartTheme.text },
      },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      yaxis: [{ y: 0, borderColor: chartTheme.grid, strokeDashArray: 4 }],
    },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      custom: ({ series, seriesIndex, dataPointIndex }: any) => {
        const fii = data.fii[dataPointIndex];
        const dii = data.dii[dataPointIndex];
        const net = fii + dii;
        return `<div class="px-2 py-1 text-xs"><div>Date: ${data.dates[dataPointIndex]}</div><div>FII: ${formatCrore(fii, 0)}</div><div>DII: ${formatCrore(dii, 0)}</div><div>Net: ${formatCrore(net, 0)}</div></div>`;
      },
    },
    grid: { borderColor: chartTheme.grid },
    legend: { labels: { colors: chartTheme.text } },
    fill: { opacity: 1 },
    colors: [CHART_COLORS.bullish, CHART_COLORS.neutral],
  };

  return (
    <div className="w-full space-y-4">
      <div className="flex gap-2 flex-wrap">
        {[10, 30, 60].map((d) => (
          <button
            key={d}
            onClick={() => setSelectedDays(d)}
            className="text-xs px-3 py-1.5 rounded-btn transition-all font-medium"
            style={{
              background: selectedDays === d ? CHART_COLORS.saffron : 'transparent',
              color: selectedDays === d ? '#fff' : chartTheme.text,
              border: `1px solid ${selectedDays === d ? CHART_COLORS.saffron : chartTheme.grid}`,
            }}
          >
            {d}D
          </button>
        ))}
      </div>

      <Chart type="bar" series={series} options={options} height={300} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>FII/DII Flows:</strong> Positive = inflow, Negative = outflow. FII flows often lead market reversals. Heavy FII selling combined with DII buying can signal contrarian strength.
      </div>
    </div>
  );
}
