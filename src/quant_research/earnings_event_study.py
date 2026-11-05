"""Exploratory earnings event study using explicit publication times and sessions."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Mapping

import pandas as pd
from scipy.stats import ttest_1samp

from quant_research import __version__

DEFAULT_WINDOWS: dict[str, tuple[int, int]] = {
    "pre_runup": (-5, -1),
    "event_reaction": (-1, 0),
    "post_event": (0, 5),
}


class EventStudyError(ValueError):
    """Raised when event, calendar, or price inputs are ambiguous."""


def _timestamp(value: object, field: str) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise EventStudyError(f"{field} must be a valid timezone-aware timestamp") from exc
    if pd.isna(result) or result.tzinfo is None:
        raise EventStudyError(f"{field} must include a UTC offset or timezone")
    return result.tz_convert("UTC")


def _session_date(value: object) -> str:
    result = pd.Timestamp(value)
    if pd.isna(result) or result.strftime("%Y-%m-%d") != str(value):
        raise EventStudyError("session_date values must use YYYY-MM-DD format")
    return str(value)


def validate_events(events: pd.DataFrame) -> pd.DataFrame:
    required = {"event_id", "symbol", "fiscal_period", "announcement_at", "source"}
    missing = required - set(events.columns)
    if missing:
        raise EventStudyError(f"events missing required columns: {', '.join(sorted(missing))}")
    data = events.copy()
    if data.empty:
        raise EventStudyError("events must contain at least one row")
    for field in ("event_id", "symbol", "fiscal_period", "source"):
        if data[field].isna().any() or data[field].astype(str).str.strip().eq("").any():
            raise EventStudyError(f"{field} must be populated for every event")
    if data["event_id"].duplicated().any():
        raise EventStudyError("event_id values must be unique")
    data["symbol"] = data["symbol"].astype(str).str.upper()
    if not data["symbol"].str.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}").all():
        raise EventStudyError("symbol values must be uppercase ticker-like strings")
    data["announcement_at_utc"] = [_timestamp(value, "announcement_at") for value in data["announcement_at"]]
    actual = data["actual_eps"].notna() if "actual_eps" in data else pd.Series(False, index=data.index)
    consensus = data["consensus_eps"].notna() if "consensus_eps" in data else pd.Series(False, index=data.index)
    if not actual.equals(consensus):
        raise EventStudyError("actual_eps and consensus_eps must be supplied together")
    data["surprise_group"] = "unclassified"
    classified = actual & consensus
    if classified.any():
        if "consensus_available_at" not in data:
            raise EventStudyError("consensus_available_at is required when consensus EPS is supplied")
        available = {
            index: _timestamp(data.at[index, "consensus_available_at"], "consensus_available_at")
            for index in data.index[classified]
        }
        if any(available[index] > data.at[index, "announcement_at_utc"] for index in available):
            raise EventStudyError("consensus must have been available no later than the announcement")
        actual_eps = pd.to_numeric(data["actual_eps"], errors="coerce")
        consensus_eps = pd.to_numeric(data["consensus_eps"], errors="coerce")
        if not actual_eps[classified].map(math.isfinite).all() or not consensus_eps[classified].map(math.isfinite).all():
            raise EventStudyError("EPS values must be numeric when supplied")
        data.loc[classified, "surprise_group"] = "meet"
        data.loc[classified & (actual_eps > consensus_eps), "surprise_group"] = "beat"
        data.loc[classified & (actual_eps < consensus_eps), "surprise_group"] = "miss"
    return data


def validate_calendar(calendar: pd.DataFrame) -> pd.DataFrame:
    required = {"session_date", "close_at"}
    missing = required - set(calendar.columns)
    if missing:
        raise EventStudyError(f"calendar missing required columns: {', '.join(sorted(missing))}")
    data = calendar.loc[:, ["session_date", "close_at"]].copy()
    if data.empty:
        raise EventStudyError("calendar must contain sessions")
    data["session_date"] = [_session_date(value) for value in data["session_date"]]
    data["close_at_utc"] = [_timestamp(value, "close_at") for value in data["close_at"]]
    if data["session_date"].duplicated().any() or data["close_at_utc"].duplicated().any():
        raise EventStudyError("calendar session dates and close timestamps must be unique")
    data = data.sort_values("close_at_utc", kind="stable").reset_index(drop=True)
    if not data["close_at_utc"].is_monotonic_increasing:
        raise EventStudyError("calendar closes must be strictly increasing")
    if not pd.to_datetime(data["session_date"]).is_monotonic_increasing:
        raise EventStudyError("calendar session dates must increase with close timestamps")
    return data


def map_events_to_sessions(events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Map each release to the first supplied close strictly after publication."""
    data, sessions = validate_events(events), validate_calendar(calendar)
    closes = sessions["close_at_utc"].tolist()
    mapped = []
    for _, event in data.iterrows():
        index = next((i for i, close in enumerate(closes) if close > event["announcement_at_utc"]), None)
        mapped.append({
            "event_id": event["event_id"],
            "reaction_session": None if index is None else sessions.iloc[index]["session_date"],
            "calendar_index": index,
            "mapping_exclusion": "no_calendar_close_after_announcement" if index is None else None,
        })
    return data.merge(pd.DataFrame(mapped), on="event_id", validate="one_to_one")


def build_event_windows(events: pd.DataFrame, prices: pd.DataFrame, calendar: pd.DataFrame,
                        windows: Mapping[str, tuple[int, int]] = DEFAULT_WINDOWS) -> pd.DataFrame:
    """Calculate adjusted close returns; missing price bars are retained as exclusions."""
    if not windows or any(
        not name or isinstance(start, bool) or isinstance(end, bool)
        or not isinstance(start, int) or not isinstance(end, int) or start >= end
        for name, (start, end) in windows.items()
    ):
        raise EventStudyError("each event window must have increasing offsets")
    required = {"session_date", "symbol", "adj_close"}
    missing = required - set(prices.columns)
    if missing:
        raise EventStudyError(f"prices missing required columns: {', '.join(sorted(missing))}")
    px = prices.loc[:, ["session_date", "symbol", "adj_close"]].copy()
    px["session_date"] = [_session_date(value) for value in px["session_date"]]
    px["symbol"] = px["symbol"].astype(str).str.upper()
    numeric_close = pd.to_numeric(px["adj_close"], errors="coerce")
    if (px["adj_close"].notna() & numeric_close.isna()).any():
        raise EventStudyError("adjusted closes must be numeric or explicitly missing")
    px["adj_close"] = numeric_close
    if px.duplicated(["symbol", "session_date"]).any():
        raise EventStudyError("prices contain duplicate symbol/session rows")
    if (px["adj_close"].dropna() <= 0).any() or not px["adj_close"].dropna().map(math.isfinite).all():
        raise EventStudyError("adjusted closes must be positive")
    sessions = validate_calendar(calendar)
    mapped = map_events_to_sessions(events, sessions)
    lookup = px.set_index(["symbol", "session_date"])["adj_close"]
    span_start = min(start for start, _ in windows.values())
    span_end = max(end for _, end in windows.values())
    spans: dict[str, list[tuple[int, int, str]]] = {}
    for _, event in mapped.iterrows():
        if pd.notna(event["calendar_index"]):
            start = int(event["calendar_index"]) + span_start
            end = int(event["calendar_index"]) + span_end
            spans.setdefault(event["symbol"], []).append((start, end, event["event_id"]))
    overlapping_ids: set[str] = set()
    for symbol_spans in spans.values():
        active: list[tuple[int, int, str]] = []
        for start, end, event_id in sorted(symbol_spans):
            active = [other for other in active if other[1] > start]
            if active:
                overlapping_ids.add(event_id)
                overlapping_ids.update(other[2] for other in active if other[0] < end)
            active.append((start, end, event_id))
    output = []
    for _, event in mapped.iterrows():
        for name, (start, end) in windows.items():
            row = {"event_id": event["event_id"], "symbol": event["symbol"],
                   "fiscal_period": event["fiscal_period"], "announcement_at_utc": event["announcement_at_utc"],
                   "reaction_session": event["reaction_session"], "surprise_group": event["surprise_group"],
                   "window": name, "start_offset": start, "end_offset": end,
                   "return": float("nan"), "exclusion_reason": None,
                   "overlap_excluded": event["event_id"] in overlapping_ids}
            if pd.isna(event["calendar_index"]):
                row["exclusion_reason"] = event["mapping_exclusion"]
            else:
                left, right = int(event["calendar_index"]) + start, int(event["calendar_index"]) + end
                if left < 0 or right >= len(sessions):
                    row["exclusion_reason"] = "window_outside_calendar"
                else:
                    start_date, end_date = sessions.iloc[left]["session_date"], sessions.iloc[right]["session_date"]
                    row["start_session"], row["end_session"] = start_date, end_date
                    p0 = lookup.get((event["symbol"], start_date), float("nan"))
                    p1 = lookup.get((event["symbol"], end_date), float("nan"))
                    if pd.isna(p0) or pd.isna(p1):
                        row["exclusion_reason"] = "missing_adjusted_close_at_window_endpoint"
                    elif any(pd.isna(lookup.get((event["symbol"], d), float("nan")))
                             for d in sessions.iloc[left:right + 1]["session_date"]):
                        row["exclusion_reason"] = "missing_adjusted_close_inside_window"
                    else:
                        row["return"] = float(p1 / p0 - 1)
            if row["overlap_excluded"] and row["exclusion_reason"] is None:
                row["exclusion_reason"] = "overlapping_same_symbol_event_window"
            output.append(row)
    return pd.DataFrame(output)


def _bh(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted, running = [1.0] * len(values), 1.0
    for i in reversed(range(len(values))):
        original = order[i]
        running = min(running, values[original] * len(values) / (i + 1))
        adjusted[original] = min(1.0, running)
    return adjusted


def summarize_event_windows(results: pd.DataFrame) -> pd.DataFrame:
    """Report exploratory t-tests and BH adjusted values across this run's family."""
    valid = results.loc[
        results["exclusion_reason"].isna()
        & results["return"].notna()
        & ~results["overlap_excluded"]
    ]
    rows = []
    for window in results["window"].drop_duplicates():
        sample = valid.loc[valid["window"] == window]
        groups = [("all", sample)] + [(g, sample.loc[sample["surprise_group"] == g])
                                      for g in ("beat", "meet", "miss")]
        for group, values in groups:
            returns = values["return"].astype(float)
            p = float(ttest_1samp(returns, 0).pvalue) if len(returns) >= 2 else float("nan")
            overlap_count = results.loc[
                (results["window"] == window) & results["overlap_excluded"], "event_id"
            ].nunique()
            rows.append({"window": window, "surprise_group": group, "n": len(returns),
                         "mean_return": float(returns.mean()) if len(returns) else float("nan"),
                         "median_return": float(returns.median()) if len(returns) else float("nan"),
                         "raw_p_value": p, "overlap_excluded_event_count": overlap_count})
    summary = pd.DataFrame(rows)
    tested = summary["raw_p_value"].notna()
    summary["bh_adjusted_p_value"] = float("nan")
    if tested.any():
        summary.loc[tested, "bh_adjusted_p_value"] = _bh(summary.loc[tested, "raw_p_value"].tolist())
    summary["correction_family"] = "all_windows_and_surprise_groups"
    summary["tested_hypothesis_count"] = int(tested.sum())
    summary["inference_note"] = "Overlapping same-symbol spans are excluded; cross-sectional dependence may remain."
    return summary


def run_event_study(events_path: str, prices_path: str, calendar_path: str, output_dir: str) -> None:
    events, prices, calendar = (pd.read_csv(path) for path in (events_path, prices_path, calendar_path))
    results = build_event_windows(events, prices, calendar)
    summary = summarize_event_windows(results)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "event_windows.csv", index=False)
    summary.to_csv(output / "event_summary.csv", index=False)
    input_paths = {
        "events": Path(events_path), "prices": Path(prices_path), "calendar": Path(calendar_path),
    }
    repo_root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    manifest = {
        "study": "exploratory_daily_earnings_event_study_v1",
        "package_version": __version__,
        "source_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "window_definitions": DEFAULT_WINDOWS, "return_price_field": "adj_close",
        "input_paths": {name: str(path) for name, path in input_paths.items()},
        "input_sha256": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in input_paths.items()
        },
        "mapping_rule": "first supplied exchange close strictly after announcement timestamp",
        "multiple_testing": "Benjamini-Hochberg across tested window/group means in this run",
        "overlap_rule": "same-symbol events with intersecting configured spans are excluded and retained with a reason",
        "inference_limit": "exploratory t-tests; cross-sectional dependence and small samples may limit inference",
        "data_limit": "user-supplied inputs; historical point-in-time quality is not certified",
        "simulated_trading": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--calendar", required=True)
    parser.add_argument("--output", default="reports/earnings_event_study")
    args = parser.parse_args()
    run_event_study(args.events, args.prices, args.calendar, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
