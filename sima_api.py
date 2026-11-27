"""Respaldo de calidad del aire con el visor oficial del SIMA (Nuevo León).

WAQI republica los datos del SIMA, pero su feed puede congelarse (ocurrió desde
el 12 de noviembre de 2026). Este módulo lee directamente el visor del SIMA y
devuelve un resultado con la misma forma que ``waqi_api.fetch_air_quality_data``
para que ``update_city`` lo valide e inserte sin cambios de esquema.

El valor ``aqi_us`` es el índice horario NowCast que publica el SIMA para el
contaminante dominante de la estación (Índice AIRE y SALUD, NOM-172), no un AQI
recalculado con la escala de la EPA.
"""

import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

SIMA_SOURCE_URL = "https://aire.nl.gob.mx/airemapbing/airebing_icars_alt_ns_newNL_4_L3.php"
SIMA_TIMEOUT_SECONDS = 20
# El SIMA publica la hora de reporte en hora estándar local (UTC-6).
MONTERREY_STANDARD_TIME = timezone(timedelta(hours=-6))

# Una estación principal por municipio, la misma que usaba el mapping de WAQI.
SIMA_STATION_BY_API_NAME = {
    "Monterrey": "centro",
    "San Nicolas de los Garza": "noreste",
    "Guadalupe": "sureste",
    "San Pedro Garza Garcia": "suroeste2",
    "Santa Catarina": "suroeste",
    "General Escobedo": "norte",
    "Garcia": "noroeste2",
    "García": "noroeste2",
    "Ciudad Benito Juarez": "sureste2",
    "Ciudad Benito Juárez": "sureste2",
    "Benito Juarez": "sureste2",
    "Benito Juárez": "sureste2",
    "Cadereyta Jimenez": "sureste3",
    "Cadereyta Jiménez": "sureste3",
    "Cadereyta": "sureste3",
}

POLLUTANT_MAP = {
    "PM25": "pm25",
    "PM10": "pm10",
    "O3": "o3",
    "NO2": "no2",
    "SO2": "so2",
    "CO": "co",
}

_station_cache: dict[str, Any] = {}


def parse_station_indexes(html: str) -> dict[str, dict[str, Any]]:
    """Devuelve la fila más reciente del índice dominante por estación."""
    assignment = re.search(r"\bvar\s+arrayIMKTodo11\s*=\s*", html)
    if not assignment:
        raise ValueError("El visor de SIMA no incluye la tabla de índices esperada.")
    rows, _ = json.JSONDecoder().raw_decode(html, assignment.end())
    if not isinstance(rows, list):
        raise ValueError("La tabla de índices de SIMA tiene un formato inesperado.")

    stations: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        station = row.get("Estacion")
        index = row.get("HrAveData")
        if not isinstance(station, str) or isinstance(index, bool) or not isinstance(index, (int, float)):
            continue
        if not math.isfinite(index) or index < 0:
            continue
        try:
            observed_at = datetime.strptime(row["Date"], "%Y-%m-%d %H:%M").replace(
                tzinfo=MONTERREY_STANDARD_TIME
            )
        except (KeyError, TypeError, ValueError):
            continue
        previous = stations.get(station)
        if previous is None or observed_at > previous["observed_at"]:
            stations[station] = {"row": row, "observed_at": observed_at, "index": index}
    return stations


def get_station_indexes() -> dict[str, dict[str, Any]]:
    """Descarga el visor una sola vez por corrida."""
    if "stations" not in _station_cache:
        response = requests.get(SIMA_SOURCE_URL, timeout=SIMA_TIMEOUT_SECONDS)
        logging.info("[SIMA] HTTP GET %s status=%s", SIMA_SOURCE_URL, response.status_code)
        response.raise_for_status()
        _station_cache["stations"] = parse_station_indexes(response.text)
    return _station_cache["stations"]


def reset_cache() -> None:
    _station_cache.clear()


def fetch_air_quality_data(
    api_name: str,
    city_id: int,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, Any]:
    logging.info("--- Iniciando fetch SIMA para City ID: %s (%s) ---", city_id, api_name)
    station_id = SIMA_STATION_BY_API_NAME.get(api_name)
    if not station_id:
        return build_error_result(city_id, api_name, "station_not_mapped", f"Sin estación SIMA para {api_name}.")
    if latitude is None or longitude is None:
        return build_error_result(
            city_id, api_name, "missing_coordinates", "La ciudad no tiene coordenadas en Supabase.", station_id
        )

    try:
        stations = get_station_indexes()
    except Exception as error:
        logging.error("[SIMA] Error al obtener el visor: %s", error)
        return build_error_result(city_id, api_name, "fetch_failed", str(error), station_id)

    entry = stations.get(station_id)
    if not entry:
        return build_error_result(
            city_id, api_name, "station_without_data", f"SIMA no publicó la estación {station_id}.", station_id
        )

    row = entry["row"]
    timestamp = entry["observed_at"].astimezone(timezone.utc).isoformat()
    index = entry["index"]
    aqi = int(index) if float(index).is_integer() else index
    return {
        "city_id": city_id,
        "status": "success",
        "municipio": api_name,
        "api_name_used": api_name,
        "provider": "sima",
        "provider_station_id": station_id,
        "coordenadas": {"lat": latitude, "lon": longitude},
        "calidad_aire": {
            "aqi_us": aqi,
            "contaminante_principal_us": POLLUTANT_MAP.get(str(row.get("contaminante")), None),
            "aqi_cn": None,
            "contaminante_principal_cn": None,
        },
        "clima": {
            "temperatura_c": None,
            "presion_hpa": None,
            "humedad_relativa": None,
            "velocidad_viento_ms": None,
            "direccion_viento_deg": None,
            "icono_clima": None,
        },
        "ultima_actualizacion": timestamp,
        "reading_timestamp_iso": timestamp,
        "api_raw_response": {
            "provider": "sima",
            "source_url": SIMA_SOURCE_URL,
            "index_scale": "SIMA NowCast (Indice AIRE y SALUD, NOM-172)",
            "station": station_id,
            "row": row,
        },
    }


def build_error_result(
    city_id: int,
    api_name: str,
    error_type: str,
    message: str,
    station_id: str | None = None,
) -> dict[str, Any]:
    logging.warning("[SIMA] %s para City ID %s (%s): %s", error_type, city_id, api_name, message)
    return {
        "city_id": city_id,
        "status": "error",
        "municipio": api_name,
        "api_name_used": api_name,
        "provider": "sima",
        "provider_station_id": station_id,
        "errorType": error_type,
        "message": message,
    }
