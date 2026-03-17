"use client";
import { useMemo } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn } from "@/lib/utils";
import { MOCK_PRICE_DATA, MOCK_FORECAST } from "@/lib/mock-data";
import { useApp } from "@/lib/app-context";

const DIRECTION_CLASSES = [
  { label: "Very Bullish", pct: 42, color: "#059669" },
  { label: "Bullish", pct: 28, color: "#65A30D" },
  { label: "Neutral", pct: 15, color: "#D97706" },
  { label: "Bearish", pct: 9, color: "#EA580C" },
  { label: "Very Bearish", pct: 6, color: "#DC2626" },
];

const SHAP_FEATURES = [
  { name: "fii_net_5d_avg", value: 0.32, positive: true },
  { name: "pcr_current", value: 0.18, positive: true },
  { name: "delivery_pct", value: 0.14, positive: true },
  { name: "rsi_14", value: -0.14, positive: false },
  { name: "india_vix", value: -0.11, positive: false },
  { name: "ema_distance_20", value: 0.09, positive: true },
  { name: "gdelt_tone", value: -0.06, positive: false },
  { name: "volume_ratio", value: 0.05, positive: true },
];

export default function PredictionsPage() {
  const { analysisData } = useApp();
  const hist = MOCK_PRICE_DATA.slice(-30);

  // Combined chart data: history + forecast
  const forecastChartData = useMemo(() => {
    const histPoints = hist.map((d) => ({
      date: d.date,
      close: d.close,
      p10: null as number | null,
      p50: null as number | null,
      p90: null as number | null,
    }));
    const fPoints = MOCK_FORECAST.map((f) => ({
      date: f.date,
      close: null as number | null,
      p10: f.p10,
      p50: f.p50,
      p90: f.p90,
    }));
    return [...histPoints, ...fPoints];
  }, [hist]);

  const todayIdx = hist.length - 1;
  const todayDate = hist[todayIdx]?.date;

  const confidence = analysisData?.confidence ?? 71;

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">AI Predictions</h1>

      {/* Forecast Chart */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">
            AI Price Forecast — {analysisData?.horizon ?? 5} Day Horizon
          </h3>
          <HelpPopover content={{
            title: "AI Price Forecast — Chronos-2",
            body: "Amazon Chronos-2 time-series model generates probabilistic price forecasts. P10/P50/P90 represent bear/base/bull scenarios. Trained with 8 India-specific covariates.",
            affectsVerdict: "The P50 forecast is used as the primary target. The width of the P10–P90 band indicates uncertainty — wide bands reduce conviction.",
            source: "Amazon Chronos-2 pretrained model with India covariates (VIX, FII, PCR, delivery%)",
          }} />
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={forecastChartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                interval={5} tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={60}
                tickFormatter={(v) => `₹${v.toFixed(0)}`} domain={["auto","auto"]} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`₹${v?.toFixed(2)}`, ""]}
              />
              {/* Historical */}
              <Line type="monotone" dataKey="close" stroke="#64748B" strokeWidth={2} dot={false} name="Historical" connectNulls={false} />
              {/* Forecast band */}
              <Area type="monotone" dataKey="p90" stroke="#FF6B00" strokeWidth={1} fill="#FF6B00" fillOpacity={0.12} dot={false} name="P90 (Bull)" connectNulls={false} />
              <Area type="monotone" dataKey="p10" stroke="#FF6B00" strokeWidth={1} fill="#ffffff" fillOpacity={1} dot={false} name="P10 (Bear)" connectNulls={false} />
              {/* P50 */}
              <Line type="monotone" dataKey="p50" stroke="#FF6B00" strokeWidth={2.5} strokeDasharray="5 3" dot={false} name="P50 (Base)" connectNulls={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Forecast table */}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 text-xs text-text-muted font-medium">Date</th>
                <th className="text-right py-2 text-xs text-bearish-red font-medium">P10 Bear</th>
                <th className="text-right py-2 text-xs text-saffron font-semibold">P50 Base</th>
                <th className="text-right py-2 text-xs text-bullish-green font-medium">P90 Bull</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {MOCK_FORECAST.map((row, i) => (
                <tr key={row.date} className="hover:bg-surface-raised transition-colors duration-150">
                  <td className="py-2.5 text-text-secondary text-xs">{i === 0 ? "Tomorrow" : `Day ${i + 1}`}</td>
                  <td className="py-2.5 text-right text-bearish-red tabular-nums text-xs">₹{row.p10.toLocaleString("en-IN")}</td>
                  <td className="py-2.5 text-right text-saffron tabular-nums font-semibold">₹{row.p50.toLocaleString("en-IN")}</td>
                  <td className="py-2.5 text-right text-bullish-green tabular-nums text-xs">₹{row.p90.toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-text-muted mt-3">Generated by Amazon Chronos-2 with 8 India covariates</p>
      </div>

      {/* 2-col: Direction Probability + SHAP */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Direction Probability */}
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Direction Probability</h3>
            <HelpPopover content={{
              title: "Direction Probability",
              body: "The XGBoost/LightGBM/CatBoost ensemble outputs 5-class probabilities (Very Bullish to Very Bearish). The highest probability class is the current prediction.",
              affectsVerdict: "Total upside probability (Very Bullish + Bullish) vs downside probability determines signal strength and confidence level.",
              source: "Ensemble of XGBoost + LightGBM + CatBoost — 5-class classification",
            }} />
          </div>
          <div className="space-y-3">
            {DIRECTION_CLASSES.map((cls) => {
              const isTop = cls.label === "Very Bullish";
              return (
                <div key={cls.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={cn("text-sm", isTop ? "font-semibold text-text-primary" : "text-text-secondary")}>
                      {cls.label}
                      {isTop && <span className="ml-2 text-xs text-saffron font-medium">← current signal</span>}
                    </span>
                    <span className="text-sm font-bold tabular-nums" style={{ color: cls.color }}>{cls.pct}%</span>
                  </div>
                  <div className="h-2.5 bg-surface-raised rounded-pill overflow-hidden">
                    <div
                      className="h-full rounded-pill transition-all duration-500"
                      style={{ width: `${cls.pct}%`, background: cls.color }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 pt-3 border-t border-border space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-text-muted">Overall Confidence</span>
              <span className="font-bold text-saffron">{confidence}% — MEDIUM-HIGH</span>
            </div>
            <p className="text-xs text-text-muted">Bull Regime active — upweighting bullish signals</p>
          </div>
        </div>

        {/* SHAP Feature Importance */}
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Top Prediction Drivers (SHAP)</h3>
            <HelpPopover content={{
              title: "SHAP Feature Importance",
              body: "SHAP (SHapley Additive exPlanations) values show which features most influenced today's prediction. Green bars push toward bullish, red toward bearish.",
              affectsVerdict: "Understanding driver features helps validate whether the prediction is based on sound logic or potential data artifacts.",
              source: "SHAP library applied to XGBoost ensemble — computed on each inference",
            }} />
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={SHAP_FEATURES}
                layout="vertical"
                margin={{ top: 0, right: 40, bottom: 0, left: 110 }}
              >
                <XAxis type="number" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                  domain={[-0.4, 0.4]} tickFormatter={(v) => v.toFixed(1)} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#64748B" }} tickLine={false} axisLine={false} width={110} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [v.toFixed(3), "SHAP value"]}
                />
                <ReferenceLine x={0} stroke="hsl(var(--border))" />
                <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                  {SHAP_FEATURES.map((f, i) => (
                    <Cell key={i} fill={f.positive ? "#059669" : "#DC2626"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-text-muted mt-3">
            These are the features that most influenced today&apos;s prediction
          </p>
        </div>
      </div>
    </div>
  );
}
