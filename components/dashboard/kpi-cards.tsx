"use client";
import { useApp } from "@/lib/app-context";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn, getVixStatus, getFearGreedLabel } from "@/lib/utils";
import { ResponsiveContainer, LineChart, Line } from "recharts";

function FearGreedGauge({ score }: { score: number }) {
  const { label, color } = getFearGreedLabel(score);
  const angle = -90 + (score / 100) * 180;
  const rad = (angle * Math.PI) / 180;
  const needleX = 50 + 36 * Math.cos(rad);
  const needleY = 55 + 36 * Math.sin(rad);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 70" className="w-full max-w-[120px]">
        {[
          { start: -90, end: -54, color: "#DC2626" },
          { start: -54, end: -18, color: "#D97706" },
          { start: -18, end: 18, color: "#CA8A04" },
          { start: 18, end: 54, color: "#65A30D" },
          { start: 54, end: 90, color: "#059669" },
        ].map((seg, i) => {
          const r = 40;
          const toRad = (deg: number) => (deg * Math.PI) / 180;
          const sx = 50 + r * Math.cos(toRad(seg.start));
          const sy = 55 + r * Math.sin(toRad(seg.start));
          const ex = 50 + r * Math.cos(toRad(seg.end));
          const ey = 55 + r * Math.sin(toRad(seg.end));
          return (
            <path
              key={i}
              d={`M 50 55 L ${sx} ${sy} A ${r} ${r} 0 0 1 ${ex} ${ey} Z`}
              fill={seg.color}
              opacity={0.85}
            />
          );
        })}
        <line x1="50" y1="55" x2={needleX} y2={needleY}
          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
          className="text-text-primary" />
        <circle cx="50" cy="55" r="4" className="fill-text-primary" />
        <text x="50" y="42" textAnchor="middle" className="fill-text-primary" fontSize="14" fontWeight="700">
          {Math.round(score)}
        </text>
      </svg>
      <span className="text-xs font-medium mt-1" style={{ color }}>{label}</span>
    </div>
  );
}

export function KPICards() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const { vix_current, fii_net_5d, fear_greed_index, social_bullish_pct, social_post_volume } = analysisData;

  const vix = vix_current ?? 0;
  const fiiNet = fii_net_5d ?? 0;
  const fearGreed = fear_greed_index ?? 50;
  const vixStatus = getVixStatus(vix);

  // Single-point sparklines — real data only (current VIX point)
  const vixSparkData = [{ v: vix }];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Card 1: India VIX */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">India VIX</span>
          <HelpPopover
            content={{
              title: "India VIX — The Fear Gauge",
              body: "India VIX measures market volatility calculated from Nifty options order book. Higher values indicate more fear and uncertainty.",
              affectsVerdict: "VIX above 25 triggers a circuit breaker — all signals override to HOLD.",
              source: "NSE India via yfinance (^INDIAVIX)",
            }}
          />
        </div>
        {vix_current != null ? (
          <>
            <div className={cn("text-4xl font-bold tabular-nums", vixStatus.color)}>
              {vix.toFixed(1)}
            </div>
            <div className={cn("text-xs font-medium px-2 py-0.5 rounded-badge inline-block mt-1", vixStatus.bg, vixStatus.color)}>
              {vixStatus.label}
            </div>
          </>
        ) : (
          <div className="text-2xl font-bold text-text-muted">N/A</div>
        )}
        <div className="mt-3 h-10">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={vixSparkData}>
              <Line type="monotone" dataKey="v"
                stroke={vix < 18 ? "#059669" : vix < 25 ? "#D97706" : "#DC2626"}
                dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="text-xs text-text-muted mt-2">Live from backend</div>
      </div>

      {/* Card 2: FII Net Flow */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">FII Net 5d</span>
          <HelpPopover
            content={{
              title: "FII Net Flow — 5-Day Sum",
              body: "Foreign Institutional Investor 5-day cumulative net buy/sell. Consistent buying is a bullish signal.",
              affectsVerdict: "Strong FII buying is weighted positively in the macro agent.",
              source: "NSE India via nselib — daily participant data",
            }}
          />
        </div>
        {fii_net_5d != null ? (
          <>
            <div className={cn("text-3xl font-bold tabular-nums", fiiNet >= 0 ? "text-bullish-green" : "text-bearish-red")}>
              {fiiNet >= 0 ? "+" : ""}₹{Math.abs(fiiNet).toLocaleString("en-IN", { maximumFractionDigits: 0 })}Cr
            </div>
            <div className="text-xs text-text-muted mt-0.5">5-DAY NET FLOW</div>
            <div className={cn("text-xs font-medium mt-2", fiiNet >= 0 ? "text-bullish-green" : "text-bearish-red")}>
              {fiiNet >= 0 ? "Net Buyers" : "Net Sellers"}
            </div>
          </>
        ) : (
          <div className="text-2xl font-bold text-text-muted">N/A</div>
        )}
      </div>

      {/* Card 3: Fear & Greed */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="section-label">Fear & Greed</span>
          <HelpPopover
            content={{
              title: "Fear & Greed Index",
              body: "Composite sentiment index (0–100) combining VIX, FII flows, PCR, and social media sentiment.",
              affectsVerdict: "Extreme readings can trigger contrarian signals in the emotion agent.",
              source: "Composite — VIX + FII + PCR + StockTwits + GDELT",
            }}
          />
        </div>
        {fear_greed_index != null ? (
          <FearGreedGauge score={fearGreed} />
        ) : (
          <div className="text-2xl font-bold text-text-muted mt-4">N/A</div>
        )}
      </div>

      {/* Card 4: Social Sentiment */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">Social Pulse</span>
          <HelpPopover
            content={{
              title: "Social Sentiment",
              body: "StockTwits & MoneyControl community sentiment percentage. Post volume indicates engagement level.",
              affectsVerdict: "High social volume with extreme readings triggers euphoria flag.",
              source: "StockTwits API + MoneyControl comments scraper",
            }}
          />
        </div>
        {social_bullish_pct != null ? (
          <>
            <div className={cn("text-4xl font-bold tabular-nums", social_bullish_pct >= 50 ? "text-bullish-green" : "text-bearish-red")}>
              {social_bullish_pct.toFixed(1)}%
            </div>
            <div className="text-xs text-text-muted mt-0.5">BULLISH COMMUNITY</div>
            <div className="mt-3 h-2 bg-surface-raised rounded-pill overflow-hidden flex">
              <div className="bg-bullish-green transition-all duration-500" style={{ width: `${social_bullish_pct}%` }} />
              <div className="bg-bearish-red flex-1" />
            </div>
            <div className="text-xs text-text-muted mt-2">
              {social_post_volume != null ? `${social_post_volume} posts` : ""}
            </div>
          </>
        ) : (
          <div className="text-2xl font-bold text-text-muted">N/A</div>
        )}
      </div>
    </div>
  );
}
