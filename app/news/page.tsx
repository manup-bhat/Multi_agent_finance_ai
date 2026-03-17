"use client";
import useSWR from "swr";
import { useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { getSentiment, getApiErrorMessage } from "@/lib/api-client";

const LABEL_FILTER_OPTIONS = ["ALL", "POSITIVE", "NEUTRAL", "NEGATIVE"] as const;
type LabelFilter = typeof LABEL_FILTER_OPTIONS[number];

const LABEL_STYLES: Record<string, string> = {
  POSITIVE: "bg-bullish-bg text-bullish-green",
  BULLISH: "bg-bullish-bg text-bullish-green",
  NEUTRAL: "bg-surface-raised text-text-muted",
  NEGATIVE: "bg-bearish-bg text-bearish-red",
  BEARISH: "bg-bearish-bg text-bearish-red",
};

export default function NewsPage() {
  const { selectedTicker } = useApp();
  const [filter, setFilter] = useState<LabelFilter>("ALL");

  const { data: sentiment, error, isLoading, mutate } = useSWR(
    selectedTicker ? ["news-feed", selectedTicker] : null,
    () => getSentiment(selectedTicker),
    { revalidateOnFocus: false }
  );

  const articles = sentiment?.articles ?? [];
  const filtered = filter === "ALL"
    ? articles
    : articles.filter((a) => a.label === filter || a.label === (filter === "POSITIVE" ? "BULLISH" : filter === "NEGATIVE" ? "BEARISH" : filter));

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold text-text-primary">News Feed</h1>
          <HelpPopover content={{
            title: "FinBERT News Feed",
            body: "Every article shown here has been automatically scored by FinBERT, a financial-domain BERT model. The score ranges from -1.0 (strongly bearish) to +1.0 (strongly bullish). Unlike general sentiment tools, FinBERT understands financial language — phrases like 'cut guidance' or 'beat estimates' are correctly interpreted.",
            level: "beginner",
            tips: [
              "Green score = positive news for the stock's outlook",
              "Red score = negative news — earnings miss, regulatory concern, etc.",
              "Multiple negative articles in one day = news-driven risk flag",
              "High news volume itself is also a signal — check the post count",
            ],
            affectsVerdict: "Average FinBERT score across the last N days (where N = sentiment window) is the institutional_score input to the emotion agent.",
            source: "Alpha Vantage Financial News API + Finlight RSS + Google Finance RSS — processed via ProsusAI/finbert",
          }} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">{selectedTicker}</span>
          <button
            onClick={() => mutate()}
            disabled={isLoading}
            className="p-1.5 rounded-btn text-text-muted hover:text-saffron hover:bg-surface-raised transition-all duration-150"
            aria-label="Refresh news"
          >
            <RefreshCw size={15} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-1">
        {LABEL_FILTER_OPTIONS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "px-3 py-1.5 text-xs rounded-badge font-medium transition-all duration-150",
              filter === f
                ? "bg-saffron text-white"
                : "text-text-muted hover:text-text-primary hover:bg-surface-raised"
            )}
          >
            {f}
            {f !== "ALL" && sentiment && (
              <span className="ml-1 opacity-70">
                ({articles.filter((a) =>
                  a.label === f || a.label === (f === "POSITIVE" ? "BULLISH" : f === "NEGATIVE" ? "BEARISH" : f)
                ).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      )}

      {error && (
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load news feed</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      )}

      {!isLoading && !error && filtered.length === 0 && (
        <div className="card-base p-8 text-center text-text-muted">
          <p className="font-medium text-text-secondary mb-2">No articles found</p>
          <p className="text-sm">
            {articles.length === 0
              ? `Run an analysis from the Dashboard to load news for ${selectedTicker}.`
              : `No ${filter.toLowerCase()} articles found. Try a different filter.`}
          </p>
        </div>
      )}

      {!isLoading && filtered.length > 0 && (
        <>
          {/* Sentiment summary */}
          {sentiment && (
            <div className="flex items-center gap-4 p-3 rounded-card bg-surface-raised text-sm">
              <span className="text-text-muted">Composite:</span>
              <span className="font-semibold" style={{
                color: sentiment.composite_label === "BULLISH" || sentiment.composite_label === "POSITIVE"
                  ? "#059669"
                  : sentiment.composite_label === "BEARISH" || sentiment.composite_label === "NEGATIVE"
                  ? "#DC2626"
                  : "#D97706"
              }}>
                {sentiment.composite_label}
              </span>
              <span className="text-text-muted ml-2">Fear & Greed:</span>
              <span className="font-semibold text-text-primary">{sentiment.fear_greed_index.toFixed(0)}</span>
              <span className="text-text-muted ml-auto">{articles.length} articles indexed</span>
            </div>
          )}

          <div className="space-y-3">
            {filtered.map((a, i) => (
              <article
                key={i}
                className="card-base p-4 flex items-start gap-4 hover:bg-surface-raised transition-colors duration-150"
              >
                {/* Score indicator */}
                <div className="flex-shrink-0 pt-0.5 text-center min-w-[44px]">
                  <div
                    className={cn(
                      "text-sm font-bold tabular-nums",
                      a.sentiment > 0.05 ? "text-bullish-green"
                        : a.sentiment < -0.05 ? "text-bearish-red"
                        : "text-text-muted"
                    )}
                  >
                    {a.sentiment > 0 ? "+" : ""}{a.sentiment.toFixed(2)}
                  </div>
                  <div className={cn(
                    "text-xs mt-0.5 px-1.5 py-0.5 rounded-badge font-medium",
                    LABEL_STYLES[a.label] ?? "bg-surface-raised text-text-muted"
                  )}>
                    {a.label}
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <h2 className="text-sm font-medium text-text-primary leading-snug">{a.headline}</h2>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-xs text-text-muted font-medium">{a.source}</span>
                    <span className="text-xs text-text-muted">•</span>
                    <span className="text-xs text-text-muted">{a.date}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
