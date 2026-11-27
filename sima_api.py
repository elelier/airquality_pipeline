"""Respaldo de calidad del aire con el visor oficial del SIMA (Nuevo León).

WAQI republica los datos del SIMA, pero su feed puede congelarse (ocurrió desde
el 12 de noviembre de 2026). Este módulo lee directamente el visor del SIMA y
devuelve un resultado con la misma forma que ``waqi_api.fetch_air_quality_data``
para que ``update_city`` lo valide e inserte sin cambios de esquema.

El SIMA publica su propio índice (AIRE y SALUD, NOM-172) y la concentración
NowCast del contaminante dominante. Para no mezclar escalas en ``aqi_us``, la
concentración se convierte a AQI de la EPA con los puntos de corte oficiales; el
índice del SIMA se conserva en ``api_raw_response``.
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

# Puntos de corte AQI de la EPA (PM2.5 según la revisión de 2024).
# (concentración baja, concentración alta, AQI bajo, AQI alto)
US_AQI_BREAKPOINTS = {
    "PM25": [
        (0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
        (55.5, 125.4, 151, 200), (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500),
    ],
    "PM10": [
        (0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150),
        (255, 354, 151, 200), (355, 424, 201, 300), (425, 604, 301, 500),
    ],
    # Por encima de 200 ppb la EPA usa la tabla de ozono de 1 hora (NowCast horario).
    "O3": [
        (0, 54, 0, 50), (55, 70, 51, 100), (71, 85, 101, 150), (86, 105, 151, 200),
        (106, 200, 201, 300), (205, 404, 201, 300), (405, 604, 301, 500),
    ],
    "NO2": [
        (0, 53, 0, 50), (54, 100, 51, 100), (101, 360, 101, 150),
        (361, 649, 151, 200), (650, 1249, 201, 300), (1250, 2049, 301, 500),
    ],
    "SO2": [
        (0, 35, 0, 50), (36, 75, 51, 100), (76, 185, 101, 150),
        (186, 304, 151, 200), (305, 604, 201, 300), (605, 1004, 301, 500),
    ],
    "CO": [
        (0.0, 4.4, 0, 50), (4.5, 9.4, 51, 100), (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200), (15.5, 30.4, 201, 300), (30.5, 50.4, 301, 500),
    ],
}
# Decimales con los que la EPA trunca cada concentración antes de interpolar.
US_AQI_TRUNCATION = {"PM25": 1, "PM10": 0, "O3": 0, "NO2": 0, "SO2": 0, "CO": 1}

_station_cache: dict[str, Any] = {}


def concentration_to_us_aqi(pollutant: str, concentration: float) -> int | None:
    """Convierte una concentración a AQI de la EPA; ``None`` si no aplica."""
    breakpoints = US_AQI_BREAKPOINTS.get(pollutant)
    if not breakpoints or not math.isfinite(concentration) or concentration < 0:
        return None
    factor = 10 ** US_AQI_TRUNCATION[pollutant]
    value = math.floor(concentration * factor) / factor
    for c_low, c_high, i_low, i_high in breakpoints:
        if value <= c_high:
            value = max(value, c_low)
            return round((i_high - i_low) / (c_high - c_low) * (value - c_low) + i_low)
    return 500


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
    pollutant = str(row.get("contaminante"))
    try:
        concentration = float(row.get("concentracion"))
    except (TypeError, ValueError):
        concentration = math.nan
    aqi = concentration_to_us_aqi(pollutant, concentration)
    if aqi is None:
        return build_error_result(
            city_id,
            api_name,
            "unconvertible_reading",
            f"No se pudo convertir {pollutant}={row.get('concentracion')} a AQI EPA.",
            station_id,
        )
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
            "contaminante_principal_us": POLLUTANT_MAP.get(pollutant),
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
            "aqi_us_method": "EPA breakpoints applied to SIMA NowCast concentration of dominant pollutant",
            "sima_index": entry["index"],
            "sima_index_scale": "Indice AIRE y SALUD (NOM-172)",
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
