"use client";
import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, ReferenceLine, ComposedChart, Area
} from "recharts";
import { cn } from "@/lib/utils";
import { HelpPopover } from "@/components/ui/help-popover";
import { MOCK_PRICE_DATA } from "@/lib/mock-data";
import { useApp } from "@/lib/app-context";

function calcRSI(data: { close: number }[], period = 14): number[] {
  const rsi: number[] = new Array(period).fill(50);
  for (let i = period; i < data.length; i++) {
    let gains = 0, losses = 0;
    for (let j = i - period + 1; j <= i; j++) {
      const diff = data[j].close - data[j - 1].close;
      if (diff > 0) gains += diff; else losses -= diff;
    }
    const rs = gains / (losses || 0.001);
    rsi.push(+(100 - 100 / (1 + rs)).toFixed(2));
  }
  return rsi;
}

function calcEMA(data: { close: number }[], period: number): number[] {
  const k = 2 / (period + 1);
  const ema: number[] = [];
  data.forEach((d, i) => {
    if (i === 0) { ema.push(d.close); return; }
    ema.push(+(d.close * k + ema[i - 1] * (1 - k)).toFixed(2));
  });
  return ema;
}

function IndicatorCard({ label, value, badge, badgeColor, children }: {
  label: string; value: string; badge?: string; badgeColor?: string; children?: React.ReactNode
}) {
  return (
    <div className="card-base p-4">
      <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">{label}</div>
      <div className="text-3xl font-bold tabular-nums text-text-primary">{value}</div>
      {badge && (
        <span className={cn("inline-flex mt-1 px-2 py-0.5 rounded-badge text-xs font-medium", badgeColor)}>
          {badge}
        </span>
      )}
      {children}
    </div>
  );
}

export default function TechnicalPage() {
  const { analysisData } = useApp();
  const data = MOCK_PRICE_DATA.slice(-60);

  const rsiData = useMemo(() => {
    const rsi = calcRSI(data);
    return data.map((d, i) => ({ date: d.date, rsi: rsi[i], close: d.close }));
  }, [data]);

  const ema20 = useMemo(() => calcEMA(data, 20), [data]);
  const ema50 = useMemo(() => calcEMA(data, 50), [data]);
  const lastClose = data[data.length - 1]?.close ?? 1698;
  const lastRSI = rsiData[rsiData.length - 1]?.rsi ?? 58;

  const macdData = useMemo(() => {
    const fast = calcEMA(data, 12);
    const slow = calcEMA(data, 26);
    return data.map((d, i) => ({
      date: d.date,
      macd: +(fast[i] - slow[i]).toFixed(2),
      signal: +(fast[i] - slow[i]).toFixed(2) * 0.9,
    }));
  }, [data]);

  const chartData = useMemo(() => data.map((d, i) => ({
    ...d, ema20: ema20[i], ema50: ema50[i],
  })), [data, ema20, ema50]);

  // SMC mock events
  const smcData = useMemo(() => {
    return data.map((d, i) => ({
      ...d,
      bos: i === 30 ? d.close : null,
      choch: i === 15 ? d.close : null,
      ob: (i >= 20 && i <= 22) ? d.close : null,
    }));
  }, [data]);

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-semibold text-text-primary">Technical Analysis</h1>

      {/* Main price chart */}
      <div className="card-base p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text-primary">Price + Overlays</h3>
            <HelpPopover content={{ title: "Price Chart with Overlays", body: "Full-width chart with EMA20 and EMA50 overlaid. EMA crossovers generate Golden Cross / Death Cross signals.", affectsVerdict: "EMAs determine trend direction for the Quant Agent.", source: "yfinance daily OHLCV" }} />
          </div>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                interval={9} tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={60}
                tickFormatter={(v) => `₹${v.toFixed(0)}`} domain={["auto","auto"]} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "hsl(var(--text-primary))" }}
              />
              <Area type="monotone" dataKey="close" fill="#FF6B00" fillOpacity={0.05} stroke="#FF6B00" strokeWidth={1.5} dot={false} name="Close" />
              <Line type="monotone" dataKey="ema20" stroke="#FF6B00" strokeWidth={1.5} dot={false} name="EMA20" />
              <Line type="monotone" dataKey="ema50" stroke="#1D4ED8" strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="EMA50" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3-column indicator grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Column 1: Momentum */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-widest">Momentum</h3>
          <IndicatorCard
            label="RSI (14)"
            value={lastRSI.toFixed(1)}
            badge={lastRSI > 70 ? "Overbought" : lastRSI < 30 ? "Oversold" : "Neutral"}
            badgeColor={lastRSI > 70 ? "bg-bearish-bg text-bearish-red" : lastRSI < 30 ? "bg-bullish-bg text-bullish-green" : "bg-neutral-bg text-neutral-blue"}
          >
            <div className="mt-3 h-16">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rsiData.slice(-30)}>
                  <Line type="monotone" dataKey="rsi" stroke={lastRSI > 70 ? "#DC2626" : lastRSI < 30 ? "#059669" : "#1D4ED8"} dot={false} strokeWidth={1.5} />
                  <ReferenceLine y={70} stroke="#DC2626" strokeDasharray="3 2" strokeWidth={1} />
                  <ReferenceLine y={30} stroke="#059669" strokeDasharray="3 2" strokeWidth={1} />
                  <XAxis hide /><YAxis domain={[0, 100]} hide />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </IndicatorCard>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">MACD</div>
            <div className="h-16">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={macdData.slice(-30)}>
                  <XAxis hide /><YAxis hide />
                  <Bar dataKey="macd" fill="#059669" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="text-xs text-bullish-green font-medium mt-1">Bullish crossover active</div>
          </div>

          <IndicatorCard label="Williams %R" value="-28"
            badge="Approaching Overbought" badgeColor="bg-warning-bg text-warning-amber">
            <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
              <div className="h-full bg-warning-amber rounded-pill" style={{ width: "72%" }} />
            </div>
          </IndicatorCard>
        </div>

        {/* Column 2: Trend */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-widest">Trend</h3>
          <IndicatorCard label="ADX" value="28.4"
            badge="Moderate Trend" badgeColor="bg-neutral-bg text-neutral-blue" />

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Supertrend</div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-bullish-green" />
              <span className="text-2xl font-bold text-bullish-green">BUY</span>
            </div>
            <div className="text-xs text-text-muted mt-1">Signal since 3 sessions ago</div>
          </div>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">SMA 50 / 200</div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-text-muted">SMA50</span>
                <span className="font-medium tabular-nums text-text-primary">₹{(lastClose * 0.965).toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-text-muted">SMA200</span>
                <span className="font-medium tabular-nums text-text-primary">₹{(lastClose * 0.92).toFixed(2)}</span>
              </div>
              <div className="mt-1 px-2 py-1 rounded-badge bg-bullish-bg text-bullish-green text-xs font-medium inline-block">
                Golden Cross Active
              </div>
            </div>
          </div>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Bollinger Bands</div>
            <div className="text-2xl font-bold text-text-primary">12.4%</div>
            <div className="text-xs text-text-muted">Band Width</div>
            <div className="text-xs text-text-secondary mt-1">Normal expansion — no squeeze</div>
          </div>
        </div>

        {/* Column 3: Volume */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-widest">Volume</h3>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">OBV Slope</div>
            <div className="flex items-center gap-2">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M4 14L10 6L16 10" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="text-2xl font-bold text-bullish-green">Rising</span>
            </div>
            <div className="text-xs text-text-muted mt-1">Accumulation trend confirmed</div>
          </div>

          <IndicatorCard label="MFI (14)" value="62.3"
            badge="Bullish Zone" badgeColor="bg-bullish-bg text-bullish-green">
            <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
              <div className="h-full rounded-pill" style={{ width: "62.3%", background: "#059669" }} />
            </div>
          </IndicatorCard>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Volume vs 20d Avg</div>
            <div className="text-3xl font-bold text-saffron tabular-nums">1.4x</div>
            <div className="text-xs text-text-muted mt-1">Above average on up days</div>
            <div className="mt-2 h-2 bg-surface-raised rounded-pill overflow-hidden">
              <div className="h-full bg-saffron rounded-pill" style={{ width: "70%" }} />
            </div>
          </div>

          <div className="card-base p-4">
            <div className="text-xs text-text-muted uppercase tracking-widest font-medium mb-2">Delivery %</div>
            <div className="text-3xl font-bold text-bullish-green tabular-nums">48.3%</div>
            <div className="text-xs text-bullish-green mt-1 font-medium">High conviction</div>
          </div>
        </div>
      </div>

      {/* SMC Analysis */}
      <div className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-base font-semibold text-text-primary">Smart Money Concepts (SMC)</h3>
          <HelpPopover content={{
            title: "Smart Money Concepts (SMC)",
            body: "SMC identifies institutional footprints: Break of Structure (BOS) confirms trend continuation, Change of Character (CHoCH) warns of reversal. Order Blocks are institutional entry zones.",
            affectsVerdict: "Active bullish BOS with valid order block support confirms the Quant Agent's bullish bias.",
            source: "SMC analysis engine — custom Python implementation on OHLCV",
          }} />
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={smcData.slice(-30)} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                interval={5} tickFormatter={(v) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} width={60}
                tickFormatter={(v) => `₹${v.toFixed(0)}`} domain={["auto","auto"]} />
              <Tooltip contentStyle={{ background: "hsl(var(--surface))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="close" fill="#FF6B00" fillOpacity={0.05} stroke="#FF6B00" strokeWidth={1.5} dot={false} />
              {/* Order block zone */}
              <Area type="monotone" dataKey="ob" fill="#059669" fillOpacity={0.2} stroke="none" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 flex flex-wrap gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm bg-bullish-green" />
            <span className="text-text-muted">Bullish Order Block (₹{(lastClose * 0.965).toFixed(0)}–₹{(lastClose * 0.971).toFixed(0)})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-0 h-0 border-l-4 border-r-4 border-b-8 border-l-transparent border-r-transparent border-b-bullish-green" />
            <span className="text-text-muted">BOS at ₹{(lastClose * 0.988).toFixed(0)}</span>
          </div>
        </div>
        <p className="text-xs text-text-secondary mt-3 p-3 bg-surface-raised rounded-btn">
          Most recent BOS detected at ₹{(lastClose * 0.988).toFixed(0)}. Current trend: <strong className="text-bullish-green">Bullish continuation</strong>. Order block at ₹{(lastClose * 0.965).toFixed(0)}–₹{(lastClose * 0.971).toFixed(0)} provides strong support zone.
        </p>
      </div>
    </div>
  );
}
