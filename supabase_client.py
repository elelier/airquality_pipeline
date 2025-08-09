from dotenv import load_dotenv
import os
import logging
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def get_supabase_client() -> Client:
    """Crea y devuelve un cliente de Supabase."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase URL and Service Role Key are required.")
    try:
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
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
