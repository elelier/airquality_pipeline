from datetime import datetime, timezone

from scripts.weather_history_backfill import (
    Reading,
    WeatherHour,
    build_update_payload,
    find_nearest_weather_hour,
    validate_weather,
)


def test_build_update_payload_only_contains_canonical_weather_fields():
    hour = WeatherHour(
        timestamp=datetime(2026, 5, 30, 18, tzinfo=timezone.utc),
        temperature_c=32.9,
        humidity_percent=47,
        wind_speed_kmh=19.3,
        wind_direction_deg=91,
        wind_gust_kmh=28.4,
    )

    payload = build_update_payload(hour)

    assert payload == {
        "weather_temperature_c": 32.9,
        "weather_humidity_percent": 47,
        "weather_wind_speed_kmh": 19.3,
        "weather_wind_direction_deg": 91,
        "weather_wind_gust_kmh": 28.4,
        "weather_timestamp": "2026-05-30T18:00:00+00:00",
        "weather_provider": "open-meteo",
    }
    assert "aqi_us" not in payload
    assert "main_pollutant_us" not in payload
    assert "temperature_c" not in payload
    assert "humidity_percent" not in payload
    assert "wind_speed_ms" not in payload


def test_find_nearest_weather_hour_prefers_nearest_within_threshold():
    reading = Reading(
        city_id=9,
        reading_timestamp=datetime(2026, 5, 30, 18, 15, tzinfo=timezone.utc),
    )
    hours = [
        WeatherHour(datetime(2026, 5, 30, 17, tzinfo=timezone.utc), 31.0, 50, 10.0, None, None),
        WeatherHour(datetime(2026, 5, 30, 18, tzinfo=timezone.utc), 32.0, 48, 12.0, None, None),
    ]

    match, delta = find_nearest_weather_hour(reading.reading_timestamp, hours)

    assert match == hours[1]
    assert delta == 15


def test_find_nearest_weather_hour_rejects_outside_threshold():
    reading_time = datetime(2026, 5, 30, 18, 45, tzinfo=timezone.utc)
    hours = [WeatherHour(datetime(2026, 5, 30, 18, tzinfo=timezone.utc), 32.0, 48, 12.0, None, None)]

    match, delta = find_nearest_weather_hour(reading_time, hours)

    assert match is None
    assert delta == 45


def test_validate_weather_rejects_invalid_ranges():
    hour = WeatherHour(
        timestamp=datetime(2026, 5, 30, 18, tzinfo=timezone.utc),
        temperature_c=99,
        humidity_percent=101,
        wind_speed_kmh=-1,
        wind_direction_deg=361,
        wind_gust_kmh=-5,
    )

    assert validate_weather(hour) == [
        "weather_temperature_c_out_of_range",
        "weather_humidity_percent_out_of_range",
        "weather_wind_speed_kmh_negative",
        "weather_wind_direction_deg_out_of_range",
        "weather_wind_gust_kmh_negative",
    ]
