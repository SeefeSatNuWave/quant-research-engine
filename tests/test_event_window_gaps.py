import pandas as pd
from test_earnings_event_study import inputs
from quant_research.earnings_event_study import build_event_windows


def test_unmapped_event_retained_with_mapped_event():
    events, prices, calendar = inputs()
    events.loc[1, "announcement_at"] = "2025-01-01T17:00:00-05:00"
    result = build_event_windows(events, prices, calendar, {"reaction": (-1, 0)})
    assert "no_calendar_close_after_announcement" in result.exclusion_reason.tolist()


def test_interior_missing_bar_excluded():
    events, prices, calendar = inputs()
    prices = prices.loc[prices.session_date != "2024-01-03"]
    result = build_event_windows(events.iloc[[0]], prices, calendar, {"reaction": (-1, 1)})
    assert result.loc[0, "exclusion_reason"] == "missing_adjusted_close_inside_window"
    assert pd.isna(result.loc[0, "return"])
