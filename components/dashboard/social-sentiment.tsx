"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { Globe, MessageSquare } from "lucide-react";
import { useApp } from "@/lib/app-context";

export function SocialSentiment() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const {
    social_bullish_pct,
    social_post_volume,
    euphoria_flag,
    emotion_summary,
    sentiment_window,
  } = analysisData;

  const bullishPct = social_bullish_pct ?? 50;
  const postVolume = social_post_volume ?? 0;
  const windowDays = sentiment_window ?? 3;

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Market Pulse</h3>
        <HelpPopover
          content={{
            title: "Market Pulse — Social & News Sentiment",
            body: "Aggregates sentiment from StockTwits retail posts, RSS financial news (FinBERT scored), and GDELT global macro event tones.",
            affectsVerdict: "Elevated social volume with extreme greed triggers the Euphoria Warning, reducing conviction.",
            source: "StockTwits API + RSS (ET/LiveMint/BS) via FinBERT + GDELT v2 API",
          }}
        />
      </div>

      <div className="space-y-4">
        {/* StockTwits / Social */}
        {social_bullish_pct != null ? (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <MessageSquare size={14} className="text-text-muted" />
                <span className="text-xs font-medium text-text-secondary">Community Sentiment</span>
              </div>
              <span className="text-xs text-text-muted tabular-nums">
                {postVolume} posts / {windowDays}d
              </span>
            </div>
            <div className="h-2 rounded-pill overflow-hidden flex">
              <div className="bg-bullish-green transition-all duration-500" style={{ width: `${bullishPct}%` }} />
              <div className="bg-bearish-red flex-1" />
            </div>
            <div className="flex justify-between text-xs text-text-muted mt-1">
              <span className="text-bullish-green font-medium">{bullishPct.toFixed(1)}% Bullish</span>
              <span className="text-bearish-red font-medium">{(100 - bullishPct).toFixed(1)}% Bearish</span>
            </div>
          </div>
        ) : (
          <div className="text-xs text-text-muted">Social sentiment data unavailable.</div>
        )}

        {/* Emotion summary */}
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Globe size={14} className="text-text-muted" />
            <span className="text-xs font-medium text-text-secondary">Emotion Agent Summary</span>
          </div>
          <p className="text-xs text-text-secondary leading-relaxed">
            {emotion_summary || "Sentiment analysis not available."}
          </p>
        </div>
      </div>

      {/* Euphoria Warning */}
      {euphoria_flag && (
        <div
          className="mt-4 p-3 rounded-btn"
          style={{
            background: "linear-gradient(135deg, rgba(220,38,38,0.1), rgba(217,119,6,0.1))",
            border: "1px solid rgba(220,38,38,0.2)",
          }}
        >
          <p className="text-xs font-semibold text-bearish-red">
            EUPHORIA DETECTED — High social volume + extreme greed
          </p>
        </div>
      )}
    </div>
  );
}
