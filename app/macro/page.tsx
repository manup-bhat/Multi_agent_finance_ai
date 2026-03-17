"use client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceArea, ReferenceLine
} from "recharts";
import { ArrowUp, ArrowDown } from "lucide-react";
import { HelpPopover } from "@/components/ui/help-popover";
import { cn } from "@/lib/utils";
import { MOCK_VIX_DATA } from "@/lib/mock-data";

const GLOBAL_CUES = [
  { label: "SGX Nifty", value: "+45 pts", change: 0.21, positive: true },
  { label: "S&P 500 Fut.", value: "-0.2%", change: -0.2, positive: false },
  { label: "Nasdaq Fut.", value: "+0.1%", change: 0.1, positive: true },
  { label: "Nikkei 225", value: "+0.8%", change: 0.8, positive: true },
  { label: "USD/INR", value: "₹83.42", change: 0.1, positive: false },
  { label: "Brent Crude", value: "$78.20", change: -0.5, positive: false },
];

const CORRELATIONS = [
  { factor: "USD/INR", corr: -0.72, impact: "Strong Negative" },
  { factor: "Brent Crude", corr: -0.45, impact: "Moderate Negative" },
  { factor: "US 10Y Yield", corr: -0.38, impact: "Moderate Negative" },
  { factor: "Gold", corr: 0.12, impact: "Weak Positive" },
  { factor: "SGX Nifty", corr: 0.88, impact: "Strong Positive" },
];

const EVENTS = [
  { date: "2024-03-21", label: "RBI MPC", type: "rbi" },
  { date: "2024-03-28", label: "Expiry", type: "expiry" },
  { date: "2024-04-04", label: "Expiry", type: "expiry" },
  { date: "2024-04-10", label: "Infosys Results", type: "result" },
  { date: "2024-04-11", label: "RBI MPC", type: "rbi" },
  { date: "2024-04-18", label: "Expiry", type: "expiry" },
];

export default function MacroPage() {
  const vixSlice = MOCK_VIX_DATA.slice(-120);
  const currentVix = vixSlice[vixSlice.length - 1]?.vix ?? 14.2;

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">Macro India</h1>

      {/* Global Cues */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Pre-Market Global Cues</h3>
          <HelpPopover content={{
            title: "Pre-Market Global Cues",
            body: "Key global market indicators as of pre-market hours. SGX Nifty is the best leading indicator for Nifty50 opening direction.",
            affectsVerdict: "Strong negative global cues (SGX Nifty down >100pts + crude spike) can override the macro agent's bullish stance.",
            source: "SGX: SGX.com | Futures: CME | Forex: NSE RBI | Commodities: MCX/ICE",
          }} />
          <span className="text-xs text-text-muted ml-auto">Data as of 8:45 AM IST</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {GLOBAL_CUES.map((cue) => (
            <div key={cue.label} className="card-base p-4 text-center shadow-none">
              <div className="text-xs text-text-muted font-medium mb-1">{cue.label}</div>
              <div className={cn("text-lg font-bold tabular-nums", cue.positive ? "text-bullish-green" : "text-bearish-red")}>
                {cue.value}
              </div>
              <div className={cn("flex items-center justify-center gap-0.5 text-xs mt-1", cue.positive ? "text-bullish-green" : "text-bearish-red")}>
                {cue.positive ? <ArrowUp size={11} /> : <ArrowDown size={11} />}
                {Math.abs(cue.change)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* VIX Chart + Correlations */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* VIX Chart — 60% */}
        <div className="lg:col-span-3 card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">India VIX — 4 Month History</h3>
            <HelpPopover content={{
              title: "India VIX History",
              body: "India VIX trend shows how market fear has evolved. Zone bands indicate regime: Complacency (<13), Normal (13–18), Elevated (18–25), High Fear (>25).",
              affectsVerdict: "VIX crossing into Elevated or High Fear zone triggers circuit breaker rules and overrides position sizing.",
              source: "NSE India via yfinance (^INDIAVIX) — daily historical data",
            }} />
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={vixSlice} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                {/* Zone bands */}
                <ReferenceArea y1={0} y2={13} fill="#059669" fillOpacity={0.06} />
                <ReferenceArea y1={13} y2={18} fill="#ffffff" fillOpacity={0} />
                <ReferenceArea y1={18} y2={25} fill="#D97706" fillOpacity={0.06} />
                <ReferenceArea y1={25} y2={40} fill="#DC2626" fillOpacity={0.08} />

                <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                  interval={14} tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
                <YAxis tick={{ fontSize: 9, fill: "#94A3B8" }} tickLine={false} axisLine={false} domain={[8, 32]} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number) => [v.toFixed(2), "VIX"]}
                />
                <ReferenceLine y={13} stroke="#059669" strokeDasharray="3 2" strokeWidth={1} />
                <ReferenceLine y={18} stroke="#D97706" strokeDasharray="3 2" strokeWidth={1} />
                <ReferenceLine y={25} stroke="#DC2626" strokeDasharray="3 2" strokeWidth={1} />
                <Line type="monotone" dataKey="vix" stroke="#1D4ED8" strokeWidth={2} dot={false} name="India VIX" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {/* Zone legend */}
          <div className="flex flex-wrap gap-3 mt-3 text-xs">
            {[
              { label: "Complacency (<13)", color: "#059669" },
              { label: "Normal (13–18)", color: "#64748B" },
              { label: "Elevated (18–25)", color: "#D97706" },
              { label: "High Fear (>25)", color: "#DC2626" },
            ].map((z) => (
              <div key={z.label} className="flex items-center gap-1.5">
                <div className="w-3 h-2 rounded-sm" style={{ background: z.color, opacity: 0.6 }} />
                <span className="text-text-muted">{z.label}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-sm">
            Current VIX: <strong className={cn("tabular-nums", currentVix < 18 ? "text-bullish-green" : currentVix < 25 ? "text-warning-amber" : "text-bearish-red")}>{currentVix.toFixed(2)}</strong>
            <span className={cn("ml-2 text-xs px-2 py-0.5 rounded-badge font-medium", currentVix < 18 ? "bg-bullish-bg text-bullish-green" : currentVix < 25 ? "bg-warning-bg text-warning-amber" : "bg-bearish-bg text-bearish-red")}>
              {currentVix < 18 ? "NORMAL" : currentVix < 25 ? "ELEVATED" : "HIGH"}
            </span>
          </div>
        </div>

        {/* Correlations — 40% */}
        <div className="lg:col-span-2 card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-text-primary">Key Correlations (30-day)</h3>
            <HelpPopover content={{
              title: "Macro Correlations",
              body: "Rolling 30-day Pearson correlation between Nifty50 returns and macro variables. Negative correlation means they move in opposite directions.",
              affectsVerdict: "Strong correlations help the macro agent assess whether current macro backdrop is favorable or headwind.",
              source: "Computed from 30-day rolling returns — yfinance data",
            }} />
          </div>
          <div className="space-y-3">
            {CORRELATIONS.map((c) => (
              <div key={c.factor}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-text-secondary font-medium">{c.factor}</span>
                  <span className={cn("text-sm font-bold tabular-nums", c.corr > 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {c.corr > 0 ? "+" : ""}{c.corr.toFixed(2)}
                  </span>
                </div>
                <div className="relative h-2 bg-surface-raised rounded-pill overflow-hidden">
                  <div
                    className="absolute top-0 h-full rounded-pill"
                    style={{
                      width: `${Math.abs(c.corr) * 50}%`,
                      left: c.corr >= 0 ? "50%" : undefined,
                      right: c.corr < 0 ? "50%" : undefined,
                      background: c.corr > 0 ? "#059669" : "#DC2626",
                    }}
                  />
                  <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
                </div>
                <div className="text-xs text-text-muted mt-0.5">{c.impact}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Event Calendar */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Event Calendar — Next 30 Days</h3>
        <div className="relative">
          {/* Timeline bar */}
          <div className="absolute top-5 left-0 right-0 h-0.5 bg-border" />
          <div className="flex justify-between relative">
            {EVENTS.map((ev) => {
              const colors: Record<string, string> = {
                rbi: "bg-[#7C3AED] text-white",
                expiry: "bg-warning-amber text-white",
                result: "bg-neutral-blue text-white",
              };
              const dotColors: Record<string, string> = {
                rbi: "#7C3AED",
                expiry: "#D97706",
                result: "#1D4ED8",
              };
              return (
                <div key={ev.date + ev.label} className="flex flex-col items-center gap-2 relative">
                  <div
                    className="w-3 h-3 rounded-full border-2 border-surface z-10"
                    style={{ background: dotColors[ev.type] }}
                  />
                  <span className={cn("text-xs px-2 py-0.5 rounded-badge font-medium whitespace-nowrap", colors[ev.type])}>
                    {ev.label}
                  </span>
                  <span className="text-xs text-text-muted">{new Date(ev.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="flex gap-4 mt-4 text-xs">
          {[{ label: "RBI MPC", color: "#7C3AED" }, { label: "Expiry Thursday", color: "#D97706" }, { label: "Results", color: "#1D4ED8" }].map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: l.color }} />
              <span className="text-text-muted">{l.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
