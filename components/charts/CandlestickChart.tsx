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

// ─── Period labels shown to user → API period param ──────────────────────────
const TIMEFRAMES = [
  { label: '1D', api: '1D' },
  { label: '1W', api: '1W' },
  { label: '1M', api: '1M' },
  { label: '3M', api: '3M' },
  { label: '6M', api: '6M' },
  { label: '1Y', api: '1Y' },
  { label: '2Y', api: '2Y' },
];

const OVERLAY_BUTTONS = ['VWAP', 'EMA 20', 'EMA 50', 'EMA 200', 'BB'];

// ─── Technical helpers ───────────────────────────────────────────────────────
function calcVWAP(candles: any[]): any[] {
  let cumPV = 0, cumVol = 0;
  return candles.map((c) => {
    const vol = c.volume ?? 1;
    const tp = (c.high + c.low + c.close) / 3;
    cumPV += tp * vol;
    cumVol += vol;
    return { time: c.time, value: cumVol > 0 ? cumPV / cumVol : c.close };
  });
}

function calcEMA(candles: any[], period: number): any[] {
  if (candles.length < period) return [];
  const k = 2 / (period + 1);
  const result: any[] = [];
  let ema = candles.slice(0, period).reduce((s, c) => s + c.close, 0) / period;
  result.push({ time: candles[period - 1].time, value: ema });
  for (let i = period; i < candles.length; i++) {
    ema = candles[i].close * k + ema * (1 - k);
    result.push({ time: candles[i].time, value: ema });
  }
  return result;
}

function calcBB(candles: any[], period = 20): { upper: any[]; middle: any[]; lower: any[] } {
  const upper: any[] = [], middle: any[] = [], lower: any[] = [];
  for (let i = period - 1; i < candles.length; i++) {
    const slice = candles.slice(i - period + 1, i + 1);
    const avg = slice.reduce((s: number, c: any) => s + c.close, 0) / period;
    const std = Math.sqrt(slice.reduce((s: number, c: any) => s + (c.close - avg) ** 2, 0) / period);
    middle.push({ time: candles[i].time, value: avg });
    upper.push({ time: candles[i].time, value: avg + 2 * std });
    lower.push({ time: candles[i].time, value: avg - 2 * std });
  }
  return { upper, middle, lower };
}

// ─── Component ────────────────────────────────────────────────────────────────
export function CandlestickChart({
  ticker,
  period = '3M',
  activeOverlays = ['VWAP', 'EMA 20', 'EMA 50'],
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // Keep series refs so we can call .setData() without rebuilding the chart
  const candleSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const overlaySeriesRefs = useRef<any[]>([]);

  const [activePeriod, setActivePeriod] = useState(period);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<any>(null);
  const [overlays, setOverlays] = useState<string[]>(activeOverlays);

  // Track latest data for overlay updates without refetch
  const latestData = useRef<any[]>([]);

  const { theme, systemTheme } = useTheme();
  const isDark = theme === 'dark' || (theme === 'system' && systemTheme === 'dark');

  const textColor = isDark ? '#94A3B8' : '#475569';
  const gridColor = isDark ? '#1E293B' : '#E2E8F0';

  // ─── Step 1: Create chart ONCE on mount ─────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;

    let ro: ResizeObserver;

    const initChart = async () => {
      const lwc = await import('lightweight-charts');

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }

      const chart = lwc.createChart(containerRef.current!, {
        layout: {
          background: { type: lwc.ColorType.Solid, color: 'transparent' },
          textColor,
        },
        grid: {
          vertLines: { color: gridColor },
          horzLines: { color: gridColor },
        },
        crosshair: { mode: lwc.CrosshairMode.Normal },
        rightPriceScale: { borderColor: gridColor },
        timeScale: {
          borderColor: gridColor,
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 8,
          barSpacing: 6,
        },
        handleScroll: true,
        handleScale: true,
        width: containerRef.current!.clientWidth,
        height: 420,
      });

      chartRef.current = chart;

      // Candlestick series (v5 API: chart.addSeries(CandlestickSeries))
      candleSeriesRef.current = chart.addSeries(lwc.CandlestickSeries, {
        upColor: '#059669',
        downColor: '#DC2626',
        borderUpColor: '#047857',
        borderDownColor: '#B91C1C',
        wickUpColor: '#047857',
        wickDownColor: '#B91C1C',
      });

      // Volume histogram (priceScaleId keeps it below candles)
      volumeSeriesRef.current = chart.addSeries(lwc.HistogramSeries, {
        color: '#059669',
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });
      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.80, bottom: 0 },
      });

      // Crosshair tooltip
      chart.subscribeCrosshairMove((param: any) => {
        if (!param.point || !param.time) { setTooltip(null); return; }
        const candle = param.seriesData.get(candleSeriesRef.current);
        const vol   = param.seriesData.get(volumeSeriesRef.current);
        if (candle) {
          setTooltip({
            time: param.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            change: ((candle.close - candle.open) / candle.open) * 100,
            volume: vol?.value ?? 0,
          });
        }
      });

      // Resize observer
      ro = new ResizeObserver((entries) => {
        if (entries[0] && chartRef.current) {
          chartRef.current.applyOptions({ width: entries[0].contentRect.width });
        }
      });
      ro.observe(containerRef.current!);
    };

    initChart();

    return () => {
      if (ro) ro.disconnect();
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaySeriesRefs.current = [];
    };
  // Only re-init chart when theme actually changes (not data)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDark]);

  // ─── Step 2: Apply overlays to existing chart (no rebuild) ──────────────
  const applyOverlays = useCallback(async (candles: any[]) => {
    if (!chartRef.current || !candles.length) return;
    const lwc = await import('lightweight-charts');

    // Remove all old overlay series
    overlaySeriesRefs.current.forEach((s) => {
      try { chartRef.current.removeSeries(s); } catch {}
    });
    overlaySeriesRefs.current = [];

    if (overlays.includes('VWAP') && candles.length > 0) {
      const s = chartRef.current.addSeries(lwc.LineSeries, { color: '#F59E0B', lineWidth: 1, lineStyle: 2, title: 'VWAP' });
      s.setData(calcVWAP(candles));
      overlaySeriesRefs.current.push(s);
    }
    if (overlays.includes('EMA 20') && candles.length >= 20) {
      const s = chartRef.current.addSeries(lwc.LineSeries, { color: '#06B6D4', lineWidth: 1.5, title: 'EMA20' });
      s.setData(calcEMA(candles, 20));
      overlaySeriesRefs.current.push(s);
    }
    if (overlays.includes('EMA 50') && candles.length >= 50) {
      const s = chartRef.current.addSeries(lwc.LineSeries, { color: '#8B5CF6', lineWidth: 1.5, title: 'EMA50' });
      s.setData(calcEMA(candles, 50));
      overlaySeriesRefs.current.push(s);
    }
    if (overlays.includes('EMA 200') && candles.length >= 200) {
      const s = chartRef.current.addSeries(lwc.LineSeries, { color: '#F97316', lineWidth: 2, title: 'EMA200' });
      s.setData(calcEMA(candles, 200));
      overlaySeriesRefs.current.push(s);
    }
    if (overlays.includes('BB') && candles.length >= 20) {
      const { upper, middle, lower } = calcBB(candles);
      const uS = chartRef.current.addSeries(lwc.LineSeries, { color: '#64748B', lineWidth: 1, lineStyle: 2, title: 'BB+2σ' });
      const mS = chartRef.current.addSeries(lwc.LineSeries, { color: '#FF6B35', lineWidth: 1, title: 'BB mid' });
      const lS = chartRef.current.addSeries(lwc.LineSeries, { color: '#64748B', lineWidth: 1, lineStyle: 2, title: 'BB-2σ' });
      uS.setData(upper); mS.setData(middle); lS.setData(lower);
      overlaySeriesRefs.current.push(uS, mS, lS);
    }
  }, [overlays]);

  // ─── Step 3: Fetch data — update existing series refs ───────────────────
  const fetchAndUpdate = useCallback(async (tf: string) => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return;
    setLoading(true);
    setError(null);
    setTooltip(null);

    try {
      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/price/${encodeURIComponent(ticker)}?period=${encodeURIComponent(tf)}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `API error ${resp.status}`);
      }
      const json = await resp.json();

      // Validate and clean candles
      const candles: any[] = (json.candles || [])
        .filter((c: any) => c.time && c.open != null && c.high != null && c.low != null && c.close != null)
        .map((c: any) => ({
          time: typeof c.time === 'number' ? c.time : Math.floor(new Date(c.time).getTime() / 1000),
          open:  Number(c.open),
          high:  Number(c.high),
          low:   Number(c.low),
          close: Number(c.close),
          volume: Number(c.volume ?? 0),
        }))
        .sort((a: any, b: any) => a.time - b.time); // ascending required by LWC

      if (!candles.length) throw new Error(`No data returned for ${ticker} (${tf})`);

      // Volume bars from API or derived from candles
      const volumeBars: any[] = (json.volume?.length ? json.volume : candles).map((c: any) => ({
        time:  c.time,
        value: c.volume ?? c.value ?? 0,
        color: (c.close ?? c.value ?? 0) >= (c.open ?? 0) ? '#05966966' : '#DC262666',
      }));

      // ✅ Update EXISTING series — do NOT remove/re-create chart
      candleSeriesRef.current.setData(candles);
      volumeSeriesRef.current.setData(volumeBars);

      // Fit all data into view
      chartRef.current?.timeScale().fitContent();

      // Store for overlay reuse
      latestData.current = candles;

      // Apply overlays on top of fresh data
      await applyOverlays(candles);

    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [ticker, applyOverlays]);

  // ─── Fetch when period changes (or chart is ready) ───────────────────────
  useEffect(() => {
    // Wait for chart to be ready (slight delay after isDark effect initialises it)
    const timer = setTimeout(() => {
      fetchAndUpdate(activePeriod);
    }, 50);
    return () => clearTimeout(timer);
  }, [activePeriod, fetchAndUpdate]);

  // ─── Re-apply overlays when overlay toggle changes (no refetch) ──────────
  useEffect(() => {
    if (latestData.current.length > 0) applyOverlays(latestData.current);
  }, [overlays, applyOverlays]);

  const toggleOverlay = (o: string) =>
    setOverlays((prev) => prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]);

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="w-full space-y-2">
      {/* Period + Overlay controls */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        {/* Timeframe buttons */}
        <div className="flex items-center gap-1">
          {TIMEFRAMES.map(({ label, api }) => (
            <button
              key={label}
              onClick={() => setActivePeriod(api)}
              className="text-xs px-2.5 py-1 rounded font-medium transition-all duration-150"
              style={{
                background: activePeriod === api ? '#FF6B35' : 'transparent',
                color: activePeriod === api ? '#fff' : textColor,
                border: `1px solid ${activePeriod === api ? '#FF6B35' : gridColor}`,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Overlay buttons */}
        <div className="flex items-center gap-1 flex-wrap">
          {OVERLAY_BUTTONS.map((o) => (
            <button
              key={o}
              onClick={() => toggleOverlay(o)}
              className="text-xs px-2 py-0.5 rounded font-medium transition-all duration-150"
              style={{
                background: overlays.includes(o) ? '#FF6B35' : 'transparent',
                color: overlays.includes(o) ? '#fff' : textColor,
                border: `1px solid ${overlays.includes(o) ? '#FF6B35' : gridColor}`,
              }}
            >
              {o}
            </button>
          ))}
        </div>
      </div>

      {/* OHLCV Tooltip bar */}
      {tooltip && (
        <div className="text-xs flex items-center gap-3 px-2 py-1 rounded border border-border/50"
          style={{ background: isDark ? '#0F172A' : '#F8FAFC', color: textColor }}>
          <span className="font-mono text-text-muted">{String(tooltip.time)}</span>
          <span>O <b>{formatPrice(tooltip.open)}</b></span>
          <span>H <b style={{ color: '#059669' }}>{formatPrice(tooltip.high)}</b></span>
          <span>L <b style={{ color: '#DC2626' }}>{formatPrice(tooltip.low)}</b></span>
          <span>C <b style={{ color: tooltip.close >= tooltip.open ? '#059669' : '#DC2626' }}>{formatPrice(tooltip.close)}</b></span>
          <span style={{ color: tooltip.change >= 0 ? '#059669' : '#DC2626' }}>
            {tooltip.change >= 0 ? '▲' : '▼'} {formatPct(Math.abs(tooltip.change))}
          </span>
          <span className="text-text-muted">Vol {formatVolume(tooltip.volume)}</span>
        </div>
      )}

      {/* Loading / Error states */}
      {loading && <ChartSkeleton height={420} />}
      {!loading && error && (
        <div className="flex flex-col items-center justify-center h-48 gap-2 rounded-lg border border-red-500/30 bg-red-500/5">
          <p className="text-sm text-red-400 font-medium">⚠ {error}</p>
          <button
            onClick={() => fetchAndUpdate(activePeriod)}
            className="text-xs px-3 py-1 bg-surface-raised rounded text-text-secondary hover:text-text-primary border border-border"
          >
            Retry
          </button>
        </div>
      )}

      {/* Chart container — always rendered so chart can mount into it */}
      <div
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height: '420px', display: loading || error ? 'none' : 'block' }}
      />
    </div>
  );
}
