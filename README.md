# Multi-Agent Finance AI — India Equity Prediction Engine

A production-grade 9-agent LangGraph system for NSE/BSE equity analysis.  
Combines Chronos-2, XGBoost, LightGBM, CatBoost ensemble forecasting with FinBERT sentiment, F&O analysis, FII/DII flow tracking, and macro-India intelligence — served through a FastAPI backend and Next.js 14 dashboard.

---

## Architecture

```
┌─────────────────────────────────┐     HTTP / SWR
│   Next.js 14 Dashboard          │ ──────────────────► FastAPI :8000
│   app/  components/  lib/       │                      9 LangGraph Agents
└─────────────────────────────────┘                      ML Ensemble
                                                         FinBERT · GDELT
                                                         NSE · yfinance
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | **3.11+** | 3.12 works; 3.13 not yet tested |
| Node.js | **18+** | 20 LTS recommended |
| npm | 9+ | comes with Node.js |
| Git | any | for cloning |

Optional but recommended:
- **uv** — fast Python package manager: `pip install uv`

---

## 1. Clone the repo

```bash
git clone https://github.com/manup-bhat/Multi_agent_finance_ai.git
cd Multi_agent_finance_ai
```

---

## 2. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in **at minimum** these three keys:

```env
GOOGLE_API_KEY=your_gemini_api_key      # https://aistudio.google.com/
GROQ_API_KEY=your_groq_api_key          # https://console.groq.com/  (free tier)
FINLIGHT_API_KEY=your_finlight_key      # https://finlight.me/       (10K/month free)
```

Everything else in `.env` works out of the box for local development.

Also set the frontend API URL (only needed if you change the default port):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 3. Run the FastAPI backend

### Option A — with uv (recommended, fastest)

```bash
# Install uv if you don't have it
pip install uv

# Create virtual environment and install all dependencies
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Start the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option B — with standard pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **Swagger UI:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

> **First startup is slow** (~60–120s) — the backend preloads Chronos-2, FinBERT,  
> and GoEmotions models into memory. Subsequent starts are faster due to caching.

---

## 4. Run the Next.js frontend

Open a **second terminal** in the same repo root:

```bash
npm install
npm run dev
```

The dashboard opens at **http://localhost:3000**

---

## 5. Run both at once (parallel terminals)

If you have `concurrently` or `make`, you can start both in one command:

```bash
# Using concurrently
npm install -g concurrently
concurrently \
  "uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload" \
  "npm run dev"
```

---

## 6. First use

1. Open **http://localhost:3000**
2. The header shows **API Offline** until the backend is fully warmed up
3. Select a ticker from the search bar (e.g. `RELIANCE`, `TCS`, `INFY`)
4. Set your **horizon** (days) and toggle **F&O** and **Sentiment** as needed
5. Click **Run Analysis** — the 9-agent pipeline runs and populates all pages

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend health + module status |
| `POST` | `/analyze` | Full 9-agent analysis for a ticker |
| `POST` | `/predict` | ML ensemble directional prediction |
| `POST` | `/sentiment` | FinBERT + GDELT + RSS sentiment |
| `POST` | `/fno/analyze` | Option chain, PCR, max pain, greeks |
| `GET` | `/macro/india-cues` | VIX, USD/INR, crude, SGX Nifty, FII |
| `GET` | `/fii-dii/latest` | Latest FII/DII net flows |
| `POST` | `/backtest` | Strategy backtest with equity curve |

Full interactive docs: http://localhost:8000/docs

---

## Frontend pages

| Route | Page |
|---|---|
| `/` | Dashboard — verdict, KPIs, price chart, agent summaries |
| `/technical` | Technical indicators, regime, MACD/RSI/BB |
| `/predictions` | ML ensemble forecast, confidence, SHAP |
| `/sentiment` | FinBERT scores, emotion analysis, news feed |
| `/fo-analysis` | Option chain, PCR, max pain, IV rank |
| `/fii-dii` | FII/DII flow tracker, streak analysis |
| `/macro` | VIX, USD/INR, Brent Crude, SGX Nifty |
| `/sector-rotation` | Sector heatmap and momentum |
| `/backtest` | Strategy backtesting with equity curves |
| `/news` | Live news sentiment feed |
| `/risk` | Risk monitor, circuit breakers, key risks |
| `/model-performance` | Walk-forward accuracy, Sharpe, drawdown |
| `/audit` | Full decision audit trail |

---

## Production build

```bash
# Build Next.js for production
npm run build
npm run start          # serves on port 3000

# Run FastAPI in production mode (no --reload)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## Environment variable reference

See `.env.example` for the full list with descriptions.  
The three required keys are `GOOGLE_API_KEY`, `GROQ_API_KEY`, and `FINLIGHT_API_KEY`.  
All market data (NSE, yfinance, GDELT, RSS feeds) is fetched without API keys.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `API Offline` badge in navbar | Backend not running or still warming up — wait 60–120s |
| `ModuleNotFoundError` on start | Run `pip install -e .` from repo root with venv active |
| Port 8000 in use | `lsof -i :8000` then `kill -9 <PID>`, or change `API_PORT` in `.env` |
| `NEXT_PUBLIC_API_URL` not working | Must restart `npm run dev` after changing `.env` |
| Slow first analysis | Normal — Chronos-2 + FinBERT load once; subsequent calls are fast |
| NSE option chain errors | NSE rate-limits scrapers; retry after 30s or during off-hours |
