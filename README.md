# Quant Research Engine

An early, reproducible research codebase for a roughly 100-stock U.S. equity universe. This first increment establishes only a versioned universe format and a Yahoo Finance price-data ingestion foundation. It does not implement signals, strategy logic, backtests, or trading.

## Setup

Use Python 3.10 or newer. From this directory, install the project and development dependencies:

```powershell
py -m pip install -e ".[dev]"
```

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

## Scope limits

This is research and paper-trading infrastructure only. There are no strategy implementations, Monte Carlo simulations, broker connections, or live order routes.
