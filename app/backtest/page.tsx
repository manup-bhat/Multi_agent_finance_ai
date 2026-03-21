"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import useSWRMutation from "swr/mutation";
import { Play } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { runBacktest, getApiErrorMessage } from "@/lib/api-client";
import type { BacktestResponse } from "@/lib/api-client";
import { TICKERS } from "@/lib/mock-data";
import { ChartSkeleton } from "@/components/charts";

const EquityCurveChart = dynamic(
  () => import('@/components/charts/EquityCurveChart').then(m => m.EquityCurveChart),
  { ssr: false, loading: () => <ChartSkeleton height={280} /> }
);

type Strategy = "mean_reversion" | "ema_momentum" | "vix_gated" | "fii_flow";

const STRATEGIES: { value: Strategy; label: string; desc: string }[] = [
  { value: "mean_reversion", label: "Mean Reversion", desc: "Bollinger Band squeeze + VIX-gated entries" },
  { value: "ema_momentum", label: "EMA Momentum", desc: "20/50 EMA crossover with volume confirmation" },
  { value: "vix_gated", label: "VIX-Gated", desc: "Long-only when VIX < 18; cash otherwise" },
  { value: "fii_flow", label: "FII Flow", desc: "Trend-following based on FII net buy streaks" },
];

async function runBacktestFetcher(_: string, { arg }: { arg: { strategy: Strategy; ticker: string; years: number } }) {
  return runBacktest(arg.strategy, arg.ticker, arg.years);
}

export default function BacktestPage() {
  const [strategy, setStrategy] = useState<Strategy>("mean_reversion");
  const [ticker, setTicker] = useState("BANKNIFTY");
  const [years, setYears] = useState(5);

  const { trigger, data: result, isMutating, error } = useSWRMutation<BacktestResponse, Error, string, { strategy: Strategy; ticker: string; years: number }>(
    "backtest-run",
    runBacktestFetcher
  );

  const equityCurveData = result
    ? {
        dates: result.dates,
        strategy: result.equity_curve.map((v: number) => +((v / 100000) * 100 - 100).toFixed(2)),
        benchmark: result.benchmark_curve.map((v: number) => +((v / 100000) * 100 - 100).toFixed(2)),
      }
    : null;

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Backtest Results</h1>
        <HelpPopover content={{
          title: "Strategy Backtesting",
          body: "Backtesting simulates how a trading strategy would have performed on past data. It is not a guarantee of future returns, but it shows whether a strategy has a positive historical edge. This system uses real NSE/yfinance data — no synthetic inputs.",
          level: "intermediate",
          tips: [
            "Mean Reversion: buys when RSI < 30 + Bollinger Band compression",
            "EMA Momentum: buys when EMA20 crosses above EMA50 with volume",
            "VIX-Gated: only takes long positions when India VIX is below 18",
            "FII Flow: follows FII net buying streaks as entry signals",
          ],
          affectsVerdict: "Strategies that pass the Blueprint Gate (Sharpe > 0.8) are considered deployment-ready. Failed strategies provide a baseline for parameter optimisation.",
          source: "Historical OHLCV via yfinance, FII/DII via nselib — BacktestEngine (backtesting/engine.py)",
        }} />
      </div>

      {/* Config Panel */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Backtest Configuration</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Strategy */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2 block">
              Strategy
            </label>
            <div className="space-y-2">
              {STRATEGIES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStrategy(s.value)}
                  className={cn(
                    "w-full text-left px-3 py-2.5 rounded-btn border transition-all duration-150 text-sm",
                    strategy === s.value
                      ? "border-saffron bg-saffron-light text-saffron"
                      : "border-border bg-surface text-text-secondary hover:bg-surface-raised"
                  )}
                >
                  <div className="font-medium">{s.label}</div>
                  <div className="text-xs opacity-70 mt-0.5">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Ticker */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2 block">
              Instrument
            </label>
            <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1 scrollbar-thin">
              {TICKERS.slice(0, 20).map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTicker(t.value.replace(".NS", ""))}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-btn text-sm transition-all duration-150",
                    ticker === t.value.replace(".NS", "")
                      ? "bg-saffron-light text-saffron font-medium"
                      : "text-text-secondary hover:bg-surface-raised"
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Years + Run */}
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2 block">
                Backtest Window: {years} {years === 1 ? "year" : "years"}
              </label>
              <input
                type="range"
                min={1}
                max={10}
                value={years}
                onChange={(e) => setYears(Number(e.target.value))}
                className="w-full accent-saffron"
              />
              <div className="flex justify-between text-xs text-text-muted mt-1">
                <span>1 yr</span><span>5 yrs</span><span>10 yrs</span>
              </div>
            </div>

            <Button
              onClick={() => trigger({ strategy, ticker, years })}
              disabled={isMutating}
              className="mt-auto"
            >
              {isMutating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                  Running Backtest...
                </>
              ) : (
                <>
                  <Play size={15} className="mr-2" />
                  Run Backtest
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <div className="card-base p-4 border border-bearish-red/20">
          <p className="text-sm text-bearish-red font-medium">Backtest failed: {getApiErrorMessage(error)}</p>
        </div>
      )}

      {isMutating && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      )}

      {result && !isMutating && (
        <>
          {/* KPI Row */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { label: "CAGR", value: `${result.cagr_pct.toFixed(1)}%`, color: result.cagr_pct > 0 ? "text-bullish-green" : "text-bearish-red" },
              { label: "Sharpe Ratio", value: result.sharpe_ratio.toFixed(2), color: result.sharpe_ratio > 1 ? "text-bullish-green" : result.sharpe_ratio > 0.5 ? "text-warning-amber" : "text-bearish-red" },
              { label: "Max Drawdown", value: `${result.max_drawdown_pct.toFixed(1)}%`, color: result.max_drawdown_pct < 15 ? "text-bullish-green" : result.max_drawdown_pct < 30 ? "text-warning-amber" : "text-bearish-red" },
              { label: "Win Rate", value: `${result.win_rate_pct.toFixed(1)}%`, color: result.win_rate_pct > 55 ? "text-bullish-green" : result.win_rate_pct > 45 ? "text-warning-amber" : "text-bearish-red" },
              { label: "Total Trades", value: result.n_trades.toString(), color: "text-text-primary" },
            ].map((kpi) => (
              <div key={kpi.label} className="card-base p-4 text-center">
                <div className="text-xs text-text-muted uppercase tracking-widest mb-1">{kpi.label}</div>
                <div className={cn("text-2xl font-bold tabular-nums", kpi.color)}>{kpi.value}</div>
              </div>
            ))}
          </div>

          {/* Blueprint Gate */}
          <div className={cn(
            "card-base p-4 flex items-start gap-3",
            result.blueprint_gate_passed ? "border-bullish-green/20 bg-bullish-bg" : "border-bearish-red/20 bg-bearish-bg"
          )}>
            <div className={cn(
              "w-3 h-3 rounded-full flex-shrink-0 mt-1",
              result.blueprint_gate_passed ? "bg-bullish-green" : "bg-bearish-red"
            )} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className={cn("font-semibold", result.blueprint_gate_passed ? "text-bullish-green" : "text-bearish-red")}>
                  Blueprint Gate: {result.blueprint_gate_passed ? "PASSED" : "FAILED"}
                </span>
                <HelpPopover content={{
                  title: "Blueprint Gate — Minimum Quality Filter",
                  body: "A deployment readiness check borrowed from professional quant fund practices. Before a strategy is used for live signals, it must prove historical quality across three independent metrics simultaneously. Passing all three doesn't guarantee future profits, but failing any one is a hard disqualification.",
                  level: "advanced",
                  tips: [
                    "Sharpe > 0.8 = returns adequately compensate for risk taken",
                    "Max Drawdown < 30% = strategy survives a bad market without catastrophic loss",
                    "Win Rate > 45% = strategy wins more often than not",
                    "All three must pass simultaneously — one failure = FAILED",
                  ],
                  affectsVerdict: "PASSED gate = strategy is suitable for live deployment. FAILED gate = strategy needs parameter adjustment, different instrument, or different regime filter.",
                  source: "backtesting/engine.py — evaluated on full historical data window specified by the year slider",
                }} />
              </div>
              <p className="text-xs text-text-muted mt-0.5">
                {result.blueprint_gate_passed
                  ? `Sharpe ${result.sharpe_ratio.toFixed(2)} > 0.8 ✓ | Drawdown ${result.max_drawdown_pct.toFixed(1)}% < 30% ✓ | Win rate ${result.win_rate_pct.toFixed(1)}% > 45% ✓`
                  : `Requirements: Sharpe > 0.8 (got ${result.sharpe_ratio.toFixed(2)}) | Drawdown < 30% (got ${result.max_drawdown_pct.toFixed(1)}%) | Win rate > 45% (got ${result.win_rate_pct.toFixed(1)}%)`}
              </p>
            </div>
          </div>

          {/* Equity Curve */}
          {equityCurveData && (
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-base font-semibold text-text-primary">
                  Equity Curve — {result.strategy} on {result.ticker}
                </h3>
              </div>
              <EquityCurveChart data={equityCurveData} height={280} />
              <div className="flex gap-4 mt-2 text-xs">
                <div className="flex items-center gap-1.5"><div className="w-4 h-0.5 bg-saffron" /><span className="text-text-muted">Strategy</span></div>
                <div className="flex items-center gap-1.5"><div className="w-4 h-0.5 bg-text-muted" /><span className="text-text-muted">Buy & Hold</span></div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
