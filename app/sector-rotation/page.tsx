"use client";
import useSWR from "swr";
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts";
import { HelpPopover } from "@/components/ui/help-popover";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-client";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchSectorData() {
  const res = await fetch(`${BASE_URL}/macro/sector-rotation`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

interface SectorPoint {
  sector: string;
  momentum: number;
  relative_strength: number;
  flow: number;
  phase: string;
}

const PHASE_COLORS: Record<string, string> = {
  LEADING: "#059669",
  IMPROVING: "#65A30D",
  LAGGING: "#DC2626",
  WEAKENING: "#D97706",
};

export default function SectorRotationPage() {
  const { data, error, isLoading } = useSWR<SectorPoint[]>(
    "sector-rotation",
    fetchSectorData,
    { revalidateOnFocus: false, refreshInterval: 15 * 60 * 1000 }
  );

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <Skeleton className="h-7 w-44" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Sector Rotation</h1>
        <div className="card-base p-8 text-center">
          <p className="text-bearish-red font-medium mb-2">Failed to load sector data</p>
          <p className="text-sm text-text-muted">{getApiErrorMessage(error)}</p>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="space-y-6 max-w-screen-2xl mx-auto">
        <h1 className="text-xl font-semibold text-text-primary">Sector Rotation</h1>
        <div className="card-base p-8 text-center text-text-muted">
          <p className="text-sm">No sector rotation data available. Ensure the API backend exposes <code className="text-text-secondary">/macro/sector-rotation</code>.</p>
        </div>
      </div>
    );
  }

  const grouped = data.reduce<Record<string, SectorPoint[]>>((acc, d) => {
    (acc[d.phase] = acc[d.phase] ?? []).push(d);
    return acc;
  }, {});

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold text-text-primary">Sector Rotation</h1>
        <HelpPopover content={{
          title: "Sector Rotation — RRG Chart",
          body: "Relative Rotation Graph plots sector momentum vs relative strength. Leading quadrant = strongest sectors to invest in.",
          affectsVerdict: "When the selected stock's sector is in the Leading quadrant, bullish signals receive higher weighting.",
          source: "NSE sector indices — rolling 12-week momentum & relative strength vs Nifty50",
        }} />
      </div>

      {/* RRG Scatter */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">Relative Rotation Graph (RRG)</h3>
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,32%,91%)" opacity={0.4} />
              <XAxis
                dataKey="relative_strength"
                name="Relative Strength"
                tick={{ fontSize: 10, fill: "#94A3B8" }}
                tickLine={false}
                axisLine={false}
                label={{ value: "Relative Strength →", position: "insideBottomRight", offset: -5, fontSize: 10, fill: "#94A3B8" }}
              />
              <YAxis
                dataKey="momentum"
                name="Momentum"
                tick={{ fontSize: 10, fill: "#94A3B8" }}
                tickLine={false}
                axisLine={false}
                label={{ value: "↑ Momentum", angle: -90, position: "insideLeft", offset: 10, fontSize: 10, fill: "#94A3B8" }}
              />
              <ReferenceLine x={100} stroke="hsl(var(--border))" strokeWidth={1.5} />
              <ReferenceLine y={100} stroke="hsl(var(--border))" strokeWidth={1.5} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{
                  background: "hsl(var(--surface))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(_: unknown, name: string, props: { payload?: SectorPoint }) => {
                  if (name === "relative_strength") return [props.payload?.relative_strength.toFixed(1), "Rel. Strength"];
                  if (name === "momentum") return [props.payload?.momentum.toFixed(1), "Momentum"];
                  return [_, name];
                }}
                labelFormatter={(_: unknown, payload: { payload?: SectorPoint }[]) => payload?.[0]?.payload?.sector ?? ""}
              />
              {Object.entries(grouped).map(([phase, points]) => (
                <Scatter
                  key={phase}
                  name={phase}
                  data={points}
                  fill={PHASE_COLORS[phase] ?? "#94A3B8"}
                >
                  {points.map((p, i) => (
                    <Cell key={i} fill={PHASE_COLORS[phase] ?? "#94A3B8"} />
                  ))}
                </Scatter>
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        {/* Quadrant labels */}
        <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
          {[
            { phase: "LEADING", label: "Leading", desc: "High RS + Rising Momentum", bg: "bg-bullish-bg", color: "text-bullish-green" },
            { phase: "IMPROVING", label: "Improving", desc: "Low RS + Rising Momentum", bg: "bg-surface-raised", color: "text-text-secondary" },
            { phase: "WEAKENING", label: "Weakening", desc: "High RS + Falling Momentum", bg: "bg-warning-bg", color: "text-warning-amber" },
            { phase: "LAGGING", label: "Lagging", desc: "Low RS + Falling Momentum", bg: "bg-bearish-bg", color: "text-bearish-red" },
          ].map((q) => (
            <div key={q.phase} className={cn("p-3 rounded-btn", q.bg)}>
              <div className={cn("font-semibold mb-0.5", q.color)}>{q.label}</div>
              <div className="text-text-muted">{q.desc}</div>
              <div className={cn("mt-1 font-medium text-xs", q.color)}>
                {grouped[q.phase]?.map((s) => s.sector).join(", ") || "None"}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sector table */}
      <div className="card-base p-5">
        <h3 className="text-base font-semibold text-text-primary mb-4">All Sectors</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted">
                <th className="text-left py-2 font-medium">Sector</th>
                <th className="text-right py-2 font-medium">Momentum</th>
                <th className="text-right py-2 font-medium">Relative Strength</th>
                <th className="text-right py-2 font-medium">FII Flow</th>
                <th className="text-left py-2 font-medium pl-4">Phase</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {[...data].sort((a, b) => b.momentum - a.momentum).map((row) => (
                <tr key={row.sector} className="hover:bg-surface-raised transition-colors duration-150">
                  <td className="py-2.5 font-medium text-text-primary">{row.sector}</td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.momentum >= 100 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.momentum.toFixed(1)}
                  </td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.relative_strength >= 100 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.relative_strength.toFixed(1)}
                  </td>
                  <td className={cn("py-2.5 text-right tabular-nums", row.flow >= 0 ? "text-bullish-green" : "text-bearish-red")}>
                    {row.flow >= 0 ? "+" : ""}{row.flow.toFixed(0)}Cr
                  </td>
                  <td className="py-2.5 pl-4">
                    <span
                      className="px-2 py-0.5 rounded-badge text-xs font-semibold"
                      style={{
                        color: PHASE_COLORS[row.phase] ?? "#94A3B8",
                        background: `${PHASE_COLORS[row.phase] ?? "#94A3B8"}18`,
                      }}
                    >
                      {row.phase}
                    </span>
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
