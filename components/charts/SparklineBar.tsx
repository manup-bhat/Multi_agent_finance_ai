'use client';

import dynamic from 'next/dynamic';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <div className="w-full h-12 bg-surface-raised rounded animate-pulse" />,
});

export interface SparklineBarProps {
  data: number[];
  height?: number;
}

export function SparklineBar({ data, height = 48 }: SparklineBarProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.length === 0) {
    return <div className="w-full h-12 bg-surface-raised rounded" />;
  }

  const series = [
    {
      name: 'Value',
      data: data,
    },
  ];

  const options = {
    chart: {
      sparkline: { enabled: true },
      animations: { enabled: false },
    },
    plotOptions: {
      bar: {
        columnWidth: '70%',
        borderRadius: 2,
      },
    },
    colors: data.map((val) => (val > 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish)),
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val: number) => val.toFixed(0),
      },
    },
    states: { hover: { filter: { type: 'darken', value: 0.15 } } },
  };

  return (
    <Chart
      options={options}
      series={series}
      type="bar"
      height={height}
    />
  );
}
