"use client";
import { useApp } from "@/lib/app-context";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn, getVixStatus, getFearGreedLabel } from "@/lib/utils";

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

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Card 1: India VIX */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">India VIX</span>
          <HelpPopover
            content={{
              title: "India VIX — Volatility Index",
              body: "India VIX is NSE's official fear gauge, computed from Nifty50 option order book prices. A rising VIX means the market expects bigger price swings ahead — options traders are paying more for protection.",
              level: "beginner",
              tips: [
                "Below 13 = Low fear, complacency — be cautious of reversals",
                "13–18 = Normal range — healthy market",
                "18–25 = Elevated — reduce position sizes",
                "Above 25 = High Fear — circuit breaker active, HOLD only",
              ],
              affectsVerdict: "VIX is the primary circuit breaker trigger. Values above 20 cut position sizing by 50%; above 25 forces HOLD mode regardless of other signals.",
              source: "NSE India VIX — computed from Nifty50 near+mid-month option strikes; fetched live via yfinance ^INDIAVIX",
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
            <div className="mt-3 text-xs text-text-muted">
              {vix < 18 ? "Healthy market conditions" : vix < 25 ? "Elevated — reduce position sizes" : "High Fear — HOLD mode active"}
            </div>
          </>
        ) : (
          <div className="text-2xl font-bold text-text-muted">N/A</div>
        )}
      </div>

      {/* Card 2: FII Net Flow */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">FII Net 5d</span>
          <HelpPopover
            content={{
              title: "FII Net Flow — 5-Day Rolling Sum",
              body: "This shows how much net money (buys minus sells) Foreign Institutional Investors have put into Indian equities over the last 5 trading days. Positive = net buyers (bullish). Negative = net sellers (bearish). Large foreign outflows often precede index corrections.",
              level: "beginner",
              tips: [
                "Above +₹2,000Cr = significant foreign buying — bullish pressure",
                "Below -₹2,000Cr = significant foreign selling — bearish pressure",
                "FII flows are the single biggest driver of Nifty50 index moves",
                "FII selling + DII buying = net neutral — often sideways market",
              ],
              affectsVerdict: "The 5-day FII net flow is consistently one of the top-5 SHAP features in all three ML models. Large negative flows reduce the macro agent's score significantly.",
              source: "NSE India participant-wise daily trading data (cash + F&O) — fetched via nselib, published post-market",
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
              body: "A composite score (0–100) measuring the overall emotional state of the Indian market. It combines five data sources: India VIX, FII 5-day flow, NSE Put-Call Ratio, StockTwits social sentiment, and GDELT global news tone. Extreme values are contrarian signals — when everyone is greedy, it is often a good time to be cautious.",
              level: "beginner",
              tips: [
                "0–20 = Extreme Fear — historically strong buy zone",
                "20–40 = Fear — cautious, but quality setups exist",
                "40–60 = Neutral — no strong directional bias",
                "60–80 = Greed — be selective, profits exist but risk is rising",
                "80–100 = Extreme Greed — Euphoria Warning: HOLD mode",
              ],
              affectsVerdict: "A score above 80 activates the Euphoria Warning flag, which overrides STRONG BUY to BUY and reduces all position sizing.",
              source: "Composite: VIX 30% + FII flow 25% + PCR 20% + StockTwits 15% + GDELT 10% — computed in sentiment_analyzer.py",
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
              title: "Social Pulse — Community Sentiment",
              body: "The percentage of social media posts about this stock that are bullish (positive). Sourced from StockTwits and MoneyControl community. High post volume combined with extreme sentiment (above 80% or below 20%) is a contrarian signal — retail crowds are often wrong at extremes.",
              level: "intermediate",
              tips: [
                "Above 80% bullish + high volume = Euphoria warning zone",
                "Below 20% bullish + high volume = Capitulation — potential bounce",
                "50–70% = Normal healthy bullish skew",
                "Low post volume = low conviction reading, treat cautiously",
              ],
              affectsVerdict: "Social sentiment carries a 15% weight in the Fear & Greed Index. Above 85% bullish with 500+ posts triggers the Euphoria flag.",
              source: "StockTwits API (ticker-specific) + MoneyControl discussion board — processed via GoEmotions classifier",
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
