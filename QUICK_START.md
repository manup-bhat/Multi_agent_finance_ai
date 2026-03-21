# 🚀 Quick Start Guide

## Installation

All dependencies have been added to `package.json`. Install them:

```bash
npm install
# or
pnpm install
# or
yarn install
```

## Verify Implementation

### 1. Run the Dashboard Demo

```bash
npm run dev
```

Navigate to: `http://localhost:3000/dashboard-demo`

You should see:
- All 7 chart components
- KPI cards with sparklines
- Color reference section
- Typography showcase

### 2. Test Dark Mode

Click the theme toggle in the top-right to switch between light and dark modes. All charts should update colors automatically.

### 3. Validate Colors

```bash
npx ts-node scripts/validate-colors.ts
```

This will output a full WCAG compliance report showing all color contrasts.

## Using Charts in Your Pages

### Basic Usage

```tsx
'use client';

import { FearGreedGauge, VixChart, FiiDiiChart } from '@/components/charts';

export default function AnalysisPage() {
  const mockFiiData = [
    { date: '2024-03-01', fiiNetCrore: 2500, diiNetCrore: 1200 },
    { date: '2024-03-02', fiiNetCrore: -1800, diiNetCrore: 900 },
  ];

  const mockVixData = [
    { date: '2024-03-01', value: 18.5 },
    { date: '2024-03-02', value: 20.2 },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Fear & Greed Gauge */}
      <div className="bg-surface rounded-lg p-6 border border-border">
        <FearGreedGauge value={65} label="Market Sentiment" />
      </div>

      {/* VIX Chart */}
      <div className="bg-surface rounded-lg p-6 border border-border">
        <VixChart data={mockVixData} variant="full" height={300} />
      </div>

      {/* FII/DII Chart */}
      <div className="bg-surface rounded-lg p-6 border border-border">
        <FiiDiiChart data={mockFiiData} height={300} />
      </div>
    </div>
  );
}
```

## Accessing Theme & Colors

### Get Chart Theme Colors

```tsx
import { useChartTheme, CHART_COLORS } from '@/lib/chart-theme';

export function MyComponent() {
  const chartTheme = useChartTheme();
  // Returns: { bg, text, grid, tooltipBg, border }

  return (
    <div style={{ color: chartTheme.text, backgroundColor: chartTheme.bg }}>
      {/* Content */}
    </div>
  );
}
```

### Format Indian Numbers

```tsx
import { formatCrore, formatINR, formatPct } from '@/lib/format-india';

// In your component
const amount = formatCrore(52000000); // "₹5,200 Cr"
const value = formatINR(45000000); // "₹4.5 L"
const change = formatPct(2.34); // "+2.34%"
```

### Use Semantic Colors

```tsx
import { CHART_COLORS } from '@/lib/chart-theme';

<div style={{ color: CHART_COLORS.bullish }}>
  {/* Green text */}
</div>

<div style={{ color: CHART_COLORS.bearish }}>
  {/* Red text */}
</div>
```

## Component Reference

### 1. FearGreedGauge
**Purpose**: Market sentiment gauge (0-100)

```tsx
<FearGreedGauge 
  value={65}              // 0-100
  label="Market Sentiment" // Optional
  height={250}            // Optional, default 250
/>
```

**Output**: 270° radial gauge with 5 sentiment zones

---

### 2. VixChart
**Purpose**: VIX index visualization

```tsx
<VixChart 
  data={[
    { date: '2024-03-01', value: 18.5 },
    // ... more data
  ]}
  variant="full"  // "sparkline" or "full"
  height={250}    // Optional
/>
```

**Output**: Area chart with regime-based coloring

---

### 3. FiiDiiChart
**Purpose**: FII/DII flow analysis

```tsx
<FiiDiiChart 
  data={[
    { date: '2024-03-01', fiiNetCrore: 2500, diiNetCrore: 1200 },
    // ... more data
  ]}
  height={300}  // Optional
/>
```

**Output**: Grouped bar chart + KPI cards

---

### 4. RiskGauge
**Purpose**: Risk level assessment

```tsx
<RiskGauge 
  riskLevel="MODERATE"  // "LOW" | "MODERATE" | "HIGH" | "EXTREME"
  riskScore={55}        // 0-100
  positionSize={1.2}    // Optional multiplier
  height={250}          // Optional
/>
```

**Output**: 270° risk gauge with guidelines

---

### 5. SectorHeatmap
**Purpose**: Sector relative strength

```tsx
<SectorHeatmap 
  data={[
    { sector: 'IT', marketCap: 450000, rs5d: 2.5 },
    // ... more sectors
  ]}
  height={400}
  onSectorClick={(sector) => console.log(sector)}
/>
```

**Output**: Treemap with market-cap sizing and RS coloring

---

### 6. SentimentTimelineChart
**Purpose**: Multi-source sentiment analysis

```tsx
<SentimentTimelineChart 
  data={[
    { 
      date: '2024-03-01',
      composite: 0.25,
      institutional: 0.3,
      socialFg: 0.2,
      gdelt: 0.15
    },
    // ... more data (-1 to +1 range)
  ]}
  height={300}
/>
```

**Output**: Multi-line area chart with 4 sources

---

### 7. SparklineBar
**Purpose**: Mini bar chart for KPI cards

```tsx
<SparklineBar 
  data={[10, -5, 8, 15, -3]}  // Positive/negative values
  height={40}                  // Optional
/>
```

**Output**: Compact bar chart with per-value coloring

---

## Color Validation

### Check Contrast Ratio

```tsx
import { getContrastRatio } from '@/lib/color-validation';

const contrast = getContrastRatio('#FFFFFF', '#0F172A');
// Returns: { ratio: 17, wcagAA: true, wcagAAA: true, level: 'AAA' }
```

### Get Safe Text Color

```tsx
import { getSafeTextColor } from '@/lib/color-validation';

const textColor = getSafeTextColor('#FF6B00');
// Returns: '#FFFFFF' (white for better contrast)
```

### Validate Entire Palette

```tsx
import { validatePalette } from '@/lib/color-validation';

const validation = validatePalette();
if (!validation.valid) {
  console.log('Issues:', validation.issues);
}
```

## Styling Best Practices

### ✅ DO

```tsx
// Use design tokens
<div className="bg-surface text-text-primary">
  Content
</div>

// Use semantic colors
<div style={{ color: CHART_COLORS.bullish }}>
  Good news
</div>

// Use theme hook
const chartTheme = useChartTheme();
```

### ❌ DON'T

```tsx
// Never hardcode colors
<div style={{ color: '#059669' }}>
  This might fail in dark mode
</div>

// Never use random colors
<div className="text-red-500">
  Unvalidated contrast
</div>

// Don't ignore theme context
const isDark = true; // Wrong! Use useTheme()
```

## Tailwind Color Classes

**Available Semantic Classes:**
- `text-bullish-green` / `bg-bullish-bg`
- `text-bearish-red` / `bg-bearish-bg`
- `text-neutral-blue` / `bg-neutral-bg`
- `text-warning-amber` / `bg-warning-bg`
- `text-saffron` / `bg-saffron-light`

**Chart Text Classes:**
- `text-chart-primary` - High contrast primary
- `text-chart-secondary` - Readable secondary
- `text-chart-muted` - Low emphasis text

## File Organization

| File | Purpose | Usage |
|------|---------|-------|
| `lib/chart-theme.ts` | Theme management | Import `useChartTheme()` hook |
| `lib/format-india.ts` | Number formatting | Import format functions |
| `lib/color-validation.ts` | Contrast validation | Import validation functions |
| `components/charts/*` | Chart components | Import chart components |
| `app/globals.css` | Design tokens | Automatic via Tailwind |
| `CHART_SYSTEM.md` | Full documentation | Reference guide |
| `IMPLEMENTATION_SUMMARY.md` | Overview | High-level summary |

## Troubleshooting

### Charts Not Rendering?
1. Ensure you're using `'use client'` directive
2. Check that dynamic imports have `ssr: false`
3. Verify data is in correct format
4. Check browser console for errors

### Dark Mode Not Working?
1. Verify `next-themes` is in providers
2. Check `useTheme()` hook is called
3. Ensure components are wrapped in `<ThemeProvider>`
4. Test with `localStorage.getItem('theme')`

### Colors Look Wrong?
1. Run `validate-colors.ts` to check contrast
2. Verify you're using token colors, not hardcoded
3. Check that dark/light mode is switching
4. Use DevTools to inspect computed styles

### Numbers Not Formatted?
1. Import from `lib/format-india.ts`
2. Ensure input is a number, not string
3. Check return format matches expectation
4. Test with `console.log(formatCrore(value))`

## Next Steps

1. **Connect Backend**: Integrate with FastAPI endpoints
2. **Add More Charts**: Implement CandlestickChart, PayoffChart, etc.
3. **Create Pages**: Build dashboard, analysis, and reports pages
4. **Add Real Data**: Connect to market data APIs
5. **Optimize**: Implement caching and lazy loading

## Resources

- **Documentation**: `CHART_SYSTEM.md`
- **Examples**: `app/dashboard-demo/page.tsx`
- **Reference**: `components/color-reference.tsx`
- **Validation**: `scripts/validate-colors.ts`

## Support

For detailed information:
- Component specs → `CHART_SYSTEM.md`
- Implementation details → `IMPLEMENTATION_SUMMARY.md`
- Code examples → `app/dashboard-demo/page.tsx`
- Color reference → `components/color-reference.tsx`

---

**Ready to build! 🚀**

Start with the dashboard demo to see everything in action, then explore individual charts.
