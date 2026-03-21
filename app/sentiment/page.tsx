"use client";
import useSWR from "swr";
import { useState } from "react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, getFearGreedLabel } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getSentiment, getApiErrorMessage } from "@/lib/api-client";

const LABEL_COLORS: Record<string, string> = {
  POSITIVE: "#059669",
  BULLISH: "#059669",
  NEUTRAL: "#D97706",
  NEGATIVE: "#DC2626",
  BEARISH: "#DC2626",
};

function FearGreedGauge({ score }: { score: number }) {
  const { label, color } = getFearGreedLabel(score);
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const angle = -180 + (score / 100) * 180;
  const r = 80;
  const needleX = 120 + r * Math.cos(toRad(angle));
  const needleY = 110 + r * Math.sin(toRad(angle));

  const segments = [
    { start: -180, end: -144, color: "#DC2626", label: "Extreme Fear" },
    { start: -144, end: -108, color: "#D97706", label: "Fear" },
    { start: -108, end: -72,  color: "#CA8A04", label: "Neutral" },
    { start: -72,  end: -36,  color: "#65A30D", label: "Greed" },
    { start: -36,  end: 0,    color: "#059669", label: "Extreme Greed" },
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
        {segments.map((seg, i) => {
          const mid = (seg.start + seg.end) / 2;
          const lx = 120 + (r + 18) * Math.cos(toRad(mid));
          const ly = 110 + (r + 18) * Math.sin(toRad(mid));
          return (
            <text key={i} x={lx} y={ly} textAnchor="middle" fontSize="7" fill={seg.color} fontWeight="500">
              {seg.label}
            </text>
          );
        })}
        <line x1="120" y1="110" x2={needleX} y2={needleY} stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-text-primary" />
        <circle cx="120" cy="110" r="7" className="fill-text-primary" />
        <text x="120" y="95" textAnchor="middle" className="fill-text-primary" fontSize="24" fontWeight="700">{score}</text>
      </svg>
      <span className="text-xl font-bold mt-1" style={{ color }}>{label.toUpperCase()}</span>
    </div>
  );
}

export default function SentimentPage() {
  const { selectedTicker, analysisData } = useApp();

  const { data: sentiment, error, isLoading } = useSWR(
    selectedTicker ? ["sentiment", selectedTicker] : null,
    () => getSentiment(selectedTicker),
    { revalidateOnFocus: false }
  );

  const fearGreedScore = sentiment?.fear_greed_index
    ?? analysisData?.fear_greed_index
    ?? null;

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-64 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Sentiment & Emotion</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load sentiment data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      </div>
    );
  }

  if (!sentiment) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Sentiment & Emotion</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="font-medium text-text-secondary mb-2">No sentiment data available</p>
          <p className="text-sm">Run an analysis from the Dashboard to load sentiment data for {selectedTicker}.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">Sentiment & Emotion</h1>
        <span className="text-sm text-text-muted">{selectedTicker}</span>
      </div>

      {/* Fear & Greed Gauge */}
      <div className="card-base p-6">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Fear & Greed Index</h3>
          <HelpPopover content={{
            title: "Fear & Greed Index",
            body: "A composite score from 0 to 100 that summarises the overall market emotion. 0 = Extreme Fear (everyone is panic-selling), 100 = Extreme Greed (everyone is euphoric and buying). Extreme readings in either direction are contrarian signals — the market tends to reverse when fear or greed peaks.",
            level: "beginner",
            tips: [
              "0–20 = Extreme Fear — historically a buying opportunity",
              "20–40 = Fear — cautious but opportunities exist",
              "40–60 = Neutral — balanced market sentiment",
              "60–80 = Greed — be cautious with new positions",
              "80–100 = Extreme Greed — Euphoria Warning active",
            ],
            affectsVerdict: "A score above 80 activates the Euphoria Warning flag, which overrides STRONG BUY verdicts to BUY and activates the circuit breaker rule.",
            source: "Composite formula: India VIX (30%) + FII 5-day flow (25%) + NSE PCR (20%) + StockTwits social sentiment (15%) + GDELT news tone (10%)",
          }} />
          {sentiment.euphoria_flag && (
            <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded-badge bg-bearish-bg text-bearish-red">
              EUPHORIA WARNING
            </span>
          )}
          {sentiment.high_volume_flag && (
            <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded-badge bg-warning-bg text-warning-amber">
              HIGH VOLUME
            </span>
          )}
        </div>
        {fearGreedScore != null && <FearGreedGauge score={Math.round(fearGreedScore)} />}
      </div>

      {/* 3-col breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Institutional FinBERT */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Institutional (FinBERT)</h3>
          <div className="text-3xl font-bold tabular-nums mb-1" style={{
            color: sentiment.alpha_vantage_score > 0 ? "#059669" : sentiment.alpha_vantage_score < 0 ? "#DC2626" : "#D97706"
          }}>
            {sentiment.alpha_vantage_score > 0 ? "+" : ""}{sentiment.alpha_vantage_score.toFixed(2)}
          </div>
          <div className="text-xs text-text-muted mb-3">Score from -1 (bearish) to +1 (bullish)</div>
          <div className="relative h-3 rounded-pill overflow-hidden mb-1" style={{
            background: "linear-gradient(90deg, #DC2626, #D97706, #059669)",
          }}>
            <div
              className="absolute top-0 w-3 h-3 rounded-full border-2 border-white shadow-sm transition-all duration-300"
              style={{
                left: `${((sentiment.alpha_vantage_score + 1) / 2) * 100}%`,
                transform: "translateX(-50%)",
                background: sentiment.alpha_vantage_score > 0 ? "#059669" : "#DC2626",
              }}
            />
          </div>
          <div className="flex justify-between text-xs text-text-muted mb-4">
            <span>-1 Bearish</span><span>0</span><span>+1 Bullish</span>
          </div>

          {/* Top headlines from API */}
          {sentiment.articles.slice(0, 4).map((a, i) => (
            <div key={i} className="flex items-start gap-2 mb-2">
              <span className={cn(
                "text-xs font-bold flex-shrink-0 tabular-nums",
                a.sentiment > 0 ? "text-bullish-green" : a.sentiment < 0 ? "text-bearish-red" : "text-text-muted"
              )}>
                {a.sentiment > 0 ? "+" : ""}{a.sentiment.toFixed(2)}
              </span>
              <span className="text-xs text-text-secondary line-clamp-2">{a.headline}</span>
            </div>
          ))}
        </div>

        {/* Social Sentiment */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Retail Social (StockTwits)</h3>
          <div className="text-3xl font-bold tabular-nums mb-1" style={{
            color: sentiment.composite_label === "BULLISH" || sentiment.composite_label === "POSITIVE"
              ? "#059669" : sentiment.composite_label === "BEARISH" || sentiment.composite_label === "NEGATIVE"
              ? "#DC2626" : "#D97706"
          }}>
            {sentiment.composite_label}
          </div>
          <div className="text-xs text-text-muted mb-4">
            Composite score: {sentiment.composite_score.toFixed(3)}
          </div>

          {/* Bullish / Bearish split */}
          <div className="mb-4">
            <div className="h-3 rounded-pill overflow-hidden flex mb-1">
              <div className="bg-bullish-green transition-all" style={{ width: `${sentiment.social_bullish_pct}%` }} />
              <div className="bg-bearish-red flex-1" />
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-bullish-green font-medium">{sentiment.social_bullish_pct.toFixed(0)}% Bullish</span>
              <span className="text-text-muted">{sentiment.social_post_volume.toLocaleString("en-IN")} posts</span>
            </div>
          </div>

          {/* Score breakdown */}
          <div className="space-y-2 pt-3 border-t border-border">
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Institutional Score</span>
              <span className={cn("font-medium tabular-nums", sentiment.institutional_score > 0 ? "text-bullish-green" : "text-bearish-red")}>
                {sentiment.institutional_score > 0 ? "+" : ""}{sentiment.institutional_score.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">India-Specific Score</span>
              <span className={cn("font-medium tabular-nums", sentiment.india_specific_score > 0 ? "text-bullish-green" : "text-bearish-red")}>
                {sentiment.india_specific_score > 0 ? "+" : ""}{sentiment.india_specific_score.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Sentiment Window</span>
              <span className="text-text-secondary">{sentiment.sentiment_window_days} days</span>
            </div>
          </div>
        </div>

        {/* GDELT Macro Tone */}
        <div className="card-base p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">GDELT Macro Tone</h3>
          <div className="text-center py-4">
            <div className="text-4xl font-bold tabular-nums mb-2" style={{
              color: sentiment.gdelt_macro_tone > 0 ? "#059669" : sentiment.gdelt_macro_tone < 0 ? "#DC2626" : "#D97706"
            }}>
              {sentiment.gdelt_macro_tone > 0 ? "+" : ""}{sentiment.gdelt_macro_tone.toFixed(2)}
            </div>
            <div className="text-sm text-text-muted mb-4">
              {sentiment.gdelt_macro_tone > 1 ? "Positive Global Tone"
                : sentiment.gdelt_macro_tone > 0 ? "Slightly Positive"
                : sentiment.gdelt_macro_tone > -1 ? "Slightly Negative"
                : "Negative Global Tone"}
            </div>
          </div>

          <div className="space-y-3 pt-3 border-t border-border">
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Earnings Tone</span>
              <span className={cn("font-medium tabular-nums", sentiment.earnings_tone > 0 ? "text-bullish-green" : "text-bearish-red")}>
                {sentiment.earnings_tone > 0 ? "+" : ""}{sentiment.earnings_tone.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Composite Label</span>
              <span className="font-medium" style={{
                color: LABEL_COLORS[sentiment.composite_label] ?? "#94A3B8"
              }}>
                {sentiment.composite_label}
              </span>
            </div>
          </div>

          {sentiment.warnings.length > 0 && (
            <div className="mt-3 p-2.5 rounded-btn bg-warning-bg border border-warning-amber/20">
              {sentiment.warnings.map((w, i) => (
                <p key={i} className="text-xs text-warning-amber">{w}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* News articles */}
      {sentiment.articles.length > 0 && (
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Recent News Articles</h3>
          <HelpPopover content={{
            title: "FinBERT Sentiment-Scored News",
            body: "FinBERT is a BERT language model fine-tuned specifically on financial text. It scores each article on a scale from -1.0 (very bearish) to +1.0 (very bullish), unlike general sentiment models that were trained on product reviews or social media.",
            level: "intermediate",
            tips: [
              "Score > +0.3 = clearly positive for the stock",
              "Score < -0.3 = clearly negative for the stock",
              "Scores near 0 = neutral or mixed news",
              "Multiple highly negative articles on the same day = news-driven risk flag",
            ],
            affectsVerdict: "The average FinBERT score across institutional sources (economic times, business standard, NSE announcements) is weighted 3x higher than retail/social sources.",
            source: "ProsusAI/finbert model via HuggingFace — applied to Alpha Vantage News API + Finlight RSS",
          }} />
          </div>
          <div className="space-y-3">
            {sentiment.articles.map((a, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-btn bg-surface-raised">
                <span className={cn(
                  "text-xs font-bold tabular-nums flex-shrink-0 pt-0.5",
                  a.sentiment > 0.05 ? "text-bullish-green"
                    : a.sentiment < -0.05 ? "text-bearish-red"
                    : "text-text-muted"
                )}>
                  {a.sentiment > 0 ? "+" : ""}{a.sentiment.toFixed(2)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-text-primary font-medium leading-snug">{a.headline}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-text-muted">{a.source}</span>
                    <span className="text-xs text-text-muted">•</span>
                    <span className="text-xs text-text-muted">{a.date}</span>
                    <span
                      className={cn(
                        "ml-auto text-xs px-1.5 py-0.5 rounded-badge font-medium",
                        a.label === "POSITIVE" || a.label === "BULLISH"
                          ? "bg-bullish-bg text-bullish-green"
                          : a.label === "NEGATIVE" || a.label === "BEARISH"
                          ? "bg-bearish-bg text-bearish-red"
                          : "bg-surface text-text-muted"
                      )}
                    >
                      {a.label}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
