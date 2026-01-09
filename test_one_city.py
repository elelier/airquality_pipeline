"""Script temporal para probar una sola ciudad localmente."""
import os
from dotenv import load_dotenv
from airvisual_api import fetch_air_quality_data
from update_city import update_city
from utils import setup_logging

setup_logging()
load_dotenv()

AIRVISUAL_API_KEY = os.getenv('AIRVISUAL_API_KEY')

# Cambia estos valores para probar diferentes ciudades
TEST_CITY_ID = 9  # Monterrey
TEST_CITY_NAME = "Monterrey"

print(f"\n=== Probando ciudad: {TEST_CITY_NAME} (ID: {TEST_CITY_ID}) ===\n")

# Fetch
fetch_result = fetch_air_quality_data(
    api_name=TEST_CITY_NAME,
    city_id=TEST_CITY_ID,
    state="Nuevo Leon",
    country="Mexico",
    AIRVISUAL_API_KEY=AIRVISUAL_API_KEY
)

print(f"\n--- Resultado del fetch ---")
print(f"Status: {fetch_result.get('status')}")
if fetch_result.get('status') == 'success':
    print(f"AQI US: {fetch_result.get('calidad_aire', {}).get('aqi_us')}")
    print(f"Temperatura: {fetch_result.get('clima', {}).get('temperatura_c')}°C")
    print(f"Coordenadas: {fetch_result.get('coordenadas')}")
else:
    print(f"Error: {fetch_result.get('message')}")

# Update
print(f"\n--- Intentando guardar en Supabase ---")
update_result = update_city(fetch_result)

print(f"\nResultado final:")
print(f"  - Lectura insertada: {update_result.get('readingInserted')}")
print(f"  - Ciudad actualizada: {update_result.get('cityStatusUpdated')}")
print(f"  - Errores de validación: {update_result.get('validationErrors')}")
print(f"  - Error de insert: {update_result.get('insertError')}")
print(f"  - Error de update: {update_result.get('updateError')}")

if update_result.get('readingInserted'):
    print("\n✓ ¡Éxito! La ciudad se actualizó correctamente.")
else:
    print("\n✗ No se insertó la lectura. Revisa los errores arriba.")
