'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });

interface FearGreedGaugeProps {
  value?: number;
}

const ZONES = [
  { min: 0, max: 20, label: 'Extreme Fear', color: '#DC2626' },
  { min: 20, max: 40, label: 'Fear', color: '#F97316' },
  { min: 40, max: 60, label: 'Neutral', color: '#EAB308' },
  { min: 60, max: 80, label: 'Greed', color: '#84CC16' },
  { min: 80, max: 100, label: 'Extreme Greed', color: '#059669' },
];

export function FearGreedGauge({ value: initialValue }: FearGreedGaugeProps) {
  const [value, setValue] = useState(initialValue || 65);
  const [loading, setLoading] = useState(true);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(false);
    };

    fetchData();
  }, []);

  if (loading) return <ChartSkeleton height={220} />;

  const currentZone = ZONES.find((z) => value >= z.min && value < z.max) || ZONES[2];

  const series = [value];
  const options: any = {
    chart: { type: 'radialBar', background: chartTheme.bg },
    plotOptions: {
      radialBar: {
        startAngle: -135,
        endAngle: 135,
        track: { background: chartTheme.grid, strokeWidth: '100%' },
        dataLabels: {
          name: { fontSize: '22px', color: chartTheme.text },
          value: { fontSize: '16px', color: chartTheme.text },
          total: { show: true, label: currentZone.label, fontSize: '14px', color: currentZone.color },
        },
      },
    },
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'dark',
        shadeIntensity: 0.15,
        inverseColors: false,
        opacityFrom: 1,
        opacityTo: 1,
        stops: [0, 50, 100],
        colorStops: [
          {
            offset: 0,
            color: '#DC2626',
            opacity: 1,
          },
          {
            offset: 50,
            color: '#EAB308',
            opacity: 1,
          },
          {
            offset: 100,
            color: '#059669',
            opacity: 1,
          },
        ],
      },
    },
    stroke: { lineCap: 'round' },
    labels: ['Fear & Greed Index'],
  };

  return (
    <div className="w-full space-y-4">
      <Chart type="radialBar" series={series} options={options} height={200} />

      <div className="flex justify-center gap-2 flex-wrap">
        {ZONES.map((zone) => (
          <div
            key={zone.label}
            className="px-2 py-1 text-xs font-medium rounded-btn transition-all"
            style={{
              background: zone.color,
              color: '#fff',
              opacity: currentZone.label === zone.label ? 1 : 0.4,
              textDecoration: currentZone.label === zone.label ? 'underline' : 'none',
            }}
          >
            {zone.label}
          </div>
        ))}
      </div>

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>Fear & Greed Index:</strong> Measures market sentiment on a scale of 0-100. Extreme Fear (&lt;20) often leads to capitulation lows. Extreme Greed (&gt;80) can precede corrections.
      </div>
    </div>
  );
}
