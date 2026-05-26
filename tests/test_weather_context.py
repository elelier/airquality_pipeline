from unittest.mock import MagicMock, patch

from weather_context import (
    build_weather_error,
    enrich_with_weather_context,
    fetch_weather_context,
    normalize_weather_payload,
    parse_int,
    parse_number,
)


def test_enrich_weather_context_prefers_canonical_city_coordinates():
    reading = {
        "status": "success",
        "coordenadas": {"lat": 1, "lon": 2},
    }
    expected_context = {"status": "success", "weather_provider": "open-meteo"}

    with patch("weather_context.fetch_weather_context", return_value=expected_context) as fetcher:
        result = enrich_with_weather_context(reading, canonical_lat=25.67, canonical_lon=-100.31)

    assert result["weather_context"] == expected_context
    fetcher.assert_called_once_with(25.67, -100.31)


def test_enrich_weather_context_falls_back_to_reading_coordinates():
    reading = {
        "status": "success",
        "coordenadas": {"lat": 25.67, "lon": -100.31},
    }
    expected_context = {"status": "success", "weather_provider": "open-meteo"}

    with patch("weather_context.fetch_weather_context", return_value=expected_context) as fetcher:
        result = enrich_with_weather_context(reading)

    assert result["weather_context"] == expected_context
    fetcher.assert_called_once_with(25.67, -100.31)


def test_fetch_weather_context_retries_retryable_http_failures():
    failed_response = MagicMock()
    failed_response.status_code = 502

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.raise_for_status.return_value = None
    success_response.json.return_value = {
        "current": {
            "time": "2026-05-25T01:00",
            "temperature_2m": 28.5,
        }
    }

    with patch(
        "weather_context.requests.get",
        side_effect=[failed_response, success_response],
    ) as get_mock, patch("weather_context.time.sleep") as sleep_mock:
        result = fetch_weather_context(25.67, -100.31)

    assert result["status"] == "success"
    assert result["weather_temperature_c"] == 28.5
    assert get_mock.call_count == 2
    sleep_mock.assert_called_once()


def test_fetch_weather_context_does_not_retry_nonretryable_http_failures():
    response = MagicMock()
    response.status_code = 404
    response.raise_for_status.side_effect = RuntimeError("not found")

    with patch("weather_context.requests.get", return_value=response) as get_mock, patch(
        "weather_context.time.sleep"
    ) as sleep_mock:
        result = fetch_weather_context(25.67, -100.31)

    assert result["status"] == "error"
    assert result["errorType"] == "fetch_failed"
    assert result["retryable"] is False
    assert get_mock.call_count == 1
    sleep_mock.assert_not_called()


def test_fetch_weather_context_does_not_retry_deterministic_payload_errors():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {"current": None}

    with patch("weather_context.requests.get", return_value=response) as get_mock, patch(
        "weather_context.time.sleep"
    ) as sleep_mock:
        result = fetch_weather_context(25.67, -100.31)

    assert result["status"] == "error"
    assert result["errorType"] == "missing_current"
    assert get_mock.call_count == 1
    sleep_mock.assert_not_called()


def test_normalize_weather_payload_success():
    payload = {
        "current": {
            "time": "2026-05-25T01:00",
            "temperature_2m": 28.5,
            "relative_humidity_2m": 45,
            "wind_speed_10m": 12.3,
            "wind_direction_10m": 90,
            "wind_gusts_10m": 20.1,
        },
        "current_units": {
            "temperature_2m": "°C",
            "wind_speed_10m": "km/h",
        },
    }

    result = normalize_weather_payload(payload)

    assert result["status"] == "success"
    assert result["weather_provider"] == "open-meteo"
    assert result["weather_timestamp"] == "2026-05-25T01:00:00+00:00"
    assert result["weather_temperature_c"] == 28.5
    assert result["weather_humidity_percent"] == 45
    assert result["weather_wind_speed_kmh"] == 12.3
    assert result["weather_wind_direction_deg"] == 90
    assert result["weather_wind_gust_kmh"] == 20.1
    assert result["weather_source_payload"]["current"]["temperature_2m"] == 28.5


def test_normalize_weather_payload_rejects_invalid_range():
    payload = {
        "current": {
            "time": "2026-05-25T01:00",
            "temperature_2m": 99,
            "relative_humidity_2m": 45,
        }
    }

    result = normalize_weather_payload(payload)

    assert result["status"] == "error"
    assert result["errorType"] == "validation_failed"
    assert "weather_temperature_c_out_of_range" in result["message"]


def test_normalize_weather_payload_drops_non_finite_values_before_success():
    payload = {
        "current": {
            "time": "2026-05-25T01:00",
            "temperature_2m": float("nan"),
            "relative_humidity_2m": float("inf"),
            "wind_speed_10m": float("nan"),
            "wind_direction_10m": float("inf"),
            "wind_gusts_10m": float("inf"),
        }
    }

    result = normalize_weather_payload(payload)

    assert result["status"] == "success"
    assert result["weather_temperature_c"] is None
    assert result["weather_humidity_percent"] is None
    assert result["weather_wind_speed_kmh"] is None
    assert result["weather_wind_direction_deg"] is None
    assert result["weather_wind_gust_kmh"] is None


def test_parse_helpers_return_none_for_non_finite_values():
    assert parse_number(float("nan")) is None
    assert parse_number(float("inf")) is None
    assert parse_number("nan") is None
    assert parse_number("inf") is None
    assert parse_int(float("nan")) is None
    assert parse_int(float("inf")) is None


def test_fetch_weather_context_handles_non_json_response():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("not json")

    with patch("weather_context.requests.get", return_value=response), patch("weather_context.time.sleep"):
        result = fetch_weather_context(25.67, -100.31)

    assert result["status"] == "error"
    assert result["provider"] == "open-meteo"
    assert result["errorType"] == "invalid_json"
    assert result["retryable"] is False


def test_build_weather_error_shape():
    result = build_weather_error("missing_coordinates", "lat/lon required")

    assert result == {
        "status": "error",
        "provider": "open-meteo",
        "errorType": "missing_coordinates",
        "message": "lat/lon required",
        "retryable": False,
    }