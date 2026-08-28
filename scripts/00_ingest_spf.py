#!/usr/bin/env python3
"""Pull the Philadelphia Fed Survey of Professional Forecasters' long-run
(10-year-ahead annualized) median projections for the 3-month T-bill rate
(BILL10) and CPI inflation (CPI10) -- combined here into an SPF-implied
long-run real short rate (BILL10 - CPI10).

BILL10 is asked only once a year, in the Q1 survey -- unlike CPI10, which
is quarterly -- so the implied real rate this produces is annual (Q1-only),
not quarterly like the other benchmarks on this page. Documented on the
page itself, not silently interpolated.

Usage: python3 00_ingest_spf.py
"""
import io
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPF_BASE = (
    "https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/"
    "survey-of-professional-forecasters/data-files/files/median_{name}_level.xlsx"
)


def fetch(name: str, col: str) -> pd.DataFrame:
    resp = requests.get(SPF_BASE.format(name=name), timeout=30)
    resp.raise_for_status()
    df = pd.read_excel(io.BytesIO(resp.content))
    if not {"YEAR", "QUARTER", col}.issubset(df.columns):
        sys.exit(f"Unexpected SPF {name} file columns: {df.columns.tolist()}")
    df = df.dropna(subset=[col])
    df["date"] = df["YEAR"].astype(int).astype(str) + "Q" + df["QUARTER"].astype(int).astype(str)
    return df[["date", col]]


def main():
    bill10 = fetch("bill10", "BILL10")
    cpi10 = fetch("cpi10", "CPI10")

    merged = bill10.merge(cpi10, on="date", how="inner")
    merged["spf_implied_real"] = merged["BILL10"] - merged["CPI10"]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{date.today():%Y%m%d}_spf_implied.csv"
    merged[["date", "BILL10", "CPI10", "spf_implied_real"]].to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(merged)} obs, {merged['date'].iloc[0]}..{merged['date'].iloc[-1]}, "
          f"BILL10 asked annually so this is Q1-only)")


if __name__ == "__main__":
    main()
