"""Archive the dominant pollutant concentration reported by SIMA per station and hour."""

import argparse
import json
import math
import re
from datetime import datetime, timedelta, timezone

import requests

SOURCE_URL = "https://aire.nl.gob.mx/airemapbing/airebing_icars_alt_ns_newNL_4_L3.php"
# SIMA publishes station report times in local standard time.
MONTERREY_TIME = timezone(timedelta(hours=-6))
STATIONS = {
    "centro": ("Centro", "Monterrey"),
    "este": ("Este", "Pesquería"),
    "noreste": ("Noreste", "San Nicolás"),
    "noreste2": ("Noreste 2", "Apodaca"),
    "noroeste": ("Noroeste", "Monterrey"),
    "noroeste2": ("Noroeste 2", "García"),
    "noroeste3": ("Noroeste 3", "García"),
    "norte": ("Norte", "Escobedo"),
    "norte2": ("Norte 2", "San Nicolás"),
    "sur": ("Sur", "Monterrey"),
    "sureste": ("Sureste", "Guadalupe"),
    "sureste2": ("Sureste 2", "Juárez"),
    "sureste3": ("Sureste 3", "Cadereyta"),
    "suroeste": ("Suroeste", "Santa Catarina"),
    "suroeste2": ("Suroeste 2", "San Pedro"),
}
POLLUTANTS = {
    "PM25": ("PM2.5", "µg/m³"),
    "PM10": ("PM10", "µg/m³"),
    "O3": ("O3", "ppb"),
    "NO2": ("NO2", "ppb"),
    "SO2": ("SO2", "ppb"),
    "CO": ("CO", "ppm"),
}


def parse_observations(html: str, now: datetime) -> list[dict]:
    assignment = re.search(r"\bvar\s+arrayIMKTodo11\s*=\s*", html)
    if not assignment:
        raise ValueError("El visor de SIMA no incluye la tabla de observaciones esperada.")
    source_rows, _ = json.JSONDecoder().raw_decode(html, assignment.end())
    if not isinstance(source_rows, list):
        raise ValueError("La tabla de observaciones de SIMA tiene un formato inesperado.")

    observations = {}
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        station = row.get("Estacion")
        pollutant = row.get("contaminante")
        index = row.get("HrAveData")
        if station not in STATIONS or pollutant not in POLLUTANTS or type(index) not in (int, float):
            continue
        if not math.isfinite(index) or index < 0 or isinstance(row.get("concentracion"), bool):
            continue
        try:
            concentration = float(row["concentracion"])
            observed_at = datetime.strptime(row["Date"], "%Y-%m-%d %H:%M").replace(tzinfo=MONTERREY_TIME)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(concentration) or concentration < 0:
            continue
        if not timedelta(0) <= now - observed_at <= timedelta(hours=6):
            continue

        station_name, municipality = STATIONS[station]
        pollutant_name, unit = POLLUTANTS[pollutant]
        timestamp = observed_at.astimezone(timezone.utc).isoformat()
        observation = {
            "station_id": station,
            "station_name": station_name,
            "municipality": municipality,
            "observed_at": timestamp,
            "pollutant": pollutant_name,
            "concentration": concentration,
            "unit": unit,
        }
        key = station, timestamp
        if key in observations and observations[key] != observation:
            raise ValueError(f"SIMA publicó observaciones incompatibles para {station} a las {timestamp}.")
        observations[key] = observation

    if not observations:
        raise ValueError("SIMA no publicó observaciones válidas en las últimas seis horas.")
    return list(observations.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Imprime las observaciones sin escribir en Supabase.")
    args = parser.parse_args()
    response = requests.get(SOURCE_URL, timeout=20)
    response.raise_for_status()
    rows = parse_observations(response.text, datetime.now(timezone.utc))
    if args.dry_run:
        print(json.dumps(rows, ensure_ascii=True, indent=2))
        return

    from supabase_client import get_supabase_client

    client = get_supabase_client()
    client.table("sima_observations").upsert(rows, on_conflict="station_id,observed_at").execute()
    print(f"SIMA: {len(rows)} observaciones guardadas o actualizadas.")


if __name__ == "__main__":
    main()
