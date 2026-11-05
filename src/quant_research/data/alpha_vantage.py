"""Cached earnings imports with explicit, exploratory date-only assumptions."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from quant_research.data.prices import _atomic_write_text


def normalize(payload: dict, symbol: str, as_of: date) -> pd.DataFrame:
    """Retain estimates as vendor fields, never assert historical availability."""
    if payload.get("symbol") != symbol or not payload.get("quarterlyEarnings"):
        raise ValueError("Missing earnings or mismatched symbol")
    rows = []
    seen = set()
    for item in payload["quarterlyEarnings"]:
        period = date.fromisoformat(item["fiscalDateEnding"])
        reported = date.fromisoformat(item["reportedDate"])
        if period in seen or reported > as_of or period > reported:
            raise ValueError("Duplicate period or invalid/future earnings date")
        seen.add(period)
        timing = item.get("reportTime")
        # A boundary proxy, not a claimed release timestamp. Session mapping is
        # descriptive; no fill at this proxy is assumed.
        proxy = pd.Timestamp(str(reported) + (" 23:59:59" if timing == "post-market" else " 00:00:00"), tz="America/New_York")
        rows.append({"event_id": f"{symbol}:{period}", "symbol": symbol,
                     "fiscal_period": str(period), "announcement_at": proxy.isoformat(),
                     "source": "alpha_vantage:EARNINGS", "timing_policy": "coarse_boundary_v1",
                     "vendor_report_time": timing, "consensus_verified": False,
                     "vendor_actual_eps": item.get("reportedEPS"),
                     "vendor_estimated_eps": item.get("estimatedEPS"),
                     "exclusion_reason": None if timing in ("pre-market", "post-market") else "unknown_release_timing"})
    return pd.DataFrame(rows)


def fetch(symbol: str, cache: Path, key: str | None = None) -> dict:
    """One request on cache miss; no retry that could exhaust a daily quota."""
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", symbol):
        raise ValueError("Invalid symbol")
    path = cache / f"{symbol}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    key = key or os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is required on cache miss")
    url = "https://www.alphavantage.co/query?" + urlencode({"function": "EARNINGS", "symbol": symbol, "apikey": key})
    try:
        with urlopen(url, timeout=30) as response:
            body = response.read().decode("utf-8")
    except Exception:
        raise ValueError("Alpha Vantage transport failed; credential-bearing details withheld") from None
    if key in body:
        raise ValueError("Provider echoed credential; response discarded")
    payload = json.loads(body)
    if any(k in payload for k in ("Information", "Note", "Error Message")):
        raise ValueError("Provider rejected request or reached quota; no data cached")
    normalize(payload, symbol, datetime.now(timezone.utc).date())
    _atomic_write_text(path, body)
    _atomic_write_text(path.with_suffix(".manifest.json"), json.dumps({
        "provider": "alpha_vantage", "function": "EARNINGS", "symbol": symbol,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(body.encode()).hexdigest()}, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--raw", type=Path, help="Import an existing raw response without network")
    parser.add_argument("--output", type=Path, default=Path("data/normalized/earnings"))
    args = parser.parse_args()
    payload = json.loads(args.raw.read_text(encoding="utf-8")) if args.raw else fetch(args.symbol, Path("data/raw/alpha_vantage"))
    frame = normalize(payload, args.symbol, datetime.now(timezone.utc).date())
    args.output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output / "audit.csv", index=False)
    frame.loc[frame.exclusion_reason.isna()].to_csv(args.output / "events.csv", index=False)
    _atomic_write_text(args.output / "manifest.json", json.dumps({
        "schema_version": 1, "timing_policy": "coarse_boundary_v1",
        "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "limitations": "Exploratory only; vendor fiscal labels; unverified consensus and release timing. No simulated fills."}, indent=2))


if __name__ == "__main__":
    main()
