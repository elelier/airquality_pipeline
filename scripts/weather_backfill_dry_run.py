"""Dry-run Open-Meteo weather context report for MtyRespira.

This CLI evaluates how candidate AQI readings would match coordinate-based
Open-Meteo hourly weather context. It reads local JSON/CSV exports only and
produces a local report. It does not import Supabase clients or mutate any
database state.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PROVIDER = "open-meteo"
MODE = "dry_run"
MATCH_THRESHOLD_MINUTES = 30.0
TEMPERATURE_DELTA_WARNING_C = 8.0
HUMIDITY_DELTA_WARNING_POINTS = 25.0
HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)


@dataclass(frozen=True)
class CityInput:
    city_id: str
    api_name: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class AqiReadingInput:
    city_id: str
    reading_timestamp: datetime | None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_ms: float | None = None
    wind_direction_deg: float | None = None


@dataclass(frozen=True)
class WeatherHour:
    timestamp: datetime
    temperature_c: float | None
    humidity_percent: float | None
    wind_speed_kmh: float | None
    wind_direction_deg: float | None
    wind_gust_kmh: float | None


def parse_utc_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("rows", "data", "cities", "readings"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [dict(item) for item in value if isinstance(item, dict)]
        raise ValueError(f"{path} must contain an array or an object with rows/data")
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise ValueError(f"Unsupported input format for {path}; use JSON or CSV")


def load_cities(path: Path) -> list[CityInput]:
    cities: list[CityInput] = []
    for row in _read_records(path):
        cities.append(
            CityInput(
                city_id=str(row.get("city_id", "")).strip(),
                api_name=str(row.get("api_name", "")).strip(),
                latitude=parse_optional_float(row.get("latitude")),
                longitude=parse_optional_float(row.get("longitude")),
            )
        )
    return cities


def load_readings(path: Path) -> list[AqiReadingInput]:
    readings: list[AqiReadingInput] = []
    for row in _read_records(path):
        readings.append(
            AqiReadingInput(
                city_id=str(row.get("city_id", "")).strip(),
                reading_timestamp=parse_utc_timestamp(row.get("reading_timestamp")),
                temperature_c=parse_optional_float(row.get("temperature_c")),
                humidity_percent=parse_optional_float(row.get("humidity_percent")),
                wind_speed_ms=parse_optional_float(row.get("wind_speed_ms")),
                wind_direction_deg=parse_optional_float(row.get("wind_direction_deg")),
            )
        )
    return readings


def build_open_meteo_params(city: CityInput, start_date: str, end_date: str) -> dict[str, Any]:
    return {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
    }


def fetch_open_meteo_hours(
    city: CityInput,
    *,
    start_date: str,
    end_date: str,
    timeout_seconds: int = 45,
) -> list[WeatherHour]:
    params = build_open_meteo_params(city, start_date, end_date)
    response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    return parse_open_meteo_hours(response.json())


def parse_open_meteo_hours(payload: dict[str, Any]) -> list[WeatherHour]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return []

    times = hourly.get("time") or []
    temperatures = hourly.get("temperature_2m") or []
    humidities = hourly.get("relative_humidity_2m") or []
    wind_speeds = hourly.get("wind_speed_10m") or []
    wind_directions = hourly.get("wind_direction_10m") or []
    wind_gusts = hourly.get("wind_gusts_10m") or []

    weather_hours: list[WeatherHour] = []
    for index, raw_time in enumerate(times):
        timestamp = parse_utc_timestamp(str(raw_time))
        if timestamp is None:
            continue
        weather_hours.append(
            WeatherHour(
                timestamp=timestamp,
                temperature_c=_list_float(temperatures, index),
                humidity_percent=_list_float(humidities, index),
                wind_speed_kmh=_list_float(wind_speeds, index),
                wind_direction_deg=_list_float(wind_directions, index),
                wind_gust_kmh=_list_float(wind_gusts, index),
            )
        )
    return weather_hours


def _list_float(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    return parse_optional_float(values[index])


def find_nearest_weather_hour(
    reading_timestamp: datetime,
    weather_hours: list[WeatherHour],
    *,
    threshold_minutes: float = MATCH_THRESHOLD_MINUTES,
) -> tuple[WeatherHour | None, float | None]:
    if not weather_hours:
        return None, None

    best = min(
        weather_hours,
        key=lambda hour: (
            abs((hour.timestamp - reading_timestamp).total_seconds()),
            hour.timestamp > reading_timestamp,
        ),
    )
    delta_minutes = abs((best.timestamp - reading_timestamp).total_seconds()) / 60
    if delta_minutes > threshold_minutes:
        return None, delta_minutes
    return best, delta_minutes


def validate_weather_row(
    *,
    city: CityInput,
    reading: AqiReadingInput,
    weather_hour: WeatherHour,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    selected = {
        "weather_temperature_c": weather_hour.temperature_c,
        "weather_humidity_percent": weather_hour.humidity_percent,
        "weather_wind_speed_kmh": weather_hour.wind_speed_kmh,
        "weather_wind_direction_deg": weather_hour.wind_direction_deg,
        "weather_wind_gust_kmh": weather_hour.wind_gust_kmh,
    }
    if any(value is not None for value in selected.values()):
        if not PROVIDER or weather_hour.timestamp is None:
            issues.append(
                _issue(
                    "weather_nullability",
                    "error",
                    city,
                    reading,
                    "Weather source metadata missing",
                )
            )

    temperature = weather_hour.temperature_c
    if temperature is not None:
        if temperature < -50 or temperature > 60:
            issues.append(
                _issue(
                    "weather_temperature_out_of_hard_range",
                    "error",
                    city,
                    reading,
                    "Temperature outside -50..60 C",
                )
            )
        elif temperature < -20:
            issues.append(
                _issue(
                    "weather_temperature_monterrey_low_warning",
                    "warning",
                    city,
                    reading,
                    "Temperature below Monterrey QA warning range",
                )
            )
        if (
            reading.temperature_c is not None
            and abs(temperature - reading.temperature_c) >= TEMPERATURE_DELTA_WARNING_C
        ):
            issues.append(
                _issue(
                    "large_temperature_delta_vs_waqi",
                    "warning",
                    city,
                    reading,
                    "Temperature delta vs WAQI legacy field >= 8 C",
                )
            )

    humidity = weather_hour.humidity_percent
    if humidity is not None:
        if humidity < 0 or humidity > 100:
            issues.append(
                _issue(
                    "weather_humidity_out_of_range",
                    "error",
                    city,
                    reading,
                    "Humidity outside 0..100 percent",
                )
            )
        if (
            reading.humidity_percent is not None
            and abs(humidity - reading.humidity_percent) >= HUMIDITY_DELTA_WARNING_POINTS
        ):
            issues.append(
                _issue(
                    "large_humidity_delta_vs_waqi",
                    "warning",
                    city,
                    reading,
                    "Humidity delta vs WAQI legacy field >= 25 points",
                )
            )

    wind_speed = weather_hour.wind_speed_kmh
    if wind_speed is not None:
        if wind_speed < 0:
            issues.append(
                _issue(
                    "weather_wind_speed_negative",
                    "error",
                    city,
                    reading,
                    "Wind speed is negative",
                )
            )
        elif wind_speed > 160:
            issues.append(
                _issue(
                    "weather_wind_speed_high_warning",
                    "warning",
                    city,
                    reading,
                    "Wind speed above 160 km/h",
                )
            )

    wind_gust = weather_hour.wind_gust_kmh
    if wind_gust is not None:
        if wind_gust < 0:
            issues.append(
                _issue(
                    "weather_wind_gust_negative",
                    "error",
                    city,
                    reading,
                    "Wind gust is negative",
                )
            )
        elif wind_gust > 220:
            issues.append(
                _issue(
                    "weather_wind_gust_high_warning",
                    "warning",
                    city,
                    reading,
                    "Wind gust above 220 km/h",
                )
            )

    wind_direction = weather_hour.wind_direction_deg
    if wind_direction is not None and (wind_direction < 0 or wind_direction > 360):
        issues.append(
            _issue(
                "weather_wind_direction_out_of_range",
                "error",
                city,
                reading,
                "Wind direction outside 0..360 degrees",
            )
        )

    return issues


def _issue(
    code: str,
    severity: str,
    city: CityInput,
    reading: AqiReadingInput,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "city_id": city.city_id,
        "api_name": city.api_name,
        "reading_timestamp": (
            reading.reading_timestamp.isoformat().replace("+00:00", "Z")
            if reading.reading_timestamp
            else None
        ),
        "message": message,
    }
    if extra:
        for key, value in extra.items():
            payload[key] = value
    return payload


def build_dry_run_report(
    *,
    cities: list[CityInput],
    readings: list[AqiReadingInput],
    weather_fetcher: Callable[[CityInput, str, str], list[WeatherHour]] | None = None,
    window_days: int = 60,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    fetcher = weather_fetcher or _default_weather_fetcher
    generated = generated_at or datetime.now(timezone.utc)
    cities_by_id = {city.city_id: city for city in cities}
    readings_by_city: dict[str, list[AqiReadingInput]] = {}
    validation_issues: list[dict[str, Any]] = []
    city_results: list[dict[str, Any]] = []

    for reading in readings:
        readings_by_city.setdefault(reading.city_id, []).append(reading)

    total_matched = 0
    total_unmatched = 0
    null_weather_rows = 0
    large_delta_rows = 0

    for city in cities:
        city_readings = readings_by_city.get(city.city_id, [])
        city_issues: list[dict[str, Any]] = []
        matched_rows: list[dict[str, Any]] = []
        max_delta_minutes: float | None = None
        weather_hours: list[WeatherHour] = []

        if city.latitude is None or city.longitude is None:
            city_issues.append(
                _issue(
                    "missing_coordinates",
                    "error",
                    city,
                    _empty_reading(city),
                    "City is missing latitude or longitude",
                )
            )
        else:
            dated_readings = [
                reading for reading in city_readings if reading.reading_timestamp is not None
            ]
            if dated_readings:
                start_date = min(
                    reading.reading_timestamp
                    for reading in dated_readings
                    if reading.reading_timestamp
                ).date().isoformat()
                end_date = max(
                    reading.reading_timestamp
                    for reading in dated_readings
                    if reading.reading_timestamp
                ).date().isoformat()
                try:
                    weather_hours = fetcher(city, start_date, end_date)
                except Exception as exc:  # noqa: BLE001 - keep provider failure context.
                    city_issues.append(
                        _issue("open_meteo_fetch_failed", "error", city, dated_readings[0], str(exc))
                    )

        for reading in city_readings:
            if reading.reading_timestamp is None:
                issue = _issue(
                    "missing_reading_timestamp",
                    "error",
                    city,
                    reading,
                    "AQI candidate row is missing reading_timestamp",
                )
                city_issues.append(issue)
                total_unmatched += 1
                continue

            match, delta_minutes = find_nearest_weather_hour(reading.reading_timestamp, weather_hours)
            if match is None:
                issue = _issue(
                    "unmatched_weather_hour",
                    "warning",
                    city,
                    reading,
                    "No Open-Meteo hourly weather bucket within threshold",
                    {"nearest_delta_minutes": delta_minutes},
                )
                city_issues.append(issue)
                total_unmatched += 1
                continue

            weather_issues = validate_weather_row(city=city, reading=reading, weather_hour=match)
            city_issues.extend(weather_issues)
            if any(issue["code"].startswith("large_") for issue in weather_issues):
                large_delta_rows += 1
            if all(
                value is None
                for value in (
                    match.temperature_c,
                    match.humidity_percent,
                    match.wind_speed_kmh,
                    match.wind_direction_deg,
                    match.wind_gust_kmh,
                )
            ):
                null_weather_rows += 1

            max_delta_minutes = (
                delta_minutes
                if max_delta_minutes is None
                else max(max_delta_minutes, delta_minutes or 0)
            )
            matched_rows.append(_matched_row(reading, match, delta_minutes))
            total_matched += 1

        validation_issues.extend(city_issues)
        city_results.append(
            _city_result(
                city=city,
                target_rows=len(city_readings),
                matched_rows=matched_rows,
                max_delta_minutes=max_delta_minutes,
                issues=city_issues,
            )
        )

    unknown_city_readings = [reading for reading in readings if reading.city_id not in cities_by_id]
    for reading in unknown_city_readings:
        placeholder_city = CityInput(reading.city_id, "", None, None)
        validation_issues.append(
            _issue(
                "unknown_city_id",
                "error",
                placeholder_city,
                reading,
                "Reading city_id not found in cities input",
            )
        )
        total_unmatched += 1

    range_violations = sum(
        1 for issue in validation_issues if "range" in issue["code"] or "negative" in issue["code"]
    )
    unit_violations = sum(
        1 for issue in validation_issues if issue["code"] == "weather_wind_unit_violation"
    )

    return {
        "mode": MODE,
        "provider": PROVIDER,
        "window_days": window_days,
        "generated_at": generated.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "summary": {
            "active_cities": len(cities),
            "target_aqi_rows": len(readings),
            "matched_rows": total_matched,
            "unmatched_rows": total_unmatched,
            "null_weather_rows": null_weather_rows,
            "unit_violations": unit_violations,
            "range_violations": range_violations,
            "large_delta_vs_waqi_rows": large_delta_rows,
            "validation_issue_count": len(validation_issues),
        },
        "city_results": city_results,
        "validation_issues": validation_issues,
        "unit_contract": {
            "weather_wind_speed_field": "weather_wind_speed_kmh",
            "open_meteo_wind_speed_unit": "kmh",
            "legacy_wind_speed_field": "wind_speed_ms",
            "legacy_wind_compare_rule": "compare only after explicit m/s to km/h normalization",
        },
    }


def _default_weather_fetcher(city: CityInput, start_date: str, end_date: str) -> list[WeatherHour]:
    return fetch_open_meteo_hours(city, start_date=start_date, end_date=end_date)


def _empty_reading(city: CityInput) -> AqiReadingInput:
    return AqiReadingInput(city_id=city.city_id, reading_timestamp=None)


def _matched_row(
    reading: AqiReadingInput,
    weather_hour: WeatherHour,
    delta_minutes: float | None,
) -> dict[str, Any]:
    return {
        "reading_timestamp": (
            reading.reading_timestamp.isoformat().replace("+00:00", "Z")
            if reading.reading_timestamp
            else None
        ),
        "weather_timestamp": weather_hour.timestamp.isoformat().replace("+00:00", "Z"),
        "alignment_delta_minutes": round(delta_minutes or 0, 3),
        "weather_provider": PROVIDER,
        "weather_temperature_c": weather_hour.temperature_c,
        "weather_humidity_percent": weather_hour.humidity_percent,
        "weather_wind_speed_kmh": weather_hour.wind_speed_kmh,
        "weather_wind_direction_deg": weather_hour.wind_direction_deg,
        "weather_wind_gust_kmh": weather_hour.wind_gust_kmh,
    }


def _city_result(
    *,
    city: CityInput,
    target_rows: int,
    matched_rows: list[dict[str, Any]],
    max_delta_minutes: float | None,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    temperatures = [
        row["weather_temperature_c"]
        for row in matched_rows
        if row["weather_temperature_c"] is not None
    ]
    wind_speeds = [
        row["weather_wind_speed_kmh"]
        for row in matched_rows
        if row["weather_wind_speed_kmh"] is not None
    ]
    humidities = [
        row["weather_humidity_percent"]
        for row in matched_rows
        if row["weather_humidity_percent"] is not None
    ]
    return {
        "city_id": city.city_id,
        "api_name": city.api_name,
        "target_rows": target_rows,
        "matched_rows": len(matched_rows),
        "unmatched_rows": target_rows - len(matched_rows),
        "max_alignment_delta_minutes": (
            round(max_delta_minutes, 3) if max_delta_minutes is not None else None
        ),
        "temperature_min_c": min(temperatures) if temperatures else None,
        "temperature_max_c": max(temperatures) if temperatures else None,
        "humidity_min_percent": min(humidities) if humidities else None,
        "humidity_max_percent": max(humidities) if humidities else None,
        "wind_speed_max_kmh": max(wind_speeds) if wind_speeds else None,
        "issue_count": len(issues),
        "sample_matches": matched_rows[:5],
    }


def write_report(report: dict[str, Any], output_path: Path | None) -> None:
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if output_path is None:
        print(serialized)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a dry-run Open-Meteo weather context evidence report."
    )
    parser.add_argument("--cities", required=True, type=Path, help="Local JSON/CSV active cities export")
    parser.add_argument(
        "--readings", required=True, type=Path, help="Local JSON/CSV AQI candidate readings export"
    )
    parser.add_argument("--window-days", type=int, default=60, help="Evidence window label")
    parser.add_argument("--output", type=Path, help="Optional local report path")
    args = parser.parse_args(argv)

    cities = load_cities(args.cities)
    readings = load_readings(args.readings)
    report = build_dry_run_report(cities=cities, readings=readings, window_days=args.window_days)
    write_report(report, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
