"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { useApp } from "@/lib/app-context";
import { AlertTriangle, CheckCircle } from "lucide-react";

function RiskGauge({ level }: { level: string }) {
  const levelMap: Record<string, { angle: number; color: string }> = {
    LOW:     { angle: -80, color: "#059669" },
    MEDIUM:  { angle: -10, color: "#1D4ED8" },
    HIGH:    { angle:  60, color: "#D97706" },
    EXTREME: { angle: 120, color: "#DC2626" },
  };
  const { angle, color } = levelMap[level.toUpperCase()] ?? levelMap.MEDIUM;
  const toRad = (deg: number) => (deg * Math.PI) / 180;

  const segments = [
    { start: -220, end: -150, color: "#059669" },
    { start: -150, end: -80,  color: "#65A30D" },
    { start: -80,  end: -10,  color: "#D97706" },
    { start: -10,  end:  40,  color: "#DC2626" },
  ];

  function arcPath(sa: number, ea: number, radius: number) {
    const sx = 80 + radius * Math.cos(toRad(sa));
    const sy = 80 + radius * Math.sin(toRad(sa));
    const ex = 80 + radius * Math.cos(toRad(ea));
    const ey = 80 + radius * Math.sin(toRad(ea));
    const large = ea - sa > 180 ? 1 : 0;
    return `M ${sx} ${sy} A ${radius} ${radius} 0 ${large} 1 ${ex} ${ey}`;
  }

  const needleX = 80 + 48 * Math.cos(toRad(angle));
  const needleY = 80 + 48 * Math.sin(toRad(angle));

  return (
    <svg viewBox="0 0 160 120" className="w-full max-w-[200px] mx-auto">
      {segments.map((seg, i) => (
        <path key={i} d={arcPath(seg.start, seg.end, 60)}
          fill="none" stroke={seg.color} strokeWidth="10" strokeLinecap="round" opacity={0.9} />
      ))}
      <line x1="80" y1="80" x2={needleX} y2={needleY}
        stroke={color} strokeWidth="3" strokeLinecap="round" />
      <circle cx="80" cy="80" r="5" fill={color} />
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
    risk_level,
    circuit_breaker_active,
    euphoria_flag,
    key_risks,
    warnings,
  } = analysisData;

  const riskUpper = risk_level.toUpperCase();

  const indicators = [
    {
      label: "Circuit Breaker",
      warn: circuit_breaker_active,
      text: circuit_breaker_active ? "ACTIVE — VIX exceeded threshold" : "Inactive",
    },
    {
      label: "Euphoria Flag",
      warn: !!euphoria_flag,
      text: euphoria_flag ? "ACTIVE — extreme social greed" : "No euphoria",
    },
    {
      label: "API Warnings",
      warn: warnings.length > 0,
      text: warnings.length > 0 ? `${warnings.length} data source warning(s)` : "All sources healthy",
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
            affectsVerdict: "EXTREME risk level overrides all signals to HOLD and reduces position size.",
            source: "India risk rules engine — VIX + FII + F&O gamma + SEBI checks",
          }}
        />
      </div>

      <RiskGauge level={riskUpper} />

      <div className="text-center mt-2 mb-4">
        <span className={cn(
          "text-2xl font-bold",
          riskUpper === "LOW"     ? "text-bullish-green"  :
          riskUpper === "MEDIUM"  ? "text-neutral-blue"   :
          riskUpper === "HIGH"    ? "text-warning-amber"  :
          "text-bearish-red"
        )}>
          {riskUpper}
        </span>
      </div>

      <div className="space-y-2">
        {indicators.map(({ label, warn, text }) => (
          <div key={label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {warn
                ? <AlertTriangle size={14} className="text-warning-amber flex-shrink-0" />
                : <CheckCircle size={14} className="text-bullish-green flex-shrink-0" />
              }
              <span className="text-xs text-text-secondary">{label}</span>
            </div>
            <span className={cn("text-xs font-medium", warn ? "text-warning-amber" : "text-bullish-green")}>
              {text}
            </span>
          </div>
        ))}
      </div>

      {/* Key risks */}
      {key_risks.length > 0 && (
        <div className="mt-4 space-y-1.5">
          <div className="text-xs font-medium text-text-muted uppercase tracking-widest mb-2">Key Risks</div>
          {key_risks.slice(0, 3).map((risk, i) => (
            <div key={i} className="flex items-start gap-2">
              <AlertTriangle size={12} className="text-warning-amber flex-shrink-0 mt-0.5" />
              <span className="text-xs text-text-secondary leading-relaxed">{risk}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
