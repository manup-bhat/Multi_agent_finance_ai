"use client";
import { cn, getVerdictColors, formatCrore } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";

export function VerdictHero() {
  const { analysisData } = useApp();

  if (!analysisData) return null;

  const {
    verdict, confidence, regime, price_targets, current_price,
    fo_strategy, fo_rr, india_vix, fii_5d_avg, fear_greed, pcr
  } = analysisData;

  const colors = getVerdictColors(verdict);
  const regimeLabel = regime === "BULL" ? "BULL REGIME" : regime === "BEAR" ? "BEAR REGIME" : "SIDEWAYS";
  const regimeEmoji = regime === "BULL" ? "🐂" : regime === "BEAR" ? "🐻" : "↔️";

  // Confidence arc
  const r = 34;
  const circumference = 2 * Math.PI * r;
  const filled = (confidence / 100) * circumference;

  return (
    <div
      className="rounded-card overflow-hidden relative"
      style={{ background: `linear-gradient(135deg, ${colors.from}, ${colors.to})` }}
    >
      {/* Help button */}
      <div className="absolute top-3 right-3">
        <HelpPopover
          content={{
            title: "AI Verdict — Final Signal",
            body: "The verdict is a weighted synthesis of 7 AI agents and 3 ML models. Confidence reflects ensemble agreement. Regime is determined by market structure analysis.",
            affectsVerdict: "Verdict directly represents the recommended trade direction. Override to HOLD if VIX > 25.",
            source: "Multi-agent LLM synthesis + XGBoost/LightGBM/CatBoost ensemble",
          }}
        />
      </div>

      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left: Verdict + Confidence */}
          <div className="flex flex-col items-center gap-3">
            <div className={cn("text-5xl font-bold text-white tracking-tight")}>
              {verdict.replace("_", " ")}
            </div>

            {/* SVG Confidence ring */}
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
                <span className="text-xl font-bold text-white tabular-nums">{confidence}%</span>
                <span className="text-xs text-white/70">confidence</span>
              </div>
            </div>

            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-pill bg-white/20 text-white text-sm font-medium">
              {regimeEmoji} {regimeLabel}
            </span>
          </div>

          {/* Center: Price targets */}
          <div className="flex flex-col justify-center gap-3">
            <div className="text-white/60 text-xs uppercase tracking-widest font-medium mb-1">Price Targets</div>
            {[
              { label: "Conservative (P10)", value: price_targets.p10, highlighted: false },
              { label: "Target (P50)", value: price_targets.p50, highlighted: true },
              { label: "Optimistic (P90)", value: price_targets.p90, highlighted: false },
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
                  ₹{value.toLocaleString("en-IN")}
                </span>
              </div>
            ))}
            <div className="text-white/50 text-xs mt-1 text-center">
              Chronos-2 AI forecast • {analysisData.horizon}-day horizon
            </div>
          </div>

          {/* Right: F&O Strategy */}
          <div className="flex flex-col justify-center gap-3">
            <div className="text-white/60 text-xs uppercase tracking-widest font-medium">F&O Strategy</div>
            <div className="bg-white/15 border border-white/20 rounded-card p-4">
              <div className="text-white font-bold text-base">{fo_strategy}</div>
              <div className="text-white/70 text-xs mt-2">{fo_rr}</div>
            </div>

            {/* Current price */}
            <div className="bg-white/10 rounded-btn px-3 py-2">
              <div className="text-white/60 text-xs">Current Price</div>
              <div className="text-white font-bold text-xl tabular-nums">
                ₹{current_price.toLocaleString("en-IN")}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom strip */}
        <div className="mt-5 pt-4 border-t border-white/20 flex flex-wrap gap-x-6 gap-y-2">
          {[
            { label: "India VIX", value: india_vix.toFixed(1) },
            { label: "FII 5d avg", value: formatCrore(fii_5d_avg) },
            { label: "Fear/Greed", value: `${fear_greed} ${fear_greed > 60 ? "🟡" : fear_greed > 40 ? "⬜" : "🔴"}` },
            { label: "PCR", value: `${pcr} ${pcr > 1.2 ? "📈" : "📉"}` },
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
