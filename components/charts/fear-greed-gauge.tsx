'use client';
import type { ApexOptions } from 'apexcharts';

import dynamic from 'next/dynamic';
import { ChartSkeleton } from './chart-skeleton';
import { CHART_COLORS } from '@/lib/chart-theme';
import { useTheme } from 'next-themes';

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={250} />,
});

export interface FearGreedGaugeProps {
  value: number; // 0-100
  label?: string;
  height?: number;
}

const FEAR_GREED_ZONES = [
  { min: 0, max: 20, label: 'EXTREME FEAR', color: CHART_COLORS.bearish },
  { min: 20, max: 40, label: 'FEAR', color: CHART_COLORS.warning },
  { min: 40, max: 60, label: 'NEUTRAL', color: CHART_COLORS.warning },
  { min: 60, max: 80, label: 'GREED', color: CHART_COLORS.bullish },
  { min: 80, max: 100, label: 'EXTREME GREED', color: CHART_COLORS.bullish },
];

function getZoneLabel(value: number): string {
  for (const zone of FEAR_GREED_ZONES) {
    if (value >= zone.min && value <= zone.max) {
      return zone.label;
    }
  }
  return 'NEUTRAL';
}

function getZoneColor(value: number): string {
  for (const zone of FEAR_GREED_ZONES) {
    if (value >= zone.min && value <= zone.max) {
      return zone.color;
    }
  }
  return CHART_COLORS.warning;
}

export function FearGreedGauge({ value, label = 'Fear & Greed Index', height = 250 }: FearGreedGaugeProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');
  
  const clampedValue = Math.max(0, Math.min(100, value));
  const zoneLabel = getZoneLabel(clampedValue);
  const zoneColor = getZoneColor(clampedValue);
  const textColor = isDark ? '#F1F5F9' : '#0F172A';
  const gridColor = isDark ? '#1E293B' : '#E2E8F0';

  const series = [clampedValue];
  const options: ApexOptions = {
    chart: {
      type: 'radialBar' as const,
      sparkline: { enabled: false },
      toolbar: { show: false },
      animations: { enabled: true, animateGradually: { enabled: true, delay: 150 }, dynamicAnimation: { enabled: true, speed: 350 } },
    },
    plotOptions: {
      radialBar: {
        startAngle: -135,
        endAngle: 135,
        hollow: {
          margin: 0,
          size: '70%',
        },
        track: {
          strokeWidth: '100%',
          background: gridColor,
        },
        dataLabels: {
          name: {
            show: true,
            fontSize: '14px',
            fontWeight: 500,
            color: textColor,
            offsetY: -10,
          },
          value: {
            show: true,
            fontSize: '32px',
            fontWeight: 700,
            color: zoneColor,
            offsetY: 10,
            formatter: (val: number) => `${val.toFixed(0)}`,
          },
        },
      },
    },
    colors: [zoneColor],
    stroke: { lineCap: 'round' },
    states: { hover: { filter: { type: 'none' } } },
    tooltip: {
      theme: isDark ? 'dark' : 'light',
      y: { formatter: (val: number) => `${val.toFixed(1)}%` },
    },
  };

  return (
    <div className="w-full">
      <div className="text-center mb-4">
        <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest">{label}</h3>
      </div>
      
      <Chart
        options={options}
        series={series}
        type="radialBar"
        height={height}
      />

      {/* Zone Labels */}
      <div className="grid grid-cols-5 gap-2 mt-6 px-4">
        {FEAR_GREED_ZONES.map((zone) => (
          <div
            key={zone.label}
            className={`text-center py-2 px-1 rounded transition-all ${
              clampedValue >= zone.min && clampedValue <= zone.max
                ? 'border-b-2 font-semibold'
                : 'opacity-50'
            }`}
            style={{
              borderBottomColor: zone.color,
              color: clampedValue >= zone.min && clampedValue <= zone.max ? zone.color : textColor,
            }}
          >
            <div className="text-xs font-semibold">{zone.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
