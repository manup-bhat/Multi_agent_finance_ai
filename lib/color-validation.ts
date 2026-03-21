/**
 * Color contrast validation utilities
 * Ensures WCAG AA/AAA compliance for accessibility
 */

export interface ContrastRatio {
  ratio: number;
  wcagAA: boolean;
  wcagAAA: boolean;
  level: 'AAA' | 'AA' | 'FAIL';
}

/**
 * Calculate relative luminance of a color
 * https://www.w3.org/TR/WCAG20/#relativeluminancedef
 */
function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Parse hex color to RGB
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

/**
 * Calculate contrast ratio between two colors
 * https://www.w3.org/TR/WCAG20/#contrast-ratiodef
 */
export function getContrastRatio(color1: string, color2: string): ContrastRatio {
  const rgb1 = hexToRgb(color1);
  const rgb2 = hexToRgb(color2);

  if (!rgb1 || !rgb2) {
    return { ratio: 0, wcagAA: false, wcagAAA: false, level: 'FAIL' };
  }

  const l1 = getLuminance(rgb1.r, rgb1.g, rgb1.b);
  const l2 = getLuminance(rgb2.r, rgb2.g, rgb2.b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  const ratio = (lighter + 0.05) / (darker + 0.05);

  return {
    ratio: Number(ratio.toFixed(2)),
    wcagAA: ratio >= 4.5,
    wcagAAA: ratio >= 7,
    level: ratio >= 7 ? 'AAA' : ratio >= 4.5 ? 'AA' : 'FAIL',
  };
}

/**
 * Validate color scheme for contrast
 */
export interface ColorScheme {
  name: string;
  background: string;
  foreground: string;
  acceptable: boolean;
  contrast: ContrastRatio;
}

export function validateColorScheme(background: string, foreground: string, name = 'Custom'): ColorScheme {
  const contrast = getContrastRatio(background, foreground);
  return {
    name,
    background,
    foreground,
    acceptable: contrast.wcagAA,
    contrast,
  };
}

/**
 * Predefined color schemes with validated contrast
 */
export const VALIDATED_COLOR_SCHEMES = {
  // Light mode
  lightPrimary: validateColorScheme('#FFFFFF', '#0F172A', 'Light Primary'),
  lightSecondary: validateColorScheme('#F8FAFC', '#0F172A', 'Light Secondary'),
  lightTertiary: validateColorScheme('#F1F5F9', '#475569', 'Light Tertiary'),

  // Dark mode
  darkPrimary: validateColorScheme('#0F172A', '#F1F5F9', 'Dark Primary'),
  darkSecondary: validateColorScheme('#1E293B', '#F1F5F9', 'Dark Secondary'),
  darkTertiary: validateColorScheme('#334155', '#CBD5E1', 'Dark Tertiary'),

  // Semantic colors (validated)
  bullish: validateColorScheme('#ECFDF5', '#059669', 'Bullish'),
  bullishInvert: validateColorScheme('#059669', '#FFFFFF', 'Bullish Invert'),

  bearish: validateColorScheme('#FEF2F2', '#DC2626', 'Bearish'),
  bearishInvert: validateColorScheme('#DC2626', '#FFFFFF', 'Bearish Invert'),

  neutral: validateColorScheme('#EFF6FF', '#1D4ED8', 'Neutral'),
  neutralInvert: validateColorScheme('#1D4ED8', '#FFFFFF', 'Neutral Invert'),

  warning: validateColorScheme('#FFFBEB', '#D97706', 'Warning'),
  warningInvert: validateColorScheme('#D97706', '#FFFFFF', 'Warning Invert'),

  saffron: validateColorScheme('transparent', '#FF6B00', 'Saffron'),
  saffronLight: validateColorScheme('#FFF3E6', '#FF6B00', 'Saffron Light'),
  saffronInvert: validateColorScheme('#FF6B00', '#FFFFFF', 'Saffron Invert'),
};

/**
 * Get safe text color for background
 */
export function getSafeTextColor(backgroundColor: string): string {
  const whiteContrast = getContrastRatio(backgroundColor, '#FFFFFF');
  const blackContrast = getContrastRatio(backgroundColor, '#0F172A');

  // Use white if it has better contrast with the background
  if (whiteContrast.ratio > blackContrast.ratio) {
    return '#FFFFFF';
  }
  return '#0F172A';
}

/**
 * Validate entire color palette
 */
export function validatePalette(): { valid: boolean; issues: string[] } {
  const issues: string[] = [];

  Object.entries(VALIDATED_COLOR_SCHEMES).forEach(([key, scheme]) => {
    if (!scheme.acceptable) {
      issues.push(`${scheme.name} (${key}) has insufficient contrast: ${scheme.contrast.ratio}:1`);
    }
  });

  return {
    valid: issues.length === 0,
    issues,
  };
}
