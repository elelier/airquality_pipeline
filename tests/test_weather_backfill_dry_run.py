from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts.weather_backfill_dry_run import (
    AqiReadingInput,
    CityInput,
    WeatherHour,
    build_dry_run_report,
    find_nearest_weather_hour,
    validate_matched_report_row,
    validate_weather_row,
)


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def city() -> CityInput:
    return CityInput(city_id=9, api_name="Monterrey", latitude=25.6866, longitude=-100.3161)


def weather(timestamp: str, **overrides: float) -> WeatherHour:
    return WeatherHour(
        timestamp=ts(timestamp),
        temperature_c=overrides.get("temperature_c", 28.0),
        humidity_percent=overrides.get("humidity_percent", 50.0),
        wind_speed_kmh=overrides.get("wind_speed_kmh", 12.0),
        wind_direction_deg=overrides.get("wind_direction_deg", 180.0),
        wind_gust_kmh=overrides.get("wind_gust_kmh", 20.0),
    )


def test_nearest_hour_matching_within_threshold() -> None:
    match, delta = find_nearest_weather_hour(
        ts("2026-05-24T12:20:00Z"),
        [
            weather("2026-05-24T12:00:00Z"),
            weather("2026-05-24T13:00:00Z"),
        ],
    )

    assert match is not None
    assert match.timestamp == ts("2026-05-24T12:00:00Z")
    assert delta == 20


def test_nearest_hour_threshold_over_30_minutes_rejects() -> None:
    match, delta = find_nearest_weather_hour(
        ts("2026-05-24T12:31:00Z"),
        [weather("2026-05-24T12:00:00Z")],
    )

    assert match is None
    assert delta == 31


def test_nearest_hour_tie_breaker_chooses_previous_hour() -> None:
    match, delta = find_nearest_weather_hour(
        ts("2026-05-24T12:30:00Z"),
        [
            weather("2026-05-24T12:00:00Z"),
            weather("2026-05-24T13:00:00Z"),
        ],
    )

    assert match is not None
    assert match.timestamp == ts("2026-05-24T12:00:00Z")
    assert delta == 30


def test_weather_range_validation_flags_errors_and_warnings() -> None:
    reading = AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:00:00Z"))
    issues = validate_weather_row(
        city=city(),
        reading=reading,
        weather_hour=weather(
            "2026-05-24T12:00:00Z",
            temperature_c=75.0,
            humidity_percent=101.0,
            wind_speed_kmh=170.0,
            wind_gust_kmh=230.0,
            wind_direction_deg=361.0,
        ),
    )

    codes = {issue["code"] for issue in issues}
    assert "weather_temperature_out_of_hard_range" in codes
    assert "weather_humidity_out_of_range" in codes
    assert "weather_wind_speed_high_warning" in codes
    assert "weather_wind_gust_high_warning" in codes
    assert "weather_wind_direction_out_of_range" in codes


def test_delta_temperature_and_humidity_vs_waqi_legacy_fields() -> None:
    reading = AqiReadingInput(
        city_id=9,
        reading_timestamp=ts("2026-05-24T12:00:00Z"),
        temperature_c=15.5,
        humidity_percent=20.0,
    )
    issues = validate_weather_row(
        city=city(),
        reading=reading,
        weather_hour=weather("2026-05-24T12:00:00Z", temperature_c=30.0, humidity_percent=55.0),
    )

    codes = {issue["code"] for issue in issues}
    assert "large_temperature_delta_vs_waqi" in codes
    assert "large_humidity_delta_vs_waqi" in codes


def test_matched_report_row_validates_weather_metadata_nullability() -> None:
    reading = AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:00:00Z"))
    issues = validate_matched_report_row(
        city=city(),
        reading=reading,
        row={
            "weather_temperature_c": 28.0,
            "weather_timestamp": None,
            "weather_provider": None,
        },
    )

    assert {issue["code"] for issue in issues} == {"weather_nullability"}


def test_report_uses_weather_wind_speed_kmh_not_legacy_ms() -> None:
    reading = AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:00:00Z"))
    report = build_dry_run_report(
        cities=[city()],
        readings=[reading],
        weather_fetcher=lambda _city, _start, _end: [weather("2026-05-24T12:00:00Z")],
        generated_at=ts("2026-05-24T13:00:00Z"),
    )

    first_match = report["city_results"][0]["sample_matches"][0]
    assert "weather_wind_speed_kmh" in first_match
    assert "wind_speed_ms" not in first_match
    assert report["unit_contract"]["weather_wind_speed_field"] == "weather_wind_speed_kmh"


def test_matched_report_row_flags_unit_violation() -> None:
    reading = AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:00:00Z"))
    issues = validate_matched_report_row(
        city=city(),
        reading=reading,
        row={
            "weather_provider": "open-meteo",
            "weather_timestamp": "2026-05-24T12:00:00Z",
            "weather_wind_speed_ms": 12.0,
        },
    )

    assert {issue["code"] for issue in issues} == {"weather_wind_unit_violation"}


def test_report_summary_and_city_results() -> None:
    readings = [
        AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:00:00Z")),
        AqiReadingInput(city_id=9, reading_timestamp=ts("2026-05-24T12:31:00Z")),
    ]
    report = build_dry_run_report(
        cities=[city()],
        readings=readings,
        weather_fetcher=lambda _city, _start, _end: [weather("2026-05-24T12:00:00Z")],
        generated_at=ts("2026-05-24T13:00:00Z"),
    )

    assert report["mode"] == "dry_run"
    assert report["provider"] == "open-meteo"
    assert report["summary"]["active_cities"] == 1
    assert report["summary"]["target_aqi_rows"] == 2
    assert report["summary"]["matched_rows"] == 1
    assert report["summary"]["unmatched_rows"] == 1
    assert report["city_results"][0]["city_id"] == 9
    assert report["city_results"][0]["matched_rows"] == 1
    assert report["city_results"][0]["unmatched_rows"] == 1


def test_script_source_does_not_call_supabase_mutations() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "scripts" / "weather_backfill_dry_run.py").read_text(
        encoding="utf-8"
    )
    forbidden_tokens = [
        ".insert(",
        ".update(",
        ".delete(",
        ".upsert(",
        "apply_migration",
        "SUPABASE_SERVICE_ROLE_KEY",
        "get_supabase_client",
    ]

    for token in forbidden_tokens:
        assert token not in source
