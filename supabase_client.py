from supabase import create_client, Client
import os

import jwt

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

payload = jwt.decode(SUPABASE_SERVICE_ROLE_KEY, options={"verify_signature": False})
print(f"🔑 Detalle del token: rol = {payload.get('role')}")

def is_probably_service_role(key: str) -> bool:
    try:
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
