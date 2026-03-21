'use client';
import type { ApexOptions } from 'apexcharts';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS, useChartTheme } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';
import { formatPct } from '@/lib/format-india';

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={400} />,
});

export interface SectorData {
  sector: string;
  marketCap: number; // for sizing
  rs5d: number; // 5-day relative strength
  onClick?: () => void;
}

export interface SectorHeatmapProps {
  data: SectorData[];
  height?: number;
  onSectorClick?: (sector: string) => void;
}

function getRsColor(rs: number): string {
  if (rs < -3) return '#7F1D1D'; // Very bearish dark red
  if (rs < -1) return CHART_COLORS.bearish; // Red
  if (rs < 0) return CHART_COLORS.warning; // Amber
  if (rs < 1) return CHART_COLORS.bullish; // Green
  if (rs < 3) return '#059669'; // Bright green
  return '#065F46'; // Dark green - very bullish
}

export function SectorHeatmap({ data, height = 400, onSectorClick }: SectorHeatmapProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  const chartTheme = useChartTheme();

  if (!data || data.length === 0) {
    return <div className="text-text-muted text-sm p-4">No sector data available</div>;
  }

  // Calculate market cap range for sizing
  const marketCaps = data.map((d) => d.marketCap).filter((v) => v > 0);
  const minCap = Math.min(...marketCaps);
  const maxCap = Math.max(...marketCaps);
  const capRange = maxCap - minCap || 1;

  // Prepare treemap series
  const series = data.map((sector) => ({
    x: sector.sector,
    y: sector.marketCap,
    fillColor: getRsColor(sector.rs5d),
  }));

  const options: ApexOptions = {
    chart: {
      type: 'treemap' as const,
      toolbar: { show: true },
      animations: { enabled: true },
      events: {
        dataPointSelection: (_e: any, _chart: any, config: any) => {
          const sectorName = data[config.dataPointIndex]?.sector;
          if (sectorName && onSectorClick) {
            onSectorClick(sectorName);
          }
        },
      },
    },
    plotOptions: {
      treemap: {
        enableShades: false,
        useFillColorAsStroke: false,
        dataLabels: {
          format: 'scale' as const,
        },
      },
    },
    dataLabels: {
      enabled: true,
      style: {
        fontSize: '12px',
        fontWeight: 600,
        colors: ['#FFFFFF'],
      },
      formatter: (value: string, opts: any) => {
        const sector = data[opts.dataPointIndex];
        if (!sector) return value;
        const rs = sector.rs5d;
        const arrow = rs > 0 ? '↑' : rs < 0 ? '↓' : '→';
        return `${sector.sector} ${arrow} ${formatPct(rs, 1)}`;
      },
    },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      custom: ({ seriesIndex, dataPointIndex }: any) => {
        const sector = data[dataPointIndex];
        return `
          <div style="padding: 12px; border-radius: 6px;">
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px;">${sector.sector}</div>
            <div style="font-size: 12px; color: ${getRsColor(sector.rs5d)};">RS 5D: ${formatPct(sector.rs5d, 2)}</div>
            <div style="font-size: 11px; color: ${chartTheme.text}; margin-top: 4px; opacity: 0.7;">Market Cap Weight</div>
          </div>
        `;
      },
    },
    colors: data.map((d) => getRsColor(d.rs5d)),
    states: {
      hover: { filter: { type: 'darken' as const } },
      active: { filter: { type: 'darken' as const } },
    },
  };

  return (
    <div className="w-full">
      <div className="mb-4">
        <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest">Sector Heatmap (5-Day RS)</h3>
        <p className="text-xs text-text-secondary mt-1">Size = Market Cap Weight | Color = Relative Strength | Click to explore</p>
      </div>

      <Chart
        options={options}
        series={[
          {
            name: 'Sector Weight',
            data: series,
          },
        ]}
        type="treemap"
        height={height}
      />

      {/* Legend */}
      <div className="mt-6 grid grid-cols-6 gap-2 px-2">
        <LegendItem color="#065F46" label="Extreme Bull" value=">3%" />
        <LegendItem color={CHART_COLORS.bullish} label="Bull" value="1-3%" />
        <LegendItem color={CHART_COLORS.warning} label="Neutral" value="-1 to +1%" />
        <LegendItem color={CHART_COLORS.bearish} label="Bear" value="-3 to -1%" />
        <LegendItem color="#DC2626" label="Weak" value="-1 to -3%" />
        <LegendItem color="#7F1D1D" label="Crash" value="<-3%" />
      </div>
    </div>
  );
}

function LegendItem({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="w-6 h-6 rounded-sm mb-2" style={{ backgroundColor: color }} />
      <div className="text-xs font-semibold text-text-primary">{label}</div>
      <div className="text-xs text-text-muted">{value}</div>
    </div>
  );
}
