'use client';

import { useEffect, useState } from 'react';
import { CHART_COLORS } from '@/lib/chart-theme';
import { formatPrice } from '@/lib/format-india';

export interface PivotTableProps {
  ticker: string;
}

interface PivotLevels {
  pp: number;
  r1: number; r2: number; r3: number;
  s1: number; s2: number; s3: number;
  // Camarilla
  h1: number; h2: number; h3: number; h4: number;
  l1: number; l2: number; l3: number; l4: number;
  high: number; low: number; close: number;
}

function computePivots(high: number, low: number, close: number): PivotLevels {
  const pp = (high + low + close) / 3;
  const r1 = 2 * pp - low;
  const r2 = pp + (high - low);
  const r3 = high + 2 * (pp - low);
  const s1 = 2 * pp - high;
  const s2 = pp - (high - low);
  const s3 = low - 2 * (high - pp);
  // Camarilla
  const range = high - low;
  const h4 = close + range * 1.1 / 2;
  const h3 = close + range * 1.1 / 4;
  const h2 = close + range * 1.1 / 6;
  const h1 = close + range * 1.1 / 12;
  const l1 = close - range * 1.1 / 12;
  const l2 = close - range * 1.1 / 6;
  const l3 = close - range * 1.1 / 4;
  const l4 = close - range * 1.1 / 2;
  return { pp, r1, r2, r3, s1, s2, s3, h1, h2, h3, h4, l1, l2, l3, l4, high, low, close };
}

function getLevelZone(level: string, currentPrice: number, pivots: PivotLevels): string {
  const levels = [
    { name: 's3', val: pivots.s3 }, { name: 's2', val: pivots.s2 }, { name: 's1', val: pivots.s1 },
    { name: 'pp', val: pivots.pp },
    { name: 'r1', val: pivots.r1 }, { name: 'r2', val: pivots.r2 }, { name: 'r3', val: pivots.r3 },
  ].sort((a, b) => a.val - b.val);
  for (let i = 0; i < levels.length - 1; i++) {
    if (currentPrice >= levels[i].val && currentPrice <= levels[i + 1].val) {
      return `Price is between ${levels[i].name.toUpperCase()} and ${levels[i + 1].name.toUpperCase()}`;
    }
  }
  if (currentPrice < levels[0].val) return 'Price is below S3 — extreme weakness';
  return 'Price is above R3 — extreme strength';
}

export function PivotTable({ ticker }: PivotTableProps) {
  const [pivots, setPivots] = useState<PivotLevels | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'classic' | 'camarilla'>('classic');
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/price/${encodeURIComponent(ticker)}?period=5d`
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        const bars: { open: number; high: number; low: number; close: number }[] = json.bars || json.ohlcv || [];
        if (bars.length < 2) throw new Error('Insufficient price data');
        const prev = bars[bars.length - 2];
        const last = bars[bars.length - 1];
        setPivots(computePivots(prev.high, prev.low, prev.close));
        setCurrentPrice(last.close);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [ticker, retryCount]);

  if (loading) return (
    <div className="h-28 bg-surface-raised animate-pulse rounded-card" />
  );

  if (error || !pivots) {
    return (
      <div className="border border-bearish-red/40 rounded-card p-4 text-center space-y-1">
        <p className="text-bearish-red font-medium text-sm">Failed to load pivot points</p>
        <p className="text-xs text-text-muted">{error}</p>
        <button onClick={() => setRetryCount(c => c + 1)} className="text-xs text-saffron underline">Retry</button>
      </div>
    );
  }

  const classicCells = [
    { key: 's3', label: 'S3', value: pivots.s3, bg: 'bg-emerald-950/60', text: 'text-emerald-300' },
    { key: 's2', label: 'S2', value: pivots.s2, bg: 'bg-emerald-900/50', text: 'text-emerald-400' },
    { key: 's1', label: 'S1', value: pivots.s1, bg: 'bg-emerald-800/40', text: 'text-emerald-400' },
    { key: 'pp', label: 'PP', value: pivots.pp, bg: 'bg-saffron/15', text: 'text-saffron font-bold' },
    { key: 'r1', label: 'R1', value: pivots.r1, bg: 'bg-red-800/40', text: 'text-red-400' },
    { key: 'r2', label: 'R2', value: pivots.r2, bg: 'bg-red-900/50', text: 'text-red-300' },
    { key: 'r3', label: 'R3', value: pivots.r3, bg: 'bg-red-950/60', text: 'text-red-200' },
  ];

  const camarillaCells = [
    { key: 'l4', label: 'L4', value: pivots.l4, bg: 'bg-emerald-950/60', text: 'text-emerald-300' },
    { key: 'l3', label: 'L3', value: pivots.l3, bg: 'bg-emerald-900/50', text: 'text-emerald-400' },
    { key: 'l2', label: 'L2', value: pivots.l2, bg: 'bg-emerald-800/40', text: 'text-emerald-400' },
    { key: 'l1', label: 'L1', value: pivots.l1, bg: 'bg-emerald-700/30', text: 'text-emerald-400' },
    { key: 'h1', label: 'H1', value: pivots.h1, bg: 'bg-red-700/30', text: 'text-red-400' },
    { key: 'h2', label: 'H2', value: pivots.h2, bg: 'bg-red-800/40', text: 'text-red-400' },
    { key: 'h3', label: 'H3', value: pivots.h3, bg: 'bg-red-900/50', text: 'text-red-300' },
    { key: 'h4', label: 'H4', value: pivots.h4, bg: 'bg-red-950/60', text: 'text-red-200' },
  ];

  const cells = mode === 'classic' ? classicCells : camarillaCells;
  const zoneText = currentPrice ? getLevelZone('', currentPrice, pivots) : '';

  return (
    <div className="w-full space-y-3">
      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        {(['classic', 'camarilla'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1 rounded-btn text-xs font-medium capitalize transition-colors ${
              mode === m
                ? 'bg-saffron/20 text-saffron border border-saffron/40'
                : 'text-text-muted border border-border hover:border-saffron/30'
            }`}
          >
            {m}
          </button>
        ))}
        {currentPrice && (
          <span className="ml-auto text-xs text-text-muted">
            CMP: <span className="text-saffron font-semibold">{formatPrice(currentPrice)}</span>
          </span>
        )}
      </div>

      {/* Pivot cells row */}
      <div className={`grid gap-1 ${mode === 'classic' ? 'grid-cols-7' : 'grid-cols-8'}`}>
        {cells.map(({ key, label, value, bg, text }) => {
          const isActive = currentPrice != null && Math.abs(value - currentPrice) < (pivots.r1 - pivots.pp) * 0.5;
          return (
            <div
              key={key}
              className={`${bg} rounded-md p-2 text-center relative ${isActive ? 'ring-1 ring-saffron/60' : ''}`}
            >
              <div className="text-[10px] font-bold text-text-muted mb-0.5">{label}</div>
              <div className={`text-[11px] font-semibold ${text} tabular-nums`}>
                {formatPrice(value)}
              </div>
              {isActive && currentPrice && (
                <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-saffron shadow-[0_0_6px_#FF6B00]" />
              )}
            </div>
          );
        })}
      </div>

      {/* Zone description */}
      {zoneText && (
        <p className="text-xs text-text-muted text-center">{zoneText}</p>
      )}

      {/* Input data */}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span>Prev H: <span className="text-text-primary">{formatPrice(pivots.high)}</span></span>
        <span>Prev L: <span className="text-text-primary">{formatPrice(pivots.low)}</span></span>
        <span>Prev C: <span className="text-text-primary">{formatPrice(pivots.close)}</span></span>
      </div>
    </div>
  );
}
