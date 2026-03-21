// Chart system exports — all components use ApexCharts or lightweight-charts
// Import via dynamic() for SSR safety: dynamic(() => import('@/components/charts/...'), { ssr: false })

// ApexCharts components (react-apexcharts)
export { FearGreedGauge } from './fear-greed-gauge';
export type { FearGreedGaugeProps } from './fear-greed-gauge';

export { FiiDiiChart } from './fii-dii-chart';
export type { FiiDiiChartProps, FiiDiiData } from './fii-dii-chart';

export { RiskGauge } from './risk-gauge';

export { SectorHeatmap } from './sector-heatmap';

export { SentimentTimelineChart } from './sentiment-timeline';
export type { SentimentTimelineChartProps } from './sentiment-timeline';

export { VixChart } from './vix-chart';
export type { VixChartProps } from './vix-chart';

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
export type { SectorRotationChartProps, SectorRotationDataPoint } from './SectorRotationChart';

// Lightweight-charts component (canvas, always ssr:false)
export { CandlestickChart } from './CandlestickChart';
export type { CandlestickChartProps } from './CandlestickChart';

// Skeleton for loading states
export { ChartSkeleton } from './chart-skeleton';
