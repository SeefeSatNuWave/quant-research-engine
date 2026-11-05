from datetime import date
import json

import pandas as pd
import pytest

from quant_research.data.alpha_vantage import fetch, normalize
from quant_research.earnings_event_study import map_events_to_sessions


def payload(timing="post-market"):
    return {"symbol": "ABC", "quarterlyEarnings": [{"fiscalDateEnding": "2024-12-31", "reportedDate": "2025-01-30", "reportedEPS": "2", "estimatedEPS": "1", "reportTime": timing}]}


def test_import_keeps_unverified_estimates_out_of_classification():
    events = normalize(payload(), "ABC", date(2025, 2, 1))
    calendar = pd.DataFrame({"session_date": ["2025-01-30", "2025-01-31"], "close_at": ["2025-01-30T16:00:00-05:00", "2025-01-31T16:00:00-05:00"]})
    mapped = map_events_to_sessions(events, calendar)
    assert mapped.loc[0, "reaction_session"] == "2025-01-31"
    assert mapped.loc[0, "surprise_group"] == "unclassified"


def test_unknown_timing_excluded():
    assert normalize(payload("unknown"), "ABC", date(2025, 2, 1)).loc[0, "exclusion_reason"] == "unknown_release_timing"


def test_future_and_duplicate_rejected():
    with pytest.raises(ValueError):
        normalize(payload(), "ABC", date(2025, 1, 1))
    p = payload()
    p["quarterlyEarnings"] *= 2
    with pytest.raises(ValueError):
        normalize(p, "ABC", date(2025, 2, 1))


def test_cache_works_without_key_or_network(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    (tmp_path / "ABC.json").write_text(json.dumps(payload()))
    assert fetch("ABC", tmp_path) == payload()


def test_transport_error_does_not_leak_secret(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-key")
    monkeypatch.setattr("quant_research.data.alpha_vantage.urlopen", fail)
    with pytest.raises(ValueError) as error:
        fetch("ABC", tmp_path, "secret-key")
    assert "secret-key" not in str(error.value)
    assert not list(tmp_path.iterdir())
