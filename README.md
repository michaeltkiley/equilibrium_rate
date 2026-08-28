# equilibrium_rate — Equilibrium Real Interest Rate page

Served at `michaeltkiley.github.io/equilibrium_rate/` (its own page, not a
tab on `resource_utilization`), showing this project's own **UC r***
(Kiley 2020, IJCB, UC model, one-sided/filtered) alongside four
independent outside r* benchmarks, plus the **realized real fed funds
rate** that fluctuates around all five. r* itself comes from
`michaeltkiley/output_gap` (private) rather than being computed here --
see that repo's `rstar/README.md` and the `CROSS_REPO_TOKEN` deployment
setup.

- **UC r*** — `output_gap`'s `rstar` Unobserved Components model
  estimate, one-sided (filtered, real-time), read straight from
  `rstar/outputs/rstar.csv` in that repo.
- **Laubach-Williams** — the NY Fed's HLW natural-rate model.
- **SPF-implied** — Philadelphia Fed Survey of Professional Forecasters'
  10-year-ahead T-bill rate less 10-year-ahead CPI inflation.
- **SEP-implied** — the FOMC's own median longer-run federal funds rate
  projection less its median longer-run PCE inflation projection.
- **TIPS 5y5y** — the 5-year, 5-year-forward real yield implied by the
  TIPS curve, a market-based (not survey- or model-based) estimate.
- **Realized real fed funds rate** — FEDFUNDS less trailing 4-quarter
  core PCE inflation. Not an r* estimate; shown so the reader can see
  actual policy oscillate above and below the r* lines over the cycle.

## History: this page used to build its own "Global Factor"

An earlier version of this page paired UC r* with a custom-built
"Global Factor" — first a PCA of 11 countries' real rates, then several
generations of a hand-built state-space model (a common unit-root trend
plus country-specific AR(2)/AR(1) cyclical processes). After several
rounds of diagnosis and revision (see git history / prior session notes
for the full arc — trend levels distorted by a missing intercept,
parameter instability from unidentified extra factors, etc.), the
custom model was judged not good enough and **dropped entirely** in
favor of well-established, independently-published outside r* estimates
instead. Nothing from that era remains in the pipeline; this rebuild
replaced `00_ingest_global_rates.py` and `01_build_global_factor.py`
outright rather than patching them further.

## Pipeline

```
00_ingest_fred.py     FRED -> data/fred.duckdb (FEDFUNDS, PCEPILFE, DFII5,
                       DFII10, FEDTARMDLR, PCECTPIMDLR)
00_ingest_lw.py        NY Fed HLW workbook -> data/{date}_lw_rstar.csv
00_ingest_spf.py       Philadelphia Fed SPF (BILL10, CPI10)
                        -> data/{date}_spf_implied.csv
01_build_benchmarks.py data/fred.duckdb + the two data/*.csv files above
                        -> outputs/rstar_benchmarks.csv
02_build_page.py       output_gap's rstar/outputs/rstar.csv + outputs/rstar_benchmarks.csv
                        -> docs/index.html
```

Run the three `00_ingest_*.py` scripts (any order) before
`01_build_benchmarks.py`; `02_build_page.py` needs `output_gap`'s `rstar`
pipeline to have been run at least once (see that repo's
`rstar/README.md`) and takes its path via `--rstar-file` -- in CI,
`output_gap` is checked out as a sibling directory (`output_gap/`); to run
locally with `output_gap` checked out as a sibling of this repo:

```
python3 scripts/00_ingest_fred.py && python3 scripts/00_ingest_lw.py && python3 scripts/00_ingest_spf.py
python3 scripts/01_build_benchmarks.py
python3 scripts/02_build_page.py --rstar-file ../output_gap/rstar/outputs/rstar.csv
```

CI runs on `repository_dispatch` from `output_gap`'s `rstar-output-gap.yml`
workflow, plus `workflow_dispatch` for a manual run.

## Sources, in detail

**Laubach-Williams**: pulled from the NY Fed's own published workbook,
`Holston_Laubach_Williams_real_time_estimates.xlsx`
(newyorkfed.org/research/policy/rstar). That workbook is organized as one
sheet *per historical vintage* — e.g. a `"2019Q4"` sheet holds the
real-time estimate as it looked using only data available through
2019Q4, for real-time-analysis purposes. This page wants the single
*current* best estimate of the whole history, so `00_ingest_lw.py`
always reads only the **latest** vintage sheet (sorted by the
`YYYYQ#`-labeled sheet names) and takes its full time series — not an
average or splice across vintages. One-sided (filtered) by construction;
confirmed directly in the workbook's own header text ("All estimates are
one-sided").

**SPF-implied**: `BILL10` (the SPF's 10-year-ahead annualized average
3-month T-bill rate) minus `CPI10` (10-year-ahead CPI inflation), both
median responses from the Philadelphia Fed's SPF. **`BILL10` is asked
only once a year**, in the Q1 survey — confirmed directly (35 non-null
observations across 1992-2026, all in Q1) — unlike `CPI10`, which is
quarterly. The implied real rate this page shows is therefore one point
per year, not quarterly like the others; not interpolated to a false
quarterly cadence.

**SEP-implied**: FRED's `FEDTARMDLR` ("Longer Run FOMC SEP for the Fed
Funds Rate, Median") minus `PCECTPIMDLR` ("Longer Run FOMC SEP for the
PCE Inflation Rate, Median") — both already exist as clean FRED series
via the standard keyless `fredgraph.csv` endpoint, no manual scraping of
the Fed's PDF-only SEP release needed. `FEDTARMDLR` starts 2012;
`PCECTPIMDLR` only starts mid-2015, so the combined SEP-implied series
starts there. Both are event-dated (FOMC meeting days, ~4/year); each
release is snapped to the calendar quarter it falls in.

**TIPS 5y5y forward**: constructed from FRED's `DFII5` and `DFII10`
(5-year and 10-year constant-maturity TIPS real yields) via the standard
forward-rate bootstrap,
`(1+f)^5 = (1+y10)^10 / (1+y5)^5`, computed daily then averaged to
quarterly (`to_quarterly_mean`, same convention used throughout this
project). This is the one benchmark that's a genuine market price, not a
model or survey — it embeds a term premium the other four don't, which
is very likely why it runs persistently above them in recent years
(roughly +1.5 to +2pp above the model/survey cluster as of 2026) rather
than a sign of anything wrong with either side.

**Realized real fed funds rate**: `FEDFUNDS` (quarterly mean) less
trailing 4-quarter core PCE inflation (`100 * ln(PCEPILFE_t /
PCEPILFE_{t-4})`), same log-difference convention used in `../rstar` and
`../unemployment_risk`. Not an r* estimate — the whole point of plotting
it is that it swings well above and below every r* line over the cycle
(deeply negative in the 1970s and 2020-22, sharply positive in the
Volcker disinflation), which is exactly what "policy above/below
neutral" is supposed to look like.

## UC r*: one-sided, not two-sided

Earlier versions of this page showed UC r*'s two-sided (smoothed)
estimate with a ±2 std dev uncertainty band. Switched to the **one-sided
(filtered, real-time)** estimate at the same time this page was rebuilt
around outside benchmarks, specifically so it's an apples-to-apples
comparison with Laubach-Williams (one-sided by construction) rather than
mixing a real-time estimate against a smoothed, backward-looking one.
No uncertainty band is shown for the one-sided series — none exists (see
`../rstar/README.md`: the ±2 std dev band was only ever computed for the
two-sided/smoothed estimate).

## What's not done

- Uncertainty bands on any of the four outside benchmarks (none of the
  four sources published here come with one in a form this pipeline
  ingests).
- Country coverage beyond the US for Laubach-Williams, SPF, and SEP —
  HLW's workbook does include Canada and euro-area columns; not pulled
  here since the page's scope is domestic-vs-outside-benchmark, not a
  multi-country comparison (that was the now-dropped Global Factor's
  job).
- A scheduled CI workflow — doesn't exist for this project yet, matching
  `../rstar` and `../unemployment_risk`'s own "not yet done."
