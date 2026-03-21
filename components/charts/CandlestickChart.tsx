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
  activeOverlays?: string[];
}

const TIMEFRAMES = ['1D', '1W', '1M', '3M', '6M', '1Y', '2Y'];
// These keys map 1:1 to the backend PERIOD_MAP in api/routes/price.py
// Backend accepts: 1D|1W|1M|3M|6M|1Y|2Y (and legacy 1d|1w|1mo|3mo|6mo|1y|2y)

const OVERLAY_BUTTONS = ['VWAP', 'VWAP ±1σ', 'VWAP ±2σ', 'EMA 20', 'EMA 50', 'EMA 200', 'BB', 'Supertrend', 'Fibonacci', 'Pivots', 'SMC', 'RS'];

// Helper: Calculate VWAP
function calculateVWAP(candles: any[]): any[] {
  return candles.map((candle, i) => {
    const slice = candles.slice(0, i + 1);
    const cumVolumePrice = slice.reduce((sum, c) => sum + (c.close * c.volume), 0);
    const cumVolume = slice.reduce((sum, c) => sum + c.volume, 0);
    return { time: candle.time, value: cumVolume > 0 ? cumVolumePrice / cumVolume : candle.close };
  });
}

// Helper: Calculate EMA
function calculateEMA(candles: any[], period: number): any[] {
  const result = [];
  const k = 2 / (period + 1);
  let ema = candles[0].close;
  
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) {
      ema = candles[i].close;
    } else {
      ema = candles[i].close * k + ema * (1 - k);
    }
    result.push({ time: candles[i].time, value: ema });
  }
  return result;
}

// Helper: Calculate Bollinger Bands
function calculateBB(candles: any[], period = 20): { upper: any[]; middle: any[]; lower: any[] } {
  const middle = calculateSMA(candles, period);
  const upper = [];
  const lower = [];
  
  for (let i = period - 1; i < candles.length; i++) {
    const slice = candles.slice(i - period + 1, i + 1);
    const avg = slice.reduce((sum, c) => sum + c.close, 0) / period;
    const variance = slice.reduce((sum, c) => sum + Math.pow(c.close - avg, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    upper.push({ time: candles[i].time, value: avg + 2 * stdDev });
    lower.push({ time: candles[i].time, value: avg - 2 * stdDev });
  }
  
  return { upper, middle, lower };
}

// Helper: Calculate SMA
function calculateSMA(candles: any[], period: number): any[] {
  const result = [];
  for (let i = period - 1; i < candles.length; i++) {
    const avg = candles.slice(i - period + 1, i + 1).reduce((sum, c) => sum + c.close, 0) / period;
    result.push({ time: candles[i].time, value: avg });
  }
  return result;
}

export function CandlestickChart({
  ticker,
  period = '3M',
  showPrediction = false,
  predictionData,
  activeOverlays = ['VWAP', 'EMA 20', 'EMA 50'],
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [activePeriod, setActivePeriod] = useState(period);
  const [priceData, setPriceData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<any>(null);
  const [overlays, setOverlays] = useState<string[]>(activeOverlays);
  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');

  const textColor = isDark ? '#94A3B8' : '#475569';
  const gridColor = isDark ? '#1E293B' : '#E2E8F0';
  const bgColor = 'transparent';

  const fetchData = useCallback(async (tf: string) => {
    setLoading(true);
    setError(null);
    try {
      // Send the timeframe key directly — backend accepts '3M', '1Y' etc.
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/price/${encodeURIComponent(ticker)}?period=${encodeURIComponent(tf)}`
      );
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      const json = await resp.json();
      // API returns { candles: [{time, open, high, low, close}], volume: [{time, value, color}] }
      const candles = (json.candles || json.data || []).filter(
        (c: any) => c.time && c.open != null && c.high != null && c.low != null && c.close != null
      ).map((c: any) => ({
        time: typeof c.time === 'string' ? Math.floor(new Date(c.time).getTime() / 1000) : c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume ?? 0,
      }));
      if (!candles.length) throw new Error('No OHLCV data returned. Check ticker symbol.');
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
        height: 500,
      });

      chartRef.current = chart;

      // PANE 1 — CANDLESTICK + OVERLAYS (60% height)
      const candleSeries = chart.addCandlestickSeries({
        upColor: CHART_COLORS.bullish,
        downColor: CHART_COLORS.bearish,
        borderUpColor: '#047857',
        borderDownColor: '#B91C1C',
        wickUpColor: '#047857',
        wickDownColor: '#B91C1C',
      });
      candleSeries.setData(priceData);

      // Add overlays
      if (overlays.includes('VWAP')) {
        const vwapData = calculateVWAP(priceData);
        const vwapSeries = chart.addLineSeries({
          color: CHART_COLORS.warning,
          lineWidth: 1.5,
          lineStyle: 2, // dashed
        });
        vwapSeries.setData(vwapData);
      }

      if (overlays.includes('EMA 20')) {
        const emaData = calculateEMA(priceData, 20);
        const emaSeries = chart.addLineSeries({
          color: CHART_COLORS.neutral,
          lineWidth: 1.5,
        });
        emaSeries.setData(emaData);
      }

      if (overlays.includes('EMA 50')) {
        const emaData = calculateEMA(priceData, 50);
        const emaSeries = chart.addLineSeries({
          color: '#7C3AED',
          lineWidth: 1.5,
        });
        emaSeries.setData(emaData);
      }

      if (overlays.includes('EMA 200')) {
        const emaData = calculateEMA(priceData, 200);
        const emaSeries = chart.addLineSeries({
          color: CHART_COLORS.warning,
          lineWidth: 2,
        });
        emaSeries.setData(emaData);
      }

      if (overlays.includes('BB')) {
        const { upper, middle, lower } = calculateBB(priceData, 20);
        
        const upperSeries = chart.addLineSeries({
          color: '#94A3B8',
          lineWidth: 1,
          lineStyle: 2,
        });
        upperSeries.setData(upper);

        const middleSeries = chart.addLineSeries({
          color: CHART_COLORS.saffron,
          lineWidth: 1,
        });
        middleSeries.setData(middle);

        const lowerSeries = chart.addLineSeries({
          color: '#94A3B8',
          lineWidth: 1,
          lineStyle: 2,
        });
        lowerSeries.setData(lower);
      }

      // PANE 2 — VOLUME (18% height)
      const volumeData = priceData.map((c) => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? CHART_COLORS.bullish : CHART_COLORS.bearish,
      }));

      const volumeSeries = chart.addHistogramSeries({
        color: CHART_COLORS.bullish,
      });
      volumeSeries.setData(
        volumeData.map((v) => ({
          time: v.time,
          value: v.value,
          color: v.color,
        }))
      );

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
        const volume = param.seriesData.get(volumeSeries);
        if (candle) {
          setTooltip({
            time: param.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            change: ((candle.close - candle.open) / candle.open) * 100,
            volume: volume?.value || 0,
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
  }, [priceData, loading, error, isDark, overlays]);

  const toggleOverlay = (overlay: string) => {
    setOverlays((prev) =>
      prev.includes(overlay)
        ? prev.filter((o) => o !== overlay)
        : [...prev, overlay]
    );
  };

  if (loading) return <ChartSkeleton height={500} />;

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

      {/* Overlay toggle buttons */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {OVERLAY_BUTTONS.map((overlay) => (
          <button
            key={overlay}
            onClick={() => toggleOverlay(overlay)}
            className="text-xs px-2.5 py-1 rounded-btn transition-all font-medium"
            style={{
              background: overlays.includes(overlay) ? CHART_COLORS.saffron : 'transparent',
              color: overlays.includes(overlay) ? '#fff' : textColor,
              border: `1px solid ${overlays.includes(overlay) ? CHART_COLORS.saffron : gridColor}`,
            }}
          >
            {overlay}
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
          <span className="text-text-secondary mr-2">Vol {formatVolume(tooltip.volume)}</span>
          <span style={{ color: tooltip.change >= 0 ? CHART_COLORS.bullish : CHART_COLORS.bearish }}>
            {formatPct(tooltip.change)}
          </span>
        </div>
      )}

      {/* Chart container */}
      <div ref={containerRef} className="w-full rounded-card overflow-hidden" style={{ height: '500px' }} />
    </div>
  );
}
