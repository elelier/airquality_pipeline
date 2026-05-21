import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts.rpc_contract_health import EXPECTED_COLUMNS, parse_utc_timestamp

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "latest_air_quality_rpc_valid.json"

REQUIRED_FIELDS = {"city_id", "city_name", "api_name", "reading_timestamp"}
NULLABLE_FIELDS = EXPECTED_COLUMNS - REQUIRED_FIELDS
NUMERIC_OR_NULL_FIELDS = {
    "latitude",
    "longitude",
    "aqi_us",
    "temperature_c",
    "humidity_percent",
    "wind_speed_ms",
    "wind_direction_deg",
}
STRING_OR_NULL_FIELDS = {
    "main_pollutant_us",
    "weather_icon",
    "last_successful_update_at",
}


def load_fixture() -> list[dict[str, Any]]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        data = json.load(fixture_file)
    assert isinstance(data, list), "Canonical RPC fixture must be an array"
    return data


def test_canonical_rpc_fixture_preserves_expected_shape_and_required_fields():
    rows = load_fixture()

    assert rows, "Canonical RPC fixture must include at least one row"
    for index, row in enumerate(rows):
        assert isinstance(row, dict), f"row[{index}] must be an object"
        assert EXPECTED_COLUMNS.issubset(row.keys()), (
            f"row[{index}] missing canonical columns: "
            f"{sorted(EXPECTED_COLUMNS - set(row.keys()))}"
        )
        assert not REQUIRED_FIELDS - row.keys()
        for field in REQUIRED_FIELDS:
            assert row[field] is not None, f"row[{index}] {field} must not be null"


def test_canonical_rpc_fixture_uses_city_id_as_stable_numeric_identity():
    rows = load_fixture()
    city_ids = [row["city_id"] for row in rows]

    assert all(isinstance(city_id, int) and not isinstance(city_id, bool) for city_id in city_ids)
    assert len(city_ids) == len(set(city_ids)), "city_id values must be unique in RPC rows"


def test_canonical_rpc_fixture_documents_nullable_degradable_fields():
    rows = load_fixture()

    assert any(row["latitude"] is None and row["longitude"] is None for row in rows), (
        "Fixture must include a row with nullable coordinates to lock degradation behavior"
    )
    assert any(row["aqi_us"] is None for row in rows), (
        "Fixture must include a degraded contractual row with null aqi_us"
    )

    for index, row in enumerate(rows):
        for field in NUMERIC_OR_NULL_FIELDS:
            value = row[field]
            assert value is None or isinstance(value, (int, float)), (
                f"row[{index}] {field} must be numeric or null"
            )
        for field in STRING_OR_NULL_FIELDS:
            value = row[field]
            assert value is None or isinstance(value, str), (
                f"row[{index}] {field} must be string or null"
            )
        for field in NULLABLE_FIELDS:
            assert field in row, f"row[{index}] {field} must be present even when null"


def test_canonical_rpc_fixture_timestamps_are_parseable_explicit_utc():
    rows = load_fixture()

    for index, row in enumerate(rows):
        reading_timestamp = parse_utc_timestamp(row["reading_timestamp"])
        assert reading_timestamp.tzinfo is not None
        assert reading_timestamp.utcoffset() == timezone.utc.utcoffset(reading_timestamp)

        last_successful_update_at = row["last_successful_update_at"]
        if last_successful_update_at is not None:
            parsed_update_timestamp = parse_utc_timestamp(last_successful_update_at)
            assert parsed_update_timestamp.tzinfo is not None
            assert parsed_update_timestamp.utcoffset() == timezone.utc.utcoffset(
                parsed_update_timestamp
            )


def test_canonical_rpc_fixture_marks_null_aqi_as_degraded_not_healthy():
    rows = load_fixture()
    degraded_rows = [row for row in rows if row["aqi_us"] is None]

    assert degraded_rows, "Fixture must keep null aqi_us visible as a degraded contract case"
    for row in degraded_rows:
        assert row["reading_timestamp"], "Degraded row still needs traceable measurement timestamp"
        assert row["city_id"], "Degraded row still needs stable city identity"


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("city_id", None),
        ("city_id", "9"),
        ("reading_timestamp", "2026-05-21T16:00:00"),
        ("reading_timestamp", "not-a-timestamp"),
    ],
)
def test_fixture_contract_examples_would_fail_for_invalid_required_values(field, bad_value):
    row = dict(load_fixture()[0])
    row[field] = bad_value

    if field == "city_id":
        assert not (isinstance(row[field], int) and not isinstance(row[field], bool))
    elif field == "reading_timestamp":
        with pytest.raises(ValueError):
            parse_utc_timestamp(row[field])
