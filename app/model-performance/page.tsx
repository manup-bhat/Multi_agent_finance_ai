"use client";
import useSWR from "swr";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-client";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchModelPerformance() {
  const res = await fetch(`${BASE_URL}/model/performance`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface ModelMetrics {
  model_name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  sharpe: number;
  n_predictions: number;
  last_trained: string;
  feature_count: number;
}

const METRIC_KEYS: { key: keyof ModelMetrics; label: string; pct: boolean }[] = [
  { key: "accuracy",  label: "Accuracy",  pct: true },
  { key: "precision", label: "Precision", pct: true },
  { key: "recall",    label: "Recall",    pct: true },
  { key: "f1",        label: "F1 Score",  pct: true },
  { key: "sharpe",    label: "Sharpe",    pct: false },
];

export default function ModelPerformancePage() {
  const { data: models, error, isLoading } = useSWR<ModelMetrics[]>(
    "model-performance",
    fetchModelPerformance,
    { revalidateOnFocus: false }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-64 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Model Performance</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load model performance data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
          <p className="text-xs text-text-muted mt-2">Ensure the API exposes <code className="text-text-secondary">/model/performance</code>.</p>
        </div>
      </div>
    );
  }

  if (!models || models.length === 0) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Model Performance</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="font-medium text-text-secondary mb-2">No model performance data available</p>
          <p className="text-sm">The API backend needs to expose a <code className="text-text-secondary">/model/performance</code> endpoint.</p>
        </div>
      </div>
    );
  }

  // Build comparison chart data
  const chartData = models.map((m) => ({
    name: m.model_name,
    accuracy: +(m.accuracy * 100).toFixed(1),
    f1: +(m.f1 * 100).toFixed(1),
    sharpe: +m.sharpe.toFixed(2),
  }));

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Model Performance</h1>
        <HelpPopover content={{
          title: "Model Performance Metrics",
          body: "Tracks accuracy, precision, recall, F1 score, and Sharpe ratio for each ML model in the ensemble. Evaluated on out-of-sample data.",
          affectsVerdict: "Models with F1 < 0.55 or Sharpe < 0.5 are flagged for retraining and receive lower weight in the ensemble.",
          source: "Walk-forward validation on last 6 months of NSE data",
        }} />
      </div>

      {/* Comparison Bar Chart */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Accuracy vs F1 Score — Model Comparison</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number, name: string) => [name === "sharpe" ? v.toFixed(2) : `${v}%`, name === "accuracy" ? "Accuracy" : name === "f1" ? "F1" : "Sharpe"]}
              />
              <Bar dataKey="accuracy" maxBarSize={28} name="accuracy">
                {chartData.map((_, i) => <Cell key={i} fill="#FF6B00" opacity={0.85} />)}
              </Bar>
              <Bar dataKey="f1" maxBarSize={28} name="f1">
                {chartData.map((_, i) => <Cell key={i} fill="#1D4ED8" opacity={0.75} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-saffron opacity-85" /><span className="text-text-muted">Accuracy</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-neutral-blue opacity-75" /><span className="text-text-muted">F1 Score</span></div>
        </div>
      </div>

      {/* Per-model detail cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {models.map((model) => (
          <div key={model.model_name} className="card-base p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-text-primary">{model.model_name}</h3>
              <span className={cn(
                "text-xs px-2 py-0.5 rounded-badge font-semibold",
                model.f1 >= 0.65 ? "bg-bullish-bg text-bullish-green"
                  : model.f1 >= 0.55 ? "bg-warning-bg text-warning-amber"
                  : "bg-bearish-bg text-bearish-red"
              )}>
                {model.f1 >= 0.65 ? "Healthy" : model.f1 >= 0.55 ? "Monitor" : "Retrain"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-3">
              {METRIC_KEYS.map(({ key, label, pct }) => {
                const val = model[key] as number;
                return (
                  <div key={key} className="p-2 rounded-btn bg-surface-raised text-center">
                    <div className="text-xs text-text-muted mb-0.5">{label}</div>
                    <div className="text-lg font-bold tabular-nums text-text-primary">
                      {pct ? `${(val * 100).toFixed(1)}%` : val.toFixed(2)}
                    </div>
                  </div>
                );
              })}
              <div className="p-2 rounded-btn bg-surface-raised text-center">
                <div className="text-xs text-text-muted mb-0.5">Predictions</div>
                <div className="text-lg font-bold tabular-nums text-text-primary">
                  {model.n_predictions.toLocaleString("en-IN")}
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-border space-y-1 text-xs text-text-muted">
              <div className="flex justify-between">
                <span>Features</span>
                <span className="text-text-secondary">{model.feature_count}</span>
              </div>
              <div className="flex justify-between">
                <span>Last trained</span>
                <span className="text-text-secondary">{model.last_trained}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
