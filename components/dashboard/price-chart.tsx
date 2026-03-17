"use client";
import { useState, useMemo } from "react";
import useSWR from "swr";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Area, CartesianGrid,
} from "recharts";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";
import { getPrediction } from "@/lib/api-client";
import type { PredictResponse } from "@/lib/api-client";

const TIMEFRAMES = ["1W", "1M", "3M", "6M", "1Y"] as const;

function calcEMA(prices: number[], period: number): number[] {
  const k = 2 / (period + 1);
  return prices.reduce<number[]>((acc, price, i) => {
    acc.push(i === 0 ? price : price * k + acc[i - 1] * (1 - k));
    return acc;
  }, []);
}

function ChartTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ payload: { date: string; open?: number; high?: number; low?: number; close?: number; volume?: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  const bullish = (d.close ?? 0) >= (d.open ?? 0);
  return (
    <div className="bg-surface border border-border rounded-card p-3 shadow-elevated text-xs">
      <div className="font-medium text-text-primary mb-1">{d.date}</div>
      <div className="space-y-0.5">
        {d.open != null && (
          <div className="flex gap-3">
            <span className="text-text-muted">O</span>
            <span className="text-text-primary tabular-nums">₹{d.open.toFixed(2)}</span>
            <span className="text-text-muted">H</span>
            <span className="text-bullish-green tabular-nums">₹{d.high?.toFixed(2)}</span>
          </div>
        )}
        {d.low != null && (
          <div className="flex gap-3">
            <span className="text-text-muted">L</span>
            <span className="text-bearish-red tabular-nums">₹{d.low.toFixed(2)}</span>
            <span className="text-text-muted">C</span>
            <span className={cn("tabular-nums font-medium", bullish ? "text-bullish-green" : "text-bearish-red")}>
              ₹{d.close?.toFixed(2)}
            </span>
          </div>
        )}
        {d.volume != null && d.volume > 0 && (
          <div className="text-text-muted">Vol: {(d.volume / 1_000_000).toFixed(1)}M</div>
        )}
      </div>
    </div>
  );
}

export function PriceChart() {
  const [timeframe, setTimeframe] = useState<typeof TIMEFRAMES[number]>("3M");
  const [showEMA20, setShowEMA20] = useState(true);
  const [showEMA50, setShowEMA50] = useState(false);

  const { selectedTicker, analysisData, horizon } = useApp();

  // Fetch real prediction for forecast band
  const { data: prediction } = useSWR<PredictResponse>(
    analysisData ? `predict-${selectedTicker}-${horizon}` : null,
    () => getPrediction(selectedTicker, horizon),
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );

  const forecastBand = useMemo(() => {
    if (!prediction || prediction.p10 == null || prediction.p90 == null || prediction.p50 == null) return [];
    const today = new Date();
    return Array.from({ length: horizon }, (_, i) => {
      const d = new Date(today);
      d.setDate(d.getDate() + i + 1);
      return {
        date: d.toISOString().split("T")[0],
        p10: prediction.p10!,
        p50: prediction.p50!,
        p90: prediction.p90!,
        isForecast: true,
      };
    });
  }, [prediction, horizon]);

  // Without a dedicated price history endpoint, display a placeholder message
  // showing the forecast band and key stats from the analysis response
  const placeholderData = useMemo(() => {
    if (!analysisData) return [];
    const base = analysisData.price_target_p50 ?? 0;
    if (base === 0) return [];
    const today = new Date();
    // Create a minimal 2-point placeholder to anchor the chart when no price history endpoint exists
    return [
      {
        date: new Date(today.getTime() - 86400000 * 5).toISOString().split("T")[0],
        close: base,
        open: base,
        high: base,
        low: base,
        volume: 0,
      },
      {
        date: today.toISOString().split("T")[0],
        close: base,
        open: base,
        high: base,
        low: base,
        volume: 0,
      },
    ];
  }, [analysisData]);

  const combined = useMemo(() => {
    const hist = placeholderData.map((d, i) => ({
      ...d,
      ema20: calcEMA(placeholderData.map((x) => x.close), 20)[i],
      ema50: calcEMA(placeholderData.map((x) => x.close), 50)[i],
    }));
    return [...hist, ...forecastBand];
  }, [placeholderData, forecastBand]);

  const priceMin = useMemo(() => {
    const vals = combined.flatMap((d) => [
      d.low ?? d.close ?? d.p10 ?? Infinity,
      d.p10 ?? Infinity,
    ]).filter(isFinite);
    return vals.length ? Math.min(...vals) * 0.995 : 0;
  }, [combined]);

  const priceMax = useMemo(() => {
    const vals = combined.flatMap((d) => [
      d.high ?? d.close ?? d.p90 ?? 0,
      d.p90 ?? 0,
    ]).filter((v) => v > 0);
    return vals.length ? Math.max(...vals) * 1.005 : 1;
  }, [combined]);

  const noData = combined.length === 0;

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-text-primary">Price Chart</h3>
          <HelpPopover
            content={{
              title: "Price Chart — AI Forecast",
              body: "The saffron band shows the AI forecast confidence range (P10–P90) for the selected horizon. Historical OHLCV requires a dedicated price endpoint.",
              affectsVerdict: "Price action relative to EMA20/EMA50 influences the Quant Agent's technical score.",
              source: "Predictions: XGBoost/LightGBM/CatBoost + Chronos-2 ensemble",
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

      {noData ? (
        <div className="h-64 flex items-center justify-center">
          <p className="text-sm text-text-muted text-center">
            Run analysis to generate AI forecast band.
          </p>
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={combined} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border, #E2E8F0)" opacity={0.4} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "#94A3B8" }}
                tickLine={false}
                axisLine={false}
                interval={Math.max(0, Math.floor(combined.length / 6))}
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
                width={65}
                tickFormatter={(v) => `₹${v.toFixed(0)}`}
              />
              <Tooltip content={<ChartTooltip />} />

              {/* Forecast confidence band */}
              <Area
                yAxisId="0"
                data={forecastBand}
                dataKey="p90"
                stroke="none"
                fill="#FF6B00"
                fillOpacity={0.1}
              />
              <Area
                yAxisId="0"
                data={forecastBand}
                dataKey="p10"
                stroke="none"
                fill="#ffffff"
                fillOpacity={1}
              />

              {/* Historical close line */}
              <Line
                yAxisId="0"
                type="monotone"
                dataKey="close"
                stroke="#64748B"
                strokeWidth={2}
                dot={false}
                name="Close"
                connectNulls={false}
              />

              {/* EMAs */}
              {showEMA20 && (
                <Line yAxisId="0" type="monotone" dataKey="ema20"
                  stroke="#FF6B00" strokeWidth={1.5} dot={false} name="EMA20" />
              )}
              {showEMA50 && (
                <Line yAxisId="0" type="monotone" dataKey="ema50"
                  stroke="#1D4ED8" strokeWidth={1.5} dot={false} name="EMA50" strokeDasharray="4 2" />
              )}

              {/* Forecast P50 */}
              <Line
                yAxisId="0"
                data={forecastBand}
                type="monotone"
                dataKey="p50"
                stroke="#FF6B00"
                strokeWidth={2}
                strokeDasharray="5 3"
                dot={false}
                name="Forecast P50"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Overlay toggles */}
      <div className="flex gap-2 mt-3 flex-wrap">
        {[
          { label: "EMA20", active: showEMA20, toggle: () => setShowEMA20((v) => !v) },
          { label: "EMA50", active: showEMA50, toggle: () => setShowEMA50((v) => !v) },
        ].map(({ label, active, toggle }) => (
          <button
            key={label}
            onClick={toggle}
            className={cn(
              "px-2.5 py-1 text-xs rounded-badge border font-medium transition-all duration-150",
              active
                ? "bg-saffron-light text-saffron border-saffron/30"
                : "border-border text-text-muted hover:text-text-primary hover:bg-surface-raised"
            )}
          >
            {label}
          </button>
        ))}
        {forecastBand.length > 0 && (
          <span className="text-xs text-text-muted self-center ml-1">
            Saffron band = AI forecast P10–P90 ({horizon}-day)
          </span>
        )}
      </div>

      {/* Prediction summary if available */}
      {prediction && (
        <div className="mt-3 p-3 bg-surface-raised rounded-btn text-xs text-text-secondary">
          <span className="font-medium text-text-primary">{prediction.direction}</span>
          {" "}— {(prediction.confidence * 100).toFixed(1)}% confidence
          {" "}via {prediction.model_used}
          {prediction.p50 != null && (
            <> — P50 target: <span className="tabular-nums font-medium">
              ₹{prediction.p50.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span></>
          )}
        </div>
      )}
    </div>
  );
}
