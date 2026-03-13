import yfinance as yf
df = yf.Ticker("^INDIAVIX").history(period="5d", interval="1d", auto_adjust=True)
import pandas as pd
print("Is MultiIndex?", isinstance(df.columns, pd.MultiIndex))
print("Columns:", df.columns)
