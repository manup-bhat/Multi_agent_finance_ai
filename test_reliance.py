import yfinance as yf
raw = yf.download("RELIANCE.NS", period="5d", interval="1d", auto_adjust=True)
import pandas as pd
if isinstance(raw.columns, pd.MultiIndex):
    raw.columns = raw.columns.get_level_values(0)
print(raw[["Open", "High", "Low", "Close"]].tail(5))
