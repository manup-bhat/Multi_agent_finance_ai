"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";
import { CheckCircle, AlertTriangle } from "lucide-react";

function RiskGauge({ level }: { level: string }) {
  const levelMap: Record<string, { angle: number; color: string }> = {
    LOW: { angle: -80, color: "#059669" },
    MEDIUM: { angle: -10, color: "#1D4ED8" },
    HIGH: { angle: 60, color: "#D97706" },
    EXTREME: { angle: 120, color: "#DC2626" },
  };
  const { angle, color } = levelMap[level] || levelMap.MEDIUM;

  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const r = 60;
  const startAngle = -220;
  const endAngle = 40;

  // Arc segments
  const segments = [
    { start: -220, end: -150, color: "#059669" },
    { start: -150, end: -80, color: "#65A30D" },
    { start: -80, end: -10, color: "#D97706" },
    { start: -10, end: 40, color: "#DC2626" },
  ];

  function arcPath(sa: number, ea: number, radius: number) {
    const sx = 80 + radius * Math.cos(toRad(sa));
    const sy = 80 + radius * Math.sin(toRad(sa));
    const ex = 80 + radius * Math.cos(toRad(ea));
    const ey = 80 + radius * Math.sin(toRad(ea));
    const large = ea - sa > 180 ? 1 : 0;
    return `M ${sx} ${sy} A ${radius} ${radius} 0 ${large} 1 ${ex} ${ey}`;
  }

  // Needle
  const needleX = 80 + 48 * Math.cos(toRad(angle));
  const needleY = 80 + 48 * Math.sin(toRad(angle));

  return (
    <svg viewBox="0 0 160 120" className="w-full max-w-[200px] mx-auto">
      {/* Arc segments */}
      {segments.map((seg, i) => (
        <path
          key={i}
          d={arcPath(seg.start, seg.end, r)}
          fill="none"
          stroke={seg.color}
          strokeWidth="10"
          strokeLinecap="round"
          opacity={0.9}
        />
      ))}
      {/* Needle */}
      <line
        x1="80" y1="80"
        x2={needleX} y2={needleY}
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="80" cy="80" r="5" fill={color} />

      {/* Zone labels */}
      <text x="18" y="105" fontSize="7" fill="#059669" fontWeight="500">LOW</text>
      <text x="60" y="28" fontSize="7" fill="#D97706" fontWeight="500">MED</text>
      <text x="120" y="48" fontSize="7" fill="#D97706" fontWeight="500">HIGH</text>
      <text x="128" y="100" fontSize="7" fill="#DC2626" fontWeight="500">EXT</text>
    </svg>
  );
}

export function RiskMeter() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const {
    risk_level, circuit_breaker, fii_streak_alert,
    gamma_risk, sebi_compliant, kelly_fraction, position_size_mult
  } = analysisData;

  const indicators = [
    {
      label: "Circuit Breaker",
      active: circuit_breaker,
      activeText: "ACTIVE — VIX > 25",
      inactiveText: "Inactive",
      warn: circuit_breaker,
    },
    {
      label: "FII Streak Alert",
      active: fii_streak_alert,
      activeText: "Watch — 3 day streak",
      inactiveText: "No streak",
      warn: fii_streak_alert,
    },
    {
      label: "Gamma Risk",
      active: gamma_risk,
      activeText: "ACTIVE — 3 DTE",
      inactiveText: "Inactive",
      warn: gamma_risk,
    },
    {
      label: "SEBI Compliant",
      active: sebi_compliant,
      activeText: "Yes",
      inactiveText: "ALERT — Check logs",
      warn: !sebi_compliant,
    },
  ];

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Risk Assessment</h3>
        <HelpPopover
          content={{
            title: "Risk Assessment",
            body: "Composite risk level derived from VIX, FII streak, gamma exposure, and SEBI compliance checks. Determines position sizing.",
            affectsVerdict: "EXTREME risk level overrides all signals to HOLD and reduces position size to 0.25x.",
            source: "India risk rules engine — VIX + FII + F&O gamma + SEBI checks",
          }}
        />
      </div>

      {/* Gauge */}
      <RiskGauge level={risk_level} />

      {/* Risk level text */}
      <div className="text-center mt-2 mb-4">
        <span className={cn(
          "text-2xl font-bold",
          risk_level === "LOW" ? "text-bullish-green" :
          risk_level === "MEDIUM" ? "text-neutral-blue" :
          risk_level === "HIGH" ? "text-warning-amber" :
          "text-bearish-red"
        )}>
          {risk_level}
        </span>
      </div>

      {/* Indicator rows */}
      <div className="space-y-2">
        {indicators.map(({ label, warn, active, activeText, inactiveText }) => (
          <div key={label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {warn
                ? <AlertTriangle size={14} className="text-warning-amber flex-shrink-0" />
                : <CheckCircle size={14} className="text-bullish-green flex-shrink-0" />
              }
              <span className="text-xs text-text-secondary">{label}</span>
            </div>
            <span className={cn(
              "text-xs font-medium",
              warn ? "text-warning-amber" : "text-bullish-green"
            )}>
              {active ? activeText : inactiveText}
            </span>
          </div>
        ))}
      </div>

      {/* Position size */}
      <div className="mt-4 p-3 rounded-btn bg-neutral-bg border border-neutral-blue/20">
        <div className="text-xs text-text-muted mb-1">Kelly Fraction: {kelly_fraction.toFixed(2)}</div>
        <div className="text-sm font-semibold text-neutral-blue">
          Recommended: {position_size_mult}x normal
        </div>
      </div>
    </div>
  );
}
