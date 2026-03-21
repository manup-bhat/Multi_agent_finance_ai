'use client';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then((m) => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={400} />,
});

const SECTOR_ABBREVIATIONS: Record<string, string> = {
  'IT': 'IT', 'Banking': 'BANK', 'FMCG': 'FMCG', 'Auto': 'AUTO',
  'Pharma': 'PHRM', 'Energy': 'ENGY', 'Metals': 'METL', 'Realty': 'RLTY',
  'Media': 'MDA', 'Telecom': 'TELCO', 'Infrastructure': 'INFRA',
  'Chemicals': 'CHEM', 'Consumer Durables': 'CD',
};

export interface SectorRotationDataPoint {
  sector: string;
  rs: number;           // Relative Strength vs benchmark (-5 to +5)
  rsMomentum: number;   // Momentum of RS (-5 to +5)
  volumeRatio?: number; // 20d volume ratio (drives bubble size)
}

export interface SectorRotationChartProps {
  data: SectorRotationDataPoint[];
  height?: number;
}

function getQuadrantColor(rs: number, momentum: number): string {
  if (rs > 0 && momentum > 0) return CHART_COLORS.bullish;   // Leading
  if (rs < 0 && momentum > 0) return CHART_COLORS.neutral;   // Improving
  if (rs < 0 && momentum < 0) return CHART_COLORS.bearish;   // Lagging
  return CHART_COLORS.warning;                                // Weakening
}

export function SectorRotationChart({ data, height = 400 }: SectorRotationChartProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-muted text-sm">
        No sector rotation data available
      </div>
    );
  }

  const minVol = Math.min(...data.map((d) => d.volumeRatio ?? 1));
  const maxVol = Math.max(...data.map((d) => d.volumeRatio ?? 1));
  const volRange = maxVol - minVol || 1;

  const scatterData = data.map((d) => {
    const normVol = ((d.volumeRatio ?? 1) - minVol) / volRange;
    const bubbleSize = 6 + normVol * 8; // 6 to 14
    return {
      x: +d.rs.toFixed(2),
      y: +d.rsMomentum.toFixed(2),
      z: bubbleSize,
      name: d.sector,
      fillColor: getQuadrantColor(d.rs, d.rsMomentum),
    };
  });

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: 'scatter',
      toolbar: { show: false },
      animations: { enabled: true, speed: 600 },
      zoom: { enabled: false },
    },
    dataLabels: {
      enabled: true,
      formatter: (_val: any, opts: any) => {
        const sector = scatterData[opts.dataPointIndex]?.name || '';
        return SECTOR_ABBREVIATIONS[sector] || sector.slice(0, 4).toUpperCase();
      },
      style: {
        colors: [chartTheme.text],
        fontSize: '10px',
        fontWeight: '600',
      },
      offsetX: 8,
      offsetY: -4,
    },
    colors: scatterData.map((d) => d.fillColor),
    xaxis: {
      min: -5,
      max: 5,
      title: {
        text: 'Relative Strength vs Nifty 50',
        style: { color: chartTheme.text, fontSize: '11px' },
      },
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
      axisBorder: { show: false },
      axisTicks: { show: false },
    },
    yaxis: {
      min: -5,
      max: 5,
      title: {
        text: 'RS Momentum (Rate of Change)',
        style: { color: chartTheme.text, fontSize: '11px' },
      },
      labels: { style: { colors: chartTheme.text, fontSize: '11px' } },
    },
    grid: { borderColor: chartTheme.grid, strokeDashArray: 3 },
    annotations: {
      xaxis: [
        {
          x: 0,
          borderColor: chartTheme.grid,
          strokeDashArray: 4,
          borderWidth: 1,
        },
      ],
      yaxis: [
        {
          y: 0,
          borderColor: chartTheme.grid,
          strokeDashArray: 4,
          borderWidth: 1,
        },
      ],
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      custom: ({ dataPointIndex }: any) => {
        const d = scatterData[dataPointIndex];
        if (!d) return '';
        const q = d.x > 0 && d.y > 0 ? 'LEADING' : d.x < 0 && d.y > 0 ? 'IMPROVING' : d.x < 0 && d.y < 0 ? 'LAGGING' : 'WEAKENING';
        return `<div style="padding:8px;background:${chartTheme.tooltipBg};color:${chartTheme.text};font-size:12px;border-radius:6px;border:1px solid ${chartTheme.grid}">
          <div style="font-weight:700;margin-bottom:4px">${d.name}</div>
          <div>RS: ${d.x > 0 ? '+' : ''}${d.x.toFixed(2)}</div>
          <div>Momentum: ${d.y > 0 ? '+' : ''}${d.y.toFixed(2)}</div>
          <div style="color:${d.fillColor};font-weight:600;margin-top:4px">${q}</div>
        </div>`;
      },
    },
    legend: { show: false },
    markers: { size: scatterData.map((d) => d.z), strokeWidth: 0, hover: { sizeOffset: 2 } },
  };

  return (
    <div className="w-full">
      {/* Quadrant legend */}
      <div className="grid grid-cols-2 gap-1 mb-3 text-xs">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bullish-bg/30">
          <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS.bullish }} />
          <span className="text-bullish-green font-semibold">LEADING</span>
          <span className="text-text-muted">High RS + Rising</span>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-neutral-bg/30">
          <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS.neutral }} />
          <span className="text-neutral-blue font-semibold">IMPROVING</span>
          <span className="text-text-muted">Low RS + Rising</span>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bearish-bg/30">
          <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS.bearish }} />
          <span className="text-bearish-red font-semibold">LAGGING</span>
          <span className="text-text-muted">Low RS + Falling</span>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-warning-bg/30">
          <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS.warning }} />
          <span className="text-warning-amber font-semibold">WEAKENING</span>
          <span className="text-text-muted">High RS + Falling</span>
        </div>
      </div>

      <Chart
        options={options}
        series={scatterData.map((d) => ({
          name: d.name,
          data: [{ x: d.x, y: d.y }],
        }))}
        type="scatter"
        height={height}
      />
    </div>
  );
}
