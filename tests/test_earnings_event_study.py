import pandas as pd
import pytest

from quant_research.earnings_event_study import (
    EventStudyError, _bh, build_event_windows, map_events_to_sessions, run_event_study,
    summarize_event_windows,
)


def inputs():
    events = pd.DataFrame([
        {"event_id": "pre", "symbol": "ACME", "fiscal_period": "2024Q1",
         "announcement_at": "2024-01-03T08:00:00-05:00", "actual_eps": 1.2,
         "consensus_eps": 1.0, "consensus_available_at": "2024-01-02T15:00:00-05:00",
         "source": "fixture"},
        {"event_id": "post", "symbol": "ACME", "fiscal_period": "2024Q2",
         "announcement_at": "2024-01-03T16:30:00-05:00", "actual_eps": 0.8,
         "consensus_eps": 1.0, "consensus_available_at": "2024-01-03T15:00:00-05:00",
         "source": "fixture"},
    ])
    dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
             "2024-01-08", "2024-01-09", "2024-01-10"]
    calendar = pd.DataFrame({"session_date": dates,
                             "close_at": [f"{d}T16:00:00-05:00" for d in dates]})
    prices = pd.DataFrame({"session_date": dates, "symbol": "ACME",
                           "adj_close": [100, 101, 102, 100, 105, 106, 107]})
    return events, prices, calendar


def test_maps_before_open_same_day_and_after_close_next_session():
    events, _, calendar = inputs()
    mapped = map_events_to_sessions(events, calendar).set_index("event_id")
    assert mapped.loc["pre", "reaction_session"] == "2024-01-03"
    assert mapped.loc["post", "reaction_session"] == "2024-01-04"


def test_announcement_at_close_maps_to_next_close():
    events, _, calendar = inputs()
    events.loc[0, "announcement_at"] = "2024-01-03T16:00:00-05:00"
    assert map_events_to_sessions(events.iloc[[0]], calendar).loc[0, "reaction_session"] == "2024-01-04"


def test_reaction_return_uses_adjusted_closes():
    events, prices, calendar = inputs()
    result = build_event_windows(events.iloc[[0]], prices, calendar, {"reaction": (-1, 0)})
    assert result.loc[0, "return"] == pytest.approx(0.01)


def test_missing_price_is_recorded_without_forward_fill():
    events, prices, calendar = inputs()
    prices = prices.loc[prices["session_date"] != "2024-01-02"]
    result = build_event_windows(events.iloc[[0]], prices, calendar, {"reaction": (-1, 0)})
    assert result.loc[0, "exclusion_reason"] == "missing_adjusted_close_at_window_endpoint"
    assert pd.isna(result.loc[0, "return"])


def test_overlapping_same_symbol_events_are_excluded_and_recorded():
    events, prices, calendar = inputs()
    result = build_event_windows(events, prices, calendar, {"window": (-1, 1)})
    assert result["overlap_excluded"].all()
    assert set(result["exclusion_reason"]) == {"overlapping_same_symbol_event_window"}


def test_future_consensus_and_naive_announcement_are_rejected():
    events, _, calendar = inputs()
    events.loc[0, "consensus_available_at"] = "2024-01-03T09:00:00-05:00"
    with pytest.raises(EventStudyError, match="no later than"):
        map_events_to_sessions(events, calendar)
    events, _, calendar = inputs()
    events.loc[0, "announcement_at"] = "2024-01-03 08:00:00"
    with pytest.raises(EventStudyError, match="timezone"):
        map_events_to_sessions(events.iloc[[0]], calendar)


def test_summary_reports_bh_family():
    events, prices, calendar = inputs()
    result = build_event_windows(events, prices, calendar, {"reaction": (-1, 0)})
    summary = summarize_event_windows(result)
    assert set(summary["correction_family"]) == {"all_windows_and_surprise_groups"}
    assert "bh_adjusted_p_value" in summary
    assert "tested_hypothesis_count" in summary


def test_bh_adjustment_matches_known_values():
    assert _bh([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])


def test_events_without_consensus_remain_unclassified():
    events, _, calendar = inputs()
    event = events.iloc[[0]].drop(columns=["actual_eps", "consensus_eps", "consensus_available_at"])
    assert map_events_to_sessions(event, calendar).loc[0, "surprise_group"] == "unclassified"


def test_pipeline_writes_outputs_and_input_hashes(tmp_path):
    events, prices, calendar = inputs()
    paths = [tmp_path / name for name in ("events.csv", "prices.csv", "calendar.csv")]
    for frame, path in zip((events, prices, calendar), paths):
        frame.to_csv(path, index=False)
    output = tmp_path / "report"
    run_event_study(*(str(path) for path in paths), str(output))
    assert (output / "event_windows.csv").is_file()
    assert (output / "event_summary.csv").is_file()
    manifest = pd.read_json(output / "manifest.json", typ="series")
    assert set(manifest["input_sha256"]) == {"events", "prices", "calendar"}
