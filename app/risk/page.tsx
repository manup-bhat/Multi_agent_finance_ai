"use client";
import useSWR from "swr";
import { AlertTriangle, Shield, TrendingDown, Zap } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getMacro, getFIIDII, getApiErrorMessage } from "@/lib/api-client";

const CIRCUIT_BREAKER_RULES = [
  { id: "vix_elevated", label: "VIX Elevated", desc: "India VIX > 20 → reduce all positions by 50%", threshold: "VIX > 20" },
  { id: "vix_high",     label: "VIX High Fear",  desc: "India VIX > 25 → move to cash only",            threshold: "VIX > 25" },
  { id: "fii_streak",  label: "FII Sell Streak", desc: "FII net sellers for 7+ consecutive days → HOLD", threshold: "7 day streak" },
  { id: "euphoria",    label: "Euphoria Warning", desc: "Fear & Greed > 80 → downgrade BUY to HOLD",     threshold: "F&G > 80" },
  { id: "global_cue",  label: "Global Shock",     desc: "SGX Nifty down >1.5% pre-market → defer entry", threshold: "SGX < -1.5%" },
];

export default function RiskMonitorPage() {
  const { analysisData } = useApp();

  const { data: macro, isLoading: macroLoading } = useSWR("macro-risk", getMacro, { refreshInterval: 5 * 60 * 1000 });
  const { data: fiiDii, isLoading: fiiLoading } = useSWR("fii-dii-risk", getFIIDII, { refreshInterval: 5 * 60 * 1000 });

  const isLoading = macroLoading || fiiLoading;

  const vix = macro?.vix ?? null;
  const fiiStreak = fiiDii?.fii_streak_days ?? 0;
  const fiiBuying = fiiDii ? (fiiDii.fii_net_crore ?? 0) >= 0 : true;
  const fearGreed = analysisData?.fear_greed_index ?? null;
  const circuitActive = analysisData?.circuit_breaker_active ?? false;

  const getRuleStatus = (ruleId: string): "active" | "warning" | "ok" => {
    switch (ruleId) {
      case "vix_elevated": return vix != null && vix > 20 ? "active" : vix != null && vix > 18 ? "warning" : "ok";
      case "vix_high":     return vix != null && vix > 25 ? "active" : vix != null && vix > 22 ? "warning" : "ok";
      case "fii_streak":   return !fiiBuying && fiiStreak >= 7 ? "active" : !fiiBuying && fiiStreak >= 4 ? "warning" : "ok";
      case "euphoria":     return fearGreed != null && fearGreed > 80 ? "active" : fearGreed != null && fearGreed > 70 ? "warning" : "ok";
      case "global_cue":   return macro?.vix_regime === "HIGH" ? "warning" : "ok";
      default: return "ok";
    }
  };

  const activeBreakers = CIRCUIT_BREAKER_RULES.filter((r) => getRuleStatus(r.id) === "active").length;
  const warningBreakers = CIRCUIT_BREAKER_RULES.filter((r) => getRuleStatus(r.id) === "warning").length;

  const riskLevel = analysisData?.risk_level ?? (activeBreakers > 0 ? "HIGH" : warningBreakers > 1 ? "MEDIUM" : "LOW");

  const RISK_COLORS: Record<string, string> = { LOW: "#059669", MEDIUM: "#D97706", HIGH: "#DC2626" };

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Risk Monitor</h1>
        <HelpPopover content={{
          title: "Risk & Circuit Breaker Monitor",
          body: "Tracks active risk conditions and circuit breaker rules. Circuit breakers automatically reduce position sizing or override verdicts when triggered.",
          affectsVerdict: "A single active circuit breaker reduces conviction by 1 level (e.g. STRONG BUY → BUY). Two or more active → HOLD only.",
          source: "Live data from macro + FII/DII APIs, updated every 5 minutes",
        }} />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
      ) : (
        <>
          {/* Overall risk summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Overall Risk */}
            <div className={cn(
              "card-base p-5 border-l-4",
              riskLevel === "LOW" ? "border-l-bullish-green"
                : riskLevel === "MEDIUM" ? "border-l-warning-amber"
                : "border-l-bearish-red"
            )}>
              <div className="flex items-center gap-2 mb-2">
                <Shield size={18} style={{ color: RISK_COLORS[riskLevel] }} />
                <span className="text-xs text-text-muted uppercase tracking-widest font-medium">Overall Risk</span>
              </div>
              <div className="text-3xl font-bold" style={{ color: RISK_COLORS[riskLevel] }}>{riskLevel}</div>
              {circuitActive && (
                <span className="inline-flex mt-2 px-2 py-0.5 rounded-badge bg-bearish-bg text-bearish-red text-xs font-bold">
                  CIRCUIT BREAKER ACTIVE
                </span>
              )}
            </div>

            {/* VIX */}
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-2">
                <TrendingDown size={18} className="text-text-muted" />
                <span className="text-xs text-text-muted uppercase tracking-widest font-medium">India VIX</span>
              </div>
              <div className={cn(
                "text-3xl font-bold tabular-nums",
                vix == null ? "text-text-muted"
                  : vix > 25 ? "text-bearish-red"
                  : vix > 18 ? "text-warning-amber"
                  : "text-bullish-green"
              )}>
                {vix != null ? vix.toFixed(1) : "—"}
              </div>
              <div className="text-xs text-text-muted mt-1">{macro?.vix_regime ?? "Loading..."}</div>
            </div>

            {/* FII */}
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-2">
                <Zap size={18} className="text-text-muted" />
                <span className="text-xs text-text-muted uppercase tracking-widest font-medium">FII Risk Signal</span>
              </div>
              <div className={cn(
                "text-3xl font-bold",
                fiiBuying ? "text-bullish-green" : fiiStreak >= 7 ? "text-bearish-red" : "text-warning-amber"
              )}>
                {fiiBuying ? "BUYING" : `SELLING`}
              </div>
              <div className="text-xs text-text-muted mt-1">
                {fiiStreak} day streak — {fiiDii?.fii_trend ?? "—"}
              </div>
            </div>
          </div>

          {/* Circuit Breakers */}
          <div className="card-base p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-base font-semibold text-text-primary">Circuit Breaker Rules</h3>
              <HelpPopover content={{
                title: "Circuit Breaker Rules",
                body: "Automated safeguards that override or reduce position sizing when extreme market conditions are detected. Orange = warning zone; Red = actively triggered.",
                affectsVerdict: "Active circuit breakers reduce position sizing and can override BUY signals to HOLD.",
                source: "Internal risk engine — evaluated before every analysis run",
              }} />
              <div className="ml-auto flex items-center gap-2">
                {activeBreakers > 0 && (
                  <span className="flex items-center gap-1 text-xs font-bold text-bearish-red bg-bearish-bg px-2 py-1 rounded-badge">
                    <AlertTriangle size={11} /> {activeBreakers} ACTIVE
                  </span>
                )}
                {warningBreakers > 0 && (
                  <span className="flex items-center gap-1 text-xs font-bold text-warning-amber bg-warning-bg px-2 py-1 rounded-badge">
                    {warningBreakers} WARNING
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-3">
              {CIRCUIT_BREAKER_RULES.map((rule) => {
                const status = getRuleStatus(rule.id);
                return (
                  <div
                    key={rule.id}
                    className={cn(
                      "flex items-start gap-4 p-4 rounded-card border transition-all duration-150",
                      status === "active" ? "border-bearish-red/30 bg-bearish-bg"
                        : status === "warning" ? "border-warning-amber/30 bg-warning-bg"
                        : "border-border bg-surface"
                    )}
                  >
                    <div
                      className={cn(
                        "w-3 h-3 rounded-full flex-shrink-0 mt-0.5",
                        status === "active" ? "bg-bearish-red" : status === "warning" ? "bg-warning-amber" : "bg-bullish-green"
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "text-sm font-semibold",
                          status === "active" ? "text-bearish-red" : status === "warning" ? "text-warning-amber" : "text-text-primary"
                        )}>
                          {rule.label}
                        </span>
                        <span className="text-xs text-text-muted px-1.5 py-0.5 rounded-badge bg-surface-raised">
                          {rule.threshold}
                        </span>
                        <span className={cn(
                          "ml-auto text-xs font-bold px-2 py-0.5 rounded-badge",
                          status === "active" ? "text-bearish-red bg-bearish-bg border border-bearish-red/20"
                            : status === "warning" ? "text-warning-amber bg-warning-bg border border-warning-amber/20"
                            : "text-bullish-green bg-bullish-bg border border-bullish-green/20"
                        )}>
                          {status.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-xs text-text-muted mt-1">{rule.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Key Risks from analysis */}
          {analysisData?.key_risks && analysisData.key_risks.length > 0 && (
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-base font-semibold text-text-primary">Key Risks for {analysisData.ticker}</h3>
                <HelpPopover content={{
                  title: "AI-Identified Key Risks",
                  body: "These risks are extracted by the AI analysis agents from the current macro, technical, and sentiment environment.",
                  affectsVerdict: "Each identified risk reduces confidence by a calibrated amount in the multi-agent scoring model.",
                  source: "Multi-agent risk identification — updated on each analysis run",
                }} />
              </div>
              <div className="space-y-2">
                {analysisData.key_risks.map((risk, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-btn bg-surface-raised">
                    <AlertTriangle size={14} className="text-warning-amber flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-text-secondary">{risk}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
