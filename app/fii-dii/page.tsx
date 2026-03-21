"use client";
import useSWR from "swr";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatCrore } from "@/lib/utils";
import { getFIIDII, getApiErrorMessage } from "@/lib/api-client";

export default function FIIDIIPage() {
  const { data: fiiDii, error, isLoading } = useSWR(
    "fii-dii-latest",
    () => getFIIDII(),
    { refreshInterval: 5 * 60 * 1000, revalidateOnFocus: true }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">FII / DII Tracker</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load FII/DII data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      </div>
    );
  }

  if (!fiiDii) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">FII / DII Tracker</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="text-sm">No FII/DII data available. Ensure the API backend is running.</p>
        </div>
      </div>
    );
  }

  const fiiPositive = (fiiDii.fii_net_crore ?? 0) >= 0;
  const diiPositive = (fiiDii.dii_net_crore ?? 0) >= 0;

  const consensusStyle = fiiDii.consensus.includes("BOTH BUY") || fiiDii.consensus === "BOTH_BUY"
    ? "text-bullish-green bg-bullish-bg"
    : fiiDii.consensus.includes("BOTH SELL") || fiiDii.consensus === "BOTH_SELL"
    ? "text-bearish-red bg-bearish-bg"
    : "text-warning-amber bg-warning-bg";

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">FII / DII Tracker</h1>

      {/* Hero Flow Card */}
      <div className="card-base p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold text-text-primary">Latest Institutional Flows</h3>
          <HelpPopover content={{
            title: "FII & DII Net Flows",
            body: "FII (Foreign Institutional Investors) are large global funds like hedge funds and foreign pension funds that invest in Indian markets. DII (Domestic Institutional Investors) are Indian mutual funds, insurance companies, and pension funds. Their net buy/sell activity is the biggest driver of index moves in India.",
            level: "beginner",
            tips: [
              "FII net buy = foreign money entering India = bullish for the market",
              "FII net sell = foreign money leaving = bearish, often due to US/global concerns",
              "DII often buys when FII sells — they are seen as a stabilising force",
              "FII + DII both buying = strongest institutional consensus signal",
            ],
            affectsVerdict: "FII 5-day rolling net flow is consistently in the top-5 SHAP features across all three ML models. A 7-day consecutive selling streak is a hard risk flag.",
            source: "NSE India participant-wise daily trading data — published post-market, sourced via nselib",
          }} />
          <span className="text-xs text-text-muted">{fiiDii.date}</span>
        </div>

        <div className="grid grid-cols-3 gap-6 items-center mt-4">
          {/* FII */}
          <div className="text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
              FII Net Flow
            </div>
            <div className={cn(
              "text-4xl font-bold tabular-nums",
              fiiPositive ? "text-bullish-green" : "text-bearish-red"
            )}>
              {fiiDii.fii_net_crore != null ? formatCrore(fiiDii.fii_net_crore) : "—"}
            </div>
            <div className="flex items-center gap-1.5 justify-center mt-2">
              <span className="text-xs text-text-muted">Trend:</span>
              <span className={cn(
                "text-xs font-semibold",
                fiiDii.fii_trend.toLowerCase().includes("buy") ? "text-bullish-green" : "text-bearish-red"
              )}>
                {fiiDii.fii_trend}
              </span>
            </div>
            {fiiDii.fii_streak_days > 0 && (
              <div className="flex gap-1 justify-center mt-2">
                {Array.from({ length: Math.min(fiiDii.fii_streak_days, 7) }).map((_, i) => (
                  <div
                    key={i}
                    className={cn("w-3 h-3 rounded-full", fiiPositive ? "bg-bullish-green" : "bg-bearish-red")}
                  />
                ))}
              </div>
            )}
            <div className="text-xs text-text-muted mt-1">
              {fiiDii.fii_streak_days} day streak
            </div>
          </div>

          {/* Consensus */}
          <div className="text-center">
            <span className={cn(
              "inline-flex px-4 py-2 rounded-pill text-sm font-bold",
              consensusStyle
            )}>
              {fiiDii.consensus.replace(/_/g, " ")}
            </span>
            <div className="text-xs text-text-muted mt-2">Institutional consensus</div>
          </div>

          {/* DII */}
          <div className="text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
              DII Net Flow
            </div>
            <div className={cn(
              "text-4xl font-bold tabular-nums",
              diiPositive ? "text-bullish-green" : "text-bearish-red"
            )}>
              {fiiDii.dii_net_crore != null ? formatCrore(fiiDii.dii_net_crore) : "—"}
            </div>
            <div className="text-xs text-text-muted mt-3">
              {diiPositive ? "Net Buyer" : "Net Seller"}
            </div>
          </div>
        </div>
      </div>

      {/* Summary note */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-base font-semibold text-text-primary">Flow Analysis</h3>
          <HelpPopover content={{
            title: "FII Flow Streak Analysis",
            body: "A single day of FII selling is noise. A sustained streak of 5–7+ consecutive selling days is a meaningful signal that foreign institutions are reducing Indian exposure — often linked to US dollar strengthening, Fed rate concerns, or India-specific political risk.",
            level: "intermediate",
            tips: [
              "3-day streak = minor trend, watch carefully",
              "5-day streak = elevated risk, reduce new positions",
              "7-day streak = circuit breaker rule triggered (HOLD mode)",
              "Streak reversal (from selling to buying) is often a strong entry signal",
            ],
            affectsVerdict: "FII selling streak >= 7 days activates the circuit breaker and forces the verdict to HOLD regardless of other signals.",
            source: "NSE daily participant-wise cash + F&O data — build_flow_report() in macro/fii_dii_tracker.py",
          }} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-card bg-surface-raised text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest mb-1">FII Streak</div>
            <div className={cn(
              "text-3xl font-bold tabular-nums",
              fiiPositive ? "text-bullish-green" : "text-bearish-red"
            )}>
              {fiiDii.fii_streak_days}
            </div>
            <div className="text-xs text-text-muted mt-1">
              consecutive {fiiPositive ? "buying" : "selling"} days
            </div>
          </div>
          <div className="p-4 rounded-card bg-surface-raised text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest mb-1">FII Trend</div>
            <div className={cn(
              "text-lg font-bold",
              fiiDii.fii_trend.toLowerCase().includes("buy") ? "text-bullish-green" : "text-bearish-red"
            )}>
              {fiiDii.fii_trend}
            </div>
          </div>
          <div className="p-4 rounded-card bg-surface-raised text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest mb-1">Consensus</div>
            <div className={cn(
              "text-lg font-bold",
              fiiDii.consensus.includes("BUY") ? "text-bullish-green" : fiiDii.consensus.includes("SELL") ? "text-bearish-red" : "text-warning-amber"
            )}>
              {fiiDii.consensus.replace(/_/g, " ")}
            </div>
          </div>
        </div>
        <p className="text-xs text-text-muted mt-4">
          Note: Historical flow chart requires the API to expose a time-series endpoint. Displaying latest daily snapshot from <code className="text-text-secondary">/fii-dii/latest</code>.
        </p>
      </div>
    </div>
  );
}
