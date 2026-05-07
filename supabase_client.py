from datetime import datetime
from dotenv import load_dotenv
import logging
import os
import socket
from urllib.parse import urlparse

from supabase import Client, create_client

EXPECTED_SUPABASE_DOMAIN_SUFFIX = ".supabase.co"
NON_API_SUPABASE_HOST_PREFIXES = ("db.",)


def get_safe_supabase_url_host(supabase_url: str) -> str:
    """Return a sanitized Supabase API host for logs/errors.

    The Supabase project URL is public configuration, but this helper avoids
    logging paths, query strings, keys, or the full original env value.
    """
    parsed = urlparse(supabase_url)
    return parsed.hostname or "unparseable-host"


def build_invalid_supabase_api_url_error(host: str) -> ValueError:
    return ValueError(
        "SUPABASE_URL no parece una API URL de Supabase. "
        "Usa https://<project-ref>.supabase.co, no el host de Postgres ni otro endpoint. "
        f"Host detectado: {host}."
    )


def validate_supabase_url(supabase_url: str) -> None:
    """Fail fast on malformed or DNS-unresolvable Supabase API URLs."""
    parsed = urlparse(supabase_url)
    host = parsed.hostname

    if parsed.scheme != "https" or not host:
        raise ValueError(
            "SUPABASE_URL debe ser la API URL pública, por ejemplo "
            "https://<project-ref>.supabase.co. "
            f"Host detectado: {host or 'unparseable-host'}."
        )

    if not host.endswith(EXPECTED_SUPABASE_DOMAIN_SUFFIX):
        raise build_invalid_supabase_api_url_error(host)

    if host.startswith(NON_API_SUPABASE_HOST_PREFIXES):
        raise build_invalid_supabase_api_url_error(host)

    try:
        socket.getaddrinfo(host, 443)
    except socket.gaierror as error:
        raise ValueError(
            "SUPABASE_URL apunta a un host que no resuelve por DNS. "
            f"Host detectado: {host}. Revisa el secret SUPABASE_URL en GitHub Actions."
        ) from error


def get_supabase_client() -> Client:
    """Crea y devuelve un cliente de Supabase."""
    # Recargar las variables de entorno en cada llamada para permitir su
    # configuración durante las pruebas.
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        raise ValueError("Supabase URL and Service Role Key are required.")

    validate_supabase_url(supabase_url)
    safe_host = get_safe_supabase_url_host(supabase_url)

    try:
        client = create_client(supabase_url, service_role_key)
        logging.info("Supabase API host validated: %s", safe_host)
        return client
    except Exception as e:
        raise Exception(f"Error creating Supabase client for host {safe_host}: {str(e)}")

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


def log_pipeline_event(event: dict):
    """Insert a pipeline log entry into Supabase (best-effort)."""
    if not isinstance(event, dict):
        return

    try:
        supabase = get_supabase_client()
        payload = {
            "city_id": event.get("city_id"),
            "city_name": event.get("city_name"),
            "status": event.get("status"),
            "context": event.get("context"),
            "details": event.get("details"),
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("pipeline_logs").insert(payload).execute()
    except Exception as e:
        logging.warning(f"Could not persist pipeline log: {e}")
