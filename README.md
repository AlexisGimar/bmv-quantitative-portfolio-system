# BMV Quant Portfolio System

An educational project with three methodology notebooks:

1. `notebooks/methodology/01_data_pipeline.ipynb`: maintain a PostgreSQL price database.
2. `notebooks/methodology/02_quant_screener.ipynb`: calculate factors and rank eligible assets.
3. `notebooks/methodology/03_backtesting.ipynb`: evaluate monthly portfolios and costs.

Shared calculations stay in `src/features.py`, `src/screener.py`, and `src/portfolio.py`.
`src/database.py` reads local connection settings. The `competition` folder is outside
this methodology workflow.

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
Run notebook 01 first, inspect its final reports, then run notebook 02. Run notebook 03 when you want to study historical performance.
Keep the original files `data/raw/datosReto.txt` and `data/raw/datosRetoDescripcion.txt` in place.

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
with invalid observations in the last 252 observations, or unresolved rejected dates,
are excluded. Invalid observations are not silently removed from the timeline.
Inspect notebook 01's `missing_adjusted` and `pending_rejections` reports if many assets
are excluded.

The existing freshness limits, complete/finite-factor checks, safe z-scores, and equal
block weights are preserved. The 5/20/60 windows count available observations, not calendar
days. The freshness reference is the latest date in the loaded database, which is displayed
at the end. Liquidity is a zero-volume-frequency proxy, not an order-size or spread model.
Notebook 03 studies this methodology historically, subject to the limitations below.

## Understanding notebook 03

The section order is unchanged. Monthly selection still uses the same factors and
weighting rules. `src/backtest.py` handles daily execution in two loops: sells, then buys.

- Start orders on the first market day after the monthly signal. Missing quotes
  delay orders: keep cash for buys and retain holdings awaiting a sale.
- Trades use valid quotes only. The last observed price may value an existing holding,
  but never execute a trade. Review the notebook's stale-valuation and pending-order table.
- Sells fund buys. Available cash is shared proportionally across executable buys;
  there is no borrowing. Unfinished orders are replaced at the next monthly rebalance.
- Monthly target budgets are fixed at rebalance. Target units are set at each asset's
  first valid execution quote. Cash earns 0%, and quantities may be fractional.
- Turnover measures actual purchases plus sales relative to starting period capital.
  Fees reduce cash on the execution date. Cost scenarios rerun the daily simulation.
- `final_trades` shows actual dates, prices, quantities, and trade amounts. The diagnostics
  show waiting days, unfinished orders, cash weights, and the oldest holding quote.
- Long-unquoted holdings retain their last valuation and must be investigated. No
  delisting recovery value is invented. Adjusted-price units and unlimited volume
  make this an educational return model, not a brokerage execution simulator.
- 2021–2024 is calibration; 2025 onward is exploratory validation already inspected
  during development. The Defensive/category score-volatility/no-buffer V1 remains provisional.
- Today's universe creates survivorship bias; revised prices are not a point-in-time archive.
  CAGR uses elapsed time; other risk statistics use monthly observations.

Existing exports are not regenerated by code changes. Rerun notebook 02 to refresh them.

## Daily use

Open the saved notebooks, select the project kernel, and run 01 followed by 02.
After updating the code, restart the kernel and run from the top to load the updated
functions. Existing code-cell outputs were cleared to avoid showing stale results.
Review the progress output and final quality reports. `RETRY_UNAVAILABLE=false` in `.env`
can skip assets with no history after the first load, but known rejected dates are still
recovered. Never run older unsaved notebook definitions after updating files on disk.

## Offline checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use actual notebook functions with synthetic data and mocked database/provider
interfaces. They validate maintenance decisions, rejection handling, SQL generation, and
screener eligibility, portfolio weights, backtest valuation, turnover, and costs. They do not replace an integration run against PostgreSQL and Yahoo.
Dependencies use compatible ranges rather than an exact lock file.

## Sharing

Clear notebook outputs before publishing. `.env` is local and ignored by Git; `.env.example`
is the shareable template. Files already tracked by Git are not removed by adding an ignore
rule. Share the Actinver data files only if you have permission to distribute them.
