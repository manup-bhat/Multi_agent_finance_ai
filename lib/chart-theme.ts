'use client';

import { useTheme } from 'next-themes';
import { useMemo } from 'react';

export const CHART_COLORS = {
  saffron: '#FF6B00',
  bullish: '#059669',
  bearish: '#DC2626',
  neutral: '#1D4ED8',
  warning: '#D97706',
  bullishBg: '#ECFDF5',
  bearishBg: '#FEF2F2',
  neutralBg: '#EFF6FF',
  warningBg: '#FFFBEB',
};

export const CHART_THEME_LIGHT = {
  bg: 'transparent',
  text: '#475569',
  grid: '#E2E8F0',
  tooltipBg: '#FFFFFF',
  border: '#CBD5E1',
};

export const CHART_THEME_DARK = {
  bg: 'transparent',
  text: '#94A3B8',
  grid: '#1E293B',
  tooltipBg: '#111827',
  border: '#334155',
};

export interface ChartTheme {
  bg: string;
  text: string;
  grid: string;
  tooltipBg: string;
  border: string;
}

export function useChartTheme(): ChartTheme {
  const { theme, systemTheme } = useTheme();
  const isDark = useMemo(() => {
    const currentTheme = theme === 'system' ? systemTheme : theme;
    return currentTheme === 'dark';
  }, [theme, systemTheme]);

  return useMemo(
    () => (isDark ? CHART_THEME_DARK : CHART_THEME_LIGHT),
    [isDark]
  );
}

/**
 * Get contrasting text color for a given background
 * Ensures WCAG AA contrast compliance
 */
export function getContrastText(bgColor: string): string {
  // Simple luminance calculation
  const hex = bgColor.replace('#', '');
  const r = parseInt(hex.substr(0, 2), 16);
  const g = parseInt(hex.substr(2, 2), 16);
  const b = parseInt(hex.substr(4, 2), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? '#000000' : '#FFFFFF';
}

/**
 * Get WCAG compliant text color based on theme and context
 */
export function getThemeText(isDark: boolean, priority: 'primary' | 'secondary' | 'muted' = 'primary'): string {
  if (isDark) {
    switch (priority) {
      case 'primary': return '#F1F5F9'; // Near white
      case 'secondary': return '#CBD5E1'; // Lighter gray
      case 'muted': return '#94A3B8'; // Muted
    }
  } else {
    switch (priority) {
      case 'primary': return '#0F172A'; // Near black
      case 'secondary': return '#475569'; // Darker gray
      case 'muted': return '#94A3B8'; // Muted
    }
  }
}

/**
 * Get background color with proper contrast
 */
export function getThemeBg(isDark: boolean, priority: 'primary' | 'secondary' | 'tertiary' = 'primary'): string {
  if (isDark) {
    switch (priority) {
      case 'primary': return '#0F172A'; // Very dark blue
      case 'secondary': return '#1E293B'; // Dark blue
      case 'tertiary': return '#334155'; // Slightly lighter
    }
  } else {
    switch (priority) {
      case 'primary': return '#FFFFFF'; // White
      case 'secondary': return '#F8FAFC'; // Very light
      case 'tertiary': return '#F1F5F9'; // Light gray
    }
  }
}
