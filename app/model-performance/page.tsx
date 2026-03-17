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
  // Return null for 404 — endpoint may not yet be implemented in backend
  if (res.status === 404) return null;
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

const MODEL_DESCRIPTIONS: Record<string, { role: string; how: string; good: string }> = {
  XGBoost: {
    role: "Tree-boosting classifier — primary directional signal",
    how: "Trained on 80+ technical + macro features. Each tree corrects errors of the previous, making it excellent at capturing non-linear patterns.",
    good: "F1 > 0.65, Sharpe > 1.0",
  },
  LightGBM: {
    role: "Gradient boosting — fast, handles high-dimensionality",
    how: "Leaf-wise tree growth makes it faster than XGBoost and better at large feature sets (e.g. option chain data).",
    good: "F1 > 0.62, Sharpe > 0.8",
  },
  CatBoost: {
    role: "Categorical feature specialist",
    how: "Natively handles categorical features like market regime and sector label without manual encoding, reducing leakage risk.",
    good: "F1 > 0.60, Sharpe > 0.7",
  },
  "Chronos-2": {
    role: "Amazon time-series model — price level forecasting",
    how: "Pre-trained probabilistic forecaster that outputs P10/P50/P90 price targets. Does not predict direction — only magnitude.",
    good: "MAE < 2% of price, coverage 90%",
  },
};

function ModelEducationCards() {
  const entries = [
    {
      name: "XGBoost",
      badge: "Direction Classifier",
      badgeColor: "bg-saffron-light text-saffron",
      ...MODEL_DESCRIPTIONS["XGBoost"],
    },
    {
      name: "LightGBM",
      badge: "Direction Classifier",
      badgeColor: "bg-saffron-light text-saffron",
      ...MODEL_DESCRIPTIONS["LightGBM"],
    },
    {
      name: "CatBoost",
      badge: "Direction Classifier",
      badgeColor: "bg-saffron-light text-saffron",
      ...MODEL_DESCRIPTIONS["CatBoost"],
    },
    {
      name: "Chronos-2",
      badge: "Price Forecaster",
      badgeColor: "bg-neutral-bg text-neutral-blue",
      ...MODEL_DESCRIPTIONS["Chronos-2"],
    },
  ];

  return (
    <>
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-1">How the ensemble works</h3>
        <p className="text-sm text-text-secondary leading-relaxed">
          The prediction system runs three direction classifiers (XGBoost, LightGBM, CatBoost) in parallel.
          Their probability outputs are averaged into a final 5-class direction signal.
          Chronos-2 runs separately to forecast absolute price levels (P10 / P50 / P90).
          Ensemble weights are adjusted weekly based on each model&apos;s recent out-of-sample accuracy.
        </p>
        <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs">
          {["XGBoost", "LightGBM", "CatBoost"].map((m) => (
            <div key={m} className="p-3 rounded-btn bg-saffron-light">
              <div className="font-bold text-saffron">{m}</div>
              <div className="text-text-muted mt-0.5">Direction probs</div>
            </div>
          ))}
        </div>
        <div className="flex justify-center mt-2">
          <div className="w-px h-5 bg-border" />
        </div>
        <div className="flex justify-center">
          <div className="px-4 py-2 rounded-pill bg-saffron text-white text-xs font-bold">
            Weighted Average → Final Verdict
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {entries.map((e) => (
          <div key={e.name} className="card-base p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-text-primary">{e.name}</h3>
              <span className={cn("text-xs px-2 py-0.5 rounded-badge font-medium", e.badgeColor)}>
                {e.badge}
              </span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed mb-3">{e.how}</p>
            <div className="flex justify-between text-xs pt-2 border-t border-border">
              <span className="text-text-muted">Healthy when</span>
              <span className="text-bullish-green font-medium">{e.good}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Understanding the Metrics</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { term: "Accuracy", def: "% of all predictions that were correct. Simple but misleading when classes are imbalanced." },
            { term: "Precision", def: "Of all BULLISH predictions, how many were actually bullish? Measures false alarm rate." },
            { term: "Recall", def: "Of all actual BULLISH moves, how many did we catch? Measures missed opportunity rate." },
            { term: "F1 Score", def: "Harmonic mean of precision and recall. Best single metric for imbalanced markets." },
            { term: "Sharpe Ratio", def: "Return divided by volatility. Above 1.0 is excellent; below 0.5 needs retraining." },
            { term: "Walk-forward", def: "Training on past data, testing on future unseen data — simulates real trading. No look-ahead bias." },
          ].map((item) => (
            <div key={item.term} className="p-3 rounded-btn bg-surface-raised">
              <div className="text-xs font-bold text-text-primary mb-1">{item.term}</div>
              <p className="text-xs text-text-muted leading-relaxed">{item.def}</p>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default function ModelPerformancePage() {
  const { data: models, error, isLoading } = useSWR<ModelMetrics[] | null>(
    "model-performance",
    fetchModelPerformance,
    { revalidateOnFocus: false }
  );

  const heading = (
    <div className="flex items-center gap-2">
      <h1 className="text-xl font-semibold text-text-primary">Model Performance</h1>
      <HelpPopover content={{
        title: "How are Models Evaluated?",
        body: "Each ML model is evaluated on out-of-sample data using walk-forward validation — never on the same data it was trained on. This mirrors real trading conditions.",
        affectsVerdict: "Models with F1 < 0.55 or Sharpe < 0.5 receive lower ensemble weight. A 'Retrain' flag means the model needs fresh training data.",
        source: "Walk-forward validation on last 6 months of NSE data — re-evaluated weekly",
      }} />
    </div>
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
        {heading}
        <div className="rounded-btn border border-warning-amber/30 bg-warning-bg px-4 py-3 text-sm text-warning-amber">
          API returned an error loading model metrics.
        </div>
        <ModelEducationCards />
      </div>
    );
  }

  if (!models || models.length === 0) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        {heading}
        <div className="card-base p-5">
          <p className="text-sm text-text-secondary mb-1 font-medium">
            Live model metrics are not yet available
          </p>
          <p className="text-xs text-text-muted">
            The backend needs to expose{" "}
            <code className="text-text-secondary">GET /model/performance</code>.
            Until then, here is a reference guide for each model in the ensemble.
          </p>
        </div>
        <ModelEducationCards />
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
      {heading}

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
