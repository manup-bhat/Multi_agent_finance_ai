'use client';

import { Skeleton } from '@/components/ui/skeleton';

export interface ChartSkeletonProps {
  height?: number;
  variant?: 'default' | 'candlestick' | 'bar' | 'gauge';
}

export function ChartSkeleton({ height = 300, variant = 'default' }: ChartSkeletonProps) {
  return (
    <div 
      className="w-full bg-gradient-to-r from-surface-raised via-border to-surface-raised bg-[length:200%_100%] animate-shimmer rounded-lg"
      style={{ height: `${height}px` }}
      role="status"
      aria-label="Loading chart"
    />
  );
}

/**
 * Error state component for failed chart loads
 */
export interface ChartErrorProps {
  title: string;
  message?: string;
  onRetry?: () => void;
}

export function ChartError({ title, message, onRetry }: ChartErrorProps) {
  return (
    <div className="w-full p-6 rounded-lg border-2 border-bearish-red bg-bearish-bg flex flex-col items-center justify-center gap-4 min-h-[200px]">
      <div className="text-center">
        <h3 className="font-semibold text-bearish-red text-lg">{title}</h3>
        {message && <p className="text-text-secondary text-sm mt-1">{message}</p>}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 rounded-md bg-bearish-red text-white hover:bg-red-700 transition-colors text-sm font-medium"
          aria-label="Retry loading chart"
        >
          Retry
        </button>
      )}
    </div>
  );
}
