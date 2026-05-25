from weather_context import normalize_weather_payload, build_weather_error


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


def test_build_weather_error_shape():
    result = build_weather_error("missing_coordinates", "lat/lon required")

    assert result == {
        "status": "error",
        "provider": "open-meteo",
        "errorType": "missing_coordinates",
        "message": "lat/lon required",
    }
