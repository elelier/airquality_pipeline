import logging
import os
import sys
import time
from copy import deepcopy
from dotenv import load_dotenv

from airvisual_api import fetch_air_quality_data as fetch_airvisual_air_quality_data
from airvisual_api import fetch_cities as fetch_airvisual_cities
from supabase_client import get_existing_cities
from sync_cities import sync_cities
from update_city import update_city
from utils import check_if_update_needed, compute_inter_city_delay, delay, setup_logging
from waqi_api import fetch_air_quality_data as fetch_waqi_air_quality_data

setup_logging()
load_dotenv()

SUPABASE_SERVICE_ENV = "SUPABASE_" + "SERVICE_ROLE_KEY"
BASE_REQUIRED_ENV_VARS = (
    "SUPABASE_URL",
    SUPABASE_SERVICE_ENV,
)

PROVIDER_ENV_VAR = "AIR_QUALITY_PROVIDER"
DEFAULT_PROVIDER = "waqi"


class PipelineRunError(RuntimeError):
    """Raised when the pipeline completed with an unhealthy operational result."""


def get_provider() -> str:
    provider = os.getenv(PROVIDER_ENV_VAR, DEFAULT_PROVIDER).strip().lower()
    if provider not in ("waqi", "airvisual"):
        raise EnvironmentError(
            f"Proveedor no soportado: {provider}. Usa AIR_QUALITY_PROVIDER=waqi o airvisual."
        )
    return provider


def get_required_env(provider: str | None = None) -> dict[str, str]:
    selected_provider = provider or get_provider()
    required_env_vars = list(BASE_REQUIRED_ENV_VARS)

    if selected_provider == "waqi":
        required_env_vars.append("WAQI_API_TOKEN")
    elif selected_provider == "airvisual":
        required_env_vars.append("AIRVISUAL_API_KEY")

    missing = [env_name for env_name in required_env_vars if not os.getenv(env_name)]

    if missing:
        missing_list = ", ".join(missing)
        raise EnvironmentError(
            "Variables de entorno faltantes. "
            f"Configura estos secretos en GitHub Actions: {missing_list}."
        )

    return {env_name: os.environ[env_name] for env_name in required_env_vars}


def get_active_cities(db_cities_list):
    return [city for city in db_cities_list if city.get("is_active")]


def build_summary(force_update: bool, provider: str) -> dict:
    return {
        "provider": provider,
        "force_update": force_update,
        "active_cities": 0,
        "updates_attempted": 0,
        "readings_inserted": 0,
        "skipped_up_to_date": 0,
        "failed_updates": 0,
        "fetch_errors": 0,
        "validation_failures": 0,
        "insert_errors": 0,
        "update_errors": 0,
        "city_results": [],
        "sync_summary": None,
    }


def record_city_result(summary: dict, city: dict, result: dict) -> None:
    summary["city_results"].append(
        {
            "city_id": city.get("id"),
            "api_name": city.get("api_name"),
            **result,
        }
    )


def log_pipeline_summary(summary: dict) -> None:
    safe_summary = deepcopy(summary)
    logging.info("\n[SUMMARY] Pipeline operacional")
    logging.info("Provider: %s", safe_summary["provider"])
    logging.info("Force update: %s", safe_summary["force_update"])
    logging.info("Ciudades activas: %s", safe_summary["active_cities"])
    logging.info("Updates intentados: %s", safe_summary["updates_attempted"])
    logging.info("Lecturas insertadas: %s", safe_summary["readings_inserted"])
    logging.info("Ciudades sin actualizar por intervalo: %s", safe_summary["skipped_up_to_date"])
    logging.info("Updates fallidos: %s", safe_summary["failed_updates"])
    logging.info("Errores de fetch: %s", safe_summary["fetch_errors"])
    logging.info("Fallos de validacion: %s", safe_summary["validation_failures"])
    logging.info("Errores de insert: %s", safe_summary["insert_errors"])
    logging.info("Errores de update status: %s", safe_summary["update_errors"])

    if safe_summary.get("sync_summary") is not None:
        logging.info("Sync summary: %s", safe_summary["sync_summary"])

    for city_result in safe_summary["city_results"]:
        logging.info("City result: %s", city_result)


def assert_healthy_summary(summary: dict) -> None:
    if summary["active_cities"] == 0:
        raise PipelineRunError("No hay ciudades activas para actualizar.")

    if summary["failed_updates"] > 0:
        raise PipelineRunError(
            "El pipeline tuvo updates fallidos. "
            f"failed_updates={summary['failed_updates']}, "
            f"readings_inserted={summary['readings_inserted']}."
        )

    if summary["updates_attempted"] > 0 and summary["readings_inserted"] == 0:
        raise PipelineRunError(
            "El pipeline intento actualizar ciudades pero no inserto ninguna lectura."
        )

    if summary["updates_attempted"] == 0 and summary["skipped_up_to_date"] == 0:
        raise PipelineRunError("El pipeline no intento ni omitio ninguna ciudad activa.")


def get_cities_for_provider(provider: str, env: dict[str, str]) -> tuple[dict, list[dict]]:
    db_cities = get_existing_cities()

    if provider == "waqi":
        logging.info("[WAQI] Omitiendo sync_cities para preservar ciudades existentes en Supabase.")
        return {"provider": "waqi", "city_sync": "skipped_existing_supabase_cities"}, db_cities

    api_cities = fetch_airvisual_cities(env["AIRVISUAL_API_KEY"])
    return sync_cities(api_cities, db_cities)


def fetch_provider_air_quality(provider: str, city: dict, env: dict[str, str]) -> dict:
    if provider == "waqi":
        return fetch_waqi_air_quality_data(
            api_name=city["api_name"],
            city_id=city["id"],
            waqi_api_token=env["WAQI_API_TOKEN"],
        )

    return fetch_airvisual_air_quality_data(
        api_name=city["api_name"],
        city_id=city["id"],
        state="Nuevo Leon",
        country="Mexico",
        AIRVISUAL_API_KEY=env["AIRVISUAL_API_KEY"],
    )


def main(force_update=False) -> dict:
    provider = get_provider()
    env = get_required_env(provider)
    summary = build_summary(force_update=force_update, provider=provider)
    logging.info("[CONFIG] Air quality provider: %s", provider)

    sync_summary, updated_db_cities_list = get_cities_for_provider(provider, env)
    summary["sync_summary"] = sync_summary

    active_cities = get_active_cities(updated_db_cities_list)
    summary["active_cities"] = len(active_cities)

    consecutive_failures = 0

    for city in active_cities:
        city_started_at = time.perf_counter()
        check_result = check_if_update_needed(city, force_update)

        if check_result["needsUpdate"]:
            logging.info("[UPDATE] Ciudad %s necesita actualizacion.", city["api_name"])
            summary["updates_attempted"] += 1

            fetch_result = fetch_provider_air_quality(provider, city, env)
            fetch_result["city_id"] = city["id"]

            update_result = update_city(fetch_or_skip_result=fetch_result)
            successful_insert = (
                fetch_result.get("status") == "success"
                and update_result.get("readingInserted")
                and not update_result.get("insertError")
                and not update_result.get("updateError")
                and not update_result.get("validationErrors")
            )

            if successful_insert:
                consecutive_failures = 0
                summary["readings_inserted"] += 1
                logging.info("[OK] Update realizado para %s: %s", city["api_name"], update_result)
            else:
                consecutive_failures += 1
                summary["failed_updates"] += 1

                if fetch_result.get("status") == "error":
                    summary["fetch_errors"] += 1
                if update_result.get("validationErrors"):
                    summary["validation_failures"] += 1
                if update_result.get("insertError"):
                    summary["insert_errors"] += 1
                if update_result.get("updateError"):
                    summary["update_errors"] += 1

                logging.warning("[WARN] Update con alertas para %s: %s", city["api_name"], update_result)

            record_city_result(
                summary,
                city,
                {
                    "needed_update": True,
                    "fetch_status": fetch_result.get("status"),
                    "fetch_error_type": fetch_result.get("errorType"),
                    "reading_inserted": bool(update_result.get("readingInserted")),
                    "city_status_updated": bool(update_result.get("cityStatusUpdated")),
                    "insert_error": update_result.get("insertError"),
                    "update_error": update_result.get("updateError"),
                    "validation_errors": update_result.get("validationErrors"),
                },
            )
        else:
            logging.info("[SKIP] Ciudad %s no necesita actualizacion.", city["api_name"])
            summary["skipped_up_to_date"] += 1
            consecutive_failures = 0
            record_city_result(
                summary,
                city,
                {
                    "needed_update": False,
                    "reason": check_result.get("errorMessage") or "up_to_date",
                },
            )

        inter_city_delay = compute_inter_city_delay(consecutive_failures)
        elapsed_city = time.perf_counter() - city_started_at
        logging.info(
            "[TIMING] Ciudad %s procesada en %.2fs. Esperando %.1fs antes de la "
            "siguiente (fallos consecutivos: %s).",
            city["api_name"],
            elapsed_city,
            inter_city_delay,
            consecutive_failures,
        )
        delay(inter_city_delay)

    log_pipeline_summary(summary)
    assert_healthy_summary(summary)
    return summary


if __name__ == "__main__":
    force_update_enabled = "--force-update" in sys.argv

    try:
        main(force_update=force_update_enabled)
    except Exception as error:
        logging.exception("[FAIL] Pipeline terminado con error operativo: %s", error)
        sys.exit(1)

    logging.info("\n[DONE] Pipeline terminado exitosamente.\n")
