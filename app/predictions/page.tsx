"use client";
import useSWR from "swr";
import { useMemo } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine,
} from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getPrediction, getApiErrorMessage } from "@/lib/api-client";

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
              title: "AI Price Forecast — Chronos-2",
              body: "Amazon Chronos-2 time-series model generates probabilistic price forecasts. P10/P50/P90 represent bear/base/bull scenarios.",
              affectsVerdict: "The P50 forecast is used as the primary price target. Wide P10–P90 band signals high uncertainty.",
              source: "Amazon Chronos-2 pretrained model with India-specific covariates",
            }} />
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={forecastRows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `Day ${v}`}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  tickLine={false}
                  axisLine={false}
                  width={65}
                  tickFormatter={(v) => `₹${v.toLocaleString("en-IN")}`}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--surface))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v: number, name: string) => [`₹${v?.toLocaleString("en-IN")}`, name]}
                />
                <Area
                  type="monotone"
                  dataKey="p90"
                  stroke="#FF6B00"
                  strokeWidth={1}
                  fill="#FF6B00"
                  fillOpacity={0.12}
                  dot={false}
                  name="P90 Bull"
                />
                <Area
                  type="monotone"
                  dataKey="p10"
                  stroke="#FF6B00"
                  strokeWidth={1}
                  fill="#ffffff"
                  fillOpacity={1}
                  dot={false}
                  name="P10 Bear"
                />
                <Line
                  type="monotone"
                  dataKey="p50"
                  stroke="#FF6B00"
                  strokeWidth={2.5}
                  strokeDasharray="5 3"
                  dot={false}
                  name="P50 Base"
                />
              </ComposedChart>
            </ResponsiveContainer>
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
              title: "Direction Probability",
              body: "The XGBoost/LightGBM/CatBoost ensemble outputs 5-class probabilities. The highest-probability class is the current prediction.",
              affectsVerdict: "Total upside probability (Very Bullish + Bullish) vs downside probability determines signal strength.",
              source: "Ensemble of XGBoost + LightGBM + CatBoost — 5-class classification",
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
              title: "Price Targets",
              body: "Probabilistic price targets for the selected horizon. P50 is the most likely outcome; P10/P90 bracket the uncertainty range.",
              affectsVerdict: "The gap between P90 and P10 relative to current price determines position sizing aggressiveness.",
              source: "Chronos-2 time-series model output",
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
