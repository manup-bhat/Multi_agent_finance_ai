'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import 'apexcharts/features/annotations';

interface MarketBreadthData {
  dates: string[];
  niftyPrices: number[];
  above20DMA: number[];
  above50DMA: number[];
  above200DMA: number[];
}

export interface MarketBreadthChartProps {
  ticker?: string;
}

export function MarketBreadthChart({ ticker }: MarketBreadthChartProps) {
  const [data, setData] = useState<MarketBreadthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestReadings, setLatestReadings] = useState<{ above20: number; above50: number; above200: number }>({ above20: 0, above50: 0, above200: 0 });
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

        // Mock: Generate breadth data (in production, this comes from API)
        const mockDates = Array.from({ length: 30 }, (_, i) => {
          const d = new Date();
          d.setDate(d.getDate() - (29 - i));
          return d.toISOString().split('T')[0];
        });

        const mockBreadth = {
          dates: mockDates,
          niftyPrices: Array.from({ length: 30 }, () => 23000 + Math.random() * 1000),
          above20DMA: Array.from({ length: 30 }, () => 40 + Math.random() * 50),
          above50DMA: Array.from({ length: 30 }, () => 30 + Math.random() * 50),
          above200DMA: Array.from({ length: 30 }, () => 20 + Math.random() * 50),
        };

        setData(mockBreadth);
        setLatestReadings({
          above20: mockBreadth.above20DMA[29],
          above50: mockBreadth.above50DMA[29],
          above200: mockBreadth.above200DMA[29],
        });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <ChartSkeleton height={300} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load market breadth</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const niftyOptions: any = {
    chart: { type: 'area', toolbar: { show: false }, background: chartTheme.bg },
    fill: { type: 'gradient', gradient: { opacityFrom: 0.4, opacityTo: 0.05 } },
    stroke: { curve: 'smooth', width: 1.5, colors: [CHART_COLORS.saffron] },
    xaxis: { type: 'datetime', categories: data.dates, labels: { show: false } },
    yaxis: { labels: { style: { colors: chartTheme.text } } },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
  };

  const niftySeries = [
    {
      name: 'Nifty50',
      data: data.niftyPrices,
    },
  ];

  const breadthOptions: any = {
    chart: { type: 'line', toolbar: { show: false }, background: chartTheme.bg, group: 'breadth' },
    stroke: { curve: 'smooth', width: [2, 1.5, 1.5] },
    xaxis: { type: 'datetime', categories: data.dates, labels: { style: { colors: chartTheme.text } } },
    yaxis: {
      min: 0,
      max: 100,
      labels: { formatter: (val: number) => `${val}%`, style: { colors: chartTheme.text } },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      yaxis: [
        { y: 80, borderColor: '#DC2626', strokeDashArray: 4, label: { text: 'Overbought Zone', style: { color: '#DC2626' } } },
        { y: 50, borderColor: chartTheme.grid, strokeDashArray: 4, label: { text: 'Neutral', style: { color: chartTheme.text } } },
        { y: 20, borderColor: CHART_COLORS.bullish, strokeDashArray: 4, label: { text: 'Oversold Zone', style: { color: CHART_COLORS.bullish } } },
      ],
    },
    tooltip: { theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark' },
    grid: { borderColor: chartTheme.grid },
  };

  const breadthSeries = [
    { name: '% above 20DMA', data: data.above20DMA },
    { name: '% above 50DMA', data: data.above50DMA },
    { name: '% above 200DMA', data: data.above200DMA },
  ];

  const getReadingColor = (value: number) => {
    if (value > 70) return 'text-bullish-green';
    if (value < 30) return 'text-bearish-red';
    return 'text-neutral-blue';
  };

  return (
    <div className="w-full space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="card-base p-4">
          <div className="text-xs text-text-muted">Above 20DMA</div>
          <div className={`text-2xl font-bold ${getReadingColor(latestReadings.above20)}`}>{latestReadings.above20.toFixed(0)}%</div>
        </div>
        <div className="card-base p-4">
          <div className="text-xs text-text-muted">Above 50DMA</div>
          <div className={`text-2xl font-bold ${getReadingColor(latestReadings.above50)}`}>{latestReadings.above50.toFixed(0)}%</div>
        </div>
        <div className="card-base p-4">
          <div className="text-xs text-text-muted">Above 200DMA</div>
          <div className={`text-2xl font-bold ${getReadingColor(latestReadings.above200)}`}>{latestReadings.above200.toFixed(0)}%</div>
        </div>
      </div>

      <Chart type="area" series={niftySeries} options={niftyOptions} height={120} />
      <Chart type="line" series={breadthSeries} options={breadthOptions} height={180} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Market Breadth</strong> shows the percentage of Nifty50 stocks trading above key moving averages. Above 70% = broad strength. Below 30% = widespread weakness.
      </div>
    </div>
  );
}
