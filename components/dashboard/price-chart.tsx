"use client";
import { useState, useMemo } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Area, CartesianGrid
} from "recharts";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { MOCK_PRICE_DATA, MOCK_FORECAST } from "@/lib/mock-data";

const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y"] as const;
const OVERLAYS = ["VWAP", "EMA20", "EMA50", "BB Bands", "Volume"] as const;

function calcEMA(data: { close: number }[], period: number): number[] {
  const k = 2 / (period + 1);
  const ema: number[] = [];
  data.forEach((d, i) => {
    if (i === 0) { ema.push(d.close); return; }
    ema.push(d.close * k + ema[i - 1] * (1 - k));
  });
  return ema;
}

// Custom candlestick bar shape
function CandlestickBar(props: {
  x?: number; y?: number; width?: number; height?: number;
  open?: number; close?: number; high?: number; low?: number;
  yAxisMap?: Record<string, { scale: (v: number) => number }>;
  payload?: { open: number; close: number; high: number; low: number };
}) {
  const { x = 0, width = 8, payload, yAxisMap } = props;
  if (!payload || !yAxisMap) return null;
  const { open, close, high, low } = payload;
  const scale = yAxisMap["0"]?.scale;
  if (!scale) return null;

  const bullish = close >= open;
  const color = bullish ? "#059669" : "#DC2626";
  const bodyTop = scale(Math.max(open, close));
  const bodyBottom = scale(Math.min(open, close));
  const wickTop = scale(high);
  const wickBottom = scale(low);
  const bodyH = Math.max(1, bodyBottom - bodyTop);
  const cx = x + width / 2;

  return (
    <g>
      {/* Wick */}
      <line x1={cx} y1={wickTop} x2={cx} y2={wickBottom} stroke={color} strokeWidth={1} />
      {/* Body */}
      <rect x={x + 1} y={bodyTop} width={width - 2} height={bodyH} fill={color} rx={1} />
    </g>
  );
}

// Tooltip
function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { date: string; open: number; high: number; low: number; close: number; volume: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const bullish = d.close >= d.open;
  return (
    <div className="bg-surface border border-border rounded-card p-3 shadow-elevated text-xs">
      <div className="font-medium text-text-primary mb-1">{d.date}</div>
      <div className="space-y-0.5">
        <div className="flex gap-3">
          <span className="text-text-muted">O</span><span className="text-text-primary tabular-nums">₹{d.open?.toFixed(2)}</span>
          <span className="text-text-muted">H</span><span className="text-bullish-green tabular-nums">₹{d.high?.toFixed(2)}</span>
        </div>
        <div className="flex gap-3">
          <span className="text-text-muted">L</span><span className="text-bearish-red tabular-nums">₹{d.low?.toFixed(2)}</span>
          <span className="text-text-muted">C</span>
          <span className={cn("tabular-nums font-medium", bullish ? "text-bullish-green" : "text-bearish-red")}>₹{d.close?.toFixed(2)}</span>
        </div>
        <div className="text-text-muted">Vol: {(d.volume / 1_000_000).toFixed(1)}M</div>
      </div>
    </div>
  );
}

export function PriceChart() {
  const [timeframe, setTimeframe] = useState<typeof TIMEFRAMES[number]>("3M");
  const [activeOverlays, setActiveOverlays] = useState<Set<string>>(new Set(["EMA20", "Volume"]));

  const toggleOverlay = (o: string) => {
    setActiveOverlays((prev) => {
      const next = new Set(prev);
      next.has(o) ? next.delete(o) : next.add(o);
      return next;
    });
  };

  const daysMap: Record<typeof TIMEFRAMES[number], number> = {
    "1D": 1, "1W": 5, "1M": 22, "3M": 60, "6M": 130, "1Y": 252
  };
  const days = daysMap[timeframe];

  const chartData = useMemo(() => {
    const slice = MOCK_PRICE_DATA.slice(-Math.min(days, MOCK_PRICE_DATA.length));
    const ema20 = calcEMA(slice, 20);
    const ema50 = calcEMA(slice, 50);
    return slice.map((d, i) => ({
      ...d,
      ema20: +ema20[i].toFixed(2),
      ema50: +ema50[i].toFixed(2),
    }));
  }, [days]);

  // Forecast data — append to end
  const forecastData = useMemo(() => MOCK_FORECAST.map((f) => ({
    date: f.date,
    open: f.p50, high: f.p90, low: f.p10, close: f.p50,
    volume: 0,
    p10: f.p10, p50: f.p50, p90: f.p90,
    isForecast: true,
  })), []);

  const priceMin = useMemo(() => Math.min(...chartData.map((d) => d.low)) * 0.995, [chartData]);
  const priceMax = useMemo(() => Math.max(...chartData.map((d) => d.high)) * 1.005, [chartData]);

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-text-primary">Price Chart</h3>
          <HelpPopover
            content={{
              title: "Price Chart — OHLCV",
              body: "Interactive candlestick chart showing Open, High, Low, Close prices with volume. The saffron shaded region ahead shows the AI forecast confidence band (P10–P90).",
              affectsVerdict: "Price action relative to EMA20/EMA50 and volume confirmation directly influence the Quant Agent's technical score.",
              source: "NSE India via yfinance — 1-minute aggregated to daily OHLCV",
            }}
          />
        </div>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-badge font-medium transition-all duration-150",
                timeframe === tf
                  ? "bg-saffron text-white"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-raised"
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Main chart */}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border, #E2E8F0)" opacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#94A3B8" }}
              tickLine={false}
              axisLine={false}
              interval={Math.floor(chartData.length / 6)}
              tickFormatter={(v) => {
                const d = new Date(v);
                return `${d.getDate()}/${d.getMonth() + 1}`;
              }}
            />
            <YAxis
              yAxisId="0"
              domain={[priceMin, priceMax]}
              tick={{ fontSize: 10, fill: "#94A3B8" }}
              tickLine={false}
              axisLine={false}
              width={60}
              tickFormatter={(v) => `₹${v.toFixed(0)}`}
            />
            <Tooltip content={<ChartTooltip />} />

            {/* Forecast confidence band */}
            <Area
              data={forecastData}
              dataKey="p90"
              stroke="none"
              fill="#FF6B00"
              fillOpacity={0.08}
              yAxisId="0"
            />

            {/* Candlestick bars */}
            <Bar dataKey="close" yAxisId="0" shape={<CandlestickBar />} isAnimationActive={false} />

            {/* EMA20 */}
            {activeOverlays.has("EMA20") && (
              <Line
                yAxisId="0"
                type="monotone"
                dataKey="ema20"
                stroke="#FF6B00"
                strokeWidth={1.5}
                dot={false}
                name="EMA20"
              />
            )}
            {/* EMA50 */}
            {activeOverlays.has("EMA50") && (
              <Line
                yAxisId="0"
                type="monotone"
                dataKey="ema50"
                stroke="#1D4ED8"
                strokeWidth={1.5}
                dot={false}
                name="EMA50"
                strokeDasharray="4 2"
              />
            )}

            {/* Forecast P50 dashed line */}
            <Line
              data={forecastData}
              yAxisId="0"
              type="monotone"
              dataKey="p50"
              stroke="#FF6B00"
              strokeWidth={2}
              strokeDasharray="5 3"
              dot={false}
              name="Forecast"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Volume bars */}
      {activeOverlays.has("Volume") && (
        <div className="h-14 w-full mt-1 border-t border-border pt-1">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis yAxisId="0" hide />
              <Bar yAxisId="0" dataKey="volume" fill="#64748B" opacity={0.4} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Overlay toggles */}
      <div className="flex gap-2 mt-3 flex-wrap">
        {OVERLAYS.map((o) => (
          <button
            key={o}
            onClick={() => toggleOverlay(o)}
            className={cn(
              "px-2.5 py-1 text-xs rounded-badge border font-medium transition-all duration-150",
              activeOverlays.has(o)
                ? "bg-saffron-light text-saffron border-saffron/30"
                : "border-border text-text-muted hover:text-text-primary hover:bg-surface-raised"
            )}
          >
            {o}
          </button>
        ))}
        <span className="text-xs text-text-muted self-center ml-1">
          Saffron band = AI forecast (P10–P90)
        </span>
      </div>
    </div>
  );
}
