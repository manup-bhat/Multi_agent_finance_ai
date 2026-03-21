"use client";
import useSWR from "swr";
import { useState } from "react";
import { CheckCircle2, XCircle, RefreshCw, Server, Globe, Brain, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import { checkHealth, getApiErrorMessage } from "@/lib/api-client";
import type { HealthResponse } from "@/lib/api-client";
import { useApp } from "@/lib/app-context";
import { HelpPopover } from "@/components/ui/help-popover";

const MODULE_DESCRIPTIONS: Record<string, string> = {
  chronos:   "Amazon Chronos-2 — time-series price forecasting model",
  finbert:   "FinBERT — financial news sentiment analysis",
  goemotions:"GoEmotions — emotional tone detection in text",
  xgboost:   "XGBoost — directional prediction classifier",
  lightgbm:  "LightGBM — gradient boosting direction classifier",
  catboost:  "CatBoost — categorical-aware direction classifier",
  nse:       "NSE data adapter — live market data",
  yfinance:  "yfinance — historical OHLCV and macro data",
  langgraph: "LangGraph — 9-agent orchestration framework",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SettingsPage() {
  const { selectedTicker, horizon, includeFno, includeSentiment, setHorizon, setIncludeFno, setIncludeSentiment } = useApp();
  const [refreshKey, setRefreshKey] = useState(0);

  const { data: health, error, isLoading } = useSWR<HealthResponse | null>(
    ["health-check", refreshKey],
    () => checkHealth(),
    { revalidateOnFocus: false }
  );

  const apiOnline = !!health && !error;

  const moduleEntries = health?.modules
    ? Object.entries(health.modules)
    : [];

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
        <HelpPopover content={{
          title: "Settings & Diagnostics",
          body: "Configure analysis defaults and check the health of the backend API and all loaded ML modules.",
          affectsVerdict: "Settings here persist in browser session. Module status affects which agents are available for analysis.",
          source: "GET /health — polled on page load",
        }} />
      </div>

      {/* API Health */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-text-primary flex items-center gap-2">
            <Server size={16} className="text-text-muted" />
            API Health
          </h3>
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={isLoading}
            className="p-1.5 rounded-btn text-text-muted hover:text-saffron hover:bg-saffron-light transition-all duration-150"
            aria-label="Refresh health"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>

        <div className={cn(
          "flex items-center gap-3 p-4 rounded-card mb-4",
          apiOnline ? "bg-bullish-bg" : "bg-bearish-bg"
        )}>
          {apiOnline
            ? <CheckCircle2 size={20} className="text-bullish-green flex-shrink-0" />
            : <XCircle size={20} className="text-bearish-red flex-shrink-0" />
          }
          <div>
            <div className={cn("font-semibold text-sm", apiOnline ? "text-bullish-green" : "text-bearish-red")}>
              {apiOnline ? `API Connected — v${health?.version ?? "?"}` : "API Offline"}
            </div>
            <div className="text-xs text-text-muted mt-0.5">
              {apiOnline
                ? `Running at ${API_URL}`
                : `Cannot reach ${API_URL}. Start with: uvicorn api.main:app --port 8000 --reload`}
            </div>
          </div>
        </div>

        {/* Module status */}
        {moduleEntries.length > 0 && (
          <div>
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-3">
              Loaded Modules
            </div>
            <div className="space-y-2">
              {moduleEntries.map(([name, status]) => {
                const ok = status === "ok" || status === "loaded" || status === "ready";
                return (
                  <div key={name} className="flex items-center gap-3 p-2.5 rounded-btn bg-surface-raised">
                    <div className={cn("w-2 h-2 rounded-full flex-shrink-0", ok ? "bg-bullish-green" : "bg-warning-amber")} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-text-primary capitalize">{name}</div>
                      {MODULE_DESCRIPTIONS[name] && (
                        <div className="text-xs text-text-muted">{MODULE_DESCRIPTIONS[name]}</div>
                      )}
                    </div>
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded-badge font-medium",
                      ok ? "bg-bullish-bg text-bullish-green" : "bg-warning-bg text-warning-amber"
                    )}>
                      {status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {error && (
          <p className="text-xs text-bearish-red mt-2">{getApiErrorMessage(error)}</p>
        )}
      </div>

      {/* Analysis Defaults */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2 mb-4">
          <Brain size={16} className="text-text-muted" />
          Analysis Defaults
        </h3>

        <div className="space-y-4">
          {/* Horizon */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2 block">
              Default Horizon: {horizon} days
            </label>
            <div className="flex gap-2">
              {[5, 10, 30].map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizon(h)}
                  className={cn(
                    "px-4 py-2 rounded-btn text-sm font-medium transition-all duration-150",
                    horizon === h
                      ? "bg-saffron text-white"
                      : "border border-border text-text-secondary hover:bg-surface-raised"
                  )}
                >
                  {h} days
                </button>
              ))}
            </div>
          </div>

          {/* Include F&O */}
          <div className="flex items-center justify-between py-2 border-t border-border">
            <div>
              <div className="text-sm font-medium text-text-primary">Include F&O Analysis</div>
              <div className="text-xs text-text-muted">Fetches live option chain from NSE — adds ~5s to analysis time</div>
            </div>
            <div
              onClick={() => setIncludeFno(!includeFno)}
              className={cn(
                "relative w-10 h-5 rounded-pill cursor-pointer transition-colors duration-150",
                includeFno ? "bg-saffron" : "bg-border"
              )}
            >
              <span className={cn(
                "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-150",
                includeFno ? "left-5" : "left-0.5"
              )} />
            </div>
          </div>

          {/* Include Sentiment */}
          <div className="flex items-center justify-between py-2 border-t border-border">
            <div>
              <div className="text-sm font-medium text-text-primary">Include Sentiment Analysis</div>
              <div className="text-xs text-text-muted">Runs FinBERT + GDELT + RSS — adds ~8s to analysis time</div>
            </div>
            <div
              onClick={() => setIncludeSentiment(!includeSentiment)}
              className={cn(
                "relative w-10 h-5 rounded-pill cursor-pointer transition-colors duration-150",
                includeSentiment ? "bg-saffron" : "bg-border"
              )}
            >
              <span className={cn(
                "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-150",
                includeSentiment ? "left-5" : "left-0.5"
              )} />
            </div>
          </div>
        </div>
      </div>

      {/* Endpoint Reference */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2 mb-4">
          <Globe size={16} className="text-text-muted" />
          API Endpoint Reference
        </h3>
        <div className="space-y-1.5 text-xs font-mono">
          {[
            { method: "GET",  path: "/health",              desc: "Backend health + module status" },
            { method: "POST", path: "/analyze",             desc: "Full 9-agent analysis" },
            { method: "POST", path: "/predict",             desc: "ML ensemble direction + price targets" },
            { method: "POST", path: "/sentiment",           desc: "FinBERT + GDELT + RSS sentiment" },
            { method: "POST", path: "/fno/analyze",         desc: "Option chain, PCR, max pain, greeks" },
            { method: "GET",  path: "/macro/india-cues",    desc: "VIX, USD/INR, Crude, SGX proxy" },
            { method: "GET",  path: "/fii-dii/latest",      desc: "Latest FII/DII net flows" },
            { method: "POST", path: "/backtest",            desc: "Strategy backtest with equity curve" },
            { method: "GET",  path: "/macro/sector-rotation", desc: "RRG sector data (pending)" },
            { method: "GET",  path: "/model/performance",   desc: "ML model metrics (pending)" },
            { method: "GET",  path: "/audit/{ticker}",      desc: "Decision audit trail (pending)" },
          ].map((ep) => (
            <div key={ep.path} className="flex items-center gap-2 p-2 rounded-btn hover:bg-surface-raised">
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-bold",
                ep.method === "GET" ? "bg-neutral-bg text-neutral-blue" : "bg-saffron-light text-saffron"
              )}>
                {ep.method}
              </span>
              <code className="text-text-primary flex-1">{ep.path}</code>
              <span className="text-text-muted text-[11px] hidden sm:block">{ep.desc}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-text-muted mt-4">
          Full interactive docs at <code className="text-text-secondary">{API_URL}/docs</code>
        </p>
      </div>

      {/* Data Source Reference */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary flex items-center gap-2 mb-4">
          <Database size={16} className="text-text-muted" />
          Data Sources
        </h3>
        <div className="space-y-2 text-sm">
          {[
            { name: "NSE India",      type: "Market Data",   desc: "Option chains, participant OI, F&O data — scraped post-market",         free: true },
            { name: "yfinance",       type: "Price Data",    desc: "Historical OHLCV, India VIX, USD/INR, Brent Crude, SGX proxy",          free: true },
            { name: "GDELT",          type: "Macro Tone",    desc: "Global news event database — 250K+ news sources in 65 languages",       free: true },
            { name: "Alpha Vantage",  type: "News Sentiment", desc: "Financial news API with FinBERT scoring — 25 req/day free",           free: true },
            { name: "Finlight",       type: "RSS News",      desc: "India-specific financial news RSS — 10K req/month free tier",          free: true },
            { name: "Google Gemini",  type: "LLM Agent",     desc: "Powers the 9 LangGraph agents for reasoning and synthesis",            free: false },
            { name: "Groq",           type: "LLM Agent",     desc: "Fast inference fallback — used when Gemini quota is hit",              free: false },
          ].map((src) => (
            <div key={src.name} className="flex items-start gap-3 p-3 rounded-btn bg-surface-raised">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text-primary">{src.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded-badge bg-surface text-text-muted">{src.type}</span>
                  {src.free && (
                    <span className="text-xs px-1.5 py-0.5 rounded-badge bg-bullish-bg text-bullish-green">Free</span>
                  )}
                  {!src.free && (
                    <span className="text-xs px-1.5 py-0.5 rounded-badge bg-saffron-light text-saffron">API Key</span>
                  )}
                </div>
                <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{src.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
