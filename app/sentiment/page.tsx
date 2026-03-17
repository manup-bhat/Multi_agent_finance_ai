"use client";
import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn, getFearGreedLabel } from "@/lib/utils";
import { MOCK_SENTIMENT_TIMELINE } from "@/lib/mock-data";
import { useApp } from "@/lib/app-context";

const EMOTIONS = [
  { name: "Excitement", pct: 35, color: "#059669" },
  { name: "Optimism", pct: 28, color: "#65A30D" },
  { name: "Fear", pct: 18, color: "#D97706" },
  { name: "Nervousness", pct: 12, color: "#EA580C" },
  { name: "Other", pct: 7, color: "#94A3B8" },
];

const TOP_HEADLINES = [
  { text: "Reliance Q3 PAT beats estimates by 4.2%", score: 0.82 },
  { text: "FII net buyers for 3rd consecutive session", score: 0.45 },
  { text: "Jio subscriber growth continues strong momentum", score: 0.61 },
];

const TIME_RANGES = ["3 days", "1 week", "1 month"] as const;

function FearGreedGaugeLarge({ score }: { score: number }) {
  const { label, color } = getFearGreedLabel(score);
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const angle = -180 + (score / 100) * 180;
  const r = 80;
  const needleX = 120 + r * Math.cos(toRad(angle));
  const needleY = 110 + r * Math.sin(toRad(angle));

  const segments = [
    { start: -180, end: -144, color: "#DC2626", label: "Extreme Fear" },
    { start: -144, end: -108, color: "#D97706", label: "Fear" },
    { start: -108, end: -72, color: "#CA8A04", label: "Neutral" },
    { start: -72, end: -36, color: "#65A30D", label: "Greed" },
    { start: -36, end: 0, color: "#059669", label: "Extreme Greed" },
  ];

  function arcPath(sa: number, ea: number, rOuter: number, rInner: number) {
    const sx = 120 + rOuter * Math.cos(toRad(sa));
    const sy = 110 + rOuter * Math.sin(toRad(sa));
    const ex = 120 + rOuter * Math.cos(toRad(ea));
    const ey = 110 + rOuter * Math.sin(toRad(ea));
    const ixs = 120 + rInner * Math.cos(toRad(sa));
    const iys = 110 + rInner * Math.sin(toRad(sa));
    const ixe = 120 + rInner * Math.cos(toRad(ea));
    const iye = 110 + rInner * Math.sin(toRad(ea));
    return `M ${sx} ${sy} A ${rOuter} ${rOuter} 0 0 1 ${ex} ${ey} L ${ixe} ${iye} A ${rInner} ${rInner} 0 0 0 ${ixs} ${iys} Z`;
  }

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 240 130" className="w-full max-w-xs">
        {segments.map((seg, i) => (
          <path key={i} d={arcPath(seg.start, seg.end, r, r * 0.65)} fill={seg.color} opacity={0.85} />
        ))}
        {/* Zone labels */}
        {segments.map((seg, i) => {
          const mid = (seg.start + seg.end) / 2;
          const lx = 120 + (r + 18) * Math.cos(toRad(mid));
          const ly = 110 + (r + 18) * Math.sin(toRad(mid));
          return <text key={i} x={lx} y={ly} textAnchor="middle" fontSize="7" fill={seg.color} fontWeight="500">{seg.label}</text>;
        })}
        {/* Needle */}
        <line x1="120" y1="110" x2={needleX} y2={needleY} stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-text-primary" />
        <circle cx="120" cy="110" r="7" className="fill-text-primary" />
        {/* Score */}
        <text x="120" y="95" textAnchor="middle" className="fill-text-primary" fontSize="24" fontWeight="700">{score}</text>
      </svg>
      <span className="text-xl font-bold mt-1" style={{ color }}>{label.toUpperCase()}</span>
    </div>
  );
}

export default function SentimentPage() {
  const { analysisData } = useApp();
  const [timeRange, setTimeRange] = useState<typeof TIME_RANGES[number]>("1 month");
  const score = analysisData?.fear_greed ?? 62;

  const sliceMap: Record<typeof TIME_RANGES[number], number> = { "3 days": 3, "1 week": 7, "1 month": 30 };
  const timelineData = MOCK_SENTIMENT_TIMELINE.slice(-sliceMap[timeRange]);

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">Sentiment & Emotion</h1>

      {/* Fear & Greed Gauge */}
      <div className="card-base p-6">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Fear & Greed Index</h3>
          <HelpPopover content={{
            title: "Fear & Greed Index",
            body: "Composite index combining India VIX, FII flows, PCR, StockTwits sentiment, and GDELT global tone. Range 0–100: extreme fear to extreme greed.",
            affectsVerdict: "Readings above 80 (Extreme Greed) trigger the Euphoria Warning and can override bullish signals to HOLD.",
            source: "Composite: VIX (30%) + FII (25%) + PCR (20%) + Social (15%) + GDELT (10%)",
          }} />
        </div>
        <FearGreedGaugeLarge score={score} />
      </div>

      {/* 3-col breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Institutional — FinBERT */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Institutional (FinBERT)</h3>
          <div className="text-3xl font-bold tabular-nums text-bullish-green mb-1">+0.42</div>
          <div className="text-xs text-text-muted mb-3">Score from -1 (bearish) to +1 (bullish)</div>
          {/* Horizontal sentiment bar */}
          <div className="relative h-3 rounded-pill overflow-hidden" style={{ background: "linear-gradient(90deg, #DC2626, #D97706, #059669)" }}>
            <div
              className="absolute top-0 w-3 h-3 rounded-full border-2 border-white shadow-sm bg-bullish-green transition-all duration-300"
              style={{ left: `${(0.42 + 1) / 2 * 100}%`, transform: "translateX(-50%)" }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-muted mt-1 mb-3">
            <span>-1 Bearish</span><span>0</span><span>+1 Bullish</span>
          </div>
          <div className="text-xs text-text-muted mb-2">Based on 12 Finlight articles + 6 RSS feeds</div>
          <div className="space-y-2">
            {TOP_HEADLINES.map((h, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={cn("text-xs font-bold flex-shrink-0 tabular-nums", h.score > 0 ? "text-bullish-green" : "text-bearish-red")}>
                  {h.score > 0 ? "+" : ""}{h.score.toFixed(2)}
                </span>
                <span className="text-xs text-text-secondary line-clamp-2">{h.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Retail Social — GoEmotions */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Retail Social (GoEmotions)</h3>
          <div className="space-y-2.5 mb-4">
            {EMOTIONS.map((e) => (
              <div key={e.name}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-text-secondary">{e.name}</span>
                  <span className="font-medium tabular-nums" style={{ color: e.color }}>{e.pct}%</span>
                </div>
                <div className="h-2 bg-surface-raised rounded-pill overflow-hidden">
                  <div className="h-full rounded-pill transition-all duration-500" style={{ width: `${e.pct}%`, background: e.color }} />
                </div>
              </div>
            ))}
          </div>
          <div className="pt-3 border-t border-border">
            <div className="text-xs text-text-muted mb-1">StockTwits</div>
            <div className="h-2 rounded-pill overflow-hidden flex">
              <div className="bg-bullish-green" style={{ width: "68%" }} />
              <div className="bg-bearish-red flex-1" />
            </div>
            <div className="flex justify-between text-xs mt-1">
              <span className="text-bullish-green font-medium">68% Bullish</span>
              <span className="text-text-muted">247 posts</span>
            </div>
          </div>
        </div>

        {/* GDELT Macro */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">GDELT Macro Tone</h3>
          <div className="flex flex-col items-center py-4">
            <svg viewBox="0 0 100 100" className="w-24 h-24 text-neutral-blue">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="4" opacity="0.2" />
              <circle cx="50" cy="50" r="32" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.15" />
              <circle cx="50" cy="50" r="22" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.1" />
              {/* Meridians */}
              {[0, 45, 90, 135].map((a) => {
                const toR = (d: number) => (d * Math.PI) / 180;
                return <line key={a} x1={50 + 42 * Math.cos(toR(a))} y1={50 + 42 * Math.sin(toR(a))} x2={50 - 42 * Math.cos(toR(a))} y2={50 - 42 * Math.sin(toR(a))} stroke="currentColor" strokeWidth="1" opacity="0.1" />;
              })}
              <text x="50" y="54" textAnchor="middle" fontSize="12" fontWeight="700" className="fill-text-primary">-0.3</text>
            </svg>
          </div>
          <div className="space-y-2 text-center">
            <div className="text-2xl font-bold text-warning-amber tabular-nums">-0.3</div>
            <div className="text-xs text-text-muted">Slight Negative Global Tone</div>
            <div className="text-xs text-text-secondary">47 India-specific events tracked</div>
            <div className="px-3 py-2 rounded-btn bg-surface-raised mt-2">
              <div className="text-xs text-text-muted">Dominant theme</div>
              <div className="text-sm font-medium text-text-primary">Economic Policy</div>
            </div>
          </div>
        </div>
      </div>

      {/* Sentiment Timeline */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text-primary">Sentiment Timeline</h3>
            <HelpPopover content={{
              title: "Sentiment Timeline",
              body: "Rolling composite sentiment score showing how market mood has evolved. Annotations mark key fundamental events that shifted sentiment.",
              affectsVerdict: "Recent sentiment trend (last 3–7 days) is weighted more heavily than historical data in the emotion agent.",
              source: "Composite: FinBERT + StockTwits + GDELT, updated daily",
            }} />
          </div>
          <div className="flex gap-1">
            {TIME_RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-badge font-medium transition-all duration-150",
                  timeRange === r ? "bg-saffron text-white" : "text-text-muted hover:text-text-primary hover:bg-surface-raised"
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={timelineData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                interval="preserveStartEnd" tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} domain={[-1.5, 1.5]}
                tickFormatter={(v) => v.toFixed(1)} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [v.toFixed(3), ""]}
              />
              <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="3 2" />
              <Line type="monotone" dataKey="composite" stroke="#FF6B00" strokeWidth={2} dot={false} name="Composite" />
              <Line type="monotone" dataKey="finbert" stroke="#059669" strokeWidth={1.5} strokeDasharray="3 2" dot={false} name="FinBERT" />
              <Line type="monotone" dataKey="social" stroke="#1D4ED8" strokeWidth={1.5} strokeDasharray="3 2" dot={false} name="Social" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 bg-saffron" /><span className="text-text-muted">Composite</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 bg-bullish-green" /><span className="text-text-muted">FinBERT</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 bg-neutral-blue" /><span className="text-text-muted">Social</span></div>
        </div>
      </div>
    </div>
  );
}
