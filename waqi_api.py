import logging
from datetime import datetime, timezone
from typing import Any

import requests

WAQI_BASE_URL = "https://api.waqi.info/feed"
WAQI_TIMEOUT_SECONDS = 45

WAQI_STATION_BY_API_NAME = {
    "San Nicolas de los Garza": "6493",
    "Guadalupe": "6494",
    "San Pedro Garza Garcia": "8282",
    # TODO: verify station mapping before enabling these cities.
    "Monterrey": None,
    "Santa Catarina": None,
    "General Escobedo": None,
    "Garcia": None,
    "Ciudad Benito Juarez": None,
    "Ciudad Benito Juárez": None,
    "Cadereyta Jimenez": None,
}

POLLUTANT_MAP = {
    "pm25": "pm25",
    "pm10": "pm10",
    "o3": "o3",
    "no2": "no2",
    "so2": "so2",
    "co": "co",
}


def fetch_cities() -> list[dict[str, Any]]:
    """Return an empty city sync list for WAQI.

    WAQI integration intentionally relies on existing Supabase city rows and an
    explicit station mapping. It must not deactivate cities by comparing against
    an upstream city list with different naming semantics.
    """
    logging.info("[WAQI] City sync is disabled; using active cities already in Supabase.")
    return []


def fetch_air_quality_data(api_name: str, city_id: int, waqi_api_token: str | None) -> dict[str, Any]:
    logging.info("--- Iniciando fetch WAQI para City ID: %s (%s) ---", city_id, api_name)

    if not waqi_api_token:
        return build_error_result(city_id, api_name, "missing_token", "WAQI_API_TOKEN no configurado.")

    station_id = WAQI_STATION_BY_API_NAME.get(api_name)
    if not station_id:
        return build_error_result(
            city_id,
            api_name,
            "station_not_mapped",
            f"No hay estacion WAQI verificada para api_name={api_name}.",
        )

    url = f"{WAQI_BASE_URL}/@{station_id}/"

    try:
        response = requests.get(url, params={"token": waqi_api_token}, timeout=WAQI_TIMEOUT_SECONDS)
        logging.info("[WAQI] HTTP GET %s status=%s", url, response.status_code)
        response.raise_for_status()
        raw_api_data = response.json()
        return normalize_waqi_payload(
            raw_api_data=raw_api_data,
            api_name=api_name,
            city_id=city_id,
            station_id=station_id,
        )
    except Exception as error:
        logging.error("[WAQI] Error al obtener datos para City ID %s (%s): %s", city_id, api_name, error)
        return build_error_result(city_id, api_name, "fetch_failed", str(error))


def normalize_waqi_payload(
    raw_api_data: dict[str, Any],
    api_name: str,
    city_id: int,
    station_id: str,
) -> dict[str, Any]:
    status = raw_api_data.get("status")
    if status != "ok":
        message = str(raw_api_data.get("data") or raw_api_data.get("message") or "WAQI status != ok")
        return build_error_result(city_id, api_name, "waqi_status_not_ok", message)

    data = raw_api_data.get("data")
    if not isinstance(data, dict):
        return build_error_result(city_id, api_name, "invalid_payload", "WAQI data no es objeto.")

    aqi = parse_number(data.get("aqi"))
    if aqi is None:
        return build_error_result(city_id, api_name, "missing_aqi", "WAQI payload sin AQI valido.")

    timestamp = extract_timestamp(data)
    if not timestamp:
        return build_error_result(
            city_id,
            api_name,
            "missing_reading_ts",
            "WAQI payload sin timestamp valido.",
        )

    coordinates = extract_coordinates(data)
    if not coordinates:
        return build_error_result(
            city_id,
            api_name,
            "missing_coordinates",
            "WAQI payload sin coordenadas validas.",
        )

    iaqi = data.get("iaqi") if isinstance(data.get("iaqi"), dict) else {}
    dominant_pollutant = normalize_pollutant(data.get("dominentpol"))

    return {
        "city_id": city_id,
        "status": "success",
        "municipio": api_name,
        "api_name_used": api_name,
        "provider": "waqi",
        "provider_station_id": station_id,
        "coordenadas": {
            "lat": coordinates[0],
            "lon": coordinates[1],
        },
        "calidad_aire": {
            "aqi_us": aqi,
            "contaminante_principal_us": dominant_pollutant,
            "aqi_cn": None,
            "contaminante_principal_cn": None,
        },
        "clima": {
            "temperatura_c": read_iaqi_value(iaqi, "t"),
            "presion_hpa": read_iaqi_value(iaqi, "p"),
            "humedad_relativa": read_iaqi_value(iaqi, "h"),
            "velocidad_viento_ms": read_iaqi_value(iaqi, "w"),
            "direccion_viento_deg": read_iaqi_value(iaqi, "wd"),
            "icono_clima": None,
        },
        "ultima_actualizacion": timestamp,
        "reading_timestamp_iso": timestamp,
        "api_raw_response": data,
    }


def build_error_result(city_id: int, api_name: str, error_type: str, message: str) -> dict[str, Any]:
    logging.warning("[WAQI] %s para City ID %s (%s): %s", error_type, city_id, api_name, message)
    return {
        "city_id": city_id,
        "status": "error",
        "municipio": api_name,
        "api_name_used": api_name,
        "provider": "waqi",
        "errorType": error_type,
        "message": message,
    }


def normalize_pollutant(value: Any) -> str | None:
    if not value:
        return None
    pollutant = str(value).lower()
    return POLLUTANT_MAP.get(pollutant, pollutant)


def read_iaqi_value(iaqi: dict[str, Any], key: str) -> int | float | None:
    entry = iaqi.get(key)
    if not isinstance(entry, dict):
        return None
    return parse_number(entry.get("v"))


def parse_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def extract_timestamp(data: dict[str, Any]) -> str | None:
    time_data = data.get("time")
    if not isinstance(time_data, dict):
        return None

    for key in ("iso", "s"):
        value = time_data.get(key)
        if value:
            return normalize_timestamp(str(value))

    return None


def normalize_timestamp(value: str) -> str | None:
    clean_value = value.strip()
    if not clean_value:
        return None

    if clean_value.endswith("Z"):
        clean_value = f"{clean_value[:-1]}+00:00"

    candidate = clean_value.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.isoformat()


def extract_coordinates(data: dict[str, Any]) -> tuple[float, float] | None:
    city = data.get("city")
    if not isinstance(city, dict):
        return None

    geo = city.get("geo")
    if not isinstance(geo, list) or len(geo) < 2:
        return None

    lat = parse_number(geo[0])
    lon = parse_number(geo[1])
    if lat is None or lon is None:
        return None

    return float(lat), float(lon)
