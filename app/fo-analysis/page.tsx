"use client";
import useSWR from "swr";
import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useApp } from "@/lib/app-context";
import { getFnO, getApiErrorMessage } from "@/lib/api-client";

const NSE_SYMBOLS = ["BANKNIFTY", "NIFTY", "FINNIFTY", "MIDCPNIFTY"];

export default function FOPage() {
  const { selectedTicker, analysisData } = useApp();
  const [symbol, setSymbol] = useState("BANKNIFTY");

  const { data: fno, error, isLoading } = useSWR(
    ["fno", symbol],
    () => getFnO(symbol),
    { revalidateOnFocus: false }
  );

  // IV rank bar color
  const ivRankColor = (rank: number | null) =>
    rank == null ? "#94A3B8" : rank > 70 ? "#059669" : rank > 40 ? "#D97706" : "#DC2626";

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-44" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">F&O Analysis</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load F&O data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">F&O Analysis</h1>
        {/* Symbol selector */}
        <div className="flex gap-1">
          {NSE_SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={cn(
                "px-3 py-1.5 text-xs rounded-badge font-medium transition-all duration-150",
                symbol === s
                  ? "bg-saffron text-white"
                  : "text-text-muted hover:text-text-primary hover:bg-surface-raised"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {!fno ? (
        <div className="card-base p-8 text-center text-text-muted">
          <p className="font-medium text-text-secondary mb-2">No F&O data available</p>
          <p className="text-sm">Run an analysis from the Dashboard with F&O enabled.</p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {/* PCR */}
            <div className="card-base p-5">
              <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
                Put-Call Ratio
              </div>
              <div className={cn(
                "text-4xl font-bold tabular-nums",
                fno.pcr == null ? "text-text-muted"
                  : fno.pcr > 1.2 ? "text-bullish-green"
                  : fno.pcr < 0.8 ? "text-bearish-red"
                  : "text-warning-amber"
              )}>
                {fno.pcr != null ? fno.pcr.toFixed(2) : "—"}
              </div>
              <span className={cn(
                "inline-flex mt-1 px-2 py-0.5 rounded-badge text-xs font-medium",
                fno.pcr_signal.includes("Bullish") ? "bg-bullish-bg text-bullish-green"
                  : fno.pcr_signal.includes("Bearish") ? "bg-bearish-bg text-bearish-red"
                  : "bg-warning-bg text-warning-amber"
              )}>
                {fno.pcr_signal}
              </span>
            </div>

            {/* Max Pain */}
            <div className="card-base p-5">
              <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
                Max Pain
              </div>
              <div className="text-4xl font-bold tabular-nums text-text-primary">
                {fno.max_pain != null
                  ? `₹${fno.max_pain.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
                  : "—"}
              </div>
              <div className="text-xs text-text-muted mt-1">
                Expiry: {fno.expiry}
              </div>
            </div>

            {/* IV Rank */}
            <div className="card-base p-5">
              <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
                IV Rank
              </div>
              <div
                className="text-4xl font-bold tabular-nums"
                style={{ color: ivRankColor(fno.iv_rank_pct) }}
              >
                {fno.iv_rank_pct != null ? `${fno.iv_rank_pct.toFixed(0)}` : "—"}
              </div>
              <span className={cn(
                "inline-flex mt-1 px-2 py-0.5 rounded-badge text-xs font-medium",
                fno.iv_rank_pct == null ? "bg-surface-raised text-text-muted"
                  : fno.iv_rank_pct > 70 ? "bg-bullish-bg text-bullish-green"
                  : fno.iv_rank_pct > 40 ? "bg-warning-bg text-warning-amber"
                  : "bg-bearish-bg text-bearish-red"
              )}>
                {fno.iv_rank_pct == null ? "Unknown"
                  : fno.iv_rank_pct > 70 ? "High — Sell Premium"
                  : fno.iv_rank_pct > 40 ? "Moderate"
                  : "Low — Buy Premium"}
              </span>
            </div>

            {/* ATM IV */}
            <div className="card-base p-5">
              <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">
                ATM Implied Volatility
              </div>
              <div className="text-4xl font-bold tabular-nums text-text-primary">
                {fno.atm_iv != null ? `${fno.atm_iv.toFixed(1)}%` : "—"}
              </div>
              <div className="text-xs text-text-muted mt-1">
                IV Skew: {fno.skew ?? "—"}
              </div>
            </div>
          </div>

          {/* Strategy Recommendation */}
          <div className="card-base p-5">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-base font-semibold text-text-primary">Strategy Recommendation</h3>
              <HelpPopover content={{
                title: "F&O Strategy",
                body: "Strategy is selected based on IV rank, PCR, max pain distance, and skew. High IV → sell premium; low IV → buy premium.",
                affectsVerdict: "Recommended strategy is derived from the combined F&O analysis and affects position sizing in the overall verdict.",
                source: "F&O agent — rules-based strategy selector",
              }} />
            </div>
            <div className="px-4 py-3 rounded-card bg-saffron-light border border-saffron/20">
              <p className="text-sm font-semibold text-saffron">{fno.strategy_recommendation}</p>
            </div>
            <div className="mt-3 text-xs text-text-muted">
              Source: {fno.source} | FII Futures Net: {fno.fii_futures_net}
            </div>
          </div>

          {/* ATM Greeks */}
          {Object.keys(fno.greeks_atm).length > 0 && (
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-base font-semibold text-text-primary">ATM Option Greeks</h3>
                <HelpPopover content={{
                  title: "Option Greeks — ATM Strike",
                  body: "Greeks measure sensitivity of the ATM option price to changes in underlying, time, and volatility.",
                  affectsVerdict: "High Gamma near expiry amplifies moves; high Vega means IV changes dominate over delta moves.",
                  source: "NSE option chain — Black-Scholes Greeks",
                }} />
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                {Object.entries(fno.greeks_atm).map(([key, val]) => (
                  <div key={key} className="text-center p-3 rounded-card bg-surface-raised">
                    <div className="text-xs text-text-muted uppercase tracking-widest mb-1">{key}</div>
                    <div className="text-xl font-bold tabular-nums text-text-primary">
                      {typeof val === "number" ? val.toFixed(4) : val}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Participant OI */}
          {Object.keys(fno.participant_oi).length > 0 && (
            <div className="card-base p-5">
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-base font-semibold text-text-primary">Participant-wise Futures OI</h3>
                <HelpPopover content={{
                  title: "Participant Futures Open Interest",
                  body: "Long/short futures positions per participant category. Retail (Client) net short is historically a contrarian bullish signal.",
                  affectsVerdict: "FII net long + Client net short is a strong bullish combination.",
                  source: "NSE combined futures OI — participant-wise daily data",
                }} />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-text-muted">
                      <th className="text-left py-2 font-medium">Participant</th>
                      <th className="text-right py-2 font-medium">Long</th>
                      <th className="text-right py-2 font-medium">Short</th>
                      <th className="text-right py-2 font-medium">Net</th>
                      <th className="text-left py-2 font-medium pl-4">Signal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {Object.entries(fno.participant_oi).map(([participant, data]) => {
                      const net = data.net ?? ((data.long ?? 0) - (data.short ?? 0));
                      return (
                        <tr key={participant} className="hover:bg-surface-raised transition-colors duration-150">
                          <td className="py-3 font-semibold text-text-primary">{participant}</td>
                          <td className="py-3 text-right tabular-nums text-bullish-green">
                            {data.long != null ? data.long.toLocaleString("en-IN") : "—"}
                          </td>
                          <td className="py-3 text-right tabular-nums text-bearish-red">
                            {data.short != null ? data.short.toLocaleString("en-IN") : "—"}
                          </td>
                          <td className={cn(
                            "py-3 text-right tabular-nums font-bold",
                            net >= 0 ? "text-bullish-green" : "text-bearish-red"
                          )}>
                            {net >= 0 ? "+" : ""}{net.toLocaleString("en-IN")}
                          </td>
                          <td className="py-3 pl-4 text-xs text-text-secondary">
                            {participant === "FII" && net > 0
                              ? "Bullish — institutional accumulation"
                              : participant === "Client" && net < 0
                              ? "Retail net short — contrarian bullish"
                              : participant === "DII"
                              ? "Domestic support"
                              : "Neutral"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
