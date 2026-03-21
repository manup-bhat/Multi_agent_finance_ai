'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

interface SectorRotationChartProps {
  ticker?: string;
}

const SECTORS = ['IT', 'Finance', 'Pharma', 'Energy', 'Utilities', 'Realty', 'Consumer', 'Industrial', 'Metals', 'Auto'];

export function SectorRotationChart({ ticker }: SectorRotationChartProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Mock: Generate sector rotation data
        const mockData = SECTORS.map((sector) => ({
          x: (Math.random() - 0.5) * 10,
          y: (Math.random() - 0.5) * 10,
          z: Math.random() * 200 + 100,
          label: sector.substring(0, 2),
        }));

        setData(mockData);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (loading) return <ChartSkeleton height={400} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load sector rotation</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'Sectors',
      data: data.map((d: any, i: number) => ({
        x: d.x,
        y: d.y,
        z: d.z,
      })),
    },
  ];

  const options: any = {
    chart: { type: 'scatter', toolbar: { show: false }, background: chartTheme.bg },
    plotOptions: {
      scatter: {
        size: 5,
        dataLabels: {
          enabled: true,
          formatter: (val: any, opts: any) => SECTORS[opts.dataPointIndex]?.substring(0, 2) || '',
          style: { fontSize: '12px', fontWeight: 'bold', colors: [chartTheme.text] },
        },
      },
    },
    xaxis: {
      min: -5,
      max: 5,
      title: { text: 'Relative Strength', style: { color: chartTheme.text } },
      labels: { style: { colors: chartTheme.text } },
      axisBorder: { color: chartTheme.grid },
    },
    yaxis: {
      min: -5,
      max: 5,
      title: { text: 'RS Momentum', style: { color: chartTheme.text } },
      labels: { style: { colors: chartTheme.text } },
    },
    colors: [CHART_COLORS.saffron],
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid, xaxis: { lines: { show: true } }, yaxis: { lines: { show: true } } },
    annotations: {
      xaxis: [{ x: 0, borderColor: chartTheme.grid, strokeDashArray: 3 }],
      yaxis: [{ y: 0, borderColor: chartTheme.grid, strokeDashArray: 3 }],
    },
  };

  return (
    <div className="w-full space-y-4">
      <Chart type="scatter" series={series} options={options} height={350} />

      <div className="grid grid-cols-2 gap-4 text-xs">
        <div className="card-base p-3">
          <div className="font-semibold text-bullish-green mb-2">LEADING (Top Right)</div>
          <div className="text-text-secondary">Outperforming + gaining momentum. Best rotation candidates.</div>
        </div>
        <div className="card-base p-3">
          <div className="font-semibold text-neutral-blue mb-2">IMPROVING (Bottom Right)</div>
          <div className="text-text-secondary">Underperforming but momentum turning positive.</div>
        </div>
        <div className="card-base p-3">
          <div className="font-semibold text-bearish-red mb-2">WEAKENING (Top Left)</div>
          <div className="text-text-secondary">Outperforming but momentum deteriorating.</div>
        </div>
        <div className="card-base p-3">
          <div className="font-semibold text-warning mb-2">LAGGING (Bottom Left)</div>
          <div className="text-text-secondary">Underperforming with negative momentum. Avoid.</div>
        </div>
      </div>
    </div>
  );
}
