import yfinance as yf

SECTOR_SYMBOLS = {
    "Bank": "^NSEBANK",
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "Auto": "^CNXAUTO",
    "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY",
    "Infra": "^CNXINFRA",
    "Media": "^CNXMEDIA",
    "Nifty50": "^NSEI"
}

for name, sym in SECTOR_SYMBOLS.items():
    tkr = yf.Ticker(sym)
    hist = tkr.history(period="1mo")
    if not hist.empty:
        print(f"✅ {name} ({sym}) - Found")
    else:
        print(f"❌ {name} ({sym}) - NOT FOUND")
