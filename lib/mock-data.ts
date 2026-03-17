// ============================================================
// MOCK DATA — used as fallback when API is not connected
// ============================================================

export const MOCK_TICKERS = [
  { symbol: "RELIANCE.NS", name: "Reliance Industries Ltd", sector: "Energy" },
  { symbol: "HDFCBANK.NS", name: "HDFC Bank Ltd", sector: "Banking" },
  { symbol: "TCS.NS", name: "Tata Consultancy Services", sector: "IT" },
  { symbol: "INFY.NS", name: "Infosys Ltd", sector: "IT" },
  { symbol: "ICICIBANK.NS", name: "ICICI Bank Ltd", sector: "Banking" },
  { symbol: "SBIN.NS", name: "State Bank of India", sector: "Banking" },
  { symbol: "BHARTIARTL.NS", name: "Bharti Airtel Ltd", sector: "Telecom" },
  { symbol: "HINDUNILVR.NS", name: "Hindustan Unilever Ltd", sector: "FMCG" },
  { symbol: "BAJFINANCE.NS", name: "Bajaj Finance Ltd", sector: "Finance" },
  { symbol: "WIPRO.NS", name: "Wipro Ltd", sector: "IT" },
];

export const MOCK_ANALYSIS = {
  ticker: "RELIANCE.NS",
  company_name: "Reliance Industries Ltd",
  verdict: "BUY",
  confidence: 71,
  regime: "BULL",
  horizon: 5,
  current_price: 1698.45,
  price_targets: { p10: 1650, p50: 1720, p90: 1790 },
  fo_strategy: "Iron Condor 22000-22400",
  fo_rr: "Max Profit ₹4,200 | Max Loss ₹-11,800",
  india_vix: 14.2,
  fii_5d_avg: 2840,
  fear_greed: 62,
  pcr: 1.32,
  delivery_pct: 48.3,
  risk_level: "MEDIUM",
  kelly_fraction: 0.42,
  position_size_mult: 0.75,
  circuit_breaker: false,
  fii_streak_alert: true,
  gamma_risk: false,
  sebi_compliant: true,
  override_verdict: null,
  last_run: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  agents: [
    {
      id: "quant",
      name: "Quant Agent",
      icon: "🔢",
      sentiment: "BULLISH",
      summary: "Strong momentum confirmed by RSI at 58, MACD bullish crossover, and price above EMA50. Delivery % at 48.3% confirms institutional conviction.",
      full_report: "**Technical Analysis Summary**\n\nRSI(14) at 58 — in bullish territory without being overbought. MACD showed a bullish crossover 3 sessions ago with increasing histogram bars. Price is firmly above EMA20 (₹1,672) and EMA50 (₹1,641), confirming uptrend.\n\n**SMC Analysis**: BOS detected at ₹1,680 with bullish continuation structure. Order block identified at ₹1,645-1,655 — strong support zone.\n\n**Volume**: OBV trending up, delivery % at 48.3% (above 40% conviction threshold). Volume ratio 1.4x 20-day average on last up day.\n\n**Verdict contribution**: BULLISH — strong trend continuation setup.",
    },
    {
      id: "macro",
      name: "Macro Agent",
      icon: "🏛️",
      sentiment: "BULLISH",
      summary: "FII net buyers for 3 consecutive days. FII 5d avg +₹2,840Cr. DII slightly bearish but FII dominance supports upside.",
      full_report: "**FII/DII Flow Analysis**\n\nFII has been a net buyer for 3 consecutive sessions with a 5-day average inflow of ₹2,840Cr — strongly bullish signal. DII has been a modest seller (-₹420Cr avg) suggesting profit-booking by domestic institutions.\n\n**Participant OI**: FII net long in futures (+35,330 contracts). Client (retail) net short — a contrarian bullish signal as per historical patterns.\n\n**Global Context**: USD/INR stable at ₹83.42, Brent crude at $78.20 (manageable for India). SGX Nifty up 45 pts pre-market.\n\n**Verdict contribution**: BULLISH — institutional support with FII dominance.",
    },
    {
      id: "fundamental",
      name: "Fundamental Agent",
      icon: "📰",
      sentiment: "NEUTRAL",
      summary: "No major SEBI actions. Q3 results beat estimates by 4.2%. One minor regulatory query on telecom segment — monitored.",
      full_report: "**Fundamental & News Analysis**\n\nQ3 FY24 results: Revenue ₹2.34L Cr (4.2% beat), PAT ₹18,951Cr (2.8% beat). Jio subscriber growth continues; retail segment showing strong traction.\n\n**News Sentiment** (12 Finlight + 6 RSS articles): FinBERT composite score +0.38 (Moderately Positive). Key headlines support business momentum.\n\n**SEBI Compliance**: No current alerts or insider trading notices. Minor regulatory query on telecom segment pricing — non-material impact estimated.\n\n**Verdict contribution**: NEUTRAL — solid fundamentals but no new catalysts.",
    },
    {
      id: "prediction",
      name: "Prediction Agent",
      icon: "🔮",
      sentiment: "BULLISH",
      summary: "XGBoost ensemble: 71% confidence BUY. Chronos-2 P50 target ₹1,720. Direction probability: 70% bullish.",
      full_report: "**ML Prediction Report**\n\n**Ensemble Model (XGBoost + LightGBM + CatBoost)**:\n- Direction: Very Bullish (42%) + Bullish (28%) = 70% total upside probability\n- Confidence: 71% (MEDIUM-HIGH)\n- Calibration: Well calibrated against last 30-day holdout\n\n**Chronos-2 Forecast (5-day)**:\n- P10 (Bear): ₹1,650 | P50 (Base): ₹1,720 | P90 (Bull): ₹1,790\n- Model trained with 8 India-specific covariates including VIX, FII flows, PCR\n\n**Top SHAP features**: fii_net_5d_avg (+0.32), pcr_current (+0.18), rsi_14 (-0.14), india_vix (-0.11)\n\n**Verdict contribution**: BULLISH — model ensemble strongly agrees on upward direction.",
    },
    {
      id: "emotion",
      name: "Emotion Agent",
      icon: "😨",
      sentiment: "BULLISH",
      summary: "Fear & Greed at 62 (Greed). StockTwits 68% bullish. No euphoria detected — sustainable sentiment.",
      full_report: "**Sentiment & Emotion Analysis**\n\n**Fear & Greed Index**: 62/100 — GREED zone (not extreme). Healthy sentiment without euphoria.\n\n**StockTwits Analysis**: 68% bullish / 32% bearish across 247 posts today. Volume 2.3x normal — elevated but not euphoric.\n\n**GoEmotions Breakdown**: Excitement 35%, Optimism 28%, Fear 18%, Nervousness 12%, Other 7%. Positive emotions dominant.\n\n**GDELT Macro**: Tone score -0.3 (slight negative) on global India-related events. Dominant theme: Economic Policy (neutral-positive).\n\n**Euphoria Flag**: NOT active. Sentiment is bullish but controlled.\n\n**Verdict contribution**: BULLISH — positive sentiment without euphoria warnings.",
    },
    {
      id: "fo",
      name: "F&O Agent",
      icon: "📜",
      sentiment: "BULLISH",
      summary: "PCR 1.32 (bullish zone). Max pain ₹22,000 — current price 0.6% above. IV Rank 42 (moderate). Iron Condor recommended.",
      full_report: "**F&O Analysis Report**\n\n**Put-Call Ratio**: 1.32 — in bullish zone (>1.2 = more put writing = market makers bullish). Trend: increasing for 2 sessions.\n\n**Max Pain**: ₹22,000. Current Nifty at ₹22,143 — 0.6% above max pain. With 3 DTE, gravitational pull toward ₹22,000 possible.\n\n**IV Rank**: 42/100 — Moderate. Neither cheap nor expensive. Iron Condor is appropriate strategy.\n\n**Top OI Buildup**: Strong call writing at 22,400 CE (+1.2M OI) = resistance. Strong put writing at 21,500 PE (+800K OI) = support.\n\n**Recommended Strategy**: Iron Condor 22000 CE / 22400 CE / 21600 PE / 21200 PE\nMax Profit: ₹4,200 | Max Loss: ₹-11,800 | Breakeven: ₹21,680 / ₹22,320\n\n**Verdict contribution**: BULLISH — options market structure supports underlying uptrend.",
    },
    {
      id: "devil",
      name: "Devil's Advocate",
      icon: "😈",
      sentiment: "BEARISH",
      summary: "Global uncertainty (US yields), 3 DTE expiry risk, FII could reverse. Don't ignore macro headwinds.",
      full_report: "**Contrarian Risk Analysis**\n\n**Bear Case Scenarios:**\n\n1. **US 10Y Yield Risk**: Currently at 4.6% — if prints above 4.8%, FII selling likely to reverse sharply. This would impact the bullish thesis immediately.\n\n2. **Expiry Dynamics**: 3 DTE means gamma risk is elevated. Any large move (>1.5%) could cause options dealers to delta-hedge aggressively, amplifying moves.\n\n3. **FII Reversal Risk**: 3-day buying streak is positive but FII flows are notoriously fickle. A weak US session tonight could reverse this entirely.\n\n4. **Valuation Concern**: Reliance is trading at 24x FY25E earnings — not cheap. Any negative Jio regulatory news = 3-5% downside.\n\n5. **SMC Warning**: While BOS is bullish, there's an unfilled Fair Value Gap at ₹1,655-1,665 that could attract price back down.\n\n**Conclusion**: The bull thesis is valid but with meaningful tail risks. Position sizing discipline is critical.",
    },
  ],
};

// Generate mock price data (last 60 days)
function generatePriceData(base = 1650, days = 60) {
  const data = [];
  let price = base;
  const now = new Date();
  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const change = (Math.random() - 0.47) * 20;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 15;
    const low = Math.min(open, close) - Math.random() * 15;
    const volume = Math.floor(8000000 + Math.random() * 5000000);
    data.push({
      date: date.toISOString().split("T")[0],
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume,
    });
    price = close;
  }
  return data;
}

export const MOCK_PRICE_DATA = generatePriceData(1650, 60);

// Prediction data (next 5 days)
export const MOCK_FORECAST = (() => {
  const last = MOCK_PRICE_DATA[MOCK_PRICE_DATA.length - 1];
  const base = last.close;
  return Array.from({ length: 5 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i + 1);
    return {
      date: d.toISOString().split("T")[0],
      p10: +(base - 50 + i * 5 + Math.random() * 10).toFixed(2),
      p50: +(base + 10 + i * 10).toFixed(2),
      p90: +(base + 60 + i * 15 + Math.random() * 10).toFixed(2),
    };
  });
})();

// FII/DII data (last 30 days)
export const MOCK_FII_DII = Array.from({ length: 30 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (29 - i));
  return {
    date: d.toISOString().split("T")[0],
    fii: Math.floor((Math.random() - 0.4) * 6000),
    dii: Math.floor((Math.random() - 0.55) * 3000),
  };
});

// VIX data (last 180 days)
export const MOCK_VIX_DATA = Array.from({ length: 180 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (179 - i));
  return {
    date: d.toISOString().split("T")[0],
    vix: +(12 + Math.sin(i / 20) * 5 + Math.random() * 3).toFixed(2),
  };
});

// Sentiment timeline (last 30 days)
export const MOCK_SENTIMENT_TIMELINE = Array.from({ length: 30 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (29 - i));
  return {
    date: d.toISOString().split("T")[0],
    composite: +((Math.random() - 0.4) * 1.5).toFixed(3),
    finbert: +((Math.random() - 0.4) * 1.2).toFixed(3),
    social: +((Math.random() - 0.45) * 1.0).toFixed(3),
  };
});

// Option chain mock data
export const MOCK_OPTION_CHAIN = (() => {
  const atm = 22000;
  return Array.from({ length: 21 }, (_, i) => {
    const strike = atm - 1000 + i * 100;
    const isATM = strike === atm;
    const moneyness = (strike - atm) / atm;
    const callIV = 15 + Math.abs(moneyness) * 100 + Math.random() * 2;
    const putIV = 15 + Math.abs(moneyness) * 120 + Math.random() * 2;
    return {
      strike,
      isATM,
      call: {
        oi: Math.floor((isATM ? 1500000 : 500000 + Math.random() * 800000)),
        oiChange: Math.floor((Math.random() - 0.3) * 200000),
        volume: Math.floor(Math.random() * 500000),
        iv: +callIV.toFixed(1),
        ltp: +(Math.max(0, atm - strike + 50) + Math.random() * 20).toFixed(2),
      },
      put: {
        oi: Math.floor((isATM ? 1200000 : 400000 + Math.random() * 900000)),
        oiChange: Math.floor((Math.random() - 0.3) * 200000),
        volume: Math.floor(Math.random() * 450000),
        iv: +putIV.toFixed(1),
        ltp: +(Math.max(0, strike - atm + 50) + Math.random() * 20).toFixed(2),
      },
    };
  });
})();

// Sector data
export const MOCK_SECTOR_DATA = [
  { name: "BANK", return5d: 1.8, rs: 0.7, momentum: 0.6, quadrant: "Leading" },
  { name: "IT", return5d: -0.5, rs: -0.3, momentum: 0.4, quadrant: "Improving" },
  { name: "PHARMA", return5d: 2.4, rs: 1.1, momentum: 0.3, quadrant: "Leading" },
  { name: "FMCG", return5d: 0.3, rs: -0.2, momentum: -0.4, quadrant: "Weakening" },
  { name: "AUTO", return5d: 3.1, rs: 1.4, momentum: 0.8, quadrant: "Leading" },
  { name: "METAL", return5d: -1.2, rs: -0.8, momentum: -0.5, quadrant: "Lagging" },
  { name: "REALTY", return5d: 4.2, rs: 1.8, momentum: 1.1, quadrant: "Leading" },
  { name: "ENERGY", return5d: -0.8, rs: -0.4, momentum: 0.2, quadrant: "Improving" },
  { name: "INFRA", return5d: 1.2, rs: 0.3, momentum: -0.3, quadrant: "Weakening" },
  { name: "MEDIA", return5d: -2.1, rs: -1.2, momentum: -0.9, quadrant: "Lagging" },
];

// News feed
export const MOCK_NEWS = [
  {
    id: 1,
    title: "Reliance Industries Reports Strong Q3 Results, PAT Beats Estimates by 4.2%",
    source: "ET Markets",
    publishedAt: new Date(Date.now() - 2 * 3600000).toISOString(),
    summary: "Reliance Industries Limited reported Q3 FY24 consolidated PAT of ₹18,951 crore, beating analyst estimates by 4.2%. Jio Platforms and Retail segments drove growth.",
    sentiment_score: 0.82,
    sentiment: "POSITIVE",
    relevance: 0.95,
    url: "#",
  },
  {
    id: 2,
    title: "FII Net Buyers for Third Consecutive Session; DII Turn Sellers",
    source: "LiveMint",
    publishedAt: new Date(Date.now() - 4 * 3600000).toISOString(),
    summary: "Foreign institutional investors remained net buyers of Indian equities for the third straight session, infusing ₹3,200 crore. Domestic funds book profits.",
    sentiment_score: 0.45,
    sentiment: "POSITIVE",
    relevance: 0.88,
    url: "#",
  },
  {
    id: 3,
    title: "RBI Holds Rates, Signals Cautious Stance Amid Global Uncertainty",
    source: "Business Standard",
    publishedAt: new Date(Date.now() - 6 * 3600000).toISOString(),
    summary: "The Reserve Bank of India's monetary policy committee voted to keep the repo rate unchanged at 6.5%, maintaining its 'withdrawal of accommodation' stance.",
    sentiment_score: 0.05,
    sentiment: "NEUTRAL",
    relevance: 0.75,
    url: "#",
  },
  {
    id: 4,
    title: "US 10-Year Treasury Yield Rises to 4.65%, Concerns Mount for Emerging Markets",
    source: "The Hindu Business Line",
    publishedAt: new Date(Date.now() - 8 * 3600000).toISOString(),
    summary: "Rising US yields triggered a risk-off sentiment globally, with emerging market equities facing pressure. Analysts warn of potential FII outflows from India.",
    sentiment_score: -0.62,
    sentiment: "NEGATIVE",
    relevance: 0.72,
    url: "#",
  },
  {
    id: 5,
    title: "Nifty50 Poised for Breakout Above 22,500 — Technicals Point to Strong Upside",
    source: "StockTwits",
    publishedAt: new Date(Date.now() - 10 * 3600000).toISOString(),
    summary: "Technical analysts point to a bullish flag pattern on Nifty50 with volume confirmation. RSI at 62, MACD momentum positive. Target: 22,800-23,000.",
    sentiment_score: 0.71,
    sentiment: "POSITIVE",
    relevance: 0.80,
    url: "#",
  },
  {
    id: 6,
    title: "SEBI Proposes New F&O Margin Rules — Impact on Retail Participation",
    source: "ET Markets",
    publishedAt: new Date(Date.now() - 12 * 3600000).toISOString(),
    summary: "SEBI's proposed changes to F&O margin requirements could reduce retail participation by 15-20% per industry estimates. Broker stocks fall.",
    sentiment_score: -0.38,
    sentiment: "NEGATIVE",
    relevance: 0.68,
    url: "#",
  },
];

// Backtest metrics
export const MOCK_BACKTEST = {
  sharpe: 1.12,
  sortino: 1.45,
  max_drawdown: -8.7,
  win_rate: 56.3,
  avg_trade: 1.8,
  alpha: 4.2,
  equity_curve: Array.from({ length: 252 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (251 - i));
    return {
      date: d.toISOString().split("T")[0],
      strategy: +(100 * Math.exp(0.0004 * i + (Math.random() - 0.47) * 0.02)).toFixed(2),
      nifty: +(100 * Math.exp(0.0003 * i + (Math.random() - 0.47) * 0.018)).toFixed(2),
    };
  }),
  folds: [
    { fold: 1, train: "Jan 22 — Jun 22", test: "Jul 22", accuracy: 58.2, sharpe: 1.05 },
    { fold: 2, train: "Jan 22 — Sep 22", test: "Oct 22", accuracy: 61.4, sharpe: 1.24 },
    { fold: 3, train: "Jan 22 — Dec 22", test: "Jan 23", accuracy: 54.8, sharpe: 0.89 },
    { fold: 4, train: "Jan 22 — Mar 23", test: "Apr 23", accuracy: 62.7, sharpe: 1.31 },
    { fold: 5, train: "Jan 22 — Jun 23", test: "Jul 23", accuracy: 57.1, sharpe: 1.08 },
    { fold: 6, train: "Jan 22 — Sep 23", test: "Oct 23", accuracy: 63.5, sharpe: 1.42 },
    { fold: 7, train: "Jan 22 — Dec 23", test: "Jan 24", accuracy: 66.2, sharpe: 1.58 },
    { fold: 8, train: "Jan 22 — Mar 24", test: "Apr 24", accuracy: 64.1, sharpe: 1.45 },
  ],
};

// Model performance
export const MOCK_MODELS = [
  { name: "XGBoost 5-cls", last30: 62.3, last7: 58.1, calibration: "Well calibrated" },
  { name: "LightGBM", last30: 60.8, last7: 57.4, calibration: "Well calibrated" },
  { name: "CatBoost", last30: 61.1, last7: 59.2, calibration: "Well calibrated" },
  { name: "Chronos-2 p50", last30: 64.2, last7: 61.8, calibration: "Good" },
  { name: "Ensemble", last30: 66.1, last7: 62.4, calibration: "Good" },
];

// Audit trail
export const MOCK_AUDIT = [
  {
    stage: 0,
    name: "Pre-flight Check",
    duration: 2.1,
    status: "success",
    details: [
      "NSE OPEN — Market hours confirmed",
      "India VIX: 14.2 — NORMAL, no circuit breaker",
      "Expiry in 3 days — Elevated gamma noted",
      "SEBI holiday check: No holiday",
    ],
  },
  {
    stage: 1,
    name: "Data Ingestion",
    duration: 4.8,
    status: "partial",
    details: [
      "yfinance: 60 days OHLCV fetched",
      "nsefin: F&O chain loaded (21 strikes)",
      "nselib: FII/DII data fetched",
      "finlight: 12 articles processed",
      "gdelt: 47 events ingested",
      "stocktwits: 247 posts analyzed",
      "nsepython: FALLBACK used (API timeout)",
    ],
    sources: {
      yfinance: "success",
      nsefin: "success",
      nselib: "success",
      finlight: "success",
      gdelt: "success",
      stocktwits: "success",
      nsepython: "warning",
    },
  },
  {
    stage: 2,
    name: "ML Models",
    duration: 8.3,
    status: "success",
    details: [
      "XGBoost: BUY (71% confidence)",
      "LightGBM: BUY (68% confidence)",
      "CatBoost: BUY (70% confidence)",
      "Chronos-2: P50=₹1,720 forecast generated",
      "Feature engineering: 47 features computed",
      "SHAP values: Computed for top 8 features",
    ],
  },
  {
    stage: 3,
    name: "AI Agents",
    duration: 15.4,
    status: "success",
    details: [
      "Quant Agent (Groq 70B) — 1,840 tokens",
      "Macro Agent (Groq 70B) — 1,520 tokens",
      "Fundamental Agent (Groq 8B) — 980 tokens",
      "Prediction Agent (Groq 8B) — 760 tokens",
      "Emotion Agent (Local LLM) — 640 tokens",
      "F&O Agent (Groq 8B) — 1,120 tokens",
      "Devil's Advocate (Gemini Pro) — 2,400 tokens",
    ],
    agent_details: [
      { name: "Quant Agent", model: "Groq 70B", tokens: 1840, preview: "RSI at 58, MACD bullish crossover, price above EMA50..." },
      { name: "Macro Agent", model: "Groq 70B", tokens: 1520, preview: "FII net buyers for 3 consecutive sessions, ₹2,840Cr avg..." },
      { name: "Fundamental Agent", model: "Groq 8B", tokens: 980, preview: "Q3 results beat estimates, no SEBI concerns, GDELT..." },
      { name: "Prediction Agent", model: "Groq 8B", tokens: 760, preview: "Ensemble 71% confidence BUY, Chronos P50 ₹1,720..." },
      { name: "Emotion Agent", model: "Local LLM", tokens: 640, preview: "Fear/Greed 62 Greed zone, StockTwits 68% bullish..." },
      { name: "F&O Agent", model: "Groq 8B", tokens: 1120, preview: "PCR 1.32 bullish, max pain 22000, Iron Condor rec..." },
      { name: "Devil's Advocate", model: "Gemini Pro", tokens: 2400, preview: "US yield risk, expiry gamma, FII reversal scenarios..." },
    ],
  },
  {
    stage: 4,
    name: "Synthesis",
    duration: 2.8,
    status: "success",
    details: [
      "Weighted verdict aggregation: BUY (6/7 agents bullish)",
      "Confidence calibration: 71%",
      "Risk assessment: MEDIUM — kelly 0.42",
      "Override check: No circuit breaker triggered",
      "Final verdict: BUY",
    ],
    summary: {
      groq_calls: 7,
      gemini_calls: 1,
      local_calls: 4,
      total_tokens: 12430,
      estimated_cost: "$0.00",
    },
  },
];
