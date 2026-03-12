# Phase 0 Session Notes — March 2026

## Status: 18/18 validation checks PASSING

## Key validated facts discovered this session:
1. chronos-forecasting pip → import chronos (NOT chronos_forecasting)
2. jugaad-data pip → import jugaad_data (NOT jugaad)
3. timesfm 2.0.0 = GitHub-only, never on PyPI. Use 1.3.0
4. smartmoneyconcepts REMOVED — numba==0.58.1 incompatible with numpy>=2.4
   Replaced by: data/processors/smc_engine.py (pure Python)
5. praw REMOVED — no Reddit API. Use StockTwits + India RSS
6. pandas-ta → pandas-ta-classic==0.3.78 (import pandas_ta_classic as ta)

## Installed and working (confirmed 18/18):
- Python 3.11.15
- numpy 2.4.3, pandas 3.0.1
- chronos-forecasting 2.2.2
- timesfm 1.3.0
- torch 2.10.0
- All India adapters: yfinance, nsefin, nselib, nsepython, jugaad_data
- Full ML stack: xgboost, lightgbm, catboost, optuna, shap, hmmlearn
- Full agent stack: langchain, langgraph, langchain-google-genai, langchain-groq
- Vector DB: chromadb, qdrant-client
- Frontend: streamlit, plotly, fastapi

## Next: Phase 1 — Data Adapters
Build: data/adapters/yfinance_client.py
Gate: Each adapter returns valid DataFrame for HDFCBANK.NS
