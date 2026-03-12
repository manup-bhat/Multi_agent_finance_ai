#!/bin/bash
cd ~/multi-agent-india-engine
source .venv/bin/activate
python3 - << 'EOF'
print("=" * 60)

# ── nsefin NSEClient methods ──────────────────────────────────
print("[nsefin.NSEClient] instance methods:")
try:
    import nsefin
    client = nsefin.NSEClient()
    methods = [x for x in dir(client) if not x.startswith("_")]
    for m in methods:
        print(f"  {m}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── nsefin nse instance methods ───────────────────────────────
print("\n[nsefin.nse] instance methods:")
try:
    import nsefin
    nse = nsefin.nse
    methods = [x for x in dir(nse) if not x.startswith("_")]
    for m in methods:
        print(f"  {m}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# ── nselib all modules ────────────────────────────────────────
print("\n[nselib] all modules:")
try:
    import nselib
    mods = [x for x in dir(nselib) if not x.startswith("_")]
    for m in mods:
        print(f"  {m}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── nselib derivatives module ─────────────────────────────────
print("\n[nselib.derivatives] functions (if exists):")
try:
    import nselib.derivatives as deriv
    fns = [x for x in dir(deriv) if not x.startswith("_")]
    for f in fns:
        print(f"  {f}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── jugaad bhavcopy archives test ─────────────────────────────
print("\n[jugaad_data bhavcopy_raw] test Jan 7 2019:")
try:
    from jugaad_data.nse import bhavcopy_raw
    from datetime import date
    import io, pandas as pd
    txt = bhavcopy_raw(date(2019, 1, 7))
    df = pd.read_csv(io.StringIO(txt))
    hdfc = df[df.iloc[:,0].str.strip() == "HDFCBANK"]
    print(f"  OK: total={len(df)} rows, HDFCBANK rows={len(hdfc)}")
    if not hdfc.empty:
        print(f"  Cols: {list(hdfc.columns)}")
        print(f"  Sample: {hdfc.iloc[0].to_dict()}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

print("=" * 60)
EOF