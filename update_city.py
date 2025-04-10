from supabase import create_client, Client
from datetime import datetime
import os
from utils import delay


def update_city(fetch_or_skip_result: dict, supabase_url: str, supabase_service_role_key: str, logging=None) -> dict:
    if logging:
        logging("--- Iniciando update_city.py ---")

    city_id = -1
    reading_data_to_insert = None
    city_status_to_update = {}

    # --- Analizar resultado del fetch o skip ---
    if 'city_id' in fetch_or_skip_result:
        city_id = fetch_or_skip_result['city_id']
        if logging:
            logging(f"Procesando resultado para City ID: {city_id}")

        if fetch_or_skip_result['status'] == 'success':
            if logging:
                logging("Resultado: Fetch Exitoso")

            data = fetch_or_skip_result
            reading_ts = data.get('reading_timestamp_iso')

            if not reading_ts:
                if logging:
                    logging("Error: Falta 'reading_timestamp_iso'")
                city_status_to_update = {
                    'last_update_status': 'error: missing_reading_ts',
                    'updated_at': datetime.utcnow().isoformat()
                }
            else:
                reading_data_to_insert = {
                    'city_id': data['city_id'],
                    'reading_timestamp': reading_ts,
                    'aqi_us': data.get('calidad_aire', {}).get('aqi_us'),
                    'main_pollutant_us': data.get('calidad_aire', {}).get('contaminante_principal_us'),
                    'temperature_c': data.get('clima', {}).get('temperatura_c'),
                    'pressure_hpa': data.get('clima', {}).get('presion_hpa'),
                    'humidity_percent': data.get('clima', {}).get('humedad_relativa'),
                    'wind_speed_ms': data.get('clima', {}).get('velocidad_viento_ms'),
                    'wind_direction_deg': data.get('clima', {}).get('direccion_viento_deg'),
                    'weather_icon': data.get('clima', {}).get('icono_clima'),
                    'raw_api_response': data.get('api_raw_response')
                }

                city_status_to_update = {
                    'last_successful_update_at': datetime.utcnow().isoformat(),
                    'last_update_status': 'success',
                    'latitude': data.get('coordenadas', {}).get('lat'),
                    'longitude': data.get('coordenadas', {}).get('lon'),
                    'updated_at': datetime.utcnow().isoformat()
                }

        elif fetch_or_skip_result['status'] == 'error':
            city_status_to_update = {
                'last_update_status': f"error: {fetch_or_skip_result.get('errorType', 'unknown')}",
                'updated_at': datetime.utcnow().isoformat()
            }
            if logging:
                logging(f"Fetch Fallido: {city_status_to_update['last_update_status']}")
        else:
            city_status_to_update = {
                'last_update_status': 'error: unknown_fetch_result',
                'updated_at': datetime.utcnow().isoformat()
            }
            if logging:
                logging("Estado inesperado en fetch_or_skip_result")

    elif fetch_or_skip_result.get('needsUpdate') is False:
        city_id = fetch_or_skip_result.get('id', -1)
        city_status_to_update = {
            'last_update_status': 'skipped: up_to_date'
        }
        if logging:
            logging(f"Fetch Saltado para City ID: {city_id}")
    else:
        raise ValueError("Input inesperado recibido en fetch_or_skip_result")

    # --- Crear cliente Supabase ---
    supabase: Client = create_client(supabase_url, supabase_service_role_key)
    result = {
        'city_id': city_id,
        'readingInserted': False,
        'cityStatusUpdated': False,
        'insertError': None,
        'updateError': None
    }

    # --- Insert en air_quality_readings si aplica ---
    # Check if reading_data_to_insert is not empty before inserting
    if reading_data_to_insert:
        response = supabase.table('air_quality_readings').insert(reading_data_to_insert).execute()
        if response.data:
            result['readingInserted'] = True
            if logging:
                logging(f"Lectura insertada: {response.data}")
        elif response.error:
            result['insertError'] = f"Error al insertar lectura: {response.error}"
            if logging:
                logging(f"Error al insertar lectura: {response.error}")
    else:
        if logging:
            logging("No hay datos de lectura para insertar")


    # --- Update en cities ---
    if city_status_to_update:
        try:
            response = supabase.table('cities').update(city_status_to_update).eq('id', city_id).execute()
            if not response.error:
                result['cityStatusUpdated'] = True
                if logging:
                    logging(f"Ciudad actualizada: ID {city_id}")
            else:
                raise Exception(response.error)
        except Exception as e:
            result['updateError'] = str(e)
            if logging:
                logging(f"Error al actualizar ciudad: {e}")

    if logging:
        logging("--- Fin update_city.py ---")
        logging(result)
    post_success_delay_ms = 12000
    delay(post_success_delay_ms / 1000)
    return result
