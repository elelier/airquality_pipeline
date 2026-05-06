import logging
from datetime import datetime, timezone
from typing import Any

import requests

WAQI_BASE_URL = "https://api.waqi.info/feed"
WAQI_TIMEOUT_SECONDS = 45

NUEVO_LEON_LAT_RANGE = (25.0, 26.5)
NUEVO_LEON_LON_RANGE = (-101.0, -99.0)

EXPECTED_ACTIVE_API_NAMES = (
    "Monterrey",
    "San Nicolas de los Garza",
    "Guadalupe",
    "San Pedro Garza Garcia",
    "Santa Catarina",
    "General Escobedo",
    "Garcia",
    "Ciudad Benito Juarez",
    "Cadereyta Jimenez",
)

# Mapping is intentionally explicit and fail-closed. Station ids come from
# public AQICN station pages and runtime still validates status=ok, AQI,
# timestamp, and coordinates inside Nuevo Leon before inserting readings.
WAQI_STATION_BY_API_NAME = {
    "Monterrey": "6492",
    "San Nicolas de los Garza": "6493",
    "Guadalupe": "6494",
    "San Pedro Garza Garcia": "8282",
    "Santa Catarina": "6491",
    "General Escobedo": "6496",
    "Garcia": "6495",
    "Ciudad Benito Juarez": "8113",
    "Ciudad Benito Juárez": "8113",
    "Cadereyta Jimenez": "10950",
}

WAQI_STATION_EVIDENCE = {
    "Monterrey": "AQICN public station page for Obispado, Nuevo Leon lists Cloud API H6492.",
    "San Nicolas de los Garza": "Initial verified WAQI mapping from PR #3: @6493.",
    "Guadalupe": "Initial verified WAQI mapping from PR #3: @6494.",
    "San Pedro Garza Garcia": "Initial verified WAQI mapping from PR #3: @8282.",
    "Santa Catarina": "AQICN public station page for S. Catarina, Nuevo Leon lists Cloud API H6491.",
    "General Escobedo": "AQICN public station page for Escobedo, Nuevo Leon lists Cloud API H6496.",
    "Garcia": "AQICN public station page for Garcia, Nuevo Leon lists Cloud API H6495.",
    "Ciudad Benito Juarez": "AQICN public station page for Juarez, Nuevo Leon lists Cloud API H8113.",
    "Cadereyta Jimenez": "AQICN public station page for Cadereyta, Monterrey, Nuevo Leon lists Cloud API H10950.",
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


def get_station_mapping_snapshot() -> list[dict[str, Any]]:
    """Return mapping coverage for expected active municipalities.

    This helper is testable without network access and keeps docs/tests aligned
    with the fail-closed coverage registry.
    """
    return [
        {
            "api_name": api_name,
            "provider": "waqi",
            "station_id": WAQI_STATION_BY_API_NAME.get(api_name),
            "verified": bool(WAQI_STATION_BY_API_NAME.get(api_name)),
            "evidence": WAQI_STATION_EVIDENCE.get(api_name),
        }
        for api_name in EXPECTED_ACTIVE_API_NAMES
    ]


def fetch_air_quality_data(api_name: str, city_id: int, waqi_api_token: str | None) -> dict[str, Any]:
    logging.info("--- Iniciando fetch WAQI para City ID: %s (%s) ---", city_id, api_name)

    if not waqi_api_token:
        return build_error_result(city_id, api_name, "missing_token", "WAQI_API_TOKEN no configurado.")

    station_id = WAQI_STATION_BY_API_NAME.get(api_name)
    logging.info(
        "[WAQI] Mapping city_id=%s api_name=%s station=%s",
        city_id,
        api_name,
        f"@{station_id}" if station_id else "unmapped",
    )

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
        return build_error_result(city_id, api_name, "fetch_failed", str(error), station_id)


def normalize_waqi_payload(
    raw_api_data: dict[str, Any],
    api_name: str,
    city_id: int,
    station_id: str,
) -> dict[str, Any]:
    status = raw_api_data.get("status")
    if status != "ok":
        message = str(raw_api_data.get("data") or raw_api_data.get("message") or "WAQI status != ok")
        return build_error_result(city_id, api_name, "waqi_status_not_ok", message, station_id)

    data = raw_api_data.get("data")
    if not isinstance(data, dict):
        return build_error_result(city_id, api_name, "invalid_payload", "WAQI data no es objeto.", station_id)

    aqi = parse_number(data.get("aqi"))
    if aqi is None:
        return build_error_result(city_id, api_name, "missing_aqi", "WAQI payload sin AQI valido.", station_id)

    timestamp = extract_timestamp(data)
    if not timestamp:
        return build_error_result(
            city_id,
            api_name,
            "missing_reading_ts",
            "WAQI payload sin timestamp valido.",
            station_id,
        )

    coordinates = extract_coordinates(data)
    if not coordinates:
        return build_error_result(
            city_id,
            api_name,
            "missing_coordinates",
            "WAQI payload sin coordenadas validas.",
            station_id,
        )

    if not is_coordinate_in_nuevo_leon(coordinates[0], coordinates[1]):
        return build_error_result(
            city_id,
            api_name,
            "coordinates_out_of_nuevo_leon",
            f"WAQI station @{station_id} fuera de rango NL: {coordinates}.",
            station_id,
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


def build_error_result(
    city_id: int,
    api_name: str,
    error_type: str,
    message: str,
    station_id: str | None = None,
) -> dict[str, Any]:
    logging.warning("[WAQI] %s para City ID %s (%s): %s", error_type, city_id, api_name, message)
    return {
        "city_id": city_id,
        "status": "error",
        "municipio": api_name,
        "api_name_used": api_name,
        "provider": "waqi",
        "provider_station_id": station_id,
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


def is_coordinate_in_nuevo_leon(lat: float, lon: float) -> bool:
    return NUEVO_LEON_LAT_RANGE[0] <= lat <= NUEVO_LEON_LAT_RANGE[1] and (
        NUEVO_LEON_LON_RANGE[0] <= lon <= NUEVO_LEON_LON_RANGE[1]
    )
