'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useTheme } from 'next-themes';
import { CHART_COLORS } from '@/lib/chart-theme';
import { ChartSkeleton } from './chart-skeleton';
import { formatPrice, formatVolume, formatPct } from '@/lib/format-india';

export interface CandlestickChartProps {
  ticker: string;
  period?: string;
  showPrediction?: boolean;
  predictionData?: {
    p10?: number;
    p50?: number;
    p90?: number;
    confidence?: number;
  };
  overlays?: {
    vwap?: boolean;
    ema20?: boolean;
    ema50?: boolean;
    bb?: boolean;
  };
}

const TIMEFRAMES = ['1D', '1W', '1M', '3M', '6M', '1Y', '2Y'];
const PERIOD_MAP: Record<string, string> = {
  '1D': '1d', '1W': '1w', '1M': '1mo', '3M': '3mo', '6M': '6mo', '1Y': '1y', '2Y': '2y',
};

export function CandlestickChart({
  ticker,
  period = '3M',
  showPrediction = false,
  predictionData,
  overlays = { vwap: true, ema20: true, ema50: false, bb: false },
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [activePeriod, setActivePeriod] = useState(period);
  const [priceData, setPriceData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<any>(null);
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');

  const textColor = isDark ? '#94A3B8' : '#475569';
  const gridColor = isDark ? '#1E293B' : '#E2E8F0';
  const bgColor = 'transparent';

  const fetchData = useCallback(async (tf: string) => {
    setLoading(true);
    setError(null);
    try {
      const apiPeriod = PERIOD_MAP[tf] || '3mo';
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/price/${encodeURIComponent(ticker)}?period=${apiPeriod}`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      const candles = (json.candles || json.data || []).map((c: any) => ({
        time: c.time || c.date,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));
      setPriceData(candles);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    fetchData(activePeriod);
  }, [activePeriod, fetchData]);

  useEffect(() => {
    if (loading || error || !priceData.length || !containerRef.current) return;

    let chart: any;

    const initChart = async () => {
      const lwc = await import('lightweight-charts');

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }

      chart = lwc.createChart(containerRef.current!, {
        layout: {
          background: { type: lwc.ColorType.Solid, color: bgColor },
          textColor,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lwc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: { borderColor: gridColor, timeVisible: true, secondsVisible: false },
        handleScroll: true,
        handleScale: true,
        width: containerRef.current!.clientWidth,
        height: 360,
      });

      chartRef.current = chart;

      // Pane 1: Candlestick
      const candleSeries = chart.addCandlestickSeries({
        upColor: CHART_COLORS.bullish,
        downColor: CHART_COLORS.bearish,
        borderUpColor: CHART_COLORS.bullish,
        borderDownColor: CHART_COLORS.bearish,
        wickUpColor: CHART_COLORS.bullish,
        wickDownColor: CHART_COLORS.bearish,
      });
      candleSeries.setData(priceData);

      // Resize observer
      const ro = new ResizeObserver((entries) => {
        const { width } = entries[0].contentRect;
        chart.applyOptions({ width });
      });
      ro.observe(containerRef.current!);

      // Crosshair tooltip
      chart.subscribeCrosshairMove((param: any) => {
        if (!param.point || !param.time) {
          setTooltip(null);
          return;
        }
        const candle = param.seriesData.get(candleSeries);
        if (candle) {
          setTooltip({
            time: param.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            change: ((candle.close - candle.open) / candle.open) * 100,
          });
        }
      });

      chart.timeScale().fitContent();

      return ro;
    };

    let ro: ResizeObserver;
    initChart().then(r => { ro = r; });

    return () => {
      if (ro) ro.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceData, loading, error, isDark]);

  if (loading) return <ChartSkeleton height={420} />;

  if (error) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-6 text-center space-y-2">
        <p className="text-bearish-red font-medium">Failed to load chart data</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button
          onClick={() => fetchData(activePeriod)}
          className="text-xs px-3 py-1.5 bg-surface-raised rounded-btn text-text-secondary hover:text-text-primary transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="w-full space-y-3">
      {/* Timeframe buttons */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => setActivePeriod(tf)}
            className="text-xs px-2.5 py-1 rounded-btn transition-all font-medium"
            style={{
              background: activePeriod === tf ? CHART_COLORS.saffron : 'transparent',
              color: activePeriod === tf ? '#fff' : textColor,
              border: `1px solid ${activePeriod === tf ? CHART_COLORS.saffron : gridColor}`,
            }}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Floating tooltip */}
      {tooltip && (
        <div
          className="text-xs rounded-card px-3 py-2 pointer-events-none border border-border"
          style={{ background: isDark ? '#111827' : '#fff' }}
        >
          <span className="font-semibold text-text-primary mr-3">{String(tooltip.time)}</span>
          <span className="text-text-secondary mr-2">O {formatPrice(tooltip.open)}</span>
          <span className="text-text-secondary mr-2">H {formatPrice(tooltip.high)}</span>
          <span className="text-text-secondary mr-2">L {formatPrice(tooltip.low)}</span>
          <span className="font-bold mr-2" style={{ color: tooltip.close >= tooltip.open ? CHART_COLORS.bullish : CHART_COLORS.bearish }}>
            C {formatPrice(tooltip.close)}
          </span>
          <span style={{ color: tooltip.change >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish }}>
            {formatPct(tooltip.change)}
          </span>
        </div>
      )}

      {/* Chart container */}
      <div ref={containerRef} className="w-full rounded-card overflow-hidden" />
    </div>
  );
}
