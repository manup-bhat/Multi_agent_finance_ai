"use client";
import { useApp } from "@/lib/app-context";
import { analyzeStock } from "@/lib/api-client";

const SUGGESTIONS = ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "NIFTY50.NS", "INFY.NS"];

export function EmptyState() {
  const { setSelectedTicker, setAnalysisData, setIsAnalyzing } = useApp();

  async function handleSelect(ticker: string) {
    setSelectedTicker(ticker);
    setIsAnalyzing(true);
    try {
      const data = await analyzeStock(ticker);
      setAnalysisData(data);
    } finally {
      setIsAnalyzing(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center py-24 gap-6">
      <div className="text-6xl select-none" aria-hidden="true">🇮🇳</div>
      <div className="text-center">
        <h2 className="text-xl font-semibold text-text-primary mb-2">
          Enter a NSE ticker above to begin analysis
        </h2>
        <p className="text-sm text-text-muted">
          Powered by 7 AI agents + XGBoost / LightGBM / Chronos-2
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center">
        {SUGGESTIONS.map((ticker) => (
          <button
            key={ticker}
            onClick={() => handleSelect(ticker)}
            className="px-4 py-2 rounded-pill border border-border text-sm text-text-secondary hover:text-saffron hover:border-saffron/40 hover:bg-saffron-light transition-all duration-150 font-medium"
          >
            {ticker}
          </button>
        ))}
      </div>
    </div>
  );
}
