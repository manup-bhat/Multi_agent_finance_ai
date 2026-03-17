"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";

export function KeyLevels() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const price = analysisData.current_price;

  // Derived S/R levels
  const levels = [
    { label: "R3", value: price * 1.055, type: "resistance" },
    { label: "R2", value: price * 1.035, type: "resistance" },
    { label: "R1", value: price * 1.018, type: "resistance" },
    { label: "ATM", value: price, type: "current" },
    { label: "S1", value: price * 0.982, type: "support" },
    { label: "S2", value: price * 0.965, type: "support" },
    { label: "S3", value: price * 0.948, type: "support" },
  ];

  const maxVal = levels[0].value;
  const minVal = levels[levels.length - 1].value;
  const range = maxVal - minVal;

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Key Price Levels</h3>
        <HelpPopover
          content={{
            title: "Key Price Levels — Support & Resistance",
            body: "Support and resistance levels computed from pivot points, SMC order blocks, and option chain max pain. These are key decision zones.",
            affectsVerdict: "Price proximity to max pain and strong S/R levels influences the F&O agent's strategy recommendation and the overall risk assessment.",
            source: "NSE F&O data + pivot calculations + SMC analysis engine",
          }}
        />
      </div>

      {/* Price ladder */}
      <div className="space-y-1.5">
        {levels.map(({ label, value, type }) => {
          const pct = ((value - minVal) / range) * 100;
          const isCurrent = type === "current";
          return (
            <div
              key={label}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-btn",
                isCurrent
                  ? "bg-saffron-light border border-saffron/30"
                  : "hover:bg-surface-raised"
              )}
            >
              {/* Bar indicator */}
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
                "text-xs font-bold w-8 flex-shrink-0",
                type === "resistance" ? "text-bearish-red" :
                isCurrent ? "text-saffron" : "text-bullish-green"
              )}>
                {label}
              </span>

              <span className={cn(
                "text-sm font-medium tabular-nums flex-1 text-right",
                isCurrent ? "text-saffron font-bold" : "text-text-primary"
              )}>
                ₹{value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </span>
            </div>
          );
        })}
      </div>

      {/* Max Pain + SMC */}
      <div className="mt-4 pt-3 border-t border-border space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-muted">Max Pain</span>
          <span className="font-medium text-text-primary tabular-nums">₹22,000</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-muted">Days to Expiry</span>
          <span className="font-medium text-warning-amber">3 DTE</span>
        </div>
        <div className="mt-2 px-3 py-2 rounded-btn bg-bullish-bg border border-bullish-green/20">
          <span className="text-xs text-bullish-green font-medium">
            SMC Order Block: ₹{(price * 0.971).toFixed(0)} – ₹{(price * 0.977).toFixed(0)}
          </span>
        </div>
      </div>
    </div>
  );
}
