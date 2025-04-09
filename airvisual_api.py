import requests
import time
from datetime import datetime

# ──────────────────────────────────────────────────────────────
# Funciones auxiliares comunes
# ──────────────────────────────────────────────────────────────

def delay(seconds):
    time.sleep(seconds)

def fetch_with_retry(url, retries=5, delay_ms=5000, params=None, logging=None):
    attempts = 0
    while int(attempts) < int(retries):
        try:
            response = requests.get(url, params=params)
            if not response.ok:
                error_data = response.json() if response.status_code != 429 else {}
                if response.status_code == 429 or ('call_limit_reached' in error_data.get('data', {}).get('message', '')):
                    raise Exception('Too Many Requests')
                raise Exception(error_data.get('data', {}).get('message', f"API Error {response.status_code}"))
            data = response.json()
            if data['status'] == 'success':
                return data
            else:
                raise Exception(data.get('data', {}).get('message', 'API returned non-success status'))
        except Exception as error:
            if str(error) == 'Too Many Requests' and attempts < retries - 1:
                exponential_delay = delay_ms * (2 ** attempts)
                if logging:
                    logging(f"Rate limit hit, retrying in {exponential_delay / 1000}s... ({attempts + 1}/{retries})")
                delay(exponential_delay / 1000)
                attempts += 1
            else:
                raise error
    raise Exception(f"Failed to fetch {url} after {retries} retries")

# ──────────────────────────────────────────────────────────────
# Función para obtener ciudades
# ──────────────────────────────────────────────────────────────

def fetch_cities(api_key: str, state: str = "Nuevo Leon", country: str = "Mexico", max_retries: int = 3):
    url = "http://api.airvisual.com/v2/cities"
    params = {
        "state": state,
        "country": country,
        "key": api_key
    }

    for attempt in range(1, max_retries + 1):
        print(f"[Attempt {attempt}] Fetching cities from AirVisual...")

        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and isinstance(data.get("data"), list):
                    print(f"✔️ Success! Fetched {len(data['data'])} cities.")
                    return data["data"]
                else:
                    raise ValueError(f"Unexpected API format: {data}")
            else:
                print(f"❌ HTTP Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"⚠️ Error: {str(e)}")

        if attempt < max_retries:
            time.sleep(2.5)
        else:
            raise Exception("❌ Max retries reached. Could not fetch cities.")

# ──────────────────────────────────────────────────────────────
# Función para obtener la calidad del aire de una ciudad
# ──────────────────────────────────────────────────────────────

def fetch_air_quality_data(api_name, city_id, state, country, api_key, logging=print):
    logging(f"--- Iniciando fetchAirQualityData para City ID: {city_id} ({api_name}) ---")

    url = "http://api.airvisual.com/v2/city"
    params = {
        "city": api_name,
        "state": state,
        "country": country,
        "key": api_key
    }

    try:
        raw_api_data = fetch_with_retry(url, retries=5, delay_ms=5000, params=params, logging=logging)

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

        logging(f"✅ Fetch exitoso para City ID: {city_id}. ")
    

        return success_result

    except Exception as error:
        logging(f"❌ Error al obtener datos para City ID: {city_id} ({api_name}): {error}")

        return {
            'city_id': city_id,
            'status': 'error',
            'municipio': api_name,
            'api_name_used': api_name,
            'errorType': 'fetch_failed',
            'message': str(error)
        }
