// Chart system exports — all components use ApexCharts or lightweight-charts
// Dynamic import pattern: dynamic(() => import('@/components/charts/CandlestickChart'), { ssr: false })

// ── Lightweight Charts (canvas, always ssr:false) ──────────────────────────
export { CandlestickChart } from './CandlestickChart';
export type { CandlestickChartProps } from './CandlestickChart';

// ── ApexCharts components ──────────────────────────────────────────────────
export { FearGreedGauge } from './FearGreedGauge';

export { FiiDiiChart } from './FiiDiiChart';

export { RiskGauge } from './RiskGauge';
export type { RiskGaugeProps } from './RiskGauge';

export { SectorHeatmap } from './SectorHeatmap';

export { SentimentTimelineChart } from './SentimentTimeline';
export type { SentimentTimelineChartProps } from './SentimentTimeline';

export { SparklineBar } from './SparklineBar';

export { VixChart } from './VixChart';
export type { VixChartProps } from './VixChart';

export { ShapChart } from './ShapChart';
export type { ShapChartProps } from './ShapChart';

export { EquityCurveChart } from './EquityCurveChart';
export type { EquityCurveChartProps } from './EquityCurveChart';

export { AccuracyChart } from './AccuracyChart';
export type { AccuracyChartProps } from './AccuracyChart';

export { IvSmileChart } from './IvSmileChart';
export type { IvSmileChartProps } from './IvSmileChart';

export { PayoffChart } from './PayoffChart';
export type { PayoffChartProps } from './PayoffChart';

export { SectorRotationChart } from './SectorRotationChart';
export type { SectorRotationChartProps } from './SectorRotationChart';

export { SectorRSHeatmap } from './SectorRSHeatmap';
export type { SectorRSHeatmapProps } from './SectorRSHeatmap';

export { VolumeProfileChart } from './VolumeProfileChart';
export type { VolumeProfileChartProps } from './VolumeProfileChart';

export { MarketBreadthChart } from './MarketBreadthChart';
export type { MarketBreadthChartProps } from './MarketBreadthChart';

export { PcrHistoryChart } from './PcrHistoryChart';
export type { PcrHistoryChartProps } from './PcrHistoryChart';

export { FanChart } from './FanChart';
export type { FanChartProps } from './FanChart';

// ── New sentiment & ML charts ──────────────────────────────────────────────
export { CompositeSentimentBar } from './CompositeSentimentBar';
export type { CompositeSentimentBarProps } from './CompositeSentimentBar';

export { SentimentPieChart } from './SentimentPieChart';
export type { SentimentPieChartProps } from './SentimentPieChart';

export { ErrorHistogram } from './ErrorHistogram';
export type { ErrorHistogramProps } from './ErrorHistogram';

export { MacroAreaChart } from './MacroAreaChart';
export type { MacroAreaChartProps } from './MacroAreaChart';

export { PivotTable } from './PivotTable';
export type { PivotTableProps } from './PivotTable';

// ── Loading skeleton ───────────────────────────────────────────────────────
export { ChartSkeleton } from './chart-skeleton';
