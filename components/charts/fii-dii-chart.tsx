'use client';
import type { ApexOptions } from 'apexcharts';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';
import { formatCrore } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={300} />,
});

export interface FiiDiiData {
  date: string;
  fiiNetCrore: number | null;
  diiNetCrore: number | null;
  fiiTrend?: string;
}

export interface FiiDiiChartProps {
  data: FiiDiiData[];
  height?: number;
}

export function FiiDiiChart({ data, height = 300 }: FiiDiiChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.length === 0) {
    return <div className="text-text-muted text-sm p-4">No FII/DII data available</div>;
  }

  // Prepare series with color coding per value
  const fiiSeries = data.map((d) => ({
    x: d.date,
    y: d.fiiNetCrore || 0,
    fillColor: (d.fiiNetCrore ?? 0) >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish,
  }));

  const diiSeries = data.map((d) => ({
    x: d.date,
    y: d.diiNetCrore || 0,
    fillColor: (d.diiNetCrore ?? 0) >= 0 ? CHART_COLORS.neutral : CHART_COLORS.warning,
  }));

  const series = [
    {
      name: 'FII Net',
      data: fiiSeries,
    },
    {
      name: 'DII Net',
      data: diiSeries,
    },
  ];

  const options: ApexOptions = {
    chart: {
      type: 'bar' as const,
      toolbar: { show: true, tools: { download: true, selection: true, zoom: true, zoomin: true, zoomout: true, pan: true, reset: true } },
      animations: { enabled: true },
      zoom: { enabled: true },
    },
    plotOptions: {
      bar: {
        horizontal: false,
        columnWidth: '60%',
        borderRadius: 3,
        borderRadiusApplication: 'end',
        dataLabels: { position: 'top' },
      },
    },
    stroke: { show: false },
    xaxis: {
      type: 'datetime',
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      title: {
        text: 'Amount (₹ Crore)',
        style: { color: chartTheme.text, fontSize: '12px', fontWeight: 600 },
      },
      labels: {
        style: { colors: chartTheme.text, fontSize: '11px' },
        formatter: (value: number) => formatCrore(value, 0),
      },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    annotations: {
      yaxis: [
        {
          y: 0,
          strokeDashArray: 0,
          borderColor: chartTheme.grid,
          label: {
            borderColor: chartTheme.grid,
            style: { color: '#FFF', background: chartTheme.grid },
            text: 'Zero Line',
          },
        },
      ],
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      custom: ({ series, seriesIndex, dataPointIndex, w }: any) => {
        const fiiVal = w.globals.initialSeries[0]?.data[dataPointIndex]?.y || 0;
        const diiVal = w.globals.initialSeries[1]?.data[dataPointIndex]?.y || 0;
        const date = w.globals.labels[dataPointIndex];

        return `
          <div style="padding: 10px; background: ${chartTheme.tooltipBg}; border-radius: 6px; color: ${chartTheme.text};">
            <div style="font-size: 12px; font-weight: 600; margin-bottom: 4px;">${date}</div>
            <div style="color: ${CHART_COLORS.bullish}; font-size: 12px;">FII: ${formatCrore(fiiVal, 0)}</div>
            <div style="color: ${CHART_COLORS.neutral}; font-size: 12px;">DII: ${formatCrore(diiVal, 0)}</div>
            <div style="color: ${fiiVal + diiVal >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish}; font-size: 12px; margin-top: 4px; font-weight: 600;">
              Net: ${formatCrore(fiiVal + diiVal, 0)}
            </div>
          </div>
        `;
      },
    },
    colors: [CHART_COLORS.bullish, CHART_COLORS.neutral],
    grid: {
      borderColor: chartTheme.grid,
      strokeDashArray: 3,
      show: true,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
    },
    states: { hover: { filter: { type: 'lighten' as const } } },
  };

  const latestFii = data[data.length - 1]?.fiiNetCrore ?? 0;
  const latestDii = data[data.length - 1]?.diiNetCrore ?? 0;

  return (
    <div className="w-full">
      <div className="mb-4">
        <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest mb-3">FII/DII Flow</h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 rounded-lg bg-surface-raised">
            <div className="text-xs text-text-secondary mb-1">FII Net</div>
            <div className="text-lg font-bold" style={{ color: latestFii >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish }}>
              {formatCrore(latestFii, 0)}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-surface-raised">
            <div className="text-xs text-text-secondary mb-1">DII Net</div>
            <div className="text-lg font-bold" style={{ color: latestDii >= 0 ? CHART_COLORS.neutral : CHART_COLORS.warning }}>
              {formatCrore(latestDii, 0)}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-surface-raised">
            <div className="text-xs text-text-secondary mb-1">Total Flow</div>
            <div className="text-lg font-bold" style={{ color: latestFii + latestDii >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish }}>
              {formatCrore(latestFii + latestDii, 0)}
            </div>
          </div>
        </div>
      </div>

      <Chart
        options={options}
        series={series}
        type="bar"
        height={height}
      />
    </div>
  );
}
