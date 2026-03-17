"use client";
import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, AreaChart, Area
} from "recharts";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { MOCK_OPTION_CHAIN } from "@/lib/mock-data";
import { useApp } from "@/lib/app-context";

const STRIKE_FILTERS = ["All Strikes", "ATM ±10", "ATM ±5"] as const;

// Payoff for Iron Condor: short 22000CE, long 22400CE, short 21600PE, long 21200PE
function getIronCondorPayoff(price: number): number {
  const premium = 42; // net credit
  const shortCall = 22000, longCall = 22400;
  const shortPut = 21600, longPut = 21200;
  let pnl = premium;
  if (price > shortCall) pnl -= (price - shortCall);
  if (price > longCall) pnl += (price - longCall);
  if (price < shortPut) pnl -= (shortPut - price);
  if (price < longPut) pnl += (longPut - price);
  return pnl * 100; // lot size factor (simplified)
}

const PAYOFF_DATA = Array.from({ length: 50 }, (_, i) => {
  const price = 20500 + i * 80;
  return { price, pnl: getIronCondorPayoff(price) };
});

export default function FOPage() {
  const { analysisData } = useApp();
  const [strikeFilter, setStrikeFilter] = useState<typeof STRIKE_FILTERS[number]>("ATM ±10");

  const atm = 22000;
  const filterMap: Record<typeof STRIKE_FILTERS[number], number> = { "All Strikes": 50, "ATM ±10": 10, "ATM ±5": 5 };
  const filterSteps = filterMap[strikeFilter];

  const filteredChain = MOCK_OPTION_CHAIN.filter((row) => Math.abs(row.strike - atm) <= filterSteps * 100);

  // IV smile data
  const ivSmileData = MOCK_OPTION_CHAIN.map((row) => ({
    strike: row.strike,
    callIV: row.call.iv,
    putIV: row.put.iv,
    histIV: row.call.iv * 0.82 + 2,
  }));

  // Top OI buildup
  const oiBuildup = [...MOCK_OPTION_CHAIN]
    .flatMap((row) => [
      { strike: row.strike, type: "CE", oiChange: row.call.oiChange },
      { strike: row.strike, type: "PE", oiChange: row.put.oiChange },
    ])
    .sort((a, b) => Math.abs(b.oiChange) - Math.abs(a.oiChange))
    .slice(0, 10);

  const pcr = analysisData?.pcr ?? 1.32;

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">F&O Analysis</h1>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-base p-5">
          <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Put-Call Ratio</div>
          <div className="text-4xl font-bold tabular-nums text-bullish-green">{pcr.toFixed(2)}</div>
          <span className="inline-flex mt-1 px-2 py-0.5 rounded-badge bg-bullish-bg text-bullish-green text-xs font-medium">Bullish Zone</span>
          <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
            <div className="h-full bg-bullish-green rounded-pill transition-all duration-500" style={{ width: `${Math.min(pcr / 2, 1) * 100}%` }} />
          </div>
        </div>
        <div className="card-base p-5">
          <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Max Pain</div>
          <div className="text-4xl font-bold tabular-nums text-text-primary">₹22,000</div>
          <div className="text-xs text-text-muted mt-1">Current ₹22,143 (+0.6% above)</div>
          <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
            <div className="h-full bg-warning-amber rounded-pill" style={{ width: "52%" }} />
          </div>
        </div>
        <div className="card-base p-5">
          <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">IV Rank</div>
          <div className="text-4xl font-bold tabular-nums text-warning-amber">42</div>
          <span className="inline-flex mt-1 px-2 py-0.5 rounded-badge bg-warning-bg text-warning-amber text-xs font-medium">Moderate</span>
          <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
            <div className="h-full bg-warning-amber rounded-pill" style={{ width: "42%" }} />
          </div>
        </div>
        <div className="card-base p-5">
          <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Days to Expiry</div>
          <div className="text-4xl font-bold tabular-nums text-bearish-red">3</div>
          <span className="inline-flex mt-1 px-2 py-0.5 rounded-badge bg-bearish-bg text-bearish-red text-xs font-medium">Expiry Thursday</span>
        </div>
      </div>

      {/* Option Chain Table */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text-primary">Option Chain</h3>
            <HelpPopover content={{
              title: "Option Chain",
              body: "Live option chain showing OI, IV, volume and LTP for calls and puts at each strike. ATM strike is highlighted with saffron border.",
              affectsVerdict: "High call OI = resistance, high put OI = support. PCR and max pain are derived from this data.",
              source: "NSE India via nsefin — refreshed every 5 minutes during market hours",
            }} />
          </div>
          <div className="flex gap-1">
            {STRIKE_FILTERS.map((f) => (
              <button key={f} onClick={() => setStrikeFilter(f)}
                className={cn("px-2.5 py-1 text-xs rounded-badge font-medium transition-all duration-150",
                  strikeFilter === f ? "bg-saffron text-white" : "text-text-muted hover:bg-surface-raised hover:text-text-primary")}>
                {f}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th colSpan={5} className="text-center py-2 text-saffron font-semibold text-xs border-r border-border">CALLS</th>
                <th className="py-2 px-4 text-center font-bold text-text-primary text-sm">STRIKE</th>
                <th colSpan={5} className="text-center py-2 text-neutral-blue font-semibold text-xs border-l border-border">PUTS</th>
              </tr>
              <tr className="border-b border-border text-text-muted bg-surface-raised/50">
                <th className="py-2 px-3 text-right font-medium border-r border-border">OI</th>
                <th className="py-2 px-3 text-right font-medium">OI Chg</th>
                <th className="py-2 px-3 text-right font-medium">Vol</th>
                <th className="py-2 px-3 text-right font-medium">IV%</th>
                <th className="py-2 px-3 text-right font-medium border-r border-border">LTP</th>
                <th className="py-2 px-4 text-center font-bold text-text-primary">—</th>
                <th className="py-2 px-3 text-left font-medium border-l border-border">LTP</th>
                <th className="py-2 px-3 text-left font-medium">IV%</th>
                <th className="py-2 px-3 text-left font-medium">Vol</th>
                <th className="py-2 px-3 text-left font-medium">OI Chg</th>
                <th className="py-2 px-3 text-left font-medium">OI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredChain.map((row) => (
                <tr
                  key={row.strike}
                  className={cn(
                    "transition-colors duration-150",
                    row.isATM
                      ? "bg-saffron-light border-l-2 border-l-saffron"
                      : "hover:bg-surface-raised"
                  )}
                >
                  <td className="py-2.5 px-3 text-right tabular-nums text-text-secondary border-r border-border">{(row.call.oi / 1000).toFixed(0)}K</td>
                  <td className={cn("py-2.5 px-3 text-right tabular-nums", row.call.oiChange >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.call.oiChange >= 0 ? "+" : ""}{(row.call.oiChange / 1000).toFixed(0)}K
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-text-muted">{(row.call.volume / 1000).toFixed(0)}K</td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-text-secondary">{row.call.iv.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-text-primary font-medium border-r border-border">₹{row.call.ltp.toFixed(2)}</td>
                  <td className={cn("py-2.5 px-4 text-center font-bold text-sm", row.isATM ? "text-saffron" : "text-text-primary")}>{row.strike.toLocaleString("en-IN")}</td>
                  <td className="py-2.5 px-3 text-left tabular-nums text-text-primary font-medium border-l border-border">₹{row.put.ltp.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-left tabular-nums text-text-secondary">{row.put.iv.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-left tabular-nums text-text-muted">{(row.put.volume / 1000).toFixed(0)}K</td>
                  <td className={cn("py-2.5 px-3 text-left tabular-nums", row.put.oiChange >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.put.oiChange >= 0 ? "+" : ""}{(row.put.oiChange / 1000).toFixed(0)}K
                  </td>
                  <td className="py-2.5 px-3 text-left tabular-nums text-text-secondary">{(row.put.oi / 1000).toFixed(0)}K</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* IV Surface + Payoff Diagram */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">IV Smile</h3>
            <HelpPopover content={{
              title: "Implied Volatility Smile",
              body: "IV across strikes forms a smile/skew shape — higher IV for OTM options vs ATM. The gap between current IV and historical avg shows IV premium.",
              affectsVerdict: "When current IV is well above historical average, selling options (like Iron Condor) is preferred. Low IV → buying strategies.",
              source: "NSE option chain implied volatility — computed via Black-Scholes",
            }} />
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ivSmileData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
                <XAxis dataKey="strike" tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                  interval={3} tickFormatter={(v) => v.toLocaleString("en-IN")} />
                <YAxis tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [`${v.toFixed(1)}%`, ""]}
                />
                <Area type="monotone" dataKey="callIV" stroke="#FF6B00" fill="#FF6B00" fillOpacity={0.1} strokeWidth={2} name="Current IV" />
                <Line type="monotone" dataKey="histIV" stroke="#94A3B8" strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="Hist Avg IV" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Iron Condor Payoff</h3>
            <HelpPopover content={{
              title: "Strategy Payoff Diagram",
              body: "Shows profit/loss at expiry for every underlying price. The Iron Condor profits when the stock stays within the breakeven range.",
              affectsVerdict: "Strategy is chosen based on IV Rank (>30 → sell premium) and PCR (1.32 → neutral-bullish range trade).",
              source: "F&O strategy simulator — Black-Scholes Greeks + payoff engine",
            }} />
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={PAYOFF_DATA} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
                <XAxis dataKey="price" tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                  interval={7} tickFormatter={(v) => v.toLocaleString("en-IN")} />
                <YAxis tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [`₹${v.toLocaleString("en-IN")}`, "P&L"]}
                />
                <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
                <ReferenceLine x={21680} stroke="#DC2626" strokeDasharray="3 2" label={{ value: "BE₁", position: "top", fontSize: 9, fill: "#DC2626" }} />
                <ReferenceLine x={22320} stroke="#DC2626" strokeDasharray="3 2" label={{ value: "BE₂", position: "top", fontSize: 9, fill: "#DC2626" }} />
                <ReferenceLine x={22143} stroke="#FF6B00" strokeDasharray="3 2" label={{ value: "CMP", position: "top", fontSize: 9, fill: "#FF6B00" }} />
                <Area type="monotone" dataKey="pnl" stroke="#059669" fill="#059669" fillOpacity={0.1} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="text-center p-2 rounded-btn bg-bullish-bg">
              <div className="text-text-muted">Max Profit</div>
              <div className="font-bold text-bullish-green">₹4,200</div>
            </div>
            <div className="text-center p-2 rounded-btn bg-bearish-bg">
              <div className="text-text-muted">Max Loss</div>
              <div className="font-bold text-bearish-red">₹-11,800</div>
            </div>
            <div className="text-center p-2 rounded-btn bg-neutral-bg">
              <div className="text-text-muted">Breakevens</div>
              <div className="font-bold text-neutral-blue">21,680 / 22,320</div>
            </div>
          </div>
        </div>
      </div>

      {/* OI Buildup Table */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Top OI Buildup</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th className="text-left py-2 font-medium">Strike</th>
                <th className="text-left py-2 font-medium">Type</th>
                <th className="text-right py-2 font-medium">OI Change</th>
                <th className="text-left py-2 font-medium pl-4">Signal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {oiBuildup.map((row, i) => (
                <tr key={i} className="hover:bg-surface-raised transition-colors duration-150">
                  <td className="py-2.5 font-medium tabular-nums text-text-primary">{row.strike.toLocaleString("en-IN")}</td>
                  <td className="py-2.5">
                    <span className={cn("px-2 py-0.5 rounded-badge text-xs font-medium", row.type === "CE" ? "bg-bearish-bg text-bearish-red" : "bg-bullish-bg text-bullish-green")}>
                      {row.type}
                    </span>
                  </td>
                  <td className={cn("py-2.5 text-right tabular-nums font-medium", row.oiChange >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.oiChange >= 0 ? "+" : ""}{(row.oiChange / 1000).toFixed(0)}K
                  </td>
                  <td className="py-2.5 pl-4 text-xs text-text-secondary">
                    {row.type === "CE" && row.oiChange > 0 ? "Strong Resistance" :
                     row.type === "PE" && row.oiChange > 0 ? "Support Building" :
                     row.type === "CE" && row.oiChange < 0 ? "Resistance Unwinding" : "Support Unwinding"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
