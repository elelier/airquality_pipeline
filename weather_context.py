import logging
import math
from datetime import datetime, timezone
from typing import Any

import requests

PROVIDER_NAME = "open-meteo"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 20
CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)


def enrich_with_weather_context(reading: dict[str, Any]) -> dict[str, Any]:
    if reading.get("status") != "success":
        return reading

    coordinates = reading.get("coordenadas") if isinstance(reading.get("coordenadas"), dict) else {}
    context = fetch_weather_context(coordinates.get("lat"), coordinates.get("lon"))
    return {**reading, "weather_context": context}


def fetch_weather_context(lat: Any, lon: Any) -> dict[str, Any]:
    parsed_lat = parse_number(lat)
    parsed_lon = parse_number(lon)
    if parsed_lat is None or parsed_lon is None:
        return build_weather_error("missing_coordinates", "Weather context requires lat/lon.")

    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": parsed_lat,
                "longitude": parsed_lon,
                "current": ",".join(CURRENT_FIELDS),
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "timeformat": "iso8601",
                "timezone": "UTC",
            },
            timeout=TIMEOUT_SECONDS,
        )
        logging.info("[Weather] HTTP GET status=%s", response.status_code)
        response.raise_for_status()
        payload = response.json()
    except ValueError as error:
        return build_weather_error("invalid_json", str(error))
    except Exception as error:
        return build_weather_error("fetch_failed", str(error))

    if not isinstance(payload, dict):
        return build_weather_error("invalid_payload", "Weather payload is not an object.")

    return normalize_weather_payload(payload)


def normalize_weather_payload(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload.get("current")
    if not isinstance(current, dict):
        return build_weather_error("missing_current", "Weather payload has no current object.")

    timestamp = normalize_timestamp(current.get("time"))
    if not timestamp:
        return build_weather_error("missing_timestamp", "Weather payload has no valid time.")

    context = {
        "status": "success",
        "weather_temperature_c": parse_number(current.get("temperature_2m")),
        "weather_humidity_percent": parse_int(current.get("relative_humidity_2m")),
        "weather_wind_speed_kmh": parse_number(current.get("wind_speed_10m")),
        "weather_wind_direction_deg": parse_int(current.get("wind_direction_10m")),
        "weather_wind_gust_kmh": parse_number(current.get("wind_gusts_10m")),
        "weather_provider": PROVIDER_NAME,
        "weather_timestamp": timestamp,
        "weather_source_payload": {
            "current": {
                key: current.get(key)
                for key in ("time", *CURRENT_FIELDS)
                if key in current
            },
            "current_units": payload.get("current_units"),
        },
    }

    errors = validate_weather_context(context)
    if errors:
        return build_weather_error("validation_failed", ",".join(errors))

    return context


def validate_weather_context(context: dict[str, Any]) -> list[str]:
    errors = []
    temperature = context.get("weather_temperature_c")
    humidity = context.get("weather_humidity_percent")
    wind_speed = context.get("weather_wind_speed_kmh")
    wind_direction = context.get("weather_wind_direction_deg")
    wind_gust = context.get("weather_wind_gust_kmh")

    if temperature is not None:
        if not is_finite_number(temperature):
            errors.append("weather_temperature_c_not_finite")
        elif not (-50 <= temperature <= 60):
            errors.append("weather_temperature_c_out_of_range")
    if humidity is not None:
        if not is_finite_number(humidity):
            errors.append("weather_humidity_percent_not_finite")
        elif not (0 <= humidity <= 100):
            errors.append("weather_humidity_percent_out_of_range")
    if wind_speed is not None:
        if not is_finite_number(wind_speed):
            errors.append("weather_wind_speed_kmh_not_finite")
        elif wind_speed < 0:
            errors.append("weather_wind_speed_kmh_negative")
    if wind_direction is not None:
        if not is_finite_number(wind_direction):
            errors.append("weather_wind_direction_deg_not_finite")
        elif not (0 <= wind_direction <= 360):
            errors.append("weather_wind_direction_deg_out_of_range")
    if wind_gust is not None:
        if not is_finite_number(wind_gust):
            errors.append("weather_wind_gust_kmh_not_finite")
        elif wind_gust < 0:
            errors.append("weather_wind_gust_kmh_negative")

    has_weather_value = any(
        value is not None
        for value in (temperature, humidity, wind_speed, wind_direction, wind_gust)
    )
    if has_weather_value and not context.get("weather_provider"):
        errors.append("missing_weather_provider")
    if has_weather_value and not context.get("weather_timestamp"):
        errors.append("missing_weather_timestamp")

    return errors


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        if not math.isfinite(parsed):
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def parse_int(value: Any) -> int | None:
    parsed = parse_number(value)
    if parsed is None:
        return None
    return int(round(parsed))


def normalize_timestamp(value: Any) -> str | None:
    if not value:
        return None
    clean_value = str(value).strip()
    if not clean_value:
        return None
    if clean_value.endswith("Z"):
        clean_value = f"{clean_value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(clean_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def build_weather_error(error_type: str, message: str) -> dict[str, Any]:
    logging.warning("[Weather] %s: %s", error_type, message)
    return {
        "status": "error",
        "provider": PROVIDER_NAME,
        "errorType": error_type,
        "message": message,
    }
