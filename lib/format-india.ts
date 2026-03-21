/**
 * Indian financial formatting utilities
 * All values use Indian numbering system: Crore (Cr), Lakh (L), Thousand (K)
 */

/**
 * Format number as Crore (1 Crore = 10 Million = 1,00,00,000)
 * Returns: "₹3,200 Cr" or "₹-1,800 Cr"
 */
export function formatCrore(value: number, decimals = 0): string {
  if (!isFinite(value)) return '₹0 Cr';
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: decimals })} Cr`;
}

/**
 * Format number as Lakh (1 Lakh = 100,000)
 * Returns: "₹45.3 L" or "₹-12.5 L"
 */
export function formatLakh(value: number, decimals = 1): string {
  if (!isFinite(value)) return '₹0 L';
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);
  const inLakh = abs / 100000;
  return `${sign}₹${inLakh.toLocaleString('en-IN', { maximumFractionDigits: decimals })} L`;
}

/**
 * Auto-format number based on magnitude
 * Returns appropriate unit: Cr, L, K, or plain number
 */
export function formatINR(value: number, decimals = 1): string {
  if (!isFinite(value)) return '₹0';
  
  const sign = value < 0 ? '-' : '';
  const abs = Math.abs(value);

  // Format as Crore if >= 10 Lakh (1,000,000)
  if (abs >= 10000000) {
    const inCr = abs / 10000000;
    return `${sign}₹${inCr.toLocaleString('en-IN', { maximumFractionDigits: decimals })} Cr`;
  }

  // Format as Lakh if >= 1 Lakh (100,000)
  if (abs >= 100000) {
    const inLakh = abs / 100000;
    return `${sign}₹${inLakh.toLocaleString('en-IN', { maximumFractionDigits: decimals })} L`;
  }

  // Format as Thousand if >= 1000
  if (abs >= 1000) {
    const inK = abs / 1000;
    return `${sign}₹${inK.toLocaleString('en-IN', { maximumFractionDigits: decimals })} K`;
  }

  // Plain format for values < 1000
  return `${sign}₹${abs.toLocaleString('en-IN', { maximumFractionDigits: decimals })}`;
}

/**
 * Format percentage with sign
 * Returns: "+2.34%" or "-1.23%"
 */
export function formatPct(value: number, decimals = 2): string {
  if (!isFinite(value)) return '0%';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format percentage change with color indicator
 */
export function formatPctChange(value: number, decimals = 2): { text: string; color: string } {
  const text = formatPct(value, decimals);
  const color = value > 0 ? '#059669' : value < 0 ? '#DC2626' : '#94A3B8';
  return { text, color };
}

/**
 * Format volume in Indian system
 */
export function formatVolume(value: number): string {
  if (!isFinite(value)) return '0';
  if (value >= 10000000) {
    return `${(value / 10000000).toFixed(1)}Cr`;
  }
  if (value >= 100000) {
    return `${(value / 100000).toFixed(1)}L`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return Math.floor(value).toString();
}

/**
 * Format price with proper Indian currency formatting
 */
export function formatPrice(value: number, decimals = 2): string {
  if (!isFinite(value)) return '₹0';
  return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
}

/**
 * Parse formatted Crore string back to number
 * "₹3,200 Cr" → 320000000
 */
export function parseCrore(formatted: string): number {
  const match = formatted.match(/[\d,.]+/);
  if (!match) return 0;
  return parseFloat(match[0].replace(/,/g, '')) * 10000000;
}

/**
 * Parse formatted Lakh string back to number
 * "₹45.3 L" → 4530000
 */
export function parseLakh(formatted: string): number {
  const match = formatted.match(/[\d,.]+/);
  if (!match) return 0;
  return parseFloat(match[0].replace(/,/g, '')) * 100000;
}
