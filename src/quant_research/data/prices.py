"""Yahoo Finance historical-price adapter, normalization, validation, and cache."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd


NORMALIZED_PRICE_SCHEMA_VERSION = 1
EXCHANGE_TIMEZONE = "America/New_York"
PRICE_COLUMNS = (
    "session_date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
)
_REQUIRED_PROVIDER_FIELDS = ("open", "high", "low", "close", "volume")
_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9.-]+")


class PriceDataError(ValueError):
    """Raised for malformed, ambiguous, or incomplete market-price data."""


class PriceSource(Protocol):
    name: str

    def download(self, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        """Return a provider-shaped frame for one symbol and explicit date range."""


class YahooFinanceSource:
    """Thin, lazily imported adapter for ``yfinance``."""

    name = "yahoo_finance_yfinance"

    def download(self, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("Install the project dependencies to use YahooFinanceSource (yfinance).") from exc
        result = yf.download(
            tickers=symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            actions=True,
            progress=False,
            threads=False,
            group_by="column",
        )
        if not isinstance(result, pd.DataFrame):
            raise PriceDataError("Yahoo Finance returned an unexpected response type")
        return result


def _select_single_symbol(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        selected = None
        for level in range(data.columns.nlevels):
            values = data.columns.get_level_values(level).astype(str)
            if symbol in values:
                selected = data.xs(symbol, axis=1, level=level, drop_level=True)
                break
        if selected is None:
            raise PriceDataError(f"multi-symbol provider response does not contain requested symbol {symbol}")
        if isinstance(selected.columns, pd.MultiIndex):
            raise PriceDataError("provider response still has ambiguous multi-level price columns")
        data = selected
    return data


def normalize_prices(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize one provider response to a validated, one-row-per-session table.

    Naive provider dates are interpreted as exchange session dates. Timezone-aware
    timestamps are converted to New York before extracting the session date.
    Missing adjusted close remains null; it is not substituted with raw close.
    """
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", symbol):
        raise PriceDataError("symbol must be uppercase and ticker-like")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise PriceDataError(f"no price rows returned for {symbol}")

    data = _select_single_symbol(frame, symbol)
    aliases: dict[str, str] = {}
    for column in data.columns:
        label = str(column).strip().lower().replace(" ", "_").replace("-", "_")
        if label == "adjclose":
            label = "adj_close"
        aliases[column] = label
    data = data.rename(columns=aliases)
    if len(set(data.columns)) != len(data.columns):
        raise PriceDataError("provider response has duplicate columns after normalization")

    missing = sorted(set(_REQUIRED_PROVIDER_FIELDS) - set(data.columns))
    if missing:
        raise PriceDataError(f"provider response for {symbol} is missing required fields: {', '.join(missing)}")

    try:
        timestamps = pd.DatetimeIndex(pd.to_datetime(data.index, errors="raise"))
    except (TypeError, ValueError) as exc:
        raise PriceDataError("provider index must contain parseable session timestamps") from exc
    if timestamps.hasnans:
        raise PriceDataError("provider index contains missing timestamps")
    if timestamps.tz is not None:
        timestamps = timestamps.tz_convert(EXCHANGE_TIMEZONE).tz_localize(None)
    session_dates = timestamps.normalize().strftime("%Y-%m-%d")
    if session_dates.duplicated().any():
        duplicates = sorted(set(session_dates[session_dates.duplicated()].tolist()))
        raise PriceDataError(f"multiple rows map to the same session date: {', '.join(duplicates)}")

    normalized = pd.DataFrame(index=range(len(data)))
    normalized["session_date"] = session_dates
    normalized["symbol"] = symbol
    for column in (*_REQUIRED_PROVIDER_FIELDS, "adj_close", "dividends", "stock_splits"):
        if column in data.columns:
            try:
                normalized[column] = pd.to_numeric(data[column].reset_index(drop=True), errors="raise")
            except (TypeError, ValueError) as exc:
                raise PriceDataError(f"field {column} contains non-numeric values") from exc
        elif column in ("dividends", "stock_splits"):
            normalized[column] = 0.0
        else:
            normalized[column] = float("nan")

    for column in _REQUIRED_PROVIDER_FIELDS:
        values = normalized[column]
        if values.isna().any() or not values.map(math.isfinite).all():
            raise PriceDataError(f"required field {column} contains missing or non-finite values")
    for column in ("open", "high", "low", "close"):
        if (normalized[column] <= 0).any():
            raise PriceDataError(f"field {column} must contain positive prices")
    if (normalized["volume"] < 0).any():
        raise PriceDataError("volume cannot be negative")
    if (normalized["high"] < normalized[["open", "low", "close"]].max(axis=1)).any():
        raise PriceDataError("high must be greater than or equal to open, low, and close")
    if (normalized["low"] > normalized[["open", "high", "close"]].min(axis=1)).any():
        raise PriceDataError("low must be less than or equal to open, high, and close")
    for column in ("adj_close", "dividends", "stock_splits"):
        present = normalized[column].dropna()
        if not present.map(math.isfinite).all():
            raise PriceDataError(f"field {column} contains non-finite values")
    if (normalized["adj_close"].dropna() <= 0).any():
        raise PriceDataError("adjusted close must be positive when present")
    if (normalized["dividends"].dropna() < 0).any():
        raise PriceDataError("dividends cannot be negative")
    if (normalized["stock_splits"].dropna() < 0).any():
        raise PriceDataError("stock split ratios cannot be negative")

    return normalized.loc[:, list(PRICE_COLUMNS)].sort_values("session_date", kind="stable").reset_index(drop=True)


def _atomic_write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as temp:
            temp.write(contents)
            temp_name = temp.name
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def _cache_stem(symbol: str, start: str, end: str, interval: str) -> str:
    parts = [_SAFE_PART_RE.sub("_", part) for part in (symbol, start, end, interval)]
    return "_".join(parts)


def _read_normalized_cache(path: Path, symbol: str) -> pd.DataFrame:
    try:
        cached = pd.read_csv(path, dtype={"session_date": "string", "symbol": "string"})
    except (OSError, pd.errors.ParserError) as exc:
        raise PriceDataError(f"could not read normalized cache {path}: {exc}") from exc
    if tuple(cached.columns) != PRICE_COLUMNS:
        raise PriceDataError(f"normalized cache {path} has an unexpected schema")
    if cached.empty:
        raise PriceDataError(f"normalized cache {path} contains no rows")
    if not cached["symbol"].eq(symbol).all():
        raise PriceDataError(f"normalized cache {path} contains a different symbol")
    dates = pd.to_datetime(cached["session_date"], errors="coerce")
    if dates.isna().any() or dates.dt.strftime("%Y-%m-%d").ne(cached["session_date"]).any():
        raise PriceDataError(f"normalized cache {path} contains invalid session dates")
    try:
        numeric = cached.loc[:, list(PRICE_COLUMNS[2:])].apply(pd.to_numeric, errors="raise")
    except (TypeError, ValueError) as exc:
        raise PriceDataError(f"normalized cache {path} contains non-numeric price fields") from exc
    restored = pd.concat([cached.loc[:, ["session_date", "symbol"]], numeric], axis=1)
    return normalize_prices(restored.set_index("session_date"), symbol)


def download_and_cache_prices(
    source: PriceSource,
    symbol: str,
    start: str,
    end: str,
    cache_dir: str | Path = "data",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download (or reuse) one explicit request, retaining raw data and provenance."""
    if pd.Timestamp(start) >= pd.Timestamp(end):
        raise ValueError("start must be earlier than the exclusive end date")
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", symbol):
        raise ValueError("symbol must be uppercase and ticker-like")
    stem = _cache_stem(symbol, start, end, interval)
    root = Path(cache_dir)
    raw_path = root / "raw" / "prices" / f"{stem}.csv"
    normalized_path = root / "normalized" / "prices" / f"{stem}.csv"
    manifest_path = root / "normalized" / "prices" / f"{stem}.manifest.json"

    if normalized_path.is_file() and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PriceDataError(f"could not read cache manifest {manifest_path}: {exc}") from exc
        expected = {
            "provider": source.name,
            "symbol": symbol,
            "requested_start": start,
            "requested_end_exclusive": end,
            "interval": interval,
            "normalized_schema_version": NORMALIZED_PRICE_SCHEMA_VERSION,
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise PriceDataError(f"cache manifest {manifest_path} does not match this request")
        return _read_normalized_cache(normalized_path, symbol)

    raw = source.download(symbol=symbol, start=start, end=end, interval=interval)
    normalized = normalize_prices(raw, symbol)
    session_dates = pd.to_datetime(normalized["session_date"])
    if (session_dates < pd.Timestamp(start)).any() or (session_dates >= pd.Timestamp(end)).any():
        raise PriceDataError("provider returned rows outside the requested [start, end) date range")

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(raw_path, raw.to_csv(index=True, index_label="provider_index"))
    _atomic_write_text(normalized_path, normalized.to_csv(index=False))
    manifest = {
        "provider": source.name,
        "symbol": symbol,
        "requested_start": start,
        "requested_end_exclusive": end,
        "interval": interval,
        "auto_adjust": False,
        "actions_requested": True,
        "exchange_timezone": EXCHANGE_TIMEZONE,
        "normalized_schema_version": NORMALIZED_PRICE_SCHEMA_VERSION,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(normalized),
        "raw_file": raw_path.relative_to(root).as_posix(),
        "normalized_file": normalized_path.relative_to(root).as_posix(),
    }
    _atomic_write_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return normalized
