from dotenv import load_dotenv
import os
import jwt
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY no está configurada")

# Convertir la clave a bytes solo para decodificar el token
SUPABASE_SERVICE_ROLE_KEY_bytes = SUPABASE_SERVICE_ROLE_KEY.encode('utf-8')
payload = jwt.decode(SUPABASE_SERVICE_ROLE_KEY_bytes, options={"verify_signature": False})
print(f"🔑 Detalle del token: rol = {payload.get('role')}")

def is_probably_service_role(key: str) -> bool:
    try:
        # No necesitamos convertir a bytes aquí
        payload = jwt.decode(key, options={"verify_signature": False})
        return payload.get("role") == "service_role"
    except Exception:
        return False

def get_existing_cities():
    print("--- Iniciando Get Existing Cities from Supabase ---")

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("❌ Supabase URL y Service Role Key son requeridas.")

    if not is_probably_service_role(SUPABASE_SERVICE_ROLE_KEY):
        print("⚠️ Advertencia: Esta clave no parece ser una 'service_role key'. Revisa que estés usando la correcta.")

    try:
        # Usamos la clave original como string
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("✅ Cliente Supabase creado.")

    except Exception as e:
        raise Exception(f"Error creando cliente Supabase: {str(e)}")

    try:
        print("🔎 Consultando tabla 'cities' por columnas: id, api_name, is_active...")
        response = supabase.table("cities").select("id, api_name, is_active").execute()

        if not isinstance(response.data, list):
            raise ValueError("❌ La respuesta de Supabase no es un array.")

        print(f"✅ Consulta exitosa. Se encontraron {len(response.data)} ciudades.")
        return response.data

    except Exception as e:
        raise Exception(f"Fallo al obtener ciudades existentes de Supabase: {str(e)}")