import sys
import os
import logging
import time
from dotenv import load_dotenv
from airvisual_api import fetch_cities, fetch_air_quality_data
from supabase_client import get_existing_cities
from sync_cities import sync_cities
from utils import check_if_update_needed, setup_logging, compute_inter_city_delay, delay
from update_city import update_city

# Configurar logging
setup_logging()

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
AIRVISUAL_API_KEY = os.getenv('AIRVISUAL_API_KEY')

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, AIRVISUAL_API_KEY]):
    raise EnvironmentError("❌ Variables de entorno faltantes. Verifica tu archivo .env o los secretos en GitHub Actions.")


# Función para obtener las ciudades activas
def get_active_cities(db_cities_list):
    return [
        city for city in db_cities_list if city['is_active']
    ]

def main(force_update=False):
    try:
        # Paso 1: Obtener las ciudades desde la API de AirVisual
        api_cities = fetch_cities(AIRVISUAL_API_KEY)

        # Paso 2: Obtener las ciudades desde Supabase
        db_cities = get_existing_cities()

        # Paso 3: Sincronizar los datos
        summary, updated_db_cities_list = sync_cities(api_cities, db_cities)

        # Paso 4: Obtener las ciudades activas de la lista actualizada
        active_cities = get_active_cities(updated_db_cities_list)

        # Paso 5: Verificar si alguna ciudad necesita actualización
        consecutive_failures = 0
        for city in active_cities:
            city_started_at = time.perf_counter()
            result = check_if_update_needed(city, force_update)
            
            if result["needsUpdate"]:
                logging.info(f"[UPDATE] Ciudad {city['api_name']} necesita actualizacion.")

                # ✅ Paso 5.1: Obtener los datos en tiempo real desde la API
                fetch_result = fetch_air_quality_data(
                    api_name=city['api_name'],
                    city_id=city['id'],
                    state="Nuevo Leon",
                    country="Mexico",
                    AIRVISUAL_API_KEY=AIRVISUAL_API_KEY
                )
                fetch_result['city_id'] = city['id']  # Agregamos el ID local

                # ✅ Paso 5.2: Preparar e insertar/actualizar en Supabase
                update_result = update_city(
                    fetch_or_skip_result=fetch_result
                )
                successful_insert = fetch_result.get('status') == 'success' and update_result.get('readingInserted') and not update_result.get('insertError') and not update_result.get('validationErrors')
                if successful_insert:
                    consecutive_failures = 0
                    logging.info(f"[OK] Update realizado para {city['api_name']}: {update_result}")
                else:
                    consecutive_failures += 1
                    logging.warning(f"[WARN] Update con alertas para {city['api_name']}: {update_result}")
                    if consecutive_failures >= 3:
                        logging.error(f"[ALERT] {consecutive_failures} fallos consecutivos detectados. Revisar credenciales o limite de la API.")
            else:
                logging.info(f"[SKIP] Ciudad {city['api_name']} no necesita actualizacion.")
                consecutive_failures = 0

            inter_city_delay = compute_inter_city_delay(consecutive_failures)
            elapsed_city = time.perf_counter() - city_started_at
            logging.info(f"[TIMING] Ciudad {city['api_name']} procesada en {elapsed_city:.2f}s. Esperando {inter_city_delay:.1f}s antes de la siguiente (fallos consecutivos: {consecutive_failures}).")
            delay(inter_city_delay)

        # Paso 6: Mostrar las ciudades activas
        logging.info("\n[SUMMARY] Ciudades activas:")
        for city in active_cities:
            logging.info(f"ID: {city['id']}, Nombre: {city['api_name']}, Última actualización exitosa: {city['last_successful_update_at']}, Estado: {city['last_update_status']}")

    except Exception as e:
        # En caso de que ocurra un error, lo manejamos y seguimos
        logging.error(f"[ERROR] Ocurrio un error: {e}")
    
if __name__ == "__main__":
    force_update = "--force-update" in sys.argv
    main(force_update=force_update)
    logging.info("\n[DONE] Pipeline terminado exitosamente.\n")
