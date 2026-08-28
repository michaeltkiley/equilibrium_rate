#!/usr/bin/env python3
"""Combine the r* benchmark series into outputs/rstar_benchmarks.csv:
Laubach-Williams, SPF-implied, SEP-implied, the TIPS 5y5y-forward real
yield, and the realized real fed funds rate (FEDFUNDS less trailing
4-quarter core PCE inflation) that fluctuates around the r* benchmarks.
Domestic r* (this project's own UC model) is read directly from
../rstar/outputs/rstar.csv by 02_build_page.py, not duplicated here.

Usage: python3 01_build_benchmarks.py
"""
import glob
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "fred.duckdb"
OUT_PATH = REPO_ROOT / "outputs" / "rstar_benchmarks.csv"


def latest(pattern: str) -> Path:
    candidates = sorted(glob.glob(str(REPO_ROOT / "data" / pattern)))
    if not candidates:
        sys.exit(f"No file matching {pattern} -- run the matching 00_ingest_*.py first")
    return Path(candidates[-1])


def load_fred_wide(con) -> pd.DataFrame:
    df = con.execute("SELECT series_id, obs_date, value FROM fred_raw").fetchdf()
    wide = df.pivot(index="obs_date", columns="series_id", values="value")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def to_quarterly_mean(s: pd.Series) -> pd.Series:
    return s.resample("QS").mean()


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    w = load_fred_wide(con)
    con.close()

    # --- Realized real fed funds rate: FEDFUNDS - trailing 4Q core PCE inflation ---
    ffr_q = to_quarterly_mean(w["FEDFUNDS"])
    core_pce_q = to_quarterly_mean(w["PCEPILFE"])
    infl4q = 100 * np.log(core_pce_q / core_pce_q.shift(4))
    realized_real_ffr = (ffr_q - infl4q).rename("realized_real_ffr")

    # --- TIPS 5y5y-forward real yield, from DFII5 (5y) and DFII10 (10y) ---
    y5 = w["DFII5"] / 100.0
    y10 = w["DFII10"] / 100.0
    fwd_5y5y_daily = (((1 + y10) ** 10 / (1 + y5) ** 5) ** (1 / 5) - 1) * 100
    tips_5y5y_real = to_quarterly_mean(fwd_5y5y_daily).rename("tips_5y5y_real")

    # --- SEP-implied real longer-run rate: FEDTARMDLR - PCECTPIMDLR ---
    sep_nominal = w["FEDTARMDLR"].dropna()
    sep_infl = w["PCECTPIMDLR"].dropna()
    sep_implied = (sep_nominal - sep_infl).dropna()
    # SEP releases are event-dated (FOMC meeting days), not quarter-starts;
    # snap each release to the quarter it falls in (at most one release per
    # quarter in practice) so it lines up with the other quarterly series.
    sep_implied.index = sep_implied.index.to_period("Q").to_timestamp()
    sep_implied = sep_implied.rename("sep_implied_real")
    sep_implied = sep_implied[~sep_implied.index.duplicated(keep="last")]

    # --- Laubach-Williams (already quarterly, one-sided) ---
    lw = pd.read_csv(latest("*_lw_rstar.csv"), parse_dates=["date"]).set_index("date")["lw_rstar"]

    # --- SPF-implied (annual, Q1-only) ---
    spf = pd.read_csv(latest("*_spf_implied.csv"))
    spf["date"] = pd.PeriodIndex(spf["date"], freq="Q").to_timestamp()
    spf = spf.set_index("date")["spf_implied_real"]

    out = pd.concat(
        [realized_real_ffr, tips_5y5y_real, sep_implied, lw, spf], axis=1
    ).sort_index()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_csv = out.reset_index().rename(columns={out.index.name or "index": "date"})
    out_csv["date"] = out_csv["date"].dt.to_period("Q").astype(str)
    out_csv.to_csv(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH} ({len(out_csv)} quarters, {out_csv['date'].iloc[0]}..{out_csv['date'].iloc[-1]})")
    print(f"\nLatest 8 quarters:\n{out.tail(8).round(3)}")


if __name__ == "__main__":
    main()
