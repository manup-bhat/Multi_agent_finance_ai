"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";

export function KeyLevels() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const { price_target_p10, price_target_p50, price_target_p90, quant_summary } = analysisData;

  if (price_target_p50 == null) {
    return (
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-2">Key Price Levels</h3>
        <p className="text-sm text-text-muted">Price target data unavailable.</p>
        {quant_summary && (
          <p className="text-xs text-text-secondary mt-3 p-3 bg-surface-raised rounded-btn leading-relaxed">
            {quant_summary}
          </p>
        )}
      </div>
    );
  }

  const price = price_target_p50;
  const p10 = price_target_p10 ?? price * 0.97;
  const p90 = price_target_p90 ?? price * 1.03;

  const levels = [
    { label: "P90 Bull", value: p90, type: "resistance" as const },
    { label: "P50 Base", value: price, type: "current" as const },
    { label: "P10 Bear", value: p10, type: "support" as const },
  ];

  const maxVal = p90;
  const minVal = p10;
  const range = Math.max(maxVal - minVal, 1);

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Key Price Levels</h3>
        <HelpPopover
          content={{
            title: "Probabilistic Price Targets",
            body: "These three levels come from combining Chronos-2 (a pretrained time-series forecasting model) with the XGBoost/LightGBM/CatBoost ensemble. They represent probabilities, not guarantees: P10 means 10% chance price will be below this level; P90 means 90% chance price will be below this level (i.e., bull case ceiling).",
            level: "intermediate",
            tips: [
              "P10 = bear case floor — use as stop-loss reference",
              "P50 = base case — the primary price target",
              "P90 = bull case ceiling — take-profit reference",
              "Narrow P10–P90 band = high model confidence",
              "Wide band = high uncertainty, reduce position size",
            ],
            affectsVerdict: "The Risk:Reward ratio is (P90 - entry) / (entry - P10). The system only upgrades to STRONG BUY if R:R exceeds 2:1 and confidence is above 70%.",
            source: "Amazon Chronos-2 (bolt-small) pretrained model + XGBoost/LightGBM/CatBoost regression outputs — ml/price_target_model.py",
          }}
        />
      </div>

      <div className="space-y-1.5">
        {levels.map(({ label, value, type }) => {
          const pct = ((value - minVal) / range) * 100;
          const isCurrent = type === "current";
          return (
            <div
              key={label}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-btn",
                isCurrent ? "bg-saffron-light border border-saffron/30" : "hover:bg-surface-raised"
              )}
            >
              <div className="w-16 h-1.5 bg-surface-raised rounded-pill overflow-hidden flex-shrink-0">
                <div
                  className={cn(
                    "h-full rounded-pill",
                    type === "resistance" ? "bg-bearish-red" :
                    isCurrent ? "bg-saffron" : "bg-bullish-green"
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>

              <span className={cn(
                "text-xs font-bold w-16 flex-shrink-0",
                type === "resistance" ? "text-bearish-red" :
                isCurrent ? "text-saffron" : "text-bullish-green"
              )}>
                {label}
              </span>

              <span className={cn(
                "text-sm font-medium tabular-nums flex-1 text-right",
                isCurrent ? "text-saffron font-bold" : "text-text-primary"
              )}>
                ₹{value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </span>
            </div>
          );
        })}
      </div>

      {/* Quant summary */}
      {quant_summary && (
        <div className="mt-4 pt-3 border-t border-border">
          <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
            Quant Summary
          </div>
          <p className="text-xs text-text-secondary leading-relaxed p-3 bg-surface-raised rounded-btn">
            {quant_summary}
          </p>
        </div>
      )}
    </div>
  );
}
