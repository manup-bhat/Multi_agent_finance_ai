"use client";
import { useApp } from "@/lib/app-context";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/dashboard/empty-state";

export default function TechnicalPage() {
  const { analysisData } = useApp();

  if (!analysisData) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Technical Analysis</h1>
        <EmptyState />
      </div>
    );
  }

  const { quant_summary, regime, ticker } = analysisData;

  // Parse key=value pairs from quant_summary string
  // Format: "Close=1698.45 | RSI14=58.1 | MACD Hist=0.042 | EMA21=1672.00 | EMA50=1641.00 | ATR%=1.20"
  const parsedTA: Record<string, string> = {};
  if (quant_summary) {
    quant_summary.split("|").forEach((part) => {
      const [key, val] = part.split("=").map((s) => s.trim());
      if (key && val !== undefined) parsedTA[key] = val;
    });
  }

  const close = parsedTA["Close"];
  const rsi = parsedTA["RSI14"];
  const macdHist = parsedTA["MACD Hist"];
  const ema21 = parsedTA["EMA21"];
  const ema50 = parsedTA["EMA50"];
  const atrPct = parsedTA["ATR%"];

  function rsiStatus(v: string) {
    const n = parseFloat(v);
    if (n > 70) return { label: "Overbought", color: "bg-bearish-bg text-bearish-red" };
    if (n < 30) return { label: "Oversold", color: "bg-bullish-bg text-bullish-green" };
    return { label: "Neutral", color: "bg-neutral-bg text-neutral-blue" };
  }

  const rsiStat = rsi ? rsiStatus(rsi) : null;
  const macdNum = macdHist ? parseFloat(macdHist) : null;

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">Technical Analysis — {ticker}</h1>
        <span className={cn(
          "px-3 py-1 rounded-pill text-sm font-semibold",
          regime === "BULL" ? "bg-bullish-bg text-bullish-green" :
          regime === "BEAR" ? "bg-bearish-bg text-bearish-red" :
          "bg-neutral-bg text-neutral-blue"
        )}>
          {regime} REGIME
        </span>
      </div>

      {/* Live indicator grid from quant_summary */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          { label: "Close", value: close ? `₹${parseFloat(close).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—", color: "text-text-primary" },
          { label: "RSI (14)", value: rsi ?? "—", color: rsi && parseFloat(rsi) > 70 ? "text-bearish-red" : rsi && parseFloat(rsi) < 30 ? "text-bullish-green" : "text-neutral-blue" },
          { label: "MACD Hist", value: macdHist ?? "—", color: macdNum != null && macdNum > 0 ? "text-bullish-green" : "text-bearish-red" },
          { label: "EMA 21", value: ema21 ? `₹${parseFloat(ema21).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—", color: "text-saffron" },
          { label: "EMA 50", value: ema50 ? `₹${parseFloat(ema50).toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—", color: "text-neutral-blue" },
          { label: "ATR %", value: atrPct ? `${atrPct}%` : "—", color: "text-text-secondary" },
        ].map((item) => (
          <div key={item.label} className="card-base p-5">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
              {item.label}
            </div>
            <div className={cn("text-2xl font-bold tabular-nums", item.color)}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* RSI status */}
      {rsi && rsiStat && (
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">RSI Analysis</h3>
          <HelpPopover content={{
            title: "RSI — Relative Strength Index",
            body: "RSI measures how fast a stock is moving up or down, on a scale of 0–100. Think of it as a speedometer for momentum. It is calculated over the last 14 trading days.",
            level: "beginner",
            tips: [
              "Above 70 = Overbought — stock rose too fast, pullback likely",
              "Below 30 = Oversold — stock fell too fast, bounce likely",
              "Between 30–70 = Normal zone, trend is intact",
              "Divergence (price rising but RSI falling) is an early reversal warning",
            ],
            affectsVerdict: "RSI is consistently ranked as a top-3 SHAP feature in the XGBoost/LightGBM models. RSI < 30 combined with a bullish macro backdrop is one of the strongest buy signals.",
            source: "Computed using Wilder smoothing on NSE daily OHLCV via technical_analyzer.py",
          }} />
          </div>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-5xl font-bold tabular-nums text-text-primary">
                {parseFloat(rsi).toFixed(1)}
              </div>
              <span className={cn("inline-flex mt-2 px-2 py-0.5 rounded-badge text-xs font-medium", rsiStat.color)}>
                {rsiStat.label}
              </span>
            </div>
            <div className="flex-1 h-4 bg-surface-raised rounded-pill overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-pill transition-all duration-500",
                  parseFloat(rsi) > 70 ? "bg-bearish-red" : parseFloat(rsi) < 30 ? "bg-bullish-green" : "bg-neutral-blue"
                )}
                style={{ width: `${Math.min(parseFloat(rsi), 100)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* MACD status */}
      {macdNum != null && (
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">MACD</h3>
          <HelpPopover content={{
            title: "MACD — Moving Average Convergence Divergence",
            body: "MACD shows whether short-term price momentum is stronger or weaker than long-term momentum. The histogram is the gap between the MACD line and its signal line — bigger bars mean stronger momentum.",
            level: "intermediate",
            tips: [
              "Histogram above zero = short-term momentum is rising (bullish)",
              "Histogram below zero = short-term momentum is falling (bearish)",
              "Zero-line crossover = potential trend change signal",
              "Calculated from 12-day EMA minus 26-day EMA; signal line is 9-day EMA of that",
            ],
            affectsVerdict: "The Quant Agent uses MACD histogram sign and slope as a directional confirmation. A positive MACD histogram combined with RSI 40–70 is the 'clean trend' pattern.",
            source: "Computed on NSE daily OHLCV — technical_analyzer.py (fast=12, slow=26, signal=9)",
          }} />
          </div>
          <div className="flex items-center gap-4">
            <div className={cn(
              "text-4xl font-bold tabular-nums",
              macdNum > 0 ? "text-bullish-green" : "text-bearish-red"
            )}>
              {macdNum > 0 ? "+" : ""}{macdNum.toFixed(4)}
            </div>
            <span className={cn(
              "px-2 py-0.5 rounded-badge text-xs font-medium",
              macdNum > 0 ? "bg-bullish-bg text-bullish-green" : "bg-bearish-bg text-bearish-red"
            )}>
              {macdNum > 0 ? "Bullish Momentum" : "Bearish Momentum"}
            </span>
          </div>
        </div>
      )}

      {/* EMA Trend */}
      {ema21 && ema50 && close && (
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">EMA Trend</h3>
          <HelpPopover content={{
            title: "EMA — Exponential Moving Averages",
            body: "EMAs are smoothed averages that give more weight to recent prices than old ones. EMA21 is 'fast' (sensitive to recent moves) and EMA50 is 'slow' (stable baseline). When the fast EMA is above the slow EMA, the stock is in an uptrend.",
            level: "beginner",
            tips: [
              "Price > EMA21 > EMA50 = strong uptrend (all aligned bullish)",
              "Price < EMA21 < EMA50 = strong downtrend",
              "EMA21 crossing above EMA50 = 'Golden Cross' — bullish signal",
              "EMA21 crossing below EMA50 = 'Death Cross' — bearish signal",
            ],
            affectsVerdict: "The trend agent requires Price > EMA21 > EMA50 for a BULLISH regime classification. This is the primary condition checked before any buy signal is issued.",
            source: "Computed on NSE daily OHLCV — technical_analyzer.py (exponential smoothing, adjust=False)",
          }} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                label: "Close vs EMA21",
                current: parseFloat(close),
                ema: parseFloat(ema21),
                emaLabel: "EMA21",
              },
              {
                label: "Close vs EMA50",
                current: parseFloat(close),
                ema: parseFloat(ema50),
                emaLabel: "EMA50",
              },
              {
                label: "EMA21 vs EMA50",
                current: parseFloat(ema21),
                ema: parseFloat(ema50),
                emaLabel: "EMA50",
              },
            ].map((item) => {
              const above = item.current > item.ema;
              const diff = ((item.current - item.ema) / item.ema) * 100;
              return (
                <div key={item.label} className="p-4 bg-surface-raised rounded-btn">
                  <div className="text-xs text-text-muted mb-2">{item.label}</div>
                  <div className={cn("text-xl font-bold", above ? "text-bullish-green" : "text-bearish-red")}>
                    {above ? "Above" : "Below"}
                  </div>
                  <div className={cn("text-xs font-medium tabular-nums mt-1", above ? "text-bullish-green" : "text-bearish-red")}>
                    {diff > 0 ? "+" : ""}{diff.toFixed(2)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Full quant summary */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-base font-semibold text-text-primary">Quant Agent Full Summary</h3>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed font-mono bg-surface-raised rounded-btn p-4">
          {quant_summary || "Quant summary not available."}
        </p>
      </div>
    </div>
  );
}
