'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={280} />,
});

export interface ShapChartProps {
  shapValues: Array<{ feature: string; value: number }>;
  height?: number;
}

export function ShapChart({ shapValues, height = 280 }: ShapChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!shapValues || shapValues.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No SHAP values available
      </div>
    );
  }

  // Sort by absolute value descending, take top 8
  const sorted = [...shapValues]
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 8);

  const categories = sorted.map((s) => s.feature);
  const values = sorted.map((s) => +s.value.toFixed(4));
  const colors = values.map((v) => (v >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish));

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'bar',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
    },
    plotOptions: {
      bar: {
        horizontal: true,
        barHeight: '60%',
        borderRadius: 4,
        distributed: true,
        dataLabels: { position: 'right' },
      },
    },
    colors,
    dataLabels: {
      enabled: true,
      formatter: (val: number) => (val > 0 ? `+${val.toFixed(3)}` : val.toFixed(3)),
      style: {
        colors: [chartTheme.text],
        fontSize: '11px',
        fontWeight: 600,
      },
      offsetX: 4,
    },
    xaxis: {
      categories,
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
    },
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
      xaxis: { lines: { show: true } },
      yaxis: { lines: { show: false } },
    },
    annotations: {
      xaxis: [
        {
          x: 0,
          borderColor: chartTheme.grid,
          strokeDashArray: 0,
          borderWidth: 2,
          opacity: 0.8,
        },
      ],
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: {
        formatter: (val: number) =>
          `SHAP: ${val > 0 ? '+' : ''}${val.toFixed(4)} (${val > 0 ? '↑ bullish' : '↓ bearish'})`,
      },
    },
    legend: { show: false },
  };

  return (
    <div className="w-full">
      <Chart
        options={options}
        series={[{ name: 'SHAP Value', data: values }]}
        type="bar"
        height={height}
      />
      <p className="text-xs text-text-muted mt-1 text-center">
        Green = pushes prediction higher (bullish) · Red = pushes prediction lower (bearish)
      </p>
    </div>
  );
}
