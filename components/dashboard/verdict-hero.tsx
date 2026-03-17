"use client";
import { cn, getVerdictColors, formatCrore, getFearGreedLabel } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";

export function VerdictHero() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const {
    verdict,
    confidence,
    regime,
    price_target_p10,
    price_target_p50,
    price_target_p90,
    fno_summary,
    vix_current,
    fii_net_5d,
    fear_greed_index,
    circuit_breaker_active,
    recommended_strategy,
    errors,
    warnings,
  } = analysisData;

  const colors = getVerdictColors(verdict);
  const regimeLabel =
    regime === "BULL" ? "BULL REGIME" : regime === "BEAR" ? "BEAR REGIME" : "SIDEWAYS";

  const confidencePct = Math.round(confidence >= 1 ? confidence : confidence * 100);
  const r = 34;
  const circumference = 2 * Math.PI * r;
  const filled = (confidencePct / 100) * circumference;

  const fearGreed = fear_greed_index ?? null;
  const { label: fgLabel } = fearGreed !== null ? getFearGreedLabel(fearGreed) : { label: "N/A" };

  return (
    <div
      className="rounded-card overflow-hidden relative"
      style={{ background: `linear-gradient(135deg, ${colors.from}, ${colors.to})` }}
    >
      <div className="absolute top-3 right-3">
        <HelpPopover
          content={{
            title: "AI Verdict — Final Signal",
            body: "The verdict is a weighted synthesis of multi-agent LLM analysis and ML model ensemble. Confidence reflects ensemble agreement. Regime is determined by market structure.",
            affectsVerdict: "Verdict directly represents the recommended trade direction. Circuit breaker overrides all signals to HOLD when VIX exceeds threshold.",
            source: "Multi-agent LangGraph synthesis + XGBoost/LightGBM/CatBoost ensemble",
          }}
        />
      </div>

      {/* Circuit breaker banner */}
      {circuit_breaker_active && (
        <div className="bg-black/30 border-b border-white/20 px-6 py-2 flex items-center gap-2">
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            Circuit Breaker Active — Position sizing reduced
          </span>
        </div>
      )}

      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left: Verdict + Confidence */}
          <div className="flex flex-col items-center gap-3">
            <div className="text-5xl font-bold text-white tracking-tight">
              {verdict.replace(/_/g, " ")}
            </div>

            <div className="relative w-24 h-24">
              <svg className="w-24 h-24 -rotate-90" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r={r} strokeWidth="6" fill="none" stroke="rgba(255,255,255,0.2)" />
                <circle
                  cx="40" cy="40" r={r}
                  strokeWidth="6" fill="none"
                  stroke="white"
                  strokeDasharray={`${filled} ${circumference}`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xl font-bold text-white tabular-nums">{confidencePct}%</span>
                <span className="text-xs text-white/70">confidence</span>
              </div>
            </div>

            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-pill bg-white/20 text-white text-sm font-medium">
              {regimeLabel}
            </span>
          </div>

          {/* Center: Price targets */}
          <div className="flex flex-col justify-center gap-3">
            <div className="text-white/60 text-xs uppercase tracking-widest font-medium mb-1">
              Price Targets (AI Forecast)
            </div>
            {[
              { label: "Conservative (P10)", value: price_target_p10, highlighted: false },
              { label: "Target (P50)", value: price_target_p50, highlighted: true },
              { label: "Optimistic (P90)", value: price_target_p90, highlighted: false },
            ].map(({ label, value, highlighted }) => (
              <div
                key={label}
                className={cn(
                  "flex items-center justify-between rounded-btn px-3 py-2",
                  highlighted ? "bg-white/25 border border-white/30" : "bg-white/10"
                )}
              >
                <span className={cn("text-sm", highlighted ? "text-white font-semibold" : "text-white/70")}>
                  {label}
                </span>
                <span className={cn("font-bold tabular-nums", highlighted ? "text-white text-lg" : "text-white/80")}>
                  {value != null ? `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "N/A"}
                </span>
              </div>
            ))}
          </div>

          {/* Right: F&O / Risk info */}
          <div className="flex flex-col justify-center gap-3">
            <div className="text-white/60 text-xs uppercase tracking-widest font-medium">
              F&O / Strategy
            </div>
            <div className="bg-white/15 border border-white/20 rounded-card p-4">
              <div className="text-white font-bold text-sm leading-relaxed">
                {recommended_strategy || fno_summary || "F&O analysis not available."}
              </div>
            </div>

            {/* Errors/warnings summary */}
            {(errors.length > 0 || warnings.length > 0) && (
              <div className="bg-white/10 rounded-btn px-3 py-2">
                <div className="text-white/60 text-xs mb-1">
                  {errors.length > 0 ? `${errors.length} data source issue(s)` : `${warnings.length} warning(s)`}
                </div>
                <div className="text-white/80 text-xs line-clamp-2">
                  {errors[0] ?? warnings[0]}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bottom strip */}
        <div className="mt-5 pt-4 border-t border-white/20 flex flex-wrap gap-x-6 gap-y-2">
          {[
            {
              label: "India VIX",
              value: vix_current != null ? vix_current.toFixed(1) : "N/A",
            },
            {
              label: "FII 5d Net",
              value: fii_net_5d != null ? formatCrore(fii_net_5d) : "N/A",
            },
            {
              label: "Fear/Greed",
              value: fearGreed != null ? `${Math.round(fearGreed)} — ${fgLabel}` : "N/A",
            },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-white/50 text-xs">{label}:</span>
              <span className="text-white font-medium text-sm tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
