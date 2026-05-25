from unittest.mock import MagicMock, patch

from weather_context import build_weather_error, fetch_weather_context, normalize_weather_payload


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


def test_fetch_weather_context_handles_non_json_response():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("not json")

    with patch("weather_context.requests.get", return_value=response):
        result = fetch_weather_context(25.67, -100.31)

    assert result["status"] == "error"
    assert result["provider"] == "open-meteo"
    assert result["errorType"] == "invalid_json"


def test_build_weather_error_shape():
    result = build_weather_error("missing_coordinates", "lat/lon required")

    assert result == {
        "status": "error",
        "provider": "open-meteo",
        "errorType": "missing_coordinates",
        "message": "lat/lon required",
    }
