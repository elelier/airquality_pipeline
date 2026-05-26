import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

import requests

PROVIDER_NAME = "open-meteo"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 20
MAX_FETCH_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)


def enrich_with_weather_context(
    reading: dict[str, Any],
    canonical_lat: Any = None,
    canonical_lon: Any = None,
) -> dict[str, Any]:
    if reading.get("status") != "success":
        return reading

    reading_coordinates = (
        reading.get("coordenadas")
        if isinstance(reading.get("coordenadas"), dict)
        else {}
    )
    lat = canonical_lat if parse_number(canonical_lat) is not None else reading_coordinates.get("lat")
    lon = canonical_lon if parse_number(canonical_lon) is not None else reading_coordinates.get("lon")

    context = fetch_weather_context(lat, lon)
    return {**reading, "weather_context": context}


def fetch_weather_context(lat: Any, lon: Any) -> dict[str, Any]:
    parsed_lat = parse_number(lat)
    parsed_lon = parse_number(lon)
    if parsed_lat is None or parsed_lon is None:
        return build_weather_error("missing_coordinates", "Weather context requires lat/lon.")

    last_error: dict[str, Any] | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        result = fetch_weather_context_once(parsed_lat, parsed_lon, attempt)
        if result.get("status") == "success":
            return result

        last_error = result
        should_retry = bool(result.get("retryable"))
        if not should_retry or attempt >= MAX_FETCH_ATTEMPTS:
            return result

        logging.warning(
            "[Weather] Retrying Open-Meteo fetch after %s/%s retryable failure: %s",
            attempt,
            MAX_FETCH_ATTEMPTS,
            result.get("errorType"),
        )
        time.sleep(RETRY_DELAY_SECONDS)

    return last_error or build_weather_error("fetch_failed", "Unknown weather fetch failure.")


def fetch_weather_context_once(
    parsed_lat: int | float,
    parsed_lon: int | float,
    attempt: int,
) -> dict[str, Any]:
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
        status_code = response.status_code
        logging.info(
            "[Weather] HTTP GET attempt=%s/%s status=%s",
            attempt,
            MAX_FETCH_ATTEMPTS,
            status_code,
        )
        if should_retry_status(status_code):
            return build_weather_error(
                "fetch_failed",
                f"Retryable HTTP status {status_code}",
                retryable=True,
            )
        if is_nonretryable_client_error_status(status_code):
            return build_weather_error(
                "fetch_failed",
                f"Non-retryable HTTP status {status_code}",
                retryable=False,
            )
        response.raise_for_status()
        payload = response.json()
    except ValueError as error:
        return build_weather_error("invalid_json", str(error))
    except Exception as error:
        return build_weather_error("fetch_failed", str(error), retryable=True)

    if not isinstance(payload, dict):
        return build_weather_error("invalid_payload", "Weather payload is not an object.")

    return normalize_weather_payload(payload)


def should_retry_status(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return status_code == 429 or 500 <= status_code <= 599


def is_nonretryable_client_error_status(status_code: int | None) -> bool:
    if status_code is None:
        return False
    return 400 <= status_code <= 499 and status_code != 429


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


def build_weather_error(
    error_type: str,
    message: str,
    retryable: bool = False,
) -> dict[str, Any]:
    logging.warning("[Weather] %s: %s", error_type, message)
    return {
        "status": "error",
        "provider": PROVIDER_NAME,
        "errorType": error_type,
        "message": message,
        "retryable": retryable,
    }