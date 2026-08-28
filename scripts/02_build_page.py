#!/usr/bin/env python3
"""Build the Equilibrium Real Interest Rate page: this project's own
domestic r* (Kiley 2020, IJCB, UC model, one-sided/filtered) plotted
alongside four outside r* benchmarks -- Laubach-Williams, an SPF-implied
long-run real rate, an SEP-implied long-run real rate, and the TIPS
5y5y-forward real yield -- plus the realized real fed funds rate
(FEDFUNDS less trailing 4-quarter core PCE inflation), which fluctuates
around all of them. Self-contained static page (see page_template.html).

Usage:
    python3 02_build_page.py [--rstar-file PATH] [--benchmarks-file PATH]
"""
import argparse
import csv
import io
import json
from datetime import date
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUT_DIR = PROJECT_DIR / "output"
PAGES_OUT = PROJECT_DIR / "docs" / "index.html"
RSTAR_DEFAULT = PROJECT_DIR.parent / "rstar" / "outputs" / "rstar.csv"
BENCHMARKS_DEFAULT = PROJECT_DIR / "outputs" / "rstar_benchmarks.csv"

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def quarter_to_date(label: str) -> str:
    y, q = label[:4], label[5]
    month = {"1": "01", "2": "04", "3": "07", "4": "10"}[q]
    return f"{y}-{month}-01"


def read_rstar(path: Path) -> dict:
    """One-sided (filtered) domestic r* -- no uncertainty band exists for
    the one-sided estimate (only the smoothed/two-sided one has one)."""
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            out[quarter_to_date(row["date"])] = float(row["rstar_1side"])
    return out


def read_benchmarks(path: Path) -> dict:
    cols = ["realized_real_ffr", "tips_5y5y_real", "sep_implied_real", "lw_rstar", "spf_implied_real"]
    out = {c: {} for c in cols}
    with open(path) as f:
        for row in csv.DictReader(f):
            d = quarter_to_date(row["date"])
            for c in cols:
                v = row[c]
                if v:
                    out[c][d] = float(v)
    return out


def fetch_recessions() -> list[list[str]]:
    """NBER recession dates from FRED's USREC, same as ../dashboard."""
    resp = requests.get(FRED_CSV_URL.format(series_id="USREC"), timeout=30)
    resp.raise_for_status()
    reader = csv.reader(io.StringIO(resp.text))
    next(reader)
    rows = [(r[0], r[1]) for r in reader if len(r) == 2 and r[1] not in (".", "")]
    bands, start, prev_d = [], None, None
    for d, v in rows:
        if v == "1" and start is None:
            start = d
        elif v != "1" and start is not None:
            bands.append([start, prev_d])
            start = None
        prev_d = d
    if start is not None:
        bands.append([start, prev_d])
    return bands


def series_payload(d: dict) -> list:
    return [round(v, 4) if v is not None else None for v in d.values()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rstar-file", default=str(RSTAR_DEFAULT))
    ap.add_argument("--benchmarks-file", default=str(BENCHMARKS_DEFAULT))
    args = ap.parse_args()

    rstar_path = Path(args.rstar_file)
    if not rstar_path.exists():
        raise SystemExit(f"{rstar_path} not found -- run the rstar pipeline first (see ../rstar/README.md)")
    bench_path = Path(args.benchmarks_file)
    if not bench_path.exists():
        raise SystemExit(f"{bench_path} not found -- run 00_ingest_fred.py + 00_ingest_lw.py + "
                          f"00_ingest_spf.py + 01_build_benchmarks.py first")

    rstar = read_rstar(rstar_path)
    bench = read_benchmarks(bench_path)
    recessions = fetch_recessions()

    dates = sorted(set(rstar) | set().union(*[set(v) for v in bench.values()]))

    def col(d):
        return [round(d[dt], 4) if dt in d else None for dt in dates]

    payload = {
        "run_date": f"{date.today():%Y%m%d}",
        "as_of": max(rstar),
        "lw_as_of": max(bench["lw_rstar"]),
        "spf_as_of": max(bench["spf_implied_real"]),
        "sep_as_of": max(bench["sep_implied_real"]),
        "tips_as_of": max(bench["tips_5y5y_real"]),
        "realized_as_of": max(bench["realized_real_ffr"]),
        "dates": dates,
        "domestic": col(rstar),
        "lw": col(bench["lw_rstar"]),
        "spf": col(bench["spf_implied_real"]),
        "sep": col(bench["sep_implied_real"]),
        "tips": col(bench["tips_5y5y_real"]),
        "realized": col(bench["realized_real_ffr"]),
        "recessions": recessions,
    }

    template = (SCRIPT_DIR / "page_template.html").read_text()
    if "__DATA_JSON__" not in template:
        raise ValueError("page_template.html is missing the __DATA_JSON__ placeholder")
    html = template.replace("__DATA_JSON__", json.dumps(payload, separators=(",", ":")))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{payload['run_date']}_equilibrium_rate.html"
    out_path.write_text(html)
    print(f"Wrote {out_path} ({len(html)} bytes, {len(dates)} quarters, domestic as of {payload['as_of']})")

    PAGES_OUT.parent.mkdir(parents=True, exist_ok=True)
    PAGES_OUT.write_text(html)
    print(f"Wrote {PAGES_OUT} (stable copy)")


if __name__ == "__main__":
    main()
