"use client";
import useSWR from "swr";
import { useMemo } from "react";
import dynamic from "next/dynamic";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getPrediction, getApiErrorMessage } from "@/lib/api-client";
import { ChartSkeleton } from "@/components/charts";

const Chart = dynamic(() => import('react-apexcharts').then(m => m.default), {
  ssr: false,
  loading: () => <ChartSkeleton height={256} />,
});


const DIRECTION_COLORS: Record<string, string> = {
  "VERY_BULLISH": "#059669",
  "BULLISH": "#65A30D",
  "NEUTRAL": "#D97706",
  "BEARISH": "#EA580C",
  "VERY_BEARISH": "#DC2626",
};

const DIRECTION_LABELS: Record<string, string> = {
  "VERY_BULLISH": "Very Bullish",
  "BULLISH": "Bullish",
  "NEUTRAL": "Neutral",
  "BEARISH": "Bearish",
  "VERY_BEARISH": "Very Bearish",
};

export default function PredictionsPage() {
  const { selectedTicker, analysisData, horizon } = useApp();

  const { data: prediction, error, isLoading } = useSWR(
    selectedTicker ? ["prediction", selectedTicker, horizon] : null,
    () => getPrediction(selectedTicker, horizon),
    { revalidateOnFocus: false }
  );

  // Build a simple forecast table from P10/P50/P90 spread over horizon days
  const forecastRows = useMemo(() => {
    if (!prediction?.p50) return [];
    const base = prediction.p50;
    const step10 = prediction.p10 ? (prediction.p10 - base) / Math.max(horizon, 1) : 0;
    const step90 = prediction.p90 ? (prediction.p90 - base) / Math.max(horizon, 1) : 0;
    return Array.from({ length: Math.min(horizon, 10) }, (_, i) => ({
      day: i + 1,
      p10: prediction.p10 ? +(prediction.p10 + step10 * i).toFixed(2) : null,
      p50: +(base + ((prediction.p50! - base) / Math.max(horizon, 1)) * i).toFixed(2),
      p90: prediction.p90 ? +(prediction.p90 + step90 * i).toFixed(2) : null,
    }));
  }, [prediction, horizon]);

  // Class probabilities for bar chart
  const classProbs = useMemo(() => {
    if (!prediction?.class_probs) {
      // Build from direction + direction_prob if class_probs not returned
      if (!prediction) return [];
      return Object.entries(DIRECTION_LABELS).map(([key, label]) => ({
        key,
        label,
        pct: key === prediction.direction ? +(prediction.direction_prob * 100).toFixed(1) : +((100 - prediction.direction_prob * 100) / 4).toFixed(1),
        color: DIRECTION_COLORS[key] ?? "#94A3B8",
        isTop: key === prediction.direction,
      }));
    }
    return Object.entries(prediction.class_probs)
      .map(([key, val]) => ({
        key,
        label: DIRECTION_LABELS[key] ?? key,
        pct: +(val * 100).toFixed(1),
        color: DIRECTION_COLORS[key] ?? "#94A3B8",
        isTop: key === prediction.direction,
      }))
      .sort((a, b) => b.pct - a.pct);
  }, [prediction]);

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-72 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">AI Predictions</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load prediction data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
          <p className="text-xs text-text-muted mt-3">Run an analysis from the Dashboard first to generate predictions.</p>
        </div>
      </div>
    );
  }

  if (!prediction) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">AI Predictions</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="font-medium text-text-secondary mb-2">No prediction available</p>
          <p className="text-sm">Run an analysis from the Dashboard to generate AI predictions for {selectedTicker}.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">AI Predictions</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted">{selectedTicker}</span>
          <span className="text-xs px-2 py-0.5 rounded-badge bg-surface-raised text-text-muted font-medium">
            Model: {prediction.model_used}
          </span>
        </div>
      </div>

      {/* Forecast Table */}
      {forecastRows.length > 0 && (
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">
              AI Price Forecast — {horizon}-Day Horizon
            </h3>
            <HelpPopover content={{
              title: "Chronos-2 Probabilistic Price Forecast",
              body: "Amazon Chronos-2 is a state-of-the-art time-series model pre-trained on millions of real-world datasets. It does not predict direction — it predicts a range of likely prices. P10 is the pessimistic case (only 10% chance price goes below this), P50 is the median scenario, and P90 is the optimistic case.",
              level: "intermediate",
              tips: [
                "P50 = most likely price target over the selected horizon",
                "P10–P90 band width = uncertainty measure — wider band = less confident",
                "Horizon 5 days = very short-term swing trade target",
                "Horizon 30 days = medium-term positional trade target",
              ],
              affectsVerdict: "P50 is the primary price target shown in the verdict. If P50 > current price by more than 2%, it reinforces a BUY signal. The band width (P90-P10) affects position sizing — wide bands reduce conviction.",
              source: "Amazon Chronos-2 (pretrained, huggingface) with India-specific macro + technical covariates",
            }} />
          </div>

          <div>
            <Chart
              type="area"
              height={256}
              options={{
                chart: { type: 'area', toolbar: { show: false }, animations: { enabled: true } },
                stroke: { curve: 'smooth', width: [0, 0, 2.5], dashArray: [0, 0, 5] },
                fill: { type: ['solid', 'solid', 'gradient'], opacity: [0.2, 1, 0.05] },
                colors: ['#FF6B00', '#0F172A', '#FF6B00'],
                xaxis: {
                  categories: forecastRows.map(r => `Day ${r.day}`),
                  labels: { style: { colors: '#94A3B8', fontSize: '10px' } },
                  axisBorder: { show: false }, axisTicks: { show: false },
                },
                yaxis: {
                  labels: {
                    style: { colors: '#94A3B8', fontSize: '10px' },
                    formatter: (v: number) => `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`,
                  },
                  forceNiceScale: true,
                },
                tooltip: {
                  theme: 'dark',
                  shared: true,
                  y: { formatter: (v: number) => v ? `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '' },
                },
                grid: { borderColor: '#1E293B', strokeDashArray: 3 },
                legend: { show: true, position: 'top', horizontalAlign: 'right', labels: { colors: '#94A3B8' } },
                markers: { size: 0 },
              }}
              series={[
                { name: 'P90 Bull', data: forecastRows.map(r => r.p90) },
                { name: 'P10 Bear', data: forecastRows.map(r => r.p10) },
                { name: 'P50 Base', data: forecastRows.map(r => r.p50) },
              ]}
            />
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 text-xs text-text-muted font-medium">Horizon</th>
                  <th className="text-right py-2 text-xs text-bearish-red font-medium">P10 Bear</th>
                  <th className="text-right py-2 text-xs text-saffron font-semibold">P50 Base</th>
                  <th className="text-right py-2 text-xs text-bullish-green font-medium">P90 Bull</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {forecastRows.map((row) => (
                  <tr key={row.day} className="hover:bg-surface-raised transition-colors duration-150">
                    <td className="py-2.5 text-text-secondary text-xs">
                      {row.day === 1 ? "Tomorrow" : `Day ${row.day}`}
                    </td>
                    <td className="py-2.5 text-right text-bearish-red tabular-nums text-xs">
                      {row.p10 != null ? `₹${row.p10.toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td className="py-2.5 text-right text-saffron tabular-nums font-semibold">
                      ₹{row.p50.toLocaleString("en-IN")}
                    </td>
                    <td className="py-2.5 text-right text-bullish-green tabular-nums text-xs">
                      {row.p90 != null ? `₹${row.p90.toLocaleString("en-IN")}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted mt-3">
            Generated by {prediction.model_used} — Regime: {prediction.regime}
          </p>
        </div>
      )}

      {/* Direction Probability + Confidence */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Direction Probability</h3>
            <HelpPopover content={{
              title: "ML Ensemble Direction Probability",
              body: "Three gradient boosting models (XGBoost, LightGBM, CatBoost) each independently predict the probability of 5 outcome classes: Very Bearish, Bearish, Neutral, Bullish, Very Bullish. Their outputs are averaged into a final distribution.",
              level: "advanced",
              tips: [
                "Bullish + Very Bullish combined > 60% = high conviction BUY",
                "Bearish + Very Bearish combined > 60% = high conviction SELL",
                "Models are trained on 80+ features including RSI, MACD, VIX, FII flows, and earnings",
                "Walk-forward validation ensures no look-ahead bias",
              ],
              affectsVerdict: "The combined upside probability (Bullish + Very Bullish) is the primary signal. Confidence > 70% is required for STRONG BUY/SELL; below 50% = HOLD.",
              source: "XGBoost + LightGBM + CatBoost ensemble — trained on NSE data with India-specific features",
            }} />
          </div>
          <div className="space-y-3">
            {classProbs.map((cls) => (
              <div key={cls.key}>
                <div className="flex items-center justify-between mb-1">
                  <span className={cn("text-sm", cls.isTop ? "font-semibold text-text-primary" : "text-text-secondary")}>
                    {cls.label}
                    {cls.isTop && (
                      <span className="ml-2 text-xs text-saffron font-medium">← current signal</span>
                    )}
                  </span>
                  <span className="text-sm font-bold tabular-nums" style={{ color: cls.color }}>
                    {cls.pct}%
                  </span>
                </div>
                <div className="h-2.5 bg-surface-raised rounded-pill overflow-hidden">
                  <div
                    className="h-full rounded-pill transition-all duration-500"
                    style={{ width: `${cls.pct}%`, background: cls.color }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-border space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Overall Confidence</span>
              <span className="font-bold text-saffron">
                {(prediction.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-xs text-text-muted">
              Regime: {prediction.regime} — Model: {prediction.model_used}
            </p>
          </div>
        </div>

        {/* Price Target Summary */}
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Price Target Summary</h3>
            <HelpPopover content={{
              title: "Price Target Scenarios (P10 / P50 / P90)",
              body: "These are percentile forecasts from the Chronos-2 model. P10 is the bear case — there is only a 10% probability the price closes below this level. P50 is the median — the 50/50 scenario. P90 is the bull case — only 10% chance price exceeds this.",
              level: "beginner",
              tips: [
                "Use P50 as your primary price target for a trade",
                "Use P10 as your stop-loss reference point",
                "Use P90 as your take-profit reference point",
                "Narrow band (P90-P10 < 3%) = high-confidence prediction",
              ],
              affectsVerdict: "Risk:Reward ratio is computed as (P90 - current) / (current - P10). A ratio above 2:1 strengthens a BUY recommendation.",
              source: "Chronos-2 probabilistic forecasting model — outputs quantile forecasts at P10/P50/P90",
            }} />
          </div>

          <div className="space-y-4 mt-2">
            {[
              { label: "P10 — Bear Case", value: prediction.p10, color: "#DC2626", bg: "bg-bearish-bg" },
              { label: "P50 — Base Case", value: prediction.p50, color: "#FF6B00", bg: "bg-saffron-light" },
              { label: "P90 — Bull Case", value: prediction.p90, color: "#059669", bg: "bg-bullish-bg" },
            ].map((t) => (
              <div key={t.label} className={cn("rounded-card p-4", t.bg)}>
                <div className="text-xs text-text-muted font-medium mb-1">{t.label}</div>
                <div className="text-3xl font-bold tabular-nums" style={{ color: t.color }}>
                  {t.value != null ? `₹${t.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—"}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Direction</span>
              <span
                className="font-bold"
                style={{ color: DIRECTION_COLORS[prediction.direction] ?? "#64748B" }}
              >
                {DIRECTION_LABELS[prediction.direction] ?? prediction.direction}
              </span>
            </div>
            <div className="flex justify-between text-sm mt-1">
              <span className="text-text-muted">Signal Strength</span>
              <span className="font-medium text-text-primary">
                {(prediction.direction_prob * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
