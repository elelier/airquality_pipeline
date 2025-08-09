from datetime import datetime, timedelta, timezone
import logging
import sys

UPDATE_INTERVAL_MINUTES = 59  # Mantener el valor que decidiste

def setup_logging():
    """Configura el logging para imprimir en la consola."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_if_update_needed(city, force_update=False):
    logging.info(f"--- CheckIfUpdateNeeded para City ID: {city.get('id')} ({city.get('api_name')}) ---")

    if force_update:
        logging.warning("Se ha forzado la actualización. Omitiendo la comprobación de tiempo.")
        return {**city, "needsUpdate": True}

    # Validación básica del input
    if not city or not isinstance(city.get('id'), int) or not isinstance(city.get('api_name'), str):
        error_message = f"Input 'city' inválido o incompleto: {city}"
        logging.error(error_message)
        return {**city, "needsUpdate": False, "error": True, "errorMessage": error_message}

    needs_update = False
    last_success_string = city.get('last_successful_update_at')
    last_status = city.get('last_update_status')

    logging.info(f"Última actualización exitosa: {last_success_string or 'Nunca'}")
    logging.info(f"Último estado registrado: {last_status or 'Nunca/Desconocido'}")

    # Lógica de Decisión Modificada

    # 1. Prioridad: ¿Falló la última vez o nunca se ha intentado/registrado?
    if last_status != 'success':
        # Si el último estado NO fue 'success' (incluye null, 'error:xxx', 'skipped:xxx', etc.)
        # entonces queremos reintentar/intentar ahora.
        needs_update = True
        logging.info(f"Decisión: Necesita actualización (Último estado registrado fue '{last_status or 'null'}', no 'success').")
    else:
        # 2. Si el último estado SÍ fue 'success', AHORA comprobamos el tiempo
        logging.info("Último estado fue 'success'. Verificando intervalo de tiempo...")

        # a) ¿Hubo alguna vez un éxito? (Doble chequeo por si acaso)
        if last_success_string is None:
            needs_update = True  # Si el estado es 'success' pero no hay fecha, algo es raro, mejor actualizar.
            logging.warning("Estado es 'success' pero 'last_successful_update_at' es null. Forzando actualización.")
        else:
            # b) Calcular diferencia de tiempo desde el último éxito
            try:
                last_update_date = datetime.fromisoformat(last_success_string)
                now = datetime.now(timezone.utc)
                diff_minutes = (now - last_update_date).total_seconds() / 60

                logging.info(f"Han pasado {diff_minutes:.2f} minutos desde la última actualización *exitosa*.")

                if diff_minutes > UPDATE_INTERVAL_MINUTES:
                    needs_update = True
                    logging.info(f"Decisión: Necesita actualización (Intervalo de {UPDATE_INTERVAL_MINUTES} min superado desde el último éxito).")
                else:
                    needs_update = False  # Está al día y el último fue éxito
                    logging.info(f"Decisión: No necesita actualización (Dentro del intervalo de {UPDATE_INTERVAL_MINUTES} min y último estado fue 'success').")
            except Exception as date_error:
                logging.error(f"Error al parsear la fecha '{last_success_string}': {date_error}. Asumiendo que necesita actualización por precaución.")
                needs_update = True  # Si no podemos parsear la fecha del último éxito, mejor intentar

    # Retornar el objeto city original, pero con la propiedad 'needsUpdate' actualizada
    result = {**city, "needsUpdate": needs_update}
    logging.info(f"Resultado final para City ID {city['id']}: needsUpdate = {needs_update}")
    logging.info("--- Fin CheckIfUpdateNeeded ---")
    
    return result

def delay(seconds: float):
    import time
    time.sleep(seconds)