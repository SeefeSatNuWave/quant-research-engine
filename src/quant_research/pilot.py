"""Reproducible exploratory earnings windows with matched SPY intervals."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import exchange_calendars as xcals
import pandas as pd

from quant_research.data.alpha_vantage import fetch, normalize
from quant_research.data.prices import YahooFinanceSource, download_and_cache_prices, _atomic_write_text
from quant_research.earnings_event_study import build_event_windows, DEFAULT_WINDOWS


def calendar(start: str, end: str) -> pd.DataFrame:
    schedule = xcals.get_calendar("XNYS", start=start, end=end).schedule
    return pd.DataFrame({"session_date": schedule.index.strftime("%Y-%m-%d"),
                         "close_at": schedule.close.astype(str).values})


def compare(events: pd.DataFrame, prices: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    stock = build_event_windows(events, prices, sessions)
    benchmark_events = events.copy()
    # Compute per event: cross-stock coincidence must not count as SPY event overlap.
    benchmark = []
    for _, event in benchmark_events.iterrows():
        event["symbol"] = "SPY"
        benchmark.append(build_event_windows(pd.DataFrame([event]), prices, sessions))
    spy = pd.concat(benchmark)[["event_id", "window", "return", "exclusion_reason"]]
    merged = stock.merge(spy, on=["event_id", "window"], suffixes=("", "_spy"), validate="one_to_one")
    merged["excess_return"] = merged["return"] - merged["return_spy"]
    bad = merged.exclusion_reason.notna() | merged.exclusion_reason_spy.notna()
    merged.loc[bad, "excess_return"] = float("nan")
    return merged


def run(config_path: Path, offline: bool = False) -> None:
    config = json.loads(config_path.read_text())
    output = Path("reports") / config["version"]
    output.mkdir(parents=True, exist_ok=True)
    cache = Path("data/raw/alpha_vantage")
    cache.mkdir(parents=True, exist_ok=True)
    ledger_path = cache / "request_ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    day = datetime.now(timezone.utc).date().isoformat()
    sessions = calendar(config["price_start"], config["price_end_exclusive"])
    sessions.to_csv(output / "calendar.csv", index=False)
    audits, failures, frames = [], [], []
    for symbol in config["symbols"]:
        try:
            cached = cache / f"{symbol}.json"
            if not cached.exists():
                if offline or ledger.get(day, 0) >= config["max_new_earnings_requests"]:
                    raise ValueError("No cache: offline or conservative daily request budget exhausted")
                ledger[day] = ledger.get(day, 0) + 1
                _atomic_write_text(ledger_path, json.dumps(ledger))
                time.sleep(13)  # conservative pacing; each failed call still consumes budget
            raw = fetch(symbol, cache)
            audit = normalize(raw, symbol, datetime.now(timezone.utc).date())
            dates = audit.announcement_at.str[:10]
            audit = audit.loc[(dates >= config["event_start"]) & (dates < config["event_end_exclusive"])]
            audits.append(audit)
        except Exception as exc:
            failures.append({"symbol": symbol, "stage": "earnings", "reason": str(exc)})
    for symbol in config["symbols"] + [config["benchmark"]]:
        try:
            if offline:
                path = Path("data/normalized/prices") / f"{symbol}_{config['price_start']}_{config['price_end_exclusive']}_1d.csv"
                prices = pd.read_csv(path)
            else:
                prices = download_and_cache_prices(YahooFinanceSource(), symbol, config["price_start"], config["price_end_exclusive"])
            frames.append(prices)
        except Exception:
            failures.append({"symbol": symbol, "stage": "prices", "reason": "Price download/cache unavailable"})
    pd.DataFrame(failures, columns=["symbol", "stage", "reason"]).to_csv(output / "failures.csv", index=False)
    if not audits or not frames:
        raise ValueError("Insufficient data; see failures.csv")
    audit = pd.concat(audits, ignore_index=True)
    audit.to_csv(output / "event_audit.csv", index=False)
    events = audit.loc[audit.exclusion_reason.isna()].copy()
    if events.empty:
        raise ValueError("No events with usable timing")
    prices = pd.concat(frames, ignore_index=True)
    prices.to_csv(output / "prices.csv", index=False)
    missing_bars = []
    expected = sessions.loc[sessions.session_date < config['price_end_exclusive'], 'session_date']
    for symbol in config['symbols'] + [config['benchmark']]:
        available = set(prices.loc[(prices.symbol == symbol) & prices.adj_close.notna(), 'session_date'])
        missing_bars.extend({'symbol': symbol, 'session_date': d, 'reason': 'missing_adjusted_close'}
                            for d in expected if d not in available)
    pd.DataFrame(missing_bars, columns=['symbol', 'session_date', 'reason']).to_csv(output / 'missing_bars.csv', index=False)
    audit.groupby(['symbol', 'vendor_report_time'], dropna=False).size().rename('events').to_csv(output / 'timing_counts.csv')
    results = compare(events, prices, sessions)
    results.to_csv(output / "event_windows.csv", index=False)
    rows = []
    for symbol in config["symbols"]:
        for window in DEFAULT_WINDOWS:
            subset = results.loc[(results.symbol == symbol) & (results.window == window)]
            valid = subset.loc[subset.excess_return.notna()]
            rows.append({"symbol": symbol, "window": window, "events": len(subset), "paired_valid": len(valid),
                         "excluded": len(subset)-len(valid), "mean_stock_return": valid["return"].mean(),
                         "mean_spy_return": valid.return_spy.mean(), "mean_excess_return": valid.excess_return.mean()})
    summary = pd.DataFrame(rows)
    summary.to_csv(output / "by_stock.csv", index=False)
    limitations = "Exploratory descriptive sample. All timing labels and consensus availability remain unverified; boundary timestamps are proxies. Vendor fiscal labels are retained. SPY excess is stock minus SPY simple return, not risk-adjusted alpha. No significance claims, strategy fills, costs, or out-of-sample strategy validation. Current-name sample has survivorship bias."
    report = ["# Three-year exploratory earnings pilot", "", limitations, "", config["selection"], "",
              f"Events imported: {len(audit)}; unknown timing excluded: {int(audit.exclusion_reason.notna().sum())}; acquisition failures: {len(failures)}.", "",
              "| Stock | Window | Paired events | Excluded | Mean stock | Mean SPY | Mean excess |", "|---|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        report.append(f"| {row['symbol']} | {row['window']} | {row['paired_valid']} | {row['excluded']} | {row['mean_stock_return']:.2%} | {row['mean_spy_return']:.2%} | {row['mean_excess_return']:.2%} |")
    report.extend(['', f'Missing expected adjusted-close bars: {len(missing_bars)}. Every included event uses unverified vendor pre/post-market timing.', '',
                   'See event_audit.csv and timing_counts.csv for timing coverage, missing_bars.csv for price gaps, failures.csv for unavailable symbols, and event_windows.csv for per-window exclusions. All requested names appear in by_stock.csv even when unavailable.'])
    if failures:
        report.extend(['', 'Acquisition failures:'] + [f"- {f['symbol']} ({f['stage']}): {f['reason']}" for f in failures])
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [config_path, Path(__file__), *cache.glob('*.json'), output/'calendar.csv', output/'prices.csv', output/'event_audit.csv']}
    _atomic_write_text(output / "manifest.json", json.dumps({"config": config, "calendar": "XNYS regular sessions used for US equity sample", "calendar_version": importlib.metadata.version("exchange-calendars"), "windows": DEFAULT_WINDOWS, "sha256": hashes, "limitations": limitations}, indent=2))
    print(f"Report: {output / 'report.md'}; events={len(audit)}; failures={len(failures)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/pilot_v1.json"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    run(args.config, args.offline)
