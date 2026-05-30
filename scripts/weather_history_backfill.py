"""Controlled Open-Meteo historical weather backfill for MtyRespira.

Default mode is dry-run. Use --apply to update only canonical weather_* columns
for existing air_quality_readings rows. AQI, pollutants, coordinates, raw provider
payloads, and legacy WAQI weather fields are never modified.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import requests

from supabase_client import get_supabase_client

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PROVIDER = "open-meteo"
DEFAULT_DAYS = 90
DEFAULT_BATCH_SIZE = 100
REQUEST_DELAY_SECONDS = 1
MATCH_THRESHOLD_MINUTES = 30
HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)
CANONICAL_UPDATE_FIELDS = (
    "weather_temperature_c",
    "weather_humidity_percent",
    "weather_wind_speed_kmh",
    "weather_wind_direction_deg",
    "weather_wind_gust_kmh",
    "weather_timestamp",
    "weather_provider",
)


@dataclass(frozen=True)
class City:
    city_id: int
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Reading:
    city_id: int
    reading_timestamp: datetime


@dataclass(frozen=True)
class WeatherHour:
    timestamp: datetime
    temperature_c: float | None
    humidity_percent: int | None
    wind_speed_kmh: float | None
    wind_direction_deg: int | None
    wind_gust_kmh: float | None


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in (float("inf"), float("-inf")) else None


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    return None if parsed is None else int(round(parsed))


def validate_weather(hour: WeatherHour) -> list[str]:
    errors: list[str] = []
    if hour.temperature_c is not None and not -50 <= hour.temperature_c <= 60:
        errors.append("weather_temperature_c_out_of_range")
    if hour.humidity_percent is not None and not 0 <= hour.humidity_percent <= 100:
        errors.append("weather_humidity_percent_out_of_range")
    if hour.wind_speed_kmh is not None and hour.wind_speed_kmh < 0:
        errors.append("weather_wind_speed_kmh_negative")
    if hour.wind_direction_deg is not None and not 0 <= hour.wind_direction_deg <= 360:
        errors.append("weather_wind_direction_deg_out_of_range")
    if hour.wind_gust_kmh is not None and hour.wind_gust_kmh < 0:
        errors.append("weather_wind_gust_kmh_negative")
    return errors


def build_archive_params(city: City, start_date: str, end_date: str) -> dict[str, Any]:
    return {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
    }


def fetch_open_meteo_hours(city: City, start_date: str, end_date: str) -> list[WeatherHour]:
    response = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params=build_archive_params(city, start_date, end_date),
        timeout=45,
    )
    response.raise_for_status()
    return parse_open_meteo_hours(response.json())


def parse_open_meteo_hours(payload: dict[str, Any]) -> list[WeatherHour]:
    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not isinstance(hourly, dict):
        return []
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    humidities = hourly.get("relative_humidity_2m") or []
    wind_speeds = hourly.get("wind_speed_10m") or []
    wind_dirs = hourly.get("wind_direction_10m") or []
    wind_gusts = hourly.get("wind_gusts_10m") or []
    hours: list[WeatherHour] = []
    for index, raw_time in enumerate(times):
        timestamp = parse_utc_timestamp(raw_time)
        if timestamp is None:
            continue
        hours.append(
            WeatherHour(
                timestamp=timestamp,
                temperature_c=_list_float(temps, index),
                humidity_percent=parse_int(_list_value(humidities, index)),
                wind_speed_kmh=_list_float(wind_speeds, index),
                wind_direction_deg=parse_int(_list_value(wind_dirs, index)),
                wind_gust_kmh=_list_float(wind_gusts, index),
            )
        )
    return hours


def _list_value(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else None


def _list_float(values: Any, index: int) -> float | None:
    return parse_float(_list_value(values, index))


def find_nearest_weather_hour(reading_time: datetime, hours: Iterable[WeatherHour]) -> tuple[WeatherHour | None, float | None]:
    hours_list = list(hours)
    if not hours_list:
        return None, None
    best = min(
        hours_list,
        key=lambda hour: (
            abs((hour.timestamp - reading_time).total_seconds()),
            hour.timestamp > reading_time,
        ),
    )
    delta_minutes = abs((best.timestamp - reading_time).total_seconds()) / 60
    if delta_minutes > MATCH_THRESHOLD_MINUTES:
        return None, delta_minutes
    return best, delta_minutes


def build_update_payload(hour: WeatherHour) -> dict[str, Any]:
    return {
        "weather_temperature_c": hour.temperature_c,
        "weather_humidity_percent": hour.humidity_percent,
        "weather_wind_speed_kmh": hour.wind_speed_kmh,
        "weather_wind_direction_deg": hour.wind_direction_deg,
        "weather_wind_gust_kmh": hour.wind_gust_kmh,
        "weather_timestamp": hour.timestamp.isoformat(),
        "weather_provider": PROVIDER,
    }


def get_active_cities(supabase: Any, city_id: int | None = None) -> list[City]:
    query = supabase.table("cities").select("id, name, latitude, longitude").eq("is_active", True)
    if city_id is not None:
        query = query.eq("id", city_id)
    response = query.order("id").execute()
    rows = response.data if isinstance(response.data, list) else []
    cities: list[City] = []
    for row in rows:
        lat = parse_float(row.get("latitude"))
        lon = parse_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        cities.append(City(int(row["id"]), str(row.get("name") or ""), lat, lon))
    return cities


def get_candidate_readings(supabase: Any, city: City, days: int, limit: int) -> list[Reading]:
    start_time = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    response = (
        supabase.table("air_quality_readings")
        .select("city_id, reading_timestamp")
        .eq("city_id", city.city_id)
        .gte("reading_timestamp", start_time)
        .or_("weather_temperature_c.is.null,weather_humidity_percent.is.null,weather_wind_speed_kmh.is.null")
        .order("reading_timestamp")
        .limit(limit)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    readings: list[Reading] = []
    for row in rows:
        reading_time = parse_utc_timestamp(row.get("reading_timestamp"))
        if reading_time is not None:
            readings.append(Reading(city.city_id, reading_time))
    return readings


def update_reading(supabase: Any, reading: Reading, payload: dict[str, Any]) -> None:
    (
        supabase.table("air_quality_readings")
        .update({field: payload[field] for field in CANONICAL_UPDATE_FIELDS})
        .eq("city_id", reading.city_id)
        .eq("reading_timestamp", reading.reading_timestamp.isoformat())
        .execute()
    )


def run_backfill(*, days: int, batch_size: int, apply: bool, city_id: int | None = None) -> dict[str, Any]:
    supabase = get_supabase_client()
    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry_run",
        "provider": PROVIDER,
        "days": days,
        "batch_size_per_city": batch_size,
        "updated_fields_only": list(CANONICAL_UPDATE_FIELDS),
        "summary": {
            "cities": 0,
            "candidate_rows": 0,
            "matched_rows": 0,
            "updated_rows": 0,
            "unmatched_rows": 0,
            "invalid_weather_rows": 0,
            "fetch_errors": 0,
        },
        "city_results": [],
    }
    for city in get_active_cities(supabase, city_id=city_id):
        readings = get_candidate_readings(supabase, city, days, batch_size)
        result = {
            "city_id": city.city_id,
            "city_name": city.name,
            "candidate_rows": len(readings),
            "matched_rows": 0,
            "updated_rows": 0,
            "unmatched_rows": 0,
            "invalid_weather_rows": 0,
            "fetch_error": None,
            "sample_updates": [],
        }
        report["summary"]["cities"] += 1
        report["summary"]["candidate_rows"] += len(readings)
        if not readings:
            report["city_results"].append(result)
            continue
        start_date = min(reading.reading_timestamp for reading in readings).date().isoformat()
        end_date = max(reading.reading_timestamp for reading in readings).date().isoformat()
        try:
            weather_hours = fetch_open_meteo_hours(city, start_date, end_date)
        except Exception as exc:  # noqa: BLE001 - evidence report must include provider failure.
            result["fetch_error"] = str(exc)
            report["summary"]["fetch_errors"] += 1
            report["city_results"].append(result)
            continue
        for reading in readings:
            match, delta_minutes = find_nearest_weather_hour(reading.reading_timestamp, weather_hours)
            if match is None:
                result["unmatched_rows"] += 1
                report["summary"]["unmatched_rows"] += 1
                continue
            errors = validate_weather(match)
            if errors:
                result["invalid_weather_rows"] += 1
                report["summary"]["invalid_weather_rows"] += 1
                continue
            payload = build_update_payload(match)
            sample = {
                "reading_timestamp": reading.reading_timestamp.isoformat(),
                "weather_timestamp": payload["weather_timestamp"],
                "alignment_delta_minutes": round(delta_minutes or 0, 3),
                "weather_temperature_c": payload["weather_temperature_c"],
                "weather_humidity_percent": payload["weather_humidity_percent"],
                "weather_wind_speed_kmh": payload["weather_wind_speed_kmh"],
            }
            if len(result["sample_updates"]) < 3:
                result["sample_updates"].append(sample)
            result["matched_rows"] += 1
            report["summary"]["matched_rows"] += 1
            if apply:
                update_reading(supabase, reading, payload)
                result["updated_rows"] += 1
                report["summary"]["updated_rows"] += 1
        report["city_results"].append(result)
        time.sleep(REQUEST_DELAY_SECONDS)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill canonical Open-Meteo weather history fields.")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--city-id", type=int)
    parser.add_argument("--apply", action="store_true", help="Write canonical weather_* fields. Default is dry-run.")
    args = parser.parse_args()
    if args.days < 1 or args.days > 366:
        raise ValueError("--days must be between 1 and 366")
    if args.batch_size < 1 or args.batch_size > 1000:
        raise ValueError("--batch-size must be between 1 and 1000")
    report = run_backfill(days=args.days, batch_size=args.batch_size, apply=args.apply, city_id=args.city_id)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
