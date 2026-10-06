# BMV Quant Portfolio System

An educational project with two notebooks:

1. `01_data_pipeline.ipynb`: maintain a PostgreSQL price database.
2. `02_quant_screener.ipynb`: calculate factors and rank eligible assets.

## First-time setup

From the project root, with Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name bmv-quant --display-name "Python (bmv-quant)"
Copy-Item .env.example .env
```

Create a PostgreSQL database and configure your local `.env` with the username,
password, host, port, and database name. Select the **Python (bmv-quant)** kernel.
Run notebook 01 first, inspect its final reports, then run notebook 02.
Keep the original files `data/datosReto.txt` and `data/datosRetoDescripcion.txt` in place.

Notebook 01 runs `sql/schema.sql` automatically. The schema creates tables in a new
database and adds maintenance columns/tables to a database from this project. It does
not migrate arbitrary experimental schemas. No credentials belong in the notebooks.

## Understanding notebook 01

The order remains: configuration → schema → asset universe → download helpers →
update → final validation.

`plan_download` explains the maintenance decision for each asset:

- No stored prices: initial history from `HISTORY_START`.
- Missing adjusted prices: full history recovery, including the earliest stored date.
- Unresolved rejected dates: retry their history.
- No previous recorded refresh, or 30 days since the last refresh: full history refresh.
- Otherwise: incremental download with seven calendar days of overlap.

The settings `HISTORY_REFRESH_DAYS = 30` and `OVERLAP_DAYS = 7` are in the first code cell.
If adjusted prices differ in the overlap, the incremental response is replaced by a
full-history download. This avoids joining incompatible adjustment bases. Older provider
corrections outside the overlap may remain until the scheduled refresh.

`insert_prices` saves valid prices and rejection records together in one transaction.
It updates existing observations only when values differ and inserts new dates without
duplicate keys. All OHLCV values and their flags are updated together. `rows_affected`
counts inserted or changed price rows, not unchanged observations or rejection records.

Rejected observations are stored in `price_rejections`, including dates omitted from a
full-history response that were already in the database. A valid response for the exact
date clears its rejection. Empty responses do not clear unresolved dates. OHLC consistency
warnings are retained in `quality_flags`; the original provider values are not invented
or repaired. Nonpositive closes, missing/non-finite values, and invalid volumes are rejected.
Nonpositive Open/High/Low values remain explicitly flagged warnings.

The first run after this upgrade can take as long as a historical load: existing adjusted
prices and previously untracked gaps need recovery. A permanently invalid provider row
will remain pending and be retried on later runs. Fixing it requires an explicit data-source
or quality-policy decision; the pipeline does not fabricate a value.

The current day is excluded. Weekend/holiday requests may return no new dates. A missing
response does not prove completeness. The pipeline does not invent a full exchange calendar
or discover every date Yahoo has never returned; known rejections and stored-date omissions
are tracked, and regular full refreshes can recover historical dates the provider later adds.

## Understanding notebook 02

The order remains: connection → data → features → freshness/eligibility → standardization
→ score → candidate pool.

Returns, momentum, volatility, and current drawdown use `adjusted_close`.
`pct_change(fill_method=None)` preserves missing returns rather than filling gaps with
zero returns. Missing or invalid stored prices are kept as missing observations. Assets
with any invalid stored prices or unresolved rejected dates are excluded until recovered.
Inspect notebook 01's `missing_adjusted` and `pending_rejections` reports if many assets
are excluded.

The existing freshness limits, complete/finite-factor checks, safe z-scores, and equal
block weights are preserved. The 5/20/60 windows count available observations, not calendar
days. The freshness reference is the latest date in the loaded database, which is displayed
at the end. Liquidity is a zero-volume-frequency proxy, not an order-size or spread model.
The model is a baseline screener and has not been validated through a strategy backtest.

## Daily use

Open the saved notebooks, select the project kernel, and run 01 followed by 02.
Review the progress output and final quality reports. `RETRY_UNAVAILABLE=false` in `.env`
can skip assets with no history after the first load, but known rejected dates are still
recovered. Never run older unsaved notebook definitions after updating files on disk.

## Offline checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use actual notebook functions with synthetic data and mocked database/provider
interfaces. They validate maintenance decisions, rejection handling, SQL generation, and
screener eligibility. They do not replace an integration run against PostgreSQL and Yahoo.
Dependencies use compatible ranges rather than an exact lock file.

## Sharing

Clear notebook outputs before publishing. `.env` is local and ignored by Git; `.env.example`
is the shareable template. Files already tracked by Git are not removed by adding an ignore
rule. Share the Actinver data files only if you have permission to distribute them.
