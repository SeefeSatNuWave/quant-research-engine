import json
from datetime import date

import pytest

from quant_research.universe import UniverseValidationError, load_universe, validate_universe


def test_empty_template_is_valid():
    assert validate_universe({"schema_version": 1, "securities": []}) == ()


def test_membership_dates_are_inclusive_start_exclusive_end():
    member = validate_universe(
        {
            "schema_version": 1,
            "securities": [
                {
                    "symbol": "ACME",
                    "name": "Acme Corp",
                    "industry": "Industrials",
                    "valid_from": "2020-01-01",
                    "valid_to": "2021-01-01",
                    "source": "fixture",
                    "rationale": "test record",
                }
            ],
        }
    )[0]
    assert member.is_valid_on(date(2020, 1, 1))
    assert not member.is_valid_on(date(2021, 1, 1))


def test_rejects_overlapping_history_for_same_symbol():
    first = {
        "symbol": "ACME",
        "name": "Acme Corp",
        "industry": "Industrials",
        "valid_from": "2020-01-01",
        "valid_to": "2021-06-01",
        "source": "fixture",
        "rationale": "first interval",
    }
    second = {**first, "valid_from": "2021-01-01", "valid_to": None, "rationale": "overlap"}
    with pytest.raises(UniverseValidationError, match="overlapping"):
        validate_universe({"schema_version": 1, "securities": [first, second]})


def test_load_universe_reads_json_file(tmp_path):
    path = tmp_path / "universe.json"
    path.write_text(json.dumps({"schema_version": 1, "securities": []}), encoding="utf-8")
    assert load_universe(path) == ()


def test_rejects_unsupported_schema_version():
    with pytest.raises(UniverseValidationError, match="unsupported universe schema_version"):
        validate_universe({"schema_version": 2, "securities": []})
