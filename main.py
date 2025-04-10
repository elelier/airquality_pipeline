import time
from airvisual_api import fetch_cities, fetch_air_quality_data
from supabase_client import get_existing_cities
from sync_cities import sync_cities
from utils import check_if_update_needed
from update_city import update_city
import os

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
AIRVISUAL_API_KEY = os.getenv('AIRVISUAL_API_KEY')

# Función para obtener las ciudades activas
def get_active_cities(db_cities_list):
    return [
        {
            "id": city['id'],
            "api_name": city['api_name'],
            "last_successful_update_at": city['last_successful_update_at'],
            "last_update_status": city['last_update_status']
        }
        for city in db_cities_list if city['is_active']
    ]

def main():
    try:
        # Paso 1: Obtener las ciudades desde la API de AirVisual
        api_cities = fetch_cities(AIRVISUAL_API_KEY)

        # Paso 2: Obtener las ciudades desde Supabase
        db_cities = get_existing_cities()

        # Paso 3: Sincronizar los datos
        summary, updated_db_cities_list = sync_cities(api_cities, db_cities, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

        # Paso 4: Obtener las ciudades activas de la lista actualizada
        active_cities = get_active_cities(updated_db_cities_list)

        # Paso 5: Verificar si alguna ciudad necesita actualización
        for city in active_cities:
            result = check_if_update_needed(city)
            
            if result["needsUpdate"]:
                print(f"🌬️ Ciudad {city['api_name']} necesita actualización.")

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
                    fetch_or_skip_result=fetch_result,
                    supabase_url=SUPABASE_URL,
                    supabase_service_role_key=SUPABASE_SERVICE_ROLE_KEY
                )

                print(f"✅ Update realizado para {city['api_name']}: {update_result}")
            else:
                print(f"⏭️ Ciudad {city['api_name']} no necesita actualización.")

        # Paso 6: Mostrar las ciudades activas
        print("\n📍 Ciudades activas:")
        for city in active_cities:
            print(f"ID: {city['id']}, Nombre: {city['api_name']}, Última actualización exitosa: {city['last_successful_update_at']}, Estado: {city['last_update_status']}")

    except Exception as e:
        # En caso de que ocurra un error, lo manejamos y seguimos
        print(f"⚠️ Ocurrió un error: {e}")
    
    # Espera de 3 horas antes de volver a ejecutar el ciclo
    print("🔄 Esperando 3 horas para la próxima ejecución...")
    time.sleep(3 * 60 * 60)  # Espera de 3 horas (3 horas * 60 minutos * 60 segundos)

if __name__ == "__main__":
        main()
