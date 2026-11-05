# Quant Research Engine

Research and offline paper-trading infrastructure for a proposed universe of roughly 100 U.S. stocks. Includes data ingestion, exploratory earnings studies, conditional strategy accounting, walk-forward pairs research and a simulated cash-funded ledger. No live order execution is implemented.

## Setup

Use Python 3.10 or newer. Create a virtual environment, then install and test from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

Activate the environment or use its Python executable for subsequent commands. Tests use deterministic fixtures and need no API keys. Downloaded data and generated reports are intentionally absent from Git. See [the checked-in findings summary](docs/workflow-completion.md) for results and limitations without the local datasets.

For a new checkout, set `ALPHA_VANTAGE_API_KEY` locally and run the acquisition jobs in this order:

```powershell
python -m quant_research.pilot --config configs/ai_pilot_v1.json
python -m quant_research.research_baseline --download
python -m quant_research.workflow
```

Provider errors or exhausted quotas may leave missing inputs. Inspect `failures.csv` and retry after the provider quota resets; existing caches are reused. Later downloads may differ from the original snapshots, so identical historical results require the original input hashes. The single-Apple pilot below is an archived local example, not an included dataset.

## Completed offline workflow

Run `python -m quant_research.workflow` with cached data for the strict timing gate, corrected/excluded earnings records, self-financing cost accounting, fixed expanding walk-forward pairs evaluation and reproducible reports under `reports/workflow_v2/`. See `docs/workflow-completion.md` for acceptance evidence, exact reproduction commands and material limits. All attempted families are registered in `configs/experiment_registry_v1.json`. This retrospective evaluation has no remaining untouched holdout.

`quant_research.paper.PaperLedger` is an offline SQLite simulated-fill API. It requires an explicit order ID, signal/data versions, timezone-aware signal/quote/current times and a supplied price. It rejects stale data, future quotes, backdated fills, conflicting duplicate IDs, insufficient cash and shorts. It supports concurrent idempotency and a persistent kill switch. No broker or network endpoint exists; short borrow modeling is confined to research accounting until a paper borrow ledger is implemented.

## Earnings execution and statistical-arbitrage baseline

`configs/research_baseline_v1.json` freezes training/evaluation boundaries, four candidate pairs, post-earnings short timing, holding period, borrow assumptions and three transaction-cost levels. Run `python -m quant_research.research_baseline --download` to acquire the evaluation prices and produce local reports, or omit `--download` for offline replay. Install the pinned `statsmodels==0.14.6` dependency for Engle-Granger and ADF diagnostics. Outputs are in `reports/research_baseline_v1/`.

Read `docs/research-baseline-status.md` for the negative initial findings, timing discrepancies and remaining readiness requirements. Formation selection never reads evaluation prices. Pairs that fail the declared filters are not traded; historical correlation is not sufficient. This is conditional research accounting, not a validated paper-trading service. The 2026 evaluation period has now been inspected; preserve that fact in future experiments.

## Ten-stock benchmark pilot

For the exploratory AI-exposure hypothesis, run `python -m quant_research.pilot --config configs/ai_pilot_v1.json`, then `python -m quant_research.ai_comparison`. The predeclared cohort and paired-event definition are in `configs/ai_hypothesis_v1.json`; output is under `reports/ai_pilot_v1`. The comparison asks whether the same event has positive pre-earnings and negative post-earnings SPY-relative returns. Raw rise/drop frequency is also reported. This is a descriptive follow-up, with manual current-exposure classification and no causal or confirmatory claim. Proposed next milestones are in `docs/next-three-days.md`.

After generating the pilot, run `python -m quant_research.consistency` for descriptive consistency checks. `reports/pilot_v1/consistency.md`, `consistency.csv`, and `consistency_by_year.csv` report SPY-outperformance counts, medians, annual means and sensitivity to removing the single largest absolute excess return. The diagnostic preserves the original data and records input/code hashes. It introduces no significance claims or strategy selection; these are follow-up observations on the same sample, not a new holdout.

Install project dependencies, including the pinned `exchange-calendars==4.13.2` calendar implementation. `configs/pilot_v1.json` freezes the 2023-2025 event period, ten-name engineering sample and padded price range. XNYS regular sessions provide the common US equity calendar, with holidays, daylight-saving transitions, early closes and special closures. This shared calendar is an explicit convention for the NYSE/Nasdaq sample; it does not describe extended-hours trading.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m quant_research.pilot
python -m quant_research.pilot --offline
```

The first command reads `ALPHA_VANTAGE_API_KEY` from the environment and caches earnings and Yahoo prices. It reuses existing snapshots and records attempted new earnings requests in a local UTC-day ledger, capped at ten with 13-second spacing. Other programs' API usage is not visible to this ledger; provider rejection is recorded as a failure. Do not run concurrent collectors against this ledger. Offline replay makes no provider requests and uses the same config and snapshots.

Outputs under `reports/pilot_v1/`: `report.md`, `by_stock.csv`, `event_windows.csv`, `event_audit.csv`, `timing_counts.csv`, `missing_bars.csv`, `failures.csv`, and a manifest with input/code hashes and calendar version. Prices and calendar are exported alongside the report. Stock-minus-SPY comparisons use identical session endpoints and exclude either side's missing bars. Coincident events across different stocks do not exclude the SPY reference. Same-stock overlapping windows remain excluded.

Means are descriptive averages over valid event observations, not portfolio returns or executable profits. No p-values or significance claims are made in this pilot; event dependence and multiple testing require a separately specified inference design. All vendor release labels and estimates remain unverified. This current-name sample is not historically representative, scanner-selected or survivorship-free. Three years of retrospective observations are not an untouched strategy holdout.

## Alpha Vantage exploratory importer

Set `ALPHA_VANTAGE_API_KEY` in the process environment for new requests. Existing raw files can be imported offline:

```powershell
python -m quant_research.data.alpha_vantage --symbol AAPL --raw data/raw/alpha_vantage_probe/AAPL_earnings.json
```

Omit `--raw` to fetch one symbol, reusing its local raw cache on subsequent runs. The importer makes one request on a cache miss and stops on provider notices; it does not automatically retry or refresh. Cache entries are snapshots, not a freshness guarantee. Generated files remain under ignored `data/`.

`audit.csv` preserves every normalized event and exclusions; `events.csv` contains eligible timing labels. Estimates are retained as vendor fields and never used for beat/miss classification without separate verification. `coarse_boundary_v1` maps pre-market to local midnight and post-market to local end-of-day solely as explicit session-boundary proxies, not actual publication timestamps. Unknown timing is excluded. Vendor fiscal period labels remain unverified. The normalization manifest records the payload hash and assumptions; fetched raw responses also have retrieval manifests.

The first local pilot is in `reports/apple_pilot/`, using Apple's 2025-01-30 release, Yahoo adjusted closes from 2025-01-22 through 2025-02-10, and an explicit finite list of regular exchange sessions. Its calendar is specific to this pilot, not a reusable holiday calendar. Reproduce after importing the cached inputs:

```powershell
python -m quant_research.earnings_event_study --events data/normalized/apple_pilot/events.csv --prices data/normalized/prices/AAPL_2025-01-22_2025-02-11_1d.csv --calendar data/normalized/apple_pilot/calendar.csv --output reports/apple_pilot
```

This single-event descriptive pilot has no statistical power, cost model, portfolio accounting or out-of-sample strategy validation. Reaction returns include the announcement move and are not executable signal profits. See `docs/alpha-vantage-sample-validation.md` for unresolved consensus and timing provenance. The broader pilot implements calendar generation; provider-notice classification remains limited.

## Universe file

Edit `configs/universe.json`. Its `schema_version` must be `1`; each security has a symbol, name, industry, inclusive `valid_from` date, optional exclusive `valid_to` date, source, and inclusion rationale. The checked-in file is intentionally an empty template; no stock membership has been asserted yet. Use effective-dated rows for membership or industry changes rather than overwriting history. The machine-readable contract is `configs/universe.schema.json` and the Python loader enforces the same core constraints without requiring a JSON Schema library.

```json
{
  "schema_version": 1,
  "securities": [
    {
      "symbol": "EXAMPLE",
      "name": "Example Company",
      "industry": "Example Industry",
      "valid_from": "2020-01-01",
      "valid_to": null,
      "source": "Document the membership source",
      "rationale": "Document why this security is included"
    }
  ]
}
```

Validate the file with:

```powershell
py -m quant_research.universe
```

## Price data

The initial provider is Yahoo Finance through `yfinance`. The adapter requests unadjusted OHLCV plus corporate actions (`auto_adjust=False`). Normalized rows have a New York exchange `session_date` represented as `YYYY-MM-DD`, the symbol, OHLC, adjusted close, volume, dividends, and split ratio. If a provider omits adjusted close, it remains missing; it is never silently replaced with raw close.

Use `download_and_cache_prices` from `quant_research.data.prices` with explicit start/end dates. A small example:

```python
from quant_research.data.prices import YahooFinanceSource, download_and_cache_prices

prices = download_and_cache_prices(
    YahooFinanceSource(),
    symbol="AAPL",
    start="2020-01-01",
    end="2021-01-01",
    cache_dir="data",
)
```

The end date follows Yahoo Finance's exclusive end-date convention. Provider responses are retained under `data/raw/prices/`; validated normalized CSVs and JSON provenance manifests are stored under `data/normalized/prices/`. Identical requests reuse the normalized cache. Cache data is ignored by Git. The manifest records request parameters, UTC retrieval time, provider, schema version, and row count. Yahoo Finance coverage, corporate-action adjustments, symbol history, missing sessions, and survivorship limitations must be considered before interpreting research results.

## Tests

Install the dev extra, then run:

```powershell
py -m pytest
```

Tests use fixed in-memory provider fixtures and do not contact Yahoo Finance.

## Exploratory earnings event study

The baseline consumes researcher-supplied event and price files plus an explicit exchange calendar. It does not fetch or certify historical earnings timestamps, point-in-time analyst consensus, or EPS data.

The events CSV requires event_id, symbol, fiscal_period, announcement_at, and source. announcement_at must include a timezone offset. To classify beats and misses, also provide actual_eps, consensus_eps, and consensus_available_at; consensus published after the announcement is rejected. Events without consensus remain unclassified.

The calendar CSV requires session_date and close_at, with timezone offsets on close_at. Supply correct sessions, including holidays and early closes. Each release maps to the first supplied close strictly after its timestamp. The prices CSV requires session_date, symbol, and adj_close. Missing bars are exclusions and are never forward-filled. Same-symbol events whose configured spans overlap are retained with an exclusion reason and omitted from summary statistics.

Default close-to-close windows are pre-runup (-5,-1), reaction (-1,0), and post-event (0,5), relative to the mapped reaction session. Run with:

    py -m pip install -e ".[dev]"
    py -m quant_research.earnings_event_study --events events.csv --prices prices.csv --calendar calendar.csv

The command writes event_windows.csv, event_summary.csv, and manifest.json to reports/earnings_event_study. Summaries include one-sample t-test p-values and Benjamini-Hochberg adjusted values across the window/group family in that run. These are exploratory diagnostics: overlapping windows violate the t-test independence assumption, and correction applies only to the recorded family. No fills or trading costs are simulated.

## Scope limits

This is research and offline paper-trading infrastructure. Strategy outputs are conditional simulations. There are no Monte Carlo simulations, broker connections, or live order routes. The paper ledger rejects short positions until a borrow/locate ledger is implemented.
