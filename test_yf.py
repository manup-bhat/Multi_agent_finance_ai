import yfinance as yf
import pandas as pd
print("YF Version:", yf.__version__)
print("Pandas Version:", pd.__version__)

try:
    df = yf.download(
        "RELIANCE.NS", 
        period="6mo", 
        interval="1d",
        progress=False, 
        auto_adjust=True, 
        multi_level_col=False
    )
    print("Columns:", df.columns)
    print("Empty?", df.empty)
    print(df.head(2))
except Exception as e:
    print("Exception1:", e)

try:
    df = yf.download(
        "RELIANCE.NS", 
        period="6mo", 
        interval="1d",
        progress=False, 
        auto_adjust=True
    )
    print("Columns:", df.columns)
    print("Empty?", df.empty)
    print(df.head(2))
except Exception as e:
    print("Exception2:", e)
