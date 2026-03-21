"use client";
import { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";
import { getPrediction } from "@/lib/api-client";
import type { PredictResponse } from "@/lib/api-client";
import { ChartSkeleton } from "@/components/charts";

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={256} />,
});


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

  // No price history endpoint is implemented yet — chart shows only the AI forecast band
  // anchored to the P50 price target. Historical OHLCV requires GET /price-history/{ticker}.
  const anchorData = useMemo(() => {
    if (!analysisData) return [];
    const base = analysisData.price_target_p50;
    if (base == null || base === 0) return [];
    const today = new Date();
    // Single anchor point at today's P50 so the forecast band has a left edge
    return [
      {
        date: today.toISOString().split("T")[0],
        close: base,
        open: base,
        high: base,
        low: base,
        volume: 0,
        ema20: undefined as number | undefined,
        ema50: undefined as number | undefined,
      },
    ];
  }, [analysisData]);

  const combined = useMemo(() => {
    return [...anchorData, ...forecastBand];
  }, [anchorData, forecastBand]);

  const priceMin = useMemo(() => {
    const vals = combined.flatMap((d: any) => [
      d.low ?? d.close ?? d.p10 ?? Infinity,
      d.p10 ?? Infinity,
    ]).filter(isFinite);
    return vals.length ? Math.min(...vals) * 0.995 : 0;
  }, [combined]);

  const priceMax = useMemo(() => {
    const vals = combined.flatMap((d: any) => [
      d.high ?? d.close ?? d.p90 ?? 0,
      d.p90 ?? 0,
    ]).filter((v: number) => v > 0);
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
              title: "AI Price Forecast Chart",
              body: "After running an analysis, the chart shows the Chronos-2 probabilistic forecast band for the selected time horizon. The dashed line is the median (P50) target. The shaded band is the uncertainty range — P10 (bear case) to P90 (bull case). A narrow band means the model is confident; a wide band means high uncertainty.",
              level: "beginner",
              tips: [
                "P50 (dashed line) = the model's best guess for price at the horizon",
                "P10 lower band = your stop-loss reference level",
                "P90 upper band = your take-profit reference level",
                "Historical OHLCV chart requires the /price-history API endpoint",
              ],
              affectsVerdict: "The P50 forecast directly determines the 'Price Target' shown in the Verdict. Risk:Reward is (P90 - current) / (current - P10) — used to size positions.",
              source: "Chronos-2 (Amazon pretrained) + XGBoost/LightGBM/CatBoost ensemble price targets from /predict endpoint",
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
        <div className="h-64 flex flex-col items-center justify-center gap-3">
          <div className="w-10 h-10 rounded-full bg-surface-raised flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <p className="text-sm text-text-muted text-center">
            Run an analysis to see the AI price forecast band
          </p>
          <p className="text-xs text-text-muted/60 text-center max-w-xs">
            Historical OHLCV chart requires a <code className="text-text-secondary">GET /price-history</code> backend endpoint (not yet implemented)
          </p>
        </div>
      ) : (
        <div className="w-full">
          <Chart
            type="area"
            height={256}
            options={{
              chart: {
                type: 'area',
                toolbar: { show: false },
                animations: { enabled: true, speed: 600 },
                zoom: { enabled: false },
              },
              stroke: {
                curve: 'smooth',
                width: [0, 0, 2],
                dashArray: [0, 0, 5],
              },
              fill: {
                type: ['solid', 'solid', 'gradient'],
                opacity: [0.15, 1, 0.05],
              },
              colors: ['#FF6B00', '#0F172A', '#FF6B00'],
              xaxis: {
                categories: combined.map(d => d.date),
                labels: {
                  style: { colors: '#94A3B8', fontSize: '10px' },
                  formatter: (v: string) => {
                    const d = new Date(v);
                    return `${d.getDate()}/${d.getMonth() + 1}`;
                  },
                },
                axisBorder: { show: false },
                axisTicks: { show: false },
              },
              yaxis: {
                min: priceMin,
                max: priceMax,
                labels: {
                  style: { colors: '#94A3B8', fontSize: '10px' },
                  formatter: (v: number) => `₹${v.toFixed(0)}`,
                },
              },
              tooltip: {
                theme: 'dark',
                shared: true,
                y: { formatter: (v: number) => v ? `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '' },
              },
              grid: { borderColor: '#1E293B', strokeDashArray: 3 },
              legend: { show: false },
              markers: { size: 0 },
            }}
            series={[
              { name: 'P90 Bull', data: combined.map(d => (d as any).p90 || null) },
              { name: 'P10 Bear', data: combined.map(d => (d as any).p10 || null) },
              { name: 'P50 Forecast', data: combined.map(d => (d as any).p50 || (d as any).close || null) },
            ]}
          />
        </div>
      )}

      {/* Legend */}
      <div className="flex gap-3 mt-3 flex-wrap items-center">
        {forecastBand.length > 0 && (
          <>
            <div className="flex items-center gap-1.5">
              <div className="w-6 h-0.5 bg-saffron/30 border-t-2 border-saffron/20" style={{ borderStyle: "dashed" }} />
              <span className="text-xs text-text-muted">AI Forecast P50</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-3 rounded-sm bg-saffron/10 border border-saffron/20" />
              <span className="text-xs text-text-muted">P10–P90 band ({horizon}-day)</span>
            </div>
          </>
        )}
        <span className="text-xs text-text-muted/50 ml-auto">
          Historical OHLCV: connect <code className="text-text-secondary">GET /price-history</code>
        </span>
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
