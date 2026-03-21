// Chart system exports — all components use ApexCharts or lightweight-charts
// Import via dynamic() for SSR safety: dynamic(() => import('@/components/charts/...'), { ssr: false })

// ApexCharts components (react-apexcharts)
export { FearGreedGauge } from './fear-greed-gauge';
export type { FearGreedGaugeProps } from './fear-greed-gauge';

export { FiiDiiChart } from './fii-dii-chart';
export type { FiiDiiChartProps } from './fii-dii-chart';

export { RiskGauge } from './risk-gauge';

export { SectorHeatmap } from './sector-heatmap';

export { SentimentTimelineChart } from './sentiment-timeline';
export type { SentimentTimelineChartProps } from './sentiment-timeline';

export { VixChart } from './VixChart';
export type { VixChartProps } from './VixChart';

export { SparklineBar } from './sparkline-bar';

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

// Lightweight-charts component (canvas, always ssr:false)
export { CandlestickChart } from './CandlestickChart';
export type { CandlestickChartProps } from './CandlestickChart';

// Skeleton for loading states
export { ChartSkeleton } from './chart-skeleton';

// New Chart 14-16, 19, Pivot Table
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
