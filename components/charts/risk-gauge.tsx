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

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'EXTREME';

export interface RiskGaugeProps {
  riskLevel: RiskLevel;
  riskScore: number; // 0-100
  positionSize?: number; // multiplier
  height?: number;
}

function getRiskColor(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return CHART_COLORS.bullish; // Green
    case 'MODERATE': return CHART_COLORS.neutral; // Blue
    case 'HIGH': return CHART_COLORS.warning; // Amber
    case 'EXTREME': return CHART_COLORS.bearish; // Red
  }
}

function getRiskPercentage(level: RiskLevel): number {
  switch (level) {
    case 'LOW': return 25;
    case 'MODERATE': return 50;
    case 'HIGH': return 75;
    case 'EXTREME': return 100;
  }
}

export function RiskGauge({ riskLevel, riskScore, positionSize = 1, height = 250 }: RiskGaugeProps) {
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');

  const riskColor = getRiskColor(riskLevel);
  const riskPercentage = getRiskPercentage(riskLevel);
  const textColor = isDark ? '#F1F5F9' : '#0F172A';
  const gridColor = isDark ? '#1E293B' : '#E2E8F0';

  const series = [riskPercentage];

  const options: ApexOptions = {
    chart: {
      type: 'radialBar' as const,
      sparkline: { enabled: false },
      toolbar: { show: false },
      animations: { enabled: true },
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
            fontSize: '28px',
            fontWeight: 700,
            color: riskColor,
            offsetY: 5,
            formatter: () => riskLevel,
          },
        },
      },
    },
    colors: [riskColor],
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
        <h3 className="text-sm font-medium text-text-muted uppercase tracking-widest">Risk Assessment</h3>
      </div>

      <Chart
        options={options}
        series={series}
        type="radialBar"
        height={height}
      />

      {/* Risk Details */}
      <div className="grid grid-cols-2 gap-3 mt-6 px-4">
        <div className="p-3 rounded-lg bg-surface-raised text-center">
          <div className="text-xs text-text-secondary mb-1">Risk Score</div>
          <div className="text-xl font-bold" style={{ color: riskColor }}>
            {riskScore.toFixed(0)}%
          </div>
        </div>
        <div className="p-3 rounded-lg bg-surface-raised text-center">
          <div className="text-xs text-text-secondary mb-1">Position Size</div>
          <div className="text-xl font-bold text-text-primary">
            {positionSize.toFixed(2)}x
          </div>
        </div>
      </div>

      {/* Risk Description */}
      <div className="mt-4 px-4">
        <div
          className="p-3 rounded-lg text-sm text-center"
          style={{
            backgroundColor: getRiskBgColor(riskLevel),
            color: riskColor,
            fontWeight: 500,
          }}
        >
          {getRiskDescription(riskLevel)}
        </div>
      </div>
    </div>
  );
}

function getRiskBgColor(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return '#ECFDF5'; // Green bg
    case 'MODERATE': return '#EFF6FF'; // Blue bg
    case 'HIGH': return '#FFFBEB'; // Amber bg
    case 'EXTREME': return '#FEF2F2'; // Red bg
  }
}

function getRiskDescription(level: RiskLevel): string {
  switch (level) {
    case 'LOW': return '✓ Low Risk - Suitable for conservative positions';
    case 'MODERATE': return '⚠ Moderate Risk - Balanced approach recommended';
    case 'HIGH': return '⚠ High Risk - Consider reducing position size';
    case 'EXTREME': return '✗ Extreme Risk - Avoid new positions';
  }
}
