import yfinance as yf
df = yf.download("^INDIAVIX", period="1d", progress=False, auto_adjust=True)
try:
    val = float(df["Close"].iloc[-1])
    print("Success:", val)
except Exception as e:
    print("Error:", type(e), e)
