'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';

const Chart = dynamic(() => import('react-apexcharts/core'), { ssr: false });
import 'apexcharts/features/annotations';

interface PcrData {
  dates: string[];
  pcr: number[];
}

interface PcrHistoryChartProps {
  ticker?: string;
}

export function PcrHistoryChart({ ticker }: PcrHistoryChartProps) {
  const [data, setData] = useState<PcrData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPCR, setCurrentPCR] = useState<number>(1.32);
  const chartTheme = useChartTheme();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/fno/analyze`,
          { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol: ticker || 'NIFTY' }) }
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();

        // Mock: Generate PCR history (in production, this comes from API)
        const mockDates = Array.from({ length: 30 }, (_, i) => {
          const d = new Date();
          d.setDate(d.getDate() - (29 - i));
          return d.toISOString().split('T')[0];
        });

        const mockPCR = Array.from({ length: 30 }, (_, i) => {
          const trend = 0.05 * (i - 15);
          return Math.max(0.5, Math.min(2.0, 1.32 + trend + (Math.random() - 0.5) * 0.3));
        });

        setData({ dates: mockDates, pcr: mockPCR });
        setCurrentPCR(mockPCR[29]);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (loading) return <ChartSkeleton height={300} />;

  if (error || !data) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load PCR history</p>
        <p className="text-xs text-text-muted">{error}</p>
      </div>
    );
  }

  const getPCRColor = () => {
    if (currentPCR > 1.2) return CHART_COLORS.bullish;
    if (currentPCR < 0.8) return CHART_COLORS.bearish;
    return CHART_COLORS.neutral;
  };

  const getPCRLabel = () => {
    if (currentPCR > 1.2) return 'BULLISH ZONE';
    if (currentPCR < 0.8) return 'BEARISH ZONE';
    return 'NEUTRAL ZONE';
  };

  const series = [
    {
      name: 'PCR Ratio',
      data: data.pcr.map((pcr) => ({
        x: data.dates[data.pcr.indexOf(pcr)],
        y: pcr,
      })),
    },
  ];

  const options: any = {
    chart: { type: 'area', toolbar: { show: false }, background: chartTheme.bg },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: currentPCR > 1.2 ? 0.12 : currentPCR < 0.8 ? 0.12 : 0.08,
        opacityTo: 0.05,
        stops: [0, 90, 100],
        colorStops:
          currentPCR > 1.2
            ? [
                { offset: 0, color: CHART_COLORS.bullish, opacity: 0.12 },
                { offset: 100, color: CHART_COLORS.bullish, opacity: 0.05 },
              ]
            : currentPCR < 0.8
            ? [
                { offset: 0, color: CHART_COLORS.bearish, opacity: 0.12 },
                { offset: 100, color: CHART_COLORS.bearish, opacity: 0.05 },
              ]
            : [
                { offset: 0, color: CHART_COLORS.neutral, opacity: 0.08 },
                { offset: 100, color: CHART_COLORS.neutral, opacity: 0.05 },
              ],
      },
    },
    stroke: {
      curve: 'smooth',
      width: 2,
      colors: [getPCRColor()],
    },
    xaxis: {
      type: 'datetime',
      categories: data.dates,
      labels: { style: { colors: chartTheme.text } },
    },
    yaxis: {
      min: 0.5,
      max: 2.0,
      labels: {
        formatter: (val: number) => val.toFixed(2),
        style: { colors: chartTheme.text },
      },
      axisBorder: { color: chartTheme.grid },
    },
    annotations: {
      yaxis: [
        { y: 1.5, borderColor: CHART_COLORS.bullish, strokeDashArray: 2, label: { text: 'Extreme Bullish', style: { color: CHART_COLORS.bullish } } },
        { y: 1.2, borderColor: CHART_COLORS.bullish, strokeDashArray: 2, label: { text: 'Bullish threshold', style: { color: CHART_COLORS.bullish } } },
        { y: 0.8, borderColor: CHART_COLORS.bearish, strokeDashArray: 2, label: { text: 'Bearish threshold', style: { color: CHART_COLORS.bearish } } },
        { y: 0.6, borderColor: CHART_COLORS.bearish, strokeDashArray: 2, label: { text: 'Extreme Bearish', style: { color: CHART_COLORS.bearish } } },
      ],
    },
    tooltip: {
      theme: chartTheme.tooltipBg === '#fff' ? 'light' : 'dark',
      custom: ({ series, seriesIndex, dataPointIndex }: any) => {
        const pcr = data.pcr[dataPointIndex];
        let zone = 'Normal Zone';
        if (pcr > 1.2) zone = 'Bullish Zone';
        else if (pcr < 0.8) zone = 'Bearish Zone';
        return `<div class="px-2 py-1 text-xs"><div>PCR: ${pcr.toFixed(2)}</div><div>${zone}</div></div>`;
      },
    },
    grid: { borderColor: chartTheme.grid },
  };

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center gap-4">
        <div>
          <div className="text-lg font-bold" style={{ color: getPCRColor() }}>
            PCR: {currentPCR.toFixed(2)}
          </div>
          <div className="text-sm font-semibold" style={{ color: getPCRColor() }}>
            {getPCRLabel()}
          </div>
        </div>
      </div>

      <Chart type="area" series={series} options={options} height={300} />

      <div className="text-xs text-text-muted p-3 bg-surface-raised rounded-btn">
        <strong>PCR Ratio:</strong> PCR above 1.2 = institutions hedging = typically bullish. PCR below 0.8 = more calls = often bearish. Extreme readings (&gt;1.5 or &lt;0.6) are contrarian signals.
      </div>
    </div>
  );
}
