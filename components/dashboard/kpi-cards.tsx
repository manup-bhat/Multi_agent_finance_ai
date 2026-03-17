"use client";
import { useApp } from "@/lib/app-context";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn, getVixStatus, getFearGreedLabel } from "@/lib/utils";
import { MOCK_FII_DII } from "@/lib/mock-data";
import {
  BarChart, Bar, ResponsiveContainer, LineChart, Line, Cell
} from "recharts";

// Small sparkline for VIX
const vixSparkData = Array.from({ length: 30 }, (_, i) => ({
  v: 12 + Math.sin(i / 5) * 3 + Math.random() * 2,
}));

// Fear & Greed gauge
function FearGreedGauge({ score }: { score: number }) {
  const { label, color } = getFearGreedLabel(score);
  const angle = -90 + (score / 100) * 180;
  const rad = (angle * Math.PI) / 180;
  const needleX = 50 + 36 * Math.cos(rad);
  const needleY = 55 + 36 * Math.sin(rad);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 100 70" className="w-full max-w-[120px]">
        {/* Arc segments */}
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
        {/* Needle */}
        <line
          x1="50" y1="55"
          x2={needleX} y2={needleY}
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          className="text-text-primary"
        />
        <circle cx="50" cy="55" r="4" className="fill-text-primary" />
        {/* Score */}
        <text x="50" y="42" textAnchor="middle" className="fill-text-primary" fontSize="14" fontWeight="700">
          {score}
        </text>
      </svg>
      <span className="text-xs font-medium mt-1" style={{ color }}>
        {label}
      </span>
    </div>
  );
}

export function KPICards() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const { india_vix, fii_5d_avg, fear_greed, delivery_pct } = analysisData;
  const vixStatus = getVixStatus(india_vix);

  // Last 5 days FII data
  const fiiLast5 = MOCK_FII_DII.slice(-5);

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Card 1: India VIX */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">India VIX</span>
          <HelpPopover
            content={{
              title: "India VIX — The Fear Gauge",
              body: "India VIX measures market volatility calculated from Nifty options order book. Higher values indicate more fear and uncertainty in the market.",
              affectsVerdict: "VIX above 25 triggers a circuit breaker — all signals override to HOLD regardless of other analysis.",
              source: "NSE India via yfinance (^INDIAVIX)",
            }}
          />
        </div>
        <div className={cn("text-4xl font-bold tabular-nums", vixStatus.color)}>
          {india_vix.toFixed(1)}
        </div>
        <div className={cn("text-xs font-medium px-2 py-0.5 rounded-badge inline-block mt-1", vixStatus.bg, vixStatus.color)}>
          {vixStatus.label}
        </div>
        <div className="mt-3 h-10">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={vixSparkData}>
              <Line type="monotone" dataKey="v" stroke={india_vix < 18 ? "#059669" : india_vix < 25 ? "#D97706" : "#DC2626"} dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="text-xs text-text-muted mt-2">+0.8 from yesterday</div>
      </div>

      {/* Card 2: FII Net Flow */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">FII Net Flow</span>
          <HelpPopover
            content={{
              title: "FII Net Flow — Institutional Sentiment",
              body: "Foreign Institutional Investor net buy/sell data shows the direction of large institutional money. Consistent buying is a bullish signal.",
              affectsVerdict: "Strong FII buying (>₹2000Cr/day) is weighted positively in the macro agent's analysis.",
              source: "NSE India via nselib — daily participant data",
            }}
          />
        </div>
        <div className={cn("text-4xl font-bold tabular-nums", fii_5d_avg >= 0 ? "text-bullish-green" : "text-bearish-red")}>
          {fii_5d_avg >= 0 ? "+" : ""}₹{Math.abs(Math.round(fii_5d_avg / 100) * 100).toLocaleString("en-IN")}
        </div>
        <div className="text-xs text-text-muted mt-0.5">TODAY'S FLOW</div>
        <div className="mt-3 h-10">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={fiiLast5} barSize={10}>
              <Bar dataKey="fii">
                {fiiLast5.map((d, i) => (
                  <Cell key={i} fill={d.fii >= 0 ? "#059669" : "#DC2626"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="text-xs text-text-muted mt-2">Streak: 3 days buying</div>
      </div>

      {/* Card 3: Fear & Greed */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-2">
          <span className="section-label">Fear & Greed</span>
          <HelpPopover
            content={{
              title: "Fear & Greed Index",
              body: "Composite sentiment index (0-100) combining VIX, FII flows, PCR, and social media sentiment. Below 20 = Extreme Fear, above 80 = Extreme Greed.",
              affectsVerdict: "Extreme fear or greed readings can trigger contrarian signals in the emotion agent.",
              source: "Composite — VIX + FII + PCR + StockTwits + GDELT",
            }}
          />
        </div>
        <FearGreedGauge score={fear_greed} />
      </div>

      {/* Card 4: Delivery % */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">Delivery %</span>
          <HelpPopover
            content={{
              title: "Delivery Volume %",
              body: "Percentage of traded volume that resulted in actual delivery (not squared off intraday). High delivery % indicates strong conviction buying/selling.",
              affectsVerdict: "Delivery % above 40% is considered high conviction. The quant agent weights this positively for trend continuation.",
              source: "NSE India — daily delivery data",
            }}
          />
        </div>
        <div className={cn("text-4xl font-bold tabular-nums", delivery_pct > 40 ? "text-bullish-green" : "text-text-primary")}>
          {delivery_pct.toFixed(1)}%
        </div>
        <div className="text-xs text-text-muted mt-0.5">DELIVERY VOLUME</div>
        <div className="text-xs text-text-secondary mt-2">Above 40% = strong conviction</div>
        {/* Progress bar */}
        <div className="mt-3 h-2 bg-surface-raised rounded-pill overflow-hidden">
          <div
            className="h-full rounded-pill bg-bullish-green transition-all duration-500"
            style={{ width: `${Math.min(delivery_pct, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-text-muted mt-1">
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}
