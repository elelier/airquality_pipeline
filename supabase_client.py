from dotenv import load_dotenv
import os
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY no está configurada")

# Verificar que la clave empieza con "service_role."
if not SUPABASE_SERVICE_ROLE_KEY.startswith("service_role."):
    print("Warning: This key does not appear to be a 'service_role key'. Please check that you are using the correct one.")

def get_existing_cities():
    print("Starting Get Existing Cities from Supabase")

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase URL and Service Role Key are required.")

    try:
        # Usamos la clave original como string
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("Supabase client created successfully.")

    except Exception as e:
        raise Exception(f"Error creating Supabase client: {str(e)}")

    try:
        print("Querying 'cities' table for columns: id, api_name, is_active...")
        response = supabase.table("cities").select("id, api_name, is_active").execute()

        if not isinstance(response.data, list):
            raise ValueError("Supabase response is not an array.")

        print(f"Query successful. Found {len(response.data)} cities.")
        return response.data

    except Exception as e:
        raise Exception(f"Failed to get existing cities from Supabase: {str(e)}")