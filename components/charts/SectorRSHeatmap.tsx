'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import 'apexcharts/features/legend';

export interface SectorRSHeatmapProps {
  ticker?: string;
}

const SECTORS = ['IT', 'Finance', 'Pharma', 'Energy', 'Utilities', 'Realty', 'Consumer', 'Industrial', 'Metals', 'Auto'];
const RS_PERIODS = ['6M RS', '3M RS', '1M RS', '1W RS', '5D RS'];

export function SectorRSHeatmap({ ticker }: SectorRSHeatmapProps) {
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

        const sectorRS = json.sector_rs || json.sector_performance || {};
        // API returns: { sector_name: { rs_6m, rs_3m, rs_1m, rs_1w, rs_5d } }
        const sectors = Object.keys(sectorRS).length ? Object.keys(sectorRS) : SECTORS;
        const realData = RS_PERIODS.map((period, idx) => {
          const key = ['rs_6m', 'rs_3m', 'rs_1m', 'rs_1w', 'rs_5d'][idx];
          return {
            name: period,
            data: sectors.map((s) => sectorRS[s]?.[key] ?? sectorRS[s] ?? 0),
          };
        });
        setData(realData.length ? realData : null);
        if (!realData.length) throw new Error('No sector RS data in response');
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
        <p className="text-bearish-red font-medium">Failed to load sector heatmap</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  // Transform data for heatmap
  const heatmapSeries = RS_PERIODS.map((period, idx) => ({
    name: period,
    data: SECTORS.map((sector, sectorIdx) => ({
      x: sector,
      y: data[idx]?.data[sectorIdx] || 0,
    })),
  }));

  const options: any = {
    chart: { type: 'heatmap', toolbar: { show: false }, background: chartTheme.bg },
    dataLabels: {
      enabled: true,
      style: {
        fontSize: '11px',
        colors: ['#fff'],
      },
      formatter: (val: number) => `${val.toFixed(1)}%`,
    },
    plotOptions: {
      heatmap: {
        colorScale: {
          ranges: [
            { from: -10, to: -3, name: 'Strong Underperform', color: '#7F1D1D' },
            { from: -3, to: -1, name: 'Underperform', color: '#DC2626' },
            { from: -1, to: 0, name: 'Slight Under', color: '#F97316' },
            { from: 0, to: 1, name: 'Slight Over', color: '#84CC16' },
            { from: 1, to: 3, name: 'Outperform', color: '#059669' },
            { from: 3, to: 10, name: 'Strong Outperform', color: '#065F46' },
          ],
        },
      },
    },
    xaxis: {
      categories: SECTORS,
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      labels: { style: { colors: chartTheme.text } },
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
    legend: { labels: { colors: chartTheme.text } },
  };

  return (
    <div className="w-full space-y-4">
      <Chart type="heatmap" series={heatmapSeries} options={options} height={280} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Sector Relative Strength:</strong> Shows how each sector is performing relative to Nifty50. Green = outperforming. Red = underperforming. Used to identify leading/lagging sectors.
      </div>
    </div>
  );
}
