from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import main as pipeline
import sima_api

HTML = """<script>var arrayIMKTodo11 = [
  {"Estacion":"centro","Parameter":"O3Nc","contaminante":"O3","HrAveData":31,"concentracion":"35","Date":"2026-11-26 23:00"},
  {"Estacion":"este","Parameter":"PM10Nc","contaminante":"PM10","HrAveData":40,"concentracion":"36","Date":"2026-11-26 23:00"},
  {"Estacion":"norte","contaminante":"PM25","HrAveData":null,"concentracion":null,"Date":"2026-11-26 23:00"}
];</script>"""

NOW = datetime(2026, 11, 27, 5, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clear_cache():
    sima_api.reset_cache()
    yield
    sima_api.reset_cache()


def test_parse_station_indexes_converts_local_standard_time_and_skips_nulls():
    stations = sima_api.parse_station_indexes(HTML)
    assert set(stations) == {"centro", "este"}
    assert stations["centro"]["observed_at"].astimezone(timezone.utc) == datetime(2026, 11, 27, 5, tzinfo=timezone.utc)


def test_parse_station_indexes_requires_expected_table():
    with pytest.raises(ValueError):
        sima_api.parse_station_indexes("<html></html>")


def test_fetch_returns_waqi_shaped_valid_reading():
    with patch.object(sima_api, "get_station_indexes", return_value=sima_api.parse_station_indexes(HTML)):
        result = sima_api.fetch_air_quality_data("Monterrey", 9, 25.67, -100.31)

    assert result["status"] == "success"
    assert result["provider"] == "sima"
    assert result["calidad_aire"] == {
        "aqi_us": 31,
        "contaminante_principal_us": "o3",
        "aqi_cn": None,
        "contaminante_principal_cn": None,
    }
    assert result["reading_timestamp_iso"] == "2026-11-27T05:00:00+00:00"
    assert pipeline.validate_reading_payload(result, now=NOW)["valid"]


def test_fetch_reports_station_without_data():
    with patch.object(sima_api, "get_station_indexes", return_value=sima_api.parse_station_indexes(HTML)):
        result = sima_api.fetch_air_quality_data("General Escobedo", 6, 25.8, -100.3)
    assert result["status"] == "error"
    assert result["errorType"] == "station_without_data"


def test_every_expected_municipality_has_a_sima_station():
    from waqi_api import EXPECTED_ACTIVE_API_NAMES

    assert all(name in sima_api.SIMA_STATION_BY_API_NAME for name in EXPECTED_ACTIVE_API_NAMES)


def test_pipeline_falls_back_to_sima_when_waqi_is_stale():
    city = {"id": 9, "api_name": "Monterrey", "latitude": 25.67, "longitude": -100.31}
    stale = {"status": "success", "reading_timestamp_iso": "2026-11-12T16:00:00+00:00"}
    fresh = {"status": "success", "provider": "sima"}

    def validate(result):
        return {"valid": result is fresh}

    with (
        patch.object(pipeline, "fetch_waqi_air_quality_data", return_value=stale),
        patch.object(pipeline, "fetch_sima_air_quality_data", return_value=fresh) as sima,
        patch.object(pipeline, "validate_reading_payload", side_effect=validate),
    ):
        result = pipeline.fetch_provider_air_quality("waqi", city, {"WAQI_API_TOKEN": "t"})

    assert result is fresh
    assert result["fallback_from"] == "waqi"
    sima.assert_called_once_with(api_name="Monterrey", city_id=9, latitude=25.67, longitude=-100.31)


def test_pipeline_keeps_fresh_waqi_without_calling_sima():
    city = {"id": 9, "api_name": "Monterrey"}
    fresh = {"status": "success"}
    with (
        patch.object(pipeline, "fetch_waqi_air_quality_data", return_value=fresh),
        patch.object(pipeline, "fetch_sima_air_quality_data") as sima,
        patch.object(pipeline, "validate_reading_payload", return_value={"valid": True}),
    ):
        assert pipeline.fetch_provider_air_quality("waqi", city, {"WAQI_API_TOKEN": "t"}) is fresh
    sima.assert_not_called()


def test_pipeline_returns_waqi_error_when_both_sources_fail():
    city = {"id": 9, "api_name": "Monterrey"}
    waqi_error = {"status": "error", "errorType": "fetch_failed"}
    with (
        patch.object(pipeline, "fetch_waqi_air_quality_data", return_value=waqi_error),
        patch.object(pipeline, "fetch_sima_air_quality_data", return_value={"status": "error"}),
    ):
        assert pipeline.fetch_provider_air_quality("waqi", city, {"WAQI_API_TOKEN": "t"}) is waqi_error
