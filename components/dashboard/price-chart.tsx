"use client";
import { useMemo } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import { useApp } from "@/lib/app-context";
import { getPrediction } from "@/lib/api-client";
import type { PredictResponse } from "@/lib/api-client";
import { HelpPopover } from "@/components/ui/help-popover";

// CandlestickChart uses Lightweight Charts — must be dynamic ssr:false
const CandlestickChart = dynamic(
  () => import("@/components/charts/CandlestickChart").then((m) => m.CandlestickChart),
  { ssr: false, loading: () => <div className="h-[420px] animate-pulse bg-surface-raised rounded-lg" /> }
);

export function PriceChart() {
  const { selectedTicker, analysisData, horizon } = useApp();

  // Fetch AI forecast band from /predict
  const { data: prediction } = useSWR<PredictResponse>(
    analysisData && selectedTicker ? `predict-${selectedTicker}-${horizon}` : null,
    () => getPrediction(selectedTicker, horizon),
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );

  // Prediction summary line
  const forecastSummary = useMemo(() => {
    if (!prediction) return null;
    const dir = prediction.direction ?? "—";
    const conf = prediction.confidence != null ? `${(prediction.confidence * 100).toFixed(1)}%` : null;
    const p50 = prediction.p50 != null
      ? `₹${prediction.p50.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
      : null;
    return { dir, conf, p50, model: prediction.model_used };
  }, [prediction]);

  // If no ticker selected yet — show empty state
  if (!selectedTicker) {
    return (
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Price Chart</h3>
        <div className="h-64 flex flex-col items-center justify-center gap-2">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          <p className="text-sm text-text-muted">Search for a stock to display the candlestick chart</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card-base p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-base font-semibold text-text-primary">
          Price Chart — {selectedTicker.replace(".NS", "").replace(".BO", "")}
        </h3>
        <HelpPopover
          content={{
            title: "Live Candlestick Chart",
            body:
              "Real NSE OHLCV data from yfinance. Use the period buttons (1D–2Y) to change the timeframe. Overlays: VWAP, EMA20, EMA50, EMA200, Bollinger Bands.",
            level: "beginner",
            tips: [
              "Green candle = close ≥ open (bullish bar)",
              "Red candle = close < open (bearish bar)",
              "Volume bars shown in sub-pane below",
              "VWAP = Volume Weighted Average Price (institutional reference)",
            ],
            affectsVerdict: "The candlestick chart is for visual confirmation only — the AI verdict comes from the ML ensemble, not chart patterns.",
            source: "yfinance NSE data via GET /api/price/{ticker}?period=3M",
          }}
        />
      </div>

      {/* Candlestick Chart — full LWC implementation */}
      <CandlestickChart
        ticker={selectedTicker}
        period="3M"
        activeOverlays={["VWAP", "EMA 20", "EMA 50"]}
      />

      {/* AI Forecast summary bar (below chart) */}
      {forecastSummary && (
        <div className="mt-3 p-3 bg-surface-raised rounded-lg text-xs flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="font-semibold text-saffron">AI Forecast</span>
          <span className="text-text-primary font-medium">{forecastSummary.dir}</span>
          {forecastSummary.conf && (
            <span className="text-text-secondary">{forecastSummary.conf} confidence</span>
          )}
          {forecastSummary.model && (
            <span className="text-text-muted">via {forecastSummary.model}</span>
          )}
          {forecastSummary.p50 && (
            <span className="ml-auto font-mono font-semibold text-text-primary">
              P50 target: {forecastSummary.p50}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
