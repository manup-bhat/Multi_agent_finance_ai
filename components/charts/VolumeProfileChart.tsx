'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPrice, formatVolume } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

interface VolumeProfileChartProps {
  ticker: string;
  period?: string;
}

interface PriceBin {
  price: number;
  volume: number;
}

export function VolumeProfileChart({ ticker, period = '3M' }: VolumeProfileChartProps) {
  const [data, setData] = useState<PriceBin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ poc: number; vah: number; val: number; totalVolume: number }>({ poc: 0, vah: 0, val: 0, totalVolume: 0 });
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/price/${encodeURIComponent(ticker)}?period=${period}`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        const candles = (json.candles || json.data || []);

        // Bin prices into 50 levels
        const priceRange = { min: Infinity, max: -Infinity };
        candles.forEach((c: any) => {
          priceRange.min = Math.min(priceRange.min, c.low);
          priceRange.max = Math.max(priceRange.max, c.high);
        });

        const binCount = 50;
        const binSize = (priceRange.max - priceRange.min) / binCount;
        const bins: Record<number, number> = {};

        candles.forEach((c: any) => {
          const binIndex = Math.floor((c.close - priceRange.min) / binSize);
          const binPrice = Math.round((priceRange.min + binIndex * binSize) * 100) / 100;
          bins[binPrice] = (bins[binPrice] || 0) + c.volume;
        });

        const binnedData: PriceBin[] = Object.entries(bins)
          .map(([price, volume]) => ({ price: parseFloat(price), volume }))
          .sort((a, b) => a.price - b.price);

        // Find POC (Point of Control)
        const pocBin = binnedData.reduce((max, bin) => (bin.volume > max.volume ? bin : max));
        const poc = pocBin.price;

        // Find Value Area (70% of total volume)
        const totalVolume = binnedData.reduce((sum, bin) => sum + bin.volume, 0);
        const valueAreaVolume = totalVolume * 0.7;
        let accumulatedVolume = 0;
        let vah = poc;
        let val = poc;

        for (let i = binnedData.length - 1; i >= 0; i--) {
          if (accumulatedVolume >= valueAreaVolume) break;
          accumulatedVolume += binnedData[i].volume;
          vah = Math.max(vah, binnedData[i].price);
          val = Math.min(val, binnedData[i].price);
        }

        setData(binnedData);
        setStats({ poc, vah, val, totalVolume });
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker, period]);

  if (loading) return <ChartSkeleton height={400} />;

  if (error) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load volume profile</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const series = [
    {
      name: 'Volume',
      data: data.map((bin) => ({
        x: formatPrice(bin.price),
        y: bin.volume,
        fillColor:
          bin.price === stats.poc
            ? CHART_COLORS.saffron
            : bin.price >= stats.val && bin.price <= stats.vah
            ? CHART_COLORS.neutral
            : '#94A3B8',
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
        horizontal: true,
        borderRadius: 2,
        barHeight: '90%',
        colors: {
          ranges: data.map((bin) => ({
            from: bin.volume,
            to: bin.volume,
            color:
              bin.price === stats.poc
                ? CHART_COLORS.saffron
                : bin.price >= stats.val && bin.price <= stats.vah
                ? CHART_COLORS.neutral
                : '#94A3B8',
          })),
        },
      },
    },
    xaxis: {
      type: 'numeric',
      labels: { show: false },
    },
    yaxis: {
      labels: { style: { colors: chartTheme.text } },
    },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      custom: ({ series, seriesIndex, dataPointIndex }: any) => {
        const bin = data[dataPointIndex];
        return `<div class="px-2 py-1 text-xs"><div>Price: ${formatPrice(bin.price)}</div><div>Volume: ${formatVolume(bin.volume)}</div><div>${bin.price === stats.poc ? 'POC' : bin.price >= stats.val && bin.price <= stats.vah ? 'Value Area' : 'Normal'}</div></div>`;
      },
    },
    grid: {
      show: true,
      borderColor: chartTheme.grid,
    },
    states: {
      active: { filter: { type: 'none' } },
    },
  };

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="space-y-1">
          <div className="text-xs text-text-muted">POC (Point of Control)</div>
          <div className="text-lg font-bold text-saffron">{formatPrice(stats.poc)}</div>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-text-muted">VAH (Value Area High)</div>
          <div className="text-lg font-bold text-neutral-blue">{formatPrice(stats.vah)}</div>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-text-muted">VAL (Value Area Low)</div>
          <div className="text-lg font-bold text-neutral-blue">{formatPrice(stats.val)}</div>
        </div>
      </div>

      <Chart type="bar" series={series} options={options} height={400} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Volume Profile</strong> shows where most trading activity occurred. POC = Point of Control (highest volume price). Price tends to gravitate toward POC. Breaks beyond VAH/VAL signal strong directional moves.
      </div>
    </div>
  );
}
