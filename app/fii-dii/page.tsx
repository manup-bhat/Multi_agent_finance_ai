"use client";
import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Cell, Legend
} from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn, formatCrore } from "@/lib/utils";
import { MOCK_FII_DII } from "@/lib/mock-data";

const PARTICIPANT_OI = [
  { name: "FII", longFutures: 124560, shortFutures: 89230 },
  { name: "DII", longFutures: 45230, shortFutures: 38100 },
  { name: "Client", longFutures: 234100, shortFutures: 289800 },
  { name: "Pro/Dealer", longFutures: 12400, shortFutures: 9160 },
];

const DAY_RANGES = ["Last 10 days", "Last 30 days", "Last 60 days"] as const;

export default function FIIDIIPage() {
  const [dayRange, setDayRange] = useState<typeof DAY_RANGES[number]>("Last 30 days");

  const rangeMap: Record<typeof DAY_RANGES[number], number> = { "Last 10 days": 10, "Last 30 days": 30, "Last 60 days": 60 };
  const days = rangeMap[dayRange];

  const chartData = MOCK_FII_DII.slice(-days);

  // Today's numbers (last entry)
  const today = MOCK_FII_DII[MOCK_FII_DII.length - 1] ?? { fii: 3200, dii: -890 };
  const fiiPos = today.fii >= 0;
  const diiPos = today.dii >= 0;
  const consensus = fiiPos && diiPos ? "BOTH BUYING" : !fiiPos && !diiPos ? "BOTH SELLING" : "DIVERGENCE";
  const consensusColor = consensus === "BOTH BUYING" ? "text-bullish-green bg-bullish-bg" : consensus === "BOTH SELLING" ? "text-bearish-red bg-bearish-bg" : "text-warning-amber bg-warning-bg";

  // Streak dots — last 5 days
  const last5 = MOCK_FII_DII.slice(-5);

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">FII / DII Tracker</h1>

      {/* Hero Flow Card */}
      <div className="card-base p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold text-text-primary">Today's Institutional Flows</h3>
          <HelpPopover content={{
            title: "FII / DII Net Flows",
            body: "Foreign Institutional Investors (FII) and Domestic Institutional Investors (DII) net buy/sell data. When both are buying, it signals strong institutional confidence.",
            affectsVerdict: "FII 5-day average is one of the top SHAP features. FII selling for 7+ consecutive days triggers a streak alert.",
            source: "NSE India participant-wise trading data via nselib — daily post-market",
          }} />
        </div>

        <div className="grid grid-cols-3 gap-6 items-center mt-4">
          {/* FII */}
          <div className="text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">FII Net Today</div>
            <div className={cn("text-4xl font-bold tabular-nums", fiiPos ? "text-bullish-green" : "text-bearish-red")}>
              {formatCrore(today.fii)}
            </div>
            <div className="flex gap-1.5 justify-center mt-3">
              {last5.map((d, i) => (
                <div key={i} className={cn("w-3 h-3 rounded-full", d.fii >= 0 ? "bg-bullish-green" : "bg-bearish-red")}
                  title={`${d.date}: ${formatCrore(d.fii)}`} />
              ))}
            </div>
            <div className="text-xs text-text-muted mt-1">5-day streak</div>
          </div>

          {/* Consensus */}
          <div className="text-center">
            <span className={cn("inline-flex px-4 py-2 rounded-pill text-sm font-bold", consensusColor)}>
              {consensus}
            </span>
            <div className="text-xs text-text-muted mt-2">Institutional consensus</div>
          </div>

          {/* DII */}
          <div className="text-center">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">DII Net Today</div>
            <div className={cn("text-4xl font-bold tabular-nums", diiPos ? "text-bullish-green" : "text-bearish-red")}>
              {formatCrore(today.dii)}
            </div>
            <div className="flex gap-1.5 justify-center mt-3">
              {last5.map((d, i) => (
                <div key={i} className={cn("w-3 h-3 rounded-full", d.dii >= 0 ? "bg-bullish-green" : "bg-bearish-red")}
                  title={`${d.date}: ${formatCrore(d.dii)}`} />
              ))}
            </div>
            <div className="text-xs text-text-muted mt-1">5-day streak</div>
          </div>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text-primary">FII / DII Daily Flows</h3>
            <HelpPopover content={{
              title: "FII / DII Daily Flows Chart",
              body: "Grouped bars show FII (green/red) and DII (blue/orange) daily net flows. Hover for exact values.",
              affectsVerdict: "Sustained multi-day trends are weighted more heavily than single-day spikes.",
              source: "NSE daily F&O and cash market participant data",
            }} />
          </div>
          <div className="flex gap-1">
            {DAY_RANGES.map((r) => (
              <button key={r} onClick={() => setDayRange(r)}
                className={cn("px-2.5 py-1 text-xs rounded-badge font-medium transition-all duration-150",
                  dayRange === r ? "bg-saffron text-white" : "text-text-muted hover:bg-surface-raised hover:text-text-primary")}>
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barGap={1}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                interval={Math.floor(days / 8)} tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}K`} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number, name: string) => [`${formatCrore(v)}`, name === "fii" ? "FII" : "DII"]}
                labelFormatter={(v) => `Date: ${v}`}
              />
              <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
              <Bar dataKey="fii" name="FII" maxBarSize={12}>
                {chartData.map((d, i) => <Cell key={i} fill={d.fii >= 0 ? "#059669" : "#DC2626"} opacity={0.85} />)}
              </Bar>
              <Bar dataKey="dii" name="DII" maxBarSize={12}>
                {chartData.map((d, i) => <Cell key={i} fill={d.dii >= 0 ? "#1D4ED8" : "#D97706"} opacity={0.75} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex gap-4 mt-2 text-xs">
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-bullish-green" /><span className="text-text-muted">FII Buy</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-bearish-red" /><span className="text-text-muted">FII Sell</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-neutral-blue" /><span className="text-text-muted">DII Buy</span></div>
          <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded-sm bg-warning-amber" /><span className="text-text-muted">DII Sell</span></div>
        </div>
      </div>

      {/* Participant OI Table */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Participant-wise Futures OI</h3>
          <HelpPopover content={{
            title: "Participant Futures Open Interest",
            body: "Shows long and short futures positions held by different participant categories. Client (retail) net short is historically a contrarian bullish signal.",
            affectsVerdict: "FII net long + Client net short is a strong bullish combination. This structure is currently active.",
            source: "NSE combined futures OI — participant-wise daily data",
          }} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th className="text-left py-2 font-medium">Participant</th>
                <th className="text-right py-2 font-medium">Long Futures</th>
                <th className="text-right py-2 font-medium">Short Futures</th>
                <th className="text-right py-2 font-medium">Net</th>
                <th className="text-left py-2 font-medium pl-4">Signal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {PARTICIPANT_OI.map((row) => {
                const net = row.longFutures - row.shortFutures;
                return (
                  <tr key={row.name} className="hover:bg-surface-raised transition-colors duration-150">
                    <td className="py-3 font-semibold text-text-primary">{row.name}</td>
                    <td className="py-3 text-right tabular-nums text-bullish-green">{row.longFutures.toLocaleString("en-IN")}</td>
                    <td className="py-3 text-right tabular-nums text-bearish-red">{row.shortFutures.toLocaleString("en-IN")}</td>
                    <td className={cn("py-3 text-right tabular-nums font-bold", net >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                      {net >= 0 ? "+" : ""}{net.toLocaleString("en-IN")}
                    </td>
                    <td className="py-3 pl-4 text-xs text-text-secondary">
                      {row.name === "FII" && net > 0 ? "Bullish — institutional accumulation" :
                       row.name === "Client" && net < 0 ? "Retail net short — contrarian bullish" :
                       row.name === "DII" ? "Domestic support" : "Neutral"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
