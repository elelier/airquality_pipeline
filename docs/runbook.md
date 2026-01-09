# Runbook: Debug de ciudad sin datos

## Sintoma
- Frontend muestra "Desconocida" o AQI vacio para una ciudad.

## Pasos rapidos
1. Revisar ultima ejecucion de GitHub Actions (Air Quality Pipeline) y descargar el artifact `pipeline-log` para ver los logs detallados por ciudad.
2. Verificar que las variables de entorno esten configuradas en el repo (`AIRVISUAL_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
3. Confirmar que la tabla `cities` tenga la ciudad activa (`is_active = true`) y con `last_update_status` distinto de `error`.
4. Revisar la tabla `pipeline_logs` (si existe) filtrando por `city_id` para ver los eventos recientes.
5. Ejecutar el script local `python scripts/test_city_fetch.py --city "Monterrey" --write` (usa .env local) para confirmar fetch + insercion.

## Verificar credenciales
- AIRVISUAL_API_KEY: debe ser la llave de produccion. Una llave invalida genera 401/403 en los logs.
- SUPABASE_SERVICE_ROLE_KEY: requerida para inserts. No usar la anon key en el pipeline.
- Si se rotan las llaves, actualizar Secrets en GitHub y el archivo `.env` local.

## Check de limites y timeouts
- Llamadas maximas mensuales estimadas: ~8000 (11 ciudades * 24 * 30) < limite 10,000.
- Timeout hacia AirVisual: 45s. Si hay timeouts frecuentes, validar conectividad o estado del servicio.

## Flujos de error comunes
- `error: validation_failed`: AQI fuera de 0-500, temperatura fuera de -50 a 60 C, o coordenadas fuera de lat 25-26 y lon -100 a -99. La lectura se descarta y se mantiene el ultimo dato valido.
- `error: missing_reading_ts`: la API no envio timestamp; se descarta.
- `Too Many Requests` o `HTTP 429`: el pipeline reintenta 3 veces con backoff. Revisar frecuencia de ejecucion.
- `error: unknown_fetch_result`: estructura de respuesta inesperada. Revisar logs crudos en `api_raw_response` del log.

## Validar datos en Supabase
- Tabla `air_quality_readings`: buscar la ultima lectura para la ciudad (`order by reading_timestamp desc limit 1`).
- Tabla `cities`: verificar `last_successful_update_at` y `last_update_status`.
- Tabla `pipeline_logs` (opcional): validar eventos recientes y estados.

## Como simular y probar localmente
1. Crear `.env` con las 3 variables de entorno.
2. Ejecutar `pip install -r requirements.txt`.
3. Probar fetch sin escribir: `python scripts/test_city_fetch.py --city "Monterrey"`.
4. Probar escritura: `python scripts/test_city_fetch.py --city "Monterrey" --write`.
5. Para simular rate limit, ejecutar el script varias veces seguidas y observar los reintentos en los logs.

## Que revisar si solo falla una ciudad
- Coincidencia exacta de `api_name` con lo que espera AirVisual.
- Coordenadas fuera de rango (las descarta el validador).
- Ciudad desactivada (`is_active = false`).

## Que revisar si fallan todas las ciudades
- Credenciales incorrectas o expiradas.
- Cambios en el formato de la API de AirVisual.
- Cambios de red (IP bloqueada). Revisar logs de HTTP status.

## Escalada
- Si hay 3 o mas fallos consecutivos (ver logs), investigar inmediatamente y pausar el cron si es necesario para evitar consumo de cuota.
