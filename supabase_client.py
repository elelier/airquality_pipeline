from dotenv import load_dotenv
import os
import logging
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """Crea y devuelve un cliente de Supabase."""
    # Recargar las variables de entorno en cada llamada para permitir su
    # configuración durante las pruebas.
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        raise ValueError("Supabase URL and Service Role Key are required.")

    try:
        return create_client(supabase_url, service_role_key)
    except Exception as e:
        raise Exception(f"Error creating Supabase client: {str(e)}")

def get_existing_cities():
    logging.info("Starting Get Existing Cities from Supabase")
    
    supabase = get_supabase_client()
    logging.info("Supabase client created successfully.")

    try:
        logging.info("Querying 'cities' table for columns: id, api_name, is_active...")
        response = supabase.table("cities").select("id, api_name, is_active, last_successful_update_at, last_update_status").execute()

        if not isinstance(response.data, list):
            raise ValueError("Supabase response is not an array.")

        logging.info(f"Query successful. Found {len(response.data)} cities.")
        return response.data

    except Exception as e:
        raise Exception(f"Failed to get existing cities from Supabase: {str(e)}")
