from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts.rpc_contract_health import (
    DEFAULT_EXPECTED_ACTIVE_CITY_IDS,
    EXPECTED_COLUMNS,
    FreshnessThresholds,
    evaluate_rpc_contract,
    fetch_rpc_rows,
    main,
    parse_utc_timestamp,
)


NOW = datetime(2026, 5, 7, 13, 0, tzinfo=timezone.utc)


def make_row(city_id: int, **overrides):
    row = {
        "city_id": city_id,
        "city_name": f"City {city_id}",
        "api_name": f"City {city_id}",
        "latitude": 25.6,
        "longitude": -100.3,
        "reading_timestamp": (NOW - timedelta(minutes=45)).isoformat(),
        "aqi_us": 74,
        "main_pollutant_us": "pm25",
        "temperature_c": None,
        "humidity_percent": None,
        "wind_speed_ms": None,
        "wind_direction_deg": None,
        "weather_icon": None,
        "last_successful_update_at": (NOW - timedelta(minutes=30)).isoformat(),
    }
    row.update(overrides)
    assert EXPECTED_COLUMNS.issubset(row.keys())
    return row


def make_all_rows(**overrides):
    return [make_row(city_id, **overrides) for city_id in sorted(DEFAULT_EXPECTED_ACTIVE_CITY_IDS)]


def make_runtime_rows(*, reading_age: timedelta = timedelta(minutes=45)):
    now = datetime.now(timezone.utc)
    return make_all_rows(
        reading_timestamp=(now - reading_age).isoformat(),
        last_successful_update_at=(now - timedelta(minutes=30)).isoformat(),
    )


def test_evaluate_rpc_contract_success_for_9_expected_ids():
    result = evaluate_rpc_contract(make_all_rows(), now_utc=NOW)

    assert result["status"] == "healthy"
    assert result["returned_city_ids"] == sorted(DEFAULT_EXPECTED_ACTIVE_CITY_IDS)
    assert result["errors"] == []
    assert result["warnings"] == []


def test_evaluate_rpc_contract_fails_missing_expected_city():
    rows = [row for row in make_all_rows() if row["city_id"] != 13]

    result = evaluate_rpc_contract(rows, now_utc=NOW)

    assert result["status"] == "unhealthy"
    assert "missing expected active city_ids: [13]" in result["errors"]


def test_evaluate_rpc_contract_fails_null_aqi_for_expected_city():
    rows = make_all_rows()
    rows[0]["aqi_us"] = None

    result = evaluate_rpc_contract(rows, now_utc=NOW)

    assert result["status"] == "unhealthy"
    assert f"city_id {rows[0]['city_id']} has null aqi_us" in result["errors"]


def test_evaluate_rpc_contract_degraded_when_reading_is_warning_stale():
    rows = make_all_rows(reading_timestamp=(NOW - timedelta(hours=3)).isoformat())

    result = evaluate_rpc_contract(
        rows,
        now_utc=NOW,
        thresholds=FreshnessThresholds(warn_hours=2, fail_hours=6),
    )

    assert result["status"] == "degraded"
    assert result["errors"] == []
    assert result["warnings"]


def test_evaluate_rpc_contract_fails_when_reading_is_severely_stale():
    rows = make_all_rows(reading_timestamp=(NOW - timedelta(hours=7)).isoformat())

    result = evaluate_rpc_contract(
        rows,
        now_utc=NOW,
        thresholds=FreshnessThresholds(warn_hours=2, fail_hours=6),
    )

    assert result["status"] == "unhealthy"
    assert any("reading_timestamp is stale" in error for error in result["errors"])


def test_evaluate_rpc_contract_fails_bad_shape():
    result = evaluate_rpc_contract({"data": []}, now_utc=NOW)

    assert result["status"] == "unhealthy"
    assert result["errors"] == ["RPC response must be an array"]


def test_evaluate_rpc_contract_fails_bad_timestamp():
    rows = make_all_rows(reading_timestamp="not-a-timestamp")

    result = evaluate_rpc_contract(rows, now_utc=NOW)

    assert result["status"] == "unhealthy"
    assert any("invalid reading_timestamp" in error for error in result["errors"])


def test_evaluate_rpc_contract_fails_duplicate_city_id():
    rows = make_all_rows()
    rows.append(make_row(1))

    result = evaluate_rpc_contract(rows, now_utc=NOW)

    assert result["status"] == "unhealthy"
    assert "duplicate city_id values: [1]" in result["errors"]


def test_parse_utc_timestamp_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="UTC offset"):
        parse_utc_timestamp("2026-05-07T13:00:00")


def test_fetch_rpc_rows_uses_read_only_rpc_call():
    mock_response = SimpleNamespace(data=make_all_rows())
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value = mock_response

    with patch("scripts.rpc_contract_health.get_supabase_client", return_value=mock_client):
        rows = fetch_rpc_rows()

    assert len(rows) == 9
    mock_client.rpc.assert_called_once_with("get_latest_air_quality_per_city")
    mock_client.table.assert_not_called()


def test_fetch_rpc_rows_rejects_non_array_response():
    mock_client = MagicMock()
    mock_client.rpc.return_value.execute.return_value = SimpleNamespace(data={"bad": "shape"})

    with patch("scripts.rpc_contract_health.get_supabase_client", return_value=mock_client):
        with pytest.raises(ValueError, match="not an array"):
            fetch_rpc_rows()


def test_main_exit_codes_for_healthy_degraded_unhealthy_and_config_error(capsys):
    with patch("scripts.rpc_contract_health.fetch_rpc_rows", return_value=make_runtime_rows()):
        assert main(["--json-only"]) == 0

    with patch(
        "scripts.rpc_contract_health.fetch_rpc_rows",
        return_value=make_runtime_rows(reading_age=timedelta(hours=7)),
    ):
        assert main(["--json-only"]) == 1

    with patch("scripts.rpc_contract_health.fetch_rpc_rows", side_effect=RuntimeError("boom")):
        assert main(["--json-only"]) == 2

    captured = capsys.readouterr()
    assert "SUPABASE_SERVICE_ROLE_KEY" not in captured.out
