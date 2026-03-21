"use client";
import { useApp } from "@/lib/app-context";
import { NSE_TICKERS } from "@/lib/nse-tickers";

// Show top 6 tickers from the NSE_TICKERS static list
const SUGGESTIONS = NSE_TICKERS.slice(0, 6).map((t) => ({
  symbol: t.symbol,
  shortName: t.symbol.replace(".NS", ""),
  sector: t.sector,
}));

export function EmptyState() {
  const { setSelectedTicker } = useApp();

  // Set the ticker — the AnalyzeCard's "Run Analysis" button handles the API call
  // with full progress animation. We only need to pre-select the ticker here.
  function handleSelect(symbol: string) {
    setSelectedTicker(symbol);
    // Scroll to top so the user sees the AnalyzeCard pre-filled
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="flex flex-col items-center justify-center py-20 gap-8 max-w-2xl mx-auto">
      {/* Hero text */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold text-text-primary text-balance">
          India AI Equity Analysis Engine
        </h2>
        <p className="text-sm text-text-secondary leading-relaxed text-balance">
          Select a ticker and click{" "}
          <span className="font-semibold text-saffron">Run Analysis</span> to activate the
          9-agent LangGraph pipeline with XGBoost, LightGBM, CatBoost, and Chronos-2.
        </p>
      </div>

      {/* Quick-select tickers */}
      <div className="w-full">
        <div className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3 text-center">
          Quick Select
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {SUGGESTIONS.map(({ symbol, shortName, sector }) => (
            <button
              key={symbol}
              onClick={() => handleSelect(symbol)}
              className="flex flex-col items-center px-3 py-3 rounded-card border border-border text-center hover:border-saffron/40 hover:bg-saffron-light transition-all duration-150 group"
            >
              <span className="text-sm font-bold text-text-primary group-hover:text-saffron">{shortName}</span>
              <span className="text-[10px] text-text-muted mt-0.5">{sector}</span>
            </button>
          ))}
        </div>
      </div>

      {/* What the system does */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 w-full text-sm">
        {[
          {
            heading: "9 AI Agents",
            body: "Quant, Macro, Sentiment, F&O, Risk, and more — each independently analyses one dimension before synthesis.",
          },
          {
            heading: "ML Ensemble",
            body: "XGBoost + LightGBM + CatBoost predict direction. Chronos-2 forecasts price targets at P10/P50/P90.",
          },
          {
            heading: "Real NSE Data",
            body: "No demo data. All signals use live market feeds: NSE option chain, yfinance OHLCV, FII/DII flows.",
          },
        ].map(({ heading, body }) => (
          <div key={heading} className="card-base p-4 text-center">
            <div className="text-sm font-semibold text-text-primary mb-1">{heading}</div>
            <p className="text-xs text-text-muted leading-relaxed">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
