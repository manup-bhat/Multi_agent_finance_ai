"use client";
import { useState, useEffect, useMemo } from "react";
import { Play, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApp } from "@/lib/app-context";
import { analyzeStock, getApiErrorMessage } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { HelpPopover } from "@/components/ui/help-popover";
import { NSE_TICKERS } from "@/lib/mock-data";

const STAGES = [
  { label: "Pre-flight" },
  { label: "Data Fetch" },
  { label: "ML Models" },
  { label: "AI Agents" },
  { label: "Synthesis" },
];

export function AnalyzeCard() {
  const { selectedTicker, setAnalysisData, isAnalyzing, setIsAnalyzing, analysisStage, setAnalysisStage, horizon, setHorizon, includeFno, setIncludeFno, includeSentiment, setIncludeSentiment, addNotification } = useApp();
  const [progress, setProgress] = useState(0);
  const [lastRun, setLastRun] = useState<Date | null>(null);
  const [timeRemaining, setTimeRemaining] = useState(28);

  const tickerMeta = useMemo(
    () => NSE_TICKERS.find((t) => t.symbol === selectedTicker),
    [selectedTicker]
  );

  useEffect(() => {
    if (!isAnalyzing) return;
    setProgress(0);
    setTimeRemaining(28);
    // Use the setter from app-context — stable reference, intentionally excluded from deps
    setAnalysisStage(0);

    let current = 0;
    const interval = setInterval(() => {
      current = Math.min(current + 2, 100);
      const stageIndex = Math.min(
        Math.floor((current / 100) * STAGES.length),
        STAGES.length - 1
      );
      setProgress(current);
      setAnalysisStage(stageIndex);
      setTimeRemaining(Math.max(0, Math.ceil(28 * (1 - current / 100))));
      if (current >= 100) clearInterval(interval);
    }, 600);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAnalyzing]);

  async function handleRun() {
    setIsAnalyzing(true);
    setProgress(0);
    try {
      const data = await analyzeStock(selectedTicker, horizon, includeFno, includeSentiment);
      setAnalysisData(data);
      setLastRun(new Date());
      addNotification({ type: "success", message: `${selectedTicker} analysis complete — ${data.verdict} signal` });
      if (data.warnings.length > 0) {
        addNotification({ type: "warning", message: data.warnings[0] });
      }
    } catch (err) {
      addNotification({ type: "error", message: getApiErrorMessage(err) });
    } finally {
      setIsAnalyzing(false);
      setProgress(100);
    }
  }

  function timeAgoStr(date: Date) {
    const sec = Math.floor((Date.now() - date.getTime()) / 1000);
    if (sec < 60) return `${sec}s ago`;
    return `${Math.floor(sec / 60)}m ago`;
  }

  return (
    <div className="card-base p-5 border-t-4 border-t-saffron">
      <div className="flex flex-wrap items-center gap-4">
        {/* Left: Ticker + Help */}
        <div className="min-w-0 flex items-start gap-2">
          <div>
            <div className="text-2xl font-bold text-text-primary tabular-nums">{selectedTicker.replace(".NS", "")}</div>
            <div className="text-sm text-text-muted mt-0.5">
              {tickerMeta?.name ?? "NSE Listed Security"}{tickerMeta?.sector ? ` · ${tickerMeta.sector}` : ""}
            </div>
          </div>
          <HelpPopover content={{
            title: "How the Analysis Works",
            body: "Clicking Run Analysis triggers a 9-agent LangGraph pipeline: (1) Pre-flight checks, (2) Market data fetch, (3) ML model predictions, (4) 9 AI agents reason in parallel, (5) Synthesis into a final verdict with confidence score.",
            affectsVerdict: "Each agent contributes a weighted score. Macro, Technical, and ML signals each carry ~30% weight. Sentiment carries ~20%. F&O adjusts the final confidence.",
            source: "api/routes/analyze.py → LangGraph orchestration → 9-agent pipeline",
          }} />
        </div>

        {/* Center: Controls */}
        <div className="flex items-center gap-3 flex-wrap flex-1 justify-center">
          <Button
            variant="primary"
            size="lg"
            onClick={handleRun}
            loading={isAnalyzing}
            className="gap-2"
          >
            <Play size={16} />
            Run Analysis
          </Button>

          {/* Horizon selector */}
          <div className="relative">
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="appearance-none pl-3 pr-8 py-2 rounded-btn border border-border bg-surface text-sm text-text-primary focus:outline-none focus:border-saffron/50 cursor-pointer hover:bg-surface-raised transition-colors duration-150"
            >
              <option value={5}>5 days</option>
              <option value={10}>10 days</option>
              <option value={30}>30 days</option>
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
          </div>

          {/* Include F&O toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => setIncludeFno(!includeFno)}
              className={cn(
                "relative w-10 h-5 rounded-pill transition-colors duration-150",
                includeFno ? "bg-saffron" : "bg-border"
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-150",
                  includeFno ? "left-5" : "left-0.5"
                )}
              />
            </div>
            <span className="text-sm text-text-secondary">Include F&O</span>
          </label>

          {/* Include Sentiment toggle */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => setIncludeSentiment(!includeSentiment)}
              className={cn(
                "relative w-10 h-5 rounded-pill transition-colors duration-150",
                includeSentiment ? "bg-saffron" : "bg-border"
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-150",
                  includeSentiment ? "left-5" : "left-0.5"
                )}
              />
            </div>
            <span className="text-sm text-text-secondary">Sentiment</span>
          </label>
        </div>

        {/* Right: Last run */}
        <div className="text-right text-sm text-text-muted">
          {lastRun ? `Last run: ${timeAgoStr(lastRun)}` : "Not yet run"}
        </div>
      </div>

      {/* Progress bar */}
      {isAnalyzing && (
        <div className="mt-5 space-y-2">
          {/* Stage labels */}
          <div className="flex justify-between mb-1">
            {STAGES.map((s, i) => (
              <span
                key={s.label}
                className={cn(
                  "text-xs transition-colors duration-150",
                  i <= analysisStage ? "text-saffron font-medium" : "text-text-muted"
                )}
              >
                {s.label}
              </span>
            ))}
          </div>
          {/* Bar */}
          <div className="h-2 bg-surface-raised rounded-pill overflow-hidden">
            <div
              className="h-full rounded-pill transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, #FF6B00, #FF8C40)",
              }}
            />
          </div>
          {/* Current stage */}
          <div className="flex items-center justify-between text-xs text-text-muted">
            <span>{STAGES[analysisStage]?.label}...</span>
            <span>~{timeRemaining}s remaining</span>
          </div>
        </div>
      )}
    </div>
  );
}
