# Finance AI Dashboard - Technical Specifications

## Document Version: 1.0
**Created**: March 2026  
**Status**: ✅ COMPLETE

---

## 1. System Architecture

### 1.1 High-Level Flow
```
User Interface (Next.js)
    ↓
Chart Components (ApexCharts)
    ↓
Data Layer (Fetch API)
    ↓
Backend API (Python/Node.js)
    ↓
Market Data Feeds (NSE)
    ↓
Database / Cache (Redis/PostgreSQL)
```

### 1.2 Component Stack
- **Framework**: Next.js 16+ (App Router)
- **Charts**: ApexCharts 4.x + react-apexcharts
- **Styling**: Tailwind CSS 3.4+
- **State**: React 19+ hooks (useState, useEffect)
- **Theme**: next-themes + custom chart-theme.ts
- **Data Format**: JSON

---

## 2. Chart Specifications

### 2.1 IvSmileChart

**Purpose**: Visualize Implied Volatility across option strike prices

**Data Structure**:
```typescript
{
  strikes: number[];           // 11 points: ATM ± 2500
  currentIV: number[];         // Current IV at each strike (%)
  avgIV30d: number[];          // 30-day moving average IV (%)
  atmStrike: number;           // Current At-The-Money strike
}
```

**Chart Type**: Line with area fill

**Series**:
- Current IV (solid line, saffron color, opacity 1)
- Avg IV 30d (dashed line, slate-400, opacity 0.8)

**Annotations**:
- Vertical line at ATM strike (saffron)

**Metrics Display**:
- Min IV, Max IV, ATM IV, 30d Avg

**Example Data**:
```json
{
  "strikes": [20500, 21000, 21500, 22000, 22500, 23000, 23500, 24000, 24500, 25000, 25500],
  "currentIV": [20.5, 19.8, 19.2, 18.5, 18.0, 17.8, 17.9, 18.2, 18.8, 19.5, 20.3],
  "avgIV30d": [18.5, 18.2, 17.8, 17.5, 17.3, 17.0, 17.1, 17.4, 17.8, 18.2, 18.6],
  "atmStrike": 23000
}
```

**Update Frequency**: Real-time (1-minute)

---

### 2.2 PayoffChart

**Purpose**: Visualize options strategy profit/loss at different price levels

**Data Structure**:
```typescript
{
  prices: number[];            // 41-element array of underlying prices
  callPayoff: number[];        // Call P&L at each price
  putPayoff: number[];         // Put P&L at each price
  strategyPayoff: number[];    // Combined strategy P&L
  currentPrice: number;        // Current underlying price
  strikeCall: number;          // Call strike price
  strikePut: number;           // Put strike price
}
```

**Chart Type**: Area stacked

**Series**:
- Call Payoff (line 1.5px, neutral color)
- Put Payoff (line 1.5px, warning color)
- Strategy Total (line 2.5px, saffron - filled)

**Metrics Display**:
- Max Profit
- Max Loss
- Breakeven Level
- Current Price

**Annotations**:
- Zero line (horizontal grid reference)
- Current price indicator

**Example Data**:
```json
{
  "prices": [22500, 22600, 22700, ..., 24500],
  "callPayoff": [-150, -140, -130, ..., 1850],
  "putPayoff": [-100, -95, -90, ..., -100],
  "strategyPayoff": [-250, -235, -220, ..., 1750],
  "currentPrice": 23500,
  "strikeCall": 23500,
  "strikePut": 23200
}
```

**Update Frequency**: On demand (when strategy changes)

---

### 2.3 ShapChart

**Purpose**: Display ML model feature importance using SHAP values

**Data Structure**:
```typescript
{
  features: string[];          // 8 feature names
  importance: number[];        // SHAP value for each feature (-0.5 to +0.5)
}
```

**Chart Type**: Horizontal bar

**Features** (in order):
1. RSI(14) - Momentum oscillator
2. EMA 20/50 Ratio - Trend strength
3. MACD Histogram - Momentum divergence
4. Volume Momentum - Volume acceleration
5. VIX Level - Market volatility
6. FII Flow - Foreign investor participation
7. PCR Ratio - Put-Call balance
8. ATR % - Volatility measure

**Color Coding**:
- Positive (green): Pushes prediction higher (bullish)
- Negative (red): Pushes prediction lower (bearish)

**Data Labels**: Show percentage impact

**Example Data**:
```json
{
  "features": ["RSI(14)", "EMA_20/50", "MACD", "Volume", "VIX", "FII", "PCR", "ATR"],
  "importance": [0.28, 0.22, 0.15, 0.12, 0.10, -0.08, 0.07, 0.06]
}
```

**Update Frequency**: Once per trading session (on model retrain)

---

### 2.4 SectorRotationChart

**Purpose**: Identify sector rotation opportunities using relative strength and momentum

**Data Structure**:
```typescript
{
  sector: string[];            // 10 sector names
  rs: number[];                // Relative Strength (-5 to +5)
  rsMomentum: number[];        // RS Momentum (-5 to +5)
  volumeRatio?: number[];      // Volume ratio (bubble size)
}
```

**Chart Type**: Scatter (2D)

**X-Axis**: Relative Strength (-5 to +5)
- Negative: Underperforming vs Nifty 50
- Positive: Outperforming vs Nifty 50

**Y-Axis**: RS Momentum (-5 to +5)
- Negative: Momentum deteriorating
- Positive: Momentum improving

**Quadrants & Strategy**:

| Quadrant | Label | RS | Momentum | Action |
|----------|-------|----|-----------|----|
| Top Right | LEADING | High | Rising | BUY - Strongest momentum |
| Top Left | WEAKENING | Low | Rising | HOLD - Watch for reversal |
| Bottom Right | IMPROVING | Low | Rising | ACCUMULATE - Recovery play |
| Bottom Left | LAGGING | Low | Falling | AVOID - Downtrend likely |

**Color Coding**:
- Leading: Bullish green
- Improving: Neutral blue
- Weakening: Warning orange
- Lagging: Bearish red

**Example Data**:
```json
{
  "sector": ["IT", "Finance", "Pharma", "Energy", "Utilities", "Realty", "Consumer", "Industrial", "Metals", "Auto"],
  "rs": [2.5, -1.2, 0.8, -3.1, 1.5, -0.5, 2.1, -2.3, 3.2, -1.8],
  "rsMomentum": [1.8, -0.9, 2.3, -1.5, 0.5, 1.2, 2.8, -2.1, 1.9, -0.7]
}
```

**Update Frequency**: Daily (after market close)

---

### 2.5 EquityCurveChart

**Purpose**: Track strategy performance vs benchmark over time

**Data Structure**:
```typescript
{
  dates: string[];             // ISO 8601 dates
  strategy: number[];          // Strategy cumulative return (%)
  benchmark?: number[];        // Benchmark return (Nifty TRI) (%)
  drawdown?: number[];         // Drawdown from peak (%)
  foldBoundaries?: string[];   // Cross-validation fold splits
}
```

**Chart Type**: 
- Top: Area chart (strategy vs benchmark)
- Bottom: Area chart (drawdown, inverted)

**Features**:
- Synchronized zoom across both charts
- Fold boundaries annotated as vertical lines
- Max drawdown labeled on lower chart

**Example Data**:
```json
{
  "dates": ["2024-01-01", "2024-01-02", ...],
  "strategy": [0, 0.5, 1.2, 0.8, 2.1, ...],
  "benchmark": [0, 0.3, 0.8, 0.5, 1.5, ...],
  "drawdown": [0, 0, 0, -0.4, 0, ...],
  "foldBoundaries": ["2024-03-15", "2024-06-15"]
}
```

**Update Frequency**: Daily (after backtest completion)

---

### 2.6 AccuracyChart

**Purpose**: Monitor model directional accuracy over time

**Data Structure**:
```typescript
{
  dates: string[];             // ISO 8601 dates
  accuracy: number[];          // Directional accuracy (40-85%)
  regimes?: Array<{            // Market regime periods
    start: string;
    end: string;
    type: 'bull' | 'bear' | 'sideways';
  }>;
}
```

**Chart Type**: Area

**Features**:
- Y-axis range: 40% to 85%
- Threshold line at 55% (minimum acceptable)
- Regime backgrounds: green (bull), red (bear), orange (sideways)
- Displays average accuracy on top-right

**Example Data**:
```json
{
  "dates": ["2024-01-01", "2024-01-02", ...],
  "accuracy": [56.2, 58.5, 54.1, 59.8, 57.3, ...],
  "regimes": [
    { "start": "2024-01-01", "end": "2024-03-15", "type": "bull" },
    { "start": "2024-03-15", "end": "2024-06-01", "type": "sideways" }
  ]
}
```

**Update Frequency**: Daily (model evaluation)

---

## 3. API Contracts

### 3.1 F&O Analysis Endpoint

**Method**: POST  
**Path**: `/fno/analyze`

**Request**:
```json
{
  "symbol": "NIFTY"
}
```

**Response**:
```json
{
  "symbol": "NIFTY",
  "timestamp": "2024-03-21T10:30:00Z",
  "data": {
    "ivSmile": {
      "strikes": [...],
      "currentIV": [...],
      "avgIV30d": [...],
      "atmStrike": 23000
    },
    "payoff": {
      "prices": [...],
      "callPayoff": [...],
      "putPayoff": [...],
      "strategyPayoff": [...],
      "currentPrice": 23500,
      "maxProfit": 1250,
      "maxLoss": -350
    },
    "greeks": {
      "delta": 0.45,
      "gamma": 0.012,
      "vega": 45.2,
      "theta": -12.5,
      "rho": 0.05
    },
    "openInterest": {
      "callOI": 1250000,
      "putOI": 980000,
      "totalOI": 2230000
    }
  }
}
```

**Status Codes**:
- 200 OK: Analysis successful
- 400 Bad Request: Invalid symbol
- 429 Too Many Requests: Rate limited
- 500 Server Error: Backend failure

---

### 3.2 Sentiment Analysis Endpoint

**Method**: POST  
**Path**: `/sentiment/analyze`

**Request**:
```json
{
  "symbol": "NIFTY"
}
```

**Response**:
```json
{
  "fiiDii": {
    "fiiFlow": 2450,
    "diiFlow": -1200,
    "netFlow": 1250,
    "fiiCumulative": 85000
  },
  "pcrRatio": 0.95,
  "marketBreadth": {
    "advancers": 1850,
    "decliners": 1150,
    "breadthLine": 0.618
  },
  "vixLevel": 18.5,
  "sentiment": "bullish"
}
```

---

### 3.3 Model Prediction Endpoint

**Method**: POST  
**Path**: `/model/predict`

**Request**:
```json
{
  "symbol": "NIFTY"
}
```

**Response**:
```json
{
  "prediction": 0.72,
  "confidence": 68,
  "accuracy": 58.5,
  "shap": [
    { "feature": "RSI(14)", "value": 0.28 },
    { "feature": "EMA_20/50", "value": 0.22 },
    ...
  ]
}
```

---

## 4. Error Handling

All charts implement consistent error handling:

```typescript
if (loading) return <ChartSkeleton />;

if (error) return (
  <div className="border border-bearish-red/40 p-6">
    <p className="text-bearish-red">Failed to load chart</p>
    <p className="text-text-muted text-xs">{error}</p>
  </div>
);

if (!data) return <EmptyState />;
```

**Common Errors**:
- Network timeout: "Request timeout - check API server"
- Invalid response: "Unexpected data format"
- CORS failure: "Access denied - check API configuration"
- Rate limit: "Too many requests - please wait"

---

## 5. Performance Metrics

### Target Metrics
- Chart render time: < 500ms
- Data fetch time: < 2 seconds
- Memory per chart: < 5MB
- CPU usage (idle): < 1%

### Optimization Techniques
1. Dynamic imports with SSR disabled
2. Memoization via React hooks
3. Efficient data structures
4. Lazy loading of chart libraries
5. Canvas-based rendering (ApexCharts)

---

## 6. Browser Compatibility

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 90+ | ✅ Full support |
| Firefox | 88+ | ✅ Full support |
| Safari | 14+ | ✅ Full support |
| Edge | 90+ | ✅ Full support |
| Mobile Safari | 14+ | ✅ Full support |
| Chrome Mobile | 90+ | ✅ Full support |

---

## 7. Accessibility (WCAG 2.1 AA)

- [x] Semantic HTML structure
- [x] ARIA labels for interactive elements
- [x] Sufficient color contrast (4.5:1 minimum)
- [x] Keyboard navigation support
- [x] Screen reader compatible
- [x] No flashing content (< 3 per second)

---

## 8. Security Considerations

- [x] CORS headers configured
- [x] Input validation on API calls
- [x] XSS protection via React's built-in escaping
- [x] CSRF tokens for state-changing operations
- [x] Rate limiting (server-side)
- [x] No sensitive data in localStorage

---

## 9. Deployment Checklist

```bash
# 1. Build optimization
npm run build

# 2. Test in production mode
npm run start

# 3. Environment variables
NEXT_PUBLIC_API_URL=https://api.example.com

# 4. Cache headers
Cache-Control: public, max-age=3600

# 5. Monitor
- Track chart load times
- Monitor API error rates
- Alert on high latency (>5s)
```

---

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Mar 2026 | Initial implementation |
| - | - | IV Smile chart |
| - | - | Payoff diagram chart |
| - | - | SHAP importance chart |
| - | - | Sector rotation chart |
| - | - | Equity curve tracking |
| - | - | Accuracy monitoring |

---

## Appendix A: Data Dictionary

| Field | Type | Range | Unit | Update Freq |
|-------|------|-------|------|-------------|
| IV | Number | 0-100 | % | 1-min |
| Strike | Number | 15000-35000 | ₹ | Daily |
| RS | Number | -5 to +5 | Index | Daily |
| Accuracy | Number | 40-85 | % | Daily |
| FII Flow | Number | -5000 to +5000 | ₹ Cr | Daily |
| PCR | Number | 0.5-2.0 | Ratio | Daily |

---

**End of Technical Specifications**

For implementation details, refer to `CONFIG_IMPLEMENTATION.md`  
For change history, refer to `CHANGES.md`
