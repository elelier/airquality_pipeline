import requests
import time
import sys
import logging
from datetime import datetime
from utils import delay

AIRVISUAL_TIMEOUT_SECONDS = 45

# ──────────────────────────────────────────────────────────────
# Funciones auxiliares comunes
# ──────────────────────────────────────────────────────────────

def fetch_with_retry(url, retries=3, delay_ms=5000, params=None, timeout_seconds=AIRVISUAL_TIMEOUT_SECONDS):
    for attempt in range(1, retries + 1):
        try:
            start = time.perf_counter()
            response = requests.get(url, params=params, timeout=timeout_seconds)
            elapsed = time.perf_counter() - start
            logging.info(f"HTTP GET {url} status={response.status_code} elapsed={elapsed:.2f}s")

            if not response.ok:
                error_data = response.json() if response.status_code != 429 else {}
                is_rate_limit = response.status_code == 429 or ('call_limit_reached' in error_data.get('data', {}).get('message', ''))
                if is_rate_limit and attempt < retries:
                    exponential_delay = (delay_ms / 1000) * (2 ** (attempt - 1))
                    logging.warning(f"Rate limit hit, retrying in {exponential_delay:.1f}s... ({attempt}/{retries})")
                    delay(exponential_delay)
                    continue
                raise Exception(error_data.get('data', {}).get('message', f"API Error {response.status_code}"))

            data = response.json()
            if data['status'] == 'success':
                return data

            raise Exception(data.get('data', {}).get('message', 'API returned non-success status'))
        except Exception as error:
            logging.error(f"Attempt {attempt}/{retries} failed for {url}: {error}")
            if attempt >= retries:
                raise Exception(f"Failed to fetch {url} after {retries} retries")
            # For non-rate-limit errors we still backoff modestly to avoid hammering.
            backoff_seconds = (delay_ms / 1500) * attempt
            delay(backoff_seconds)

# ──────────────────────────────────────────────────────────────
# Función para obtener ciudades
# ──────────────────────────────────────────────────────────────

def fetch_cities(AIRVISUAL_API_KEY: str, state: str = "Nuevo Leon", country: str = "Mexico", max_retries: int = 3):
    url = "http://api.airvisual.com/v2/cities"
    params = {
        "state": state,
        "country": country,
        "key": AIRVISUAL_API_KEY
    }

    for attempt in range(1, max_retries + 1):
        logging.info(f"[Attempt {attempt}] Fetching cities from AirVisual...")

        try:
            start = time.perf_counter()
            response = requests.get(url, params=params, timeout=AIRVISUAL_TIMEOUT_SECONDS)
            elapsed = time.perf_counter() - start
            logging.info(f"HTTP GET {url} status={response.status_code} elapsed={elapsed:.2f}s")

            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and isinstance(data.get("data"), list):
                    logging.info(f"[OK] Success fetching {len(data['data'])} cities from AirVisual.")
                    return data["data"]
                raise ValueError(f"Unexpected API format: {data}")

            logging.error(f"HTTP Error {response.status_code}: {response.text}")

        except Exception as e:
            logging.error(f"[ERROR] Error fetching cities (attempt {attempt}/{max_retries}): {str(e)}")

        if attempt < max_retries:
            delay(2.5)
        else:
            raise Exception("[ERROR] Max retries reached. Could not fetch cities.")

# ──────────────────────────────────────────────────────────────
# Función para obtener la calidad del aire de una ciudad
# ──────────────────────────────────────────────────────────────

def fetch_air_quality_data(api_name, city_id, state, country, AIRVISUAL_API_KEY):
    logging.info(f"--- Iniciando fetchAirQualityData para City ID: {city_id} ({api_name}) ---")

    url = "http://api.airvisual.com/v2/city"
    params = {
        "city": api_name,
        "state": state,
        "country": country,
        "key": AIRVISUAL_API_KEY
    }

    try:
        raw_api_data = fetch_with_retry(url, retries=3, delay_ms=5000, params=params, timeout_seconds=AIRVISUAL_TIMEOUT_SECONDS)

        location_data = raw_api_data.get('data', {}).get('location', {})
        pollution_data = raw_api_data.get('data', {}).get('current', {}).get('pollution', {})
        weather_data = raw_api_data.get('data', {}).get('current', {}).get('weather', {})
        timestamp_str = pollution_data.get('ts') or weather_data.get('ts') or None

        updated_at_formatted = None
        if timestamp_str:
            updated_at_formatted = datetime.fromisoformat(timestamp_str).strftime('%d/%m/%Y %H:%M:%S')

        success_result = {
            'city_id': city_id,
            'status': 'success',
            'municipio': api_name,
            'api_name_used': api_name,
            'coordenadas': {
                'lat': location_data.get('coordinates', [None, None])[1],
                'lon': location_data.get('coordinates', [None, None])[0]
            },
            'calidad_aire': {
                'aqi_us': pollution_data.get('aqius', None),
                'contaminante_principal_us': pollution_data.get('mainus', None),
                'aqi_cn': pollution_data.get('aqicn', None),
                'contaminante_principal_cn': pollution_data.get('maincn', None)
            },
            'clima': {
                'temperatura_c': weather_data.get('tp', None),
                'presion_hpa': weather_data.get('pr', None),
                'humedad_relativa': weather_data.get('hu', None),
                'velocidad_viento_ms': weather_data.get('ws', None),
                'direccion_viento_deg': weather_data.get('wd', None),
                'icono_clima': weather_data.get('ic', None)
            },
            'ultima_actualizacion': updated_at_formatted or 'N/A',
            'reading_timestamp_iso': timestamp_str,
            'api_raw_response': raw_api_data.get('data', {})
        }

        logging.info(f"[OK] Fetch exitoso para City ID: {city_id}.")
    

        return success_result

    except Exception as error:
        logging.error(f"[ERROR] Error al obtener datos para City ID: {city_id} ({api_name}): {error}")

        return {
            'city_id': city_id,
            'status': 'error',
            'municipio': api_name,
            'api_name_used': api_name,
            'errorType': 'fetch_failed',
            'message': str(error)
        }
