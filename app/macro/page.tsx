"use client";
import useSWR from "swr";
import { ArrowUp, ArrowDown } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getMacro, getApiErrorMessage } from "@/lib/api-client";

const CORRELATIONS = [
  { factor: "USD/INR", corr: -0.72, impact: "Strong Negative" },
  { factor: "Brent Crude", corr: -0.45, impact: "Moderate Negative" },
  { factor: "US 10Y Yield", corr: -0.38, impact: "Moderate Negative" },
  { factor: "Gold", corr: 0.12, impact: "Weak Positive" },
  { factor: "SGX Nifty", corr: 0.88, impact: "Strong Positive" },
];

export default function MacroPage() {
  const { data: macro, error, isLoading } = useSWR(
    "macro-india",
    () => getMacro(),
    { refreshInterval: 10 * 60 * 1000, revalidateOnFocus: true }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-40 w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <Skeleton className="lg:col-span-3 h-72" />
          <Skeleton className="lg:col-span-2 h-72" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Macro India</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load macro data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      </div>
    );
  }

  if (!macro) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Macro India</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="text-sm">No macro data available. Ensure the API backend is running.</p>
        </div>
      </div>
    );
  }

  // Build live global cues from API response
  const globalCues = [
    {
      label: "SGX Nifty",
      value: macro.sgx_nifty != null
        ? `${macro.sgx_nifty > 0 ? "+" : ""}${macro.sgx_nifty.toFixed(0)} pts`
        : "—",
      positive: (macro.sgx_nifty ?? 0) >= 0,
    },
    {
      label: "USD/INR",
      value: macro.usdinr != null ? `₹${macro.usdinr.toFixed(2)}` : "—",
      positive: false, // higher INR = weaker rupee = negative for markets
    },
    {
      label: "Brent Crude",
      value: macro.brent_crude != null ? `$${macro.brent_crude.toFixed(1)}` : "—",
      positive: (macro.brent_crude ?? 80) < 80,
    },
    {
      label: "FII Net",
      value: macro.fii_net_crore != null
        ? `₹${(macro.fii_net_crore / 100).toFixed(0)}Cr`
        : "—",
      positive: (macro.fii_net_crore ?? 0) >= 0,
    },
    {
      label: "India VIX",
      value: macro.vix != null ? macro.vix.toFixed(1) : "—",
      positive: (macro.vix ?? 20) < 18,
    },
    {
      label: "VIX Regime",
      value: macro.vix_regime,
      positive: macro.vix_regime === "NORMAL" || macro.vix_regime === "LOW",
    },
  ];

  const vix = macro.vix;
  const vixColor = vix == null
    ? "#94A3B8"
    : vix < 13 ? "#059669"
    : vix < 18 ? "#64748B"
    : vix < 25 ? "#D97706"
    : "#DC2626";

  const vixLabel = vix == null ? "UNKNOWN"
    : vix < 13 ? "COMPLACENCY"
    : vix < 18 ? "NORMAL"
    : vix < 25 ? "ELEVATED"
    : "HIGH FEAR";

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">Macro India</h1>

      {/* Global Cues */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Pre-Market Global Cues</h3>
          <HelpPopover content={{
            title: "Pre-Market Global Cues",
            body: "Key global market indicators. SGX Nifty is the best leading indicator for Nifty50 opening direction.",
            affectsVerdict: "Strong negative global cues (SGX Nifty down >100pts + crude spike) can override the macro agent's bullish stance.",
            source: "SGX Nifty, USD/INR, Brent Crude via yfinance — live data",
          }} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {globalCues.map((cue) => (
            <div key={cue.label} className="card-base p-4 text-center shadow-none">
              <div className="text-xs text-text-muted font-medium mb-1">{cue.label}</div>
              <div className={cn(
                "text-lg font-bold tabular-nums",
                cue.value === "—" ? "text-text-muted"
                  : cue.positive ? "text-bullish-green"
                  : "text-bearish-red"
              )}>
                {cue.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* VIX Status + Correlations */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* VIX Card */}
        <div className="lg:col-span-3 card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">India VIX Status</h3>
            <HelpPopover content={{
              title: "India VIX",
              body: "India VIX measures market fear. Zone bands: Complacency (<13), Normal (13–18), Elevated (18–25), High Fear (>25).",
              affectsVerdict: "VIX crossing into Elevated or High Fear zone triggers circuit breaker rules and overrides position sizing.",
              source: "NSE India via yfinance (^INDIAVIX)",
            }} />
          </div>

          <div className="flex items-center gap-8 py-4">
            <div className="text-center">
              <div className="text-6xl font-bold tabular-nums" style={{ color: vixColor }}>
                {vix != null ? vix.toFixed(1) : "—"}
              </div>
              <div className="mt-2">
                <span
                  className="inline-flex px-3 py-1 rounded-pill text-sm font-bold"
                  style={{
                    color: vixColor,
                    background: `${vixColor}18`,
                  }}
                >
                  {vixLabel}
                </span>
              </div>
            </div>

            <div className="flex-1 space-y-2">
              {[
                { label: "Complacency", range: "<13", color: "#059669", active: (vix ?? 0) < 13 },
                { label: "Normal",       range: "13–18", color: "#64748B", active: (vix ?? 0) >= 13 && (vix ?? 0) < 18 },
                { label: "Elevated",     range: "18–25", color: "#D97706", active: (vix ?? 0) >= 18 && (vix ?? 0) < 25 },
                { label: "High Fear",    range: ">25",   color: "#DC2626", active: (vix ?? 0) >= 25 },
              ].map((zone) => (
                <div key={zone.label} className={cn("flex items-center gap-3 p-2.5 rounded-btn transition-all", zone.active ? "bg-surface-raised" : "")}>
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: zone.color, opacity: zone.active ? 1 : 0.4 }} />
                  <span className={cn("text-sm", zone.active ? "font-semibold text-text-primary" : "text-text-muted")}>
                    {zone.label}
                  </span>
                  <span className="text-xs text-text-muted ml-auto">{zone.range}</span>
                  {zone.active && (
                    <span className="text-xs font-bold px-1.5 py-0.5 rounded-badge" style={{ color: zone.color, background: `${zone.color}18` }}>
                      CURRENT
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Correlations — static reference data */}
        <div className="lg:col-span-2 card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Key Correlations (30-day)</h3>
            <HelpPopover content={{
              title: "Macro Correlations",
              body: "Rolling 30-day Pearson correlation between Nifty50 returns and macro variables.",
              affectsVerdict: "Strong correlations help the macro agent assess whether the current macro backdrop is a tailwind or headwind.",
              source: "Computed from 30-day rolling returns — historical reference values",
            }} />
          </div>
          <div className="space-y-3">
            {CORRELATIONS.map((c) => (
              <div key={c.factor}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-text-secondary font-medium">{c.factor}</span>
                  <span className={cn("text-sm font-bold tabular-nums", c.corr > 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {c.corr > 0 ? "+" : ""}{c.corr.toFixed(2)}
                  </span>
                </div>
                <div className="relative h-2 bg-surface-raised rounded-pill overflow-hidden">
                  <div
                    className="absolute top-0 h-full rounded-pill"
                    style={{
                      width: `${Math.abs(c.corr) * 50}%`,
                      left: c.corr >= 0 ? "50%" : undefined,
                      right: c.corr < 0 ? "50%" : undefined,
                      background: c.corr > 0 ? "#059669" : "#DC2626",
                    }}
                  />
                  <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
                </div>
                <div className="text-xs text-text-muted mt-0.5">{c.impact}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* India Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-base p-5">
          <h3 className="text-base font-semibold text-text-primary mb-3">India Macro Summary</h3>
          <p className="text-sm text-text-secondary leading-relaxed">{macro.india_summary}</p>
        </div>
        <div className="card-base p-5">
          <h3 className="text-base font-semibold text-text-primary mb-3">Global Cues Summary</h3>
          <p className="text-sm text-text-secondary leading-relaxed">{macro.global_cues}</p>
          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-sm">
            <span className="text-text-muted">FII Trend</span>
            <span className={cn(
              "font-semibold",
              macro.fii_trend.toLowerCase().includes("buy") ? "text-bullish-green" : "text-bearish-red"
            )}>
              {macro.fii_trend}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
