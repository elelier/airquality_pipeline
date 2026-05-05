import argparse
import json
import logging
import os
from dotenv import load_dotenv

from airvisual_api import fetch_air_quality_data
from supabase_client import get_existing_cities
from update_city import update_city
from utils import setup_logging


def resolve_city(city_name: str, city_id: int | None) -> tuple[str, int]:
    """Resolve city id from Supabase if not provided."""
    if city_id is not None:
        return city_name, city_id

    cities = get_existing_cities()
    for c in cities:
        if c.get("api_name") == city_name:
            return city_name, c["id"]

    raise ValueError(f"City {city_name} not found in Supabase. Provide --city-id explicitly.")


def main():
    parser = argparse.ArgumentParser(description="Test a single AirVisual fetch and optional Supabase insert.")
    parser.add_argument("--city", required=True, help="City name as expected by AirVisual (api_name)")
    parser.add_argument("--city-id", type=int, help="Existing Supabase city id (optional)")
    parser.add_argument("--state", default="Nuevo Leon", help="State name (default: Nuevo Leon)")
    parser.add_argument("--country", default="Mexico", help="Country name (default: Mexico)")
    parser.add_argument("--write", action="store_true", help="Persist result via update_city (default: dry-run)")
    args = parser.parse_args()

    setup_logging()
    load_dotenv()
    api_key = os.getenv("AIRVISUAL_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing AIRVISUAL_API_KEY in environment.")

    city_name, city_id = resolve_city(args.city, args.city_id)
    logging.info(f"Fetching air quality for {city_name} (id={city_id})...")
    fetch_result = fetch_air_quality_data(city_name, city_id, args.state, args.country, api_key)

    logging.info("Fetch result (raw):")
    logging.info(json.dumps(fetch_result, indent=2, default=str))

    if not args.write:
        logging.info("Dry-run mode: skipping Supabase insert/update.")
        return

    update_result = update_city(fetch_result)
    logging.info(f"Update result: {update_result}")


if __name__ == "__main__":
    main()
