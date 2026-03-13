from nselib import capital_market
import pandas as pd
df = capital_market.fii_dii_trading_activity()
print(df.head())
print(df.columns)
