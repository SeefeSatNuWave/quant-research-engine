import json

import pandas as pd
import pytest

from quant_research.data.prices import (
    PriceDataError,
    download_and_cache_prices,
    normalize_prices,
)


def sample_prices():
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 12.0],
            "Low": [9.0, 10.5],
            "Close": [11.0, 11.5],
            "Adj Close": [10.9, 11.4],
            "Volume": [1000, 1200],
            "Dividends": [0.0, 0.1],
            "Stock Splits": [0.0, 0.0],
        },
        index=pd.to_datetime(["2024-01-03", "2024-01-02"]),
    )


def test_normalize_maps_fields_and_sorts_session_dates():
    normalized = normalize_prices(sample_prices(), "ACME")
    assert normalized["session_date"].tolist() == ["2024-01-02", "2024-01-03"]
    assert normalized["symbol"].tolist() == ["ACME", "ACME"]
    assert normalized.loc[0, "adj_close"] == pytest.approx(11.4)
    dividend_row = normalized.loc[normalized["session_date"] == "2024-01-02"]
    assert dividend_row["dividends"].iloc[0] == pytest.approx(0.1)


def test_missing_adjusted_close_is_not_substituted_with_close():
    frame = sample_prices().drop(columns="Adj Close")
    normalized = normalize_prices(frame, "ACME")
    assert normalized["adj_close"].isna().all()


def test_rejects_duplicate_session_dates():
    frame = sample_prices()
    frame.index = pd.to_datetime(["2024-01-02 10:00", "2024-01-02 15:00"])
    with pytest.raises(PriceDataError, match="same session date"):
        normalize_prices(frame, "ACME")


def test_rejects_inconsistent_high_low_values():
    frame = sample_prices()
    frame.loc[frame.index[0], "High"] = 8.0
    with pytest.raises(PriceDataError, match="high must be"):
        normalize_prices(frame, "ACME")


def test_rejects_rows_outside_requested_end_exclusive_range(tmp_path):
    class FixedSource:
        name = "fixed_test_source"

        def download(self, symbol, start, end, interval):
            return sample_prices()

    with pytest.raises(PriceDataError, match="outside the requested"):
        download_and_cache_prices(FixedSource(), "ACME", "2024-01-01", "2024-01-03", tmp_path)


def test_cache_retains_raw_normalized_and_provenance_and_reuses_request(tmp_path):
    class FixedSource:
        name = "fixed_test_source"

        def __init__(self):
            self.calls = 0

        def download(self, symbol, start, end, interval):
            self.calls += 1
            return sample_prices()

    source = FixedSource()
    first = download_and_cache_prices(source, "ACME", "2024-01-01", "2024-02-01", tmp_path)
    second = download_and_cache_prices(source, "ACME", "2024-01-01", "2024-02-01", tmp_path)

    assert source.calls == 1
    pd.testing.assert_frame_equal(first, second)
    assert list((tmp_path / "raw" / "prices").glob("*.csv"))
    manifest_path = next((tmp_path / "normalized" / "prices").glob("*.manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["provider"] == "fixed_test_source"
    assert manifest["normalized_schema_version"] == 1
    assert manifest["row_count"] == 2
