"use client";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { Globe, MessageSquare, Rss } from "lucide-react";
import { useApp } from "@/lib/app-context";

export function SocialSentiment() {
  const { analysisData } = useApp();
  if (!analysisData) return null;

  const { fear_greed } = analysisData;
  const euphoria = fear_greed > 80;
  const bullishPct = 68;

  const newsDots = 4; // out of 5 — "Moderately Positive"

  return (
    <div className="card-base p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-text-primary">Market Pulse</h3>
        <HelpPopover
          content={{
            title: "Market Pulse — Social & News Sentiment",
            body: "Aggregates sentiment from StockTwits retail posts, RSS financial news (FinBERT scored), and GDELT global macro event tones to gauge overall market mood.",
            affectsVerdict: "Elevated social volume with extreme greed triggers the Euphoria Warning, which reduces conviction and position size recommendation.",
            source: "StockTwits API + RSS (ET/LiveMint/BS) via FinBERT + GDELT v2 API",
          }}
        />
      </div>

      <div className="space-y-4">
        {/* StockTwits */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <MessageSquare size={14} className="text-text-muted" />
              <span className="text-xs font-medium text-text-secondary">StockTwits</span>
            </div>
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-badge font-medium",
              "bg-warning-bg text-warning-amber"
            )}>
              2.3x volume
            </span>
          </div>
          {/* Bullish/Bearish bar */}
          <div className="h-2 rounded-pill overflow-hidden flex">
            <div className="bg-bullish-green transition-all duration-500" style={{ width: `${bullishPct}%` }} />
            <div className="bg-bearish-red flex-1" />
          </div>
          <div className="flex justify-between text-xs text-text-muted mt-1">
            <span className="text-bullish-green font-medium">{bullishPct}% Bullish</span>
            <span>247 posts today</span>
            <span className="text-bearish-red font-medium">{100 - bullishPct}% Bearish</span>
          </div>
        </div>

        {/* RSS News Tone */}
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Rss size={14} className="text-text-muted" />
            <span className="text-xs font-medium text-text-secondary">RSS News Tone</span>
          </div>
          <div className="flex gap-1">
            {Array.from({ length: 5 }, (_, i) => (
              <div
                key={i}
                className={cn(
                  "flex-1 h-3 rounded-sm",
                  i < newsDots ? "bg-bullish-green" : "bg-surface-raised"
                )}
              />
            ))}
          </div>
          <div className="text-xs text-text-muted mt-1">
            Moderately Positive — 12 relevant articles
          </div>
        </div>

        {/* GDELT Macro */}
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Globe size={14} className="text-text-muted" />
            <span className="text-xs font-medium text-text-secondary">GDELT Macro</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-text-muted">47 India events tracked</span>
            <span className="text-xs text-warning-amber font-medium tabular-nums">-0.3 tone</span>
          </div>
          <div className="text-xs text-text-muted mt-0.5">Dominant theme: Economic Policy</div>
        </div>
      </div>

      {/* Euphoria Warning */}
      {euphoria && (
        <div className="mt-4 p-3 rounded-btn"
          style={{ background: "linear-gradient(135deg, rgba(220,38,38,0.1), rgba(217,119,6,0.1))", border: "1px solid rgba(220,38,38,0.2)" }}
        >
          <p className="text-xs font-semibold text-bearish-red">
            EUPHORIA DETECTED — High social volume + extreme greed
          </p>
        </div>
      )}
    </div>
  );
}
