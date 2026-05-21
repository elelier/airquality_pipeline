# RPC Contract Smoke — MtyRespira

## Objetivo

Este smoke protege el contrato compartido de la RPC `get_latest_air_quality_per_city`, que conecta:

`pipeline -> Supabase/RPC -> frontend -> UX pública`

La validación evita drift silencioso de columnas, nullability y timestamps antes de que la app pública represente datos incompletos como sanos.

## Smoke local sin red

El smoke canónico sin credenciales usa fixture local:

```bash
pytest tests/test_latest_air_quality_rpc_contract.py
```

No llama a Supabase, no usa secretos y no escribe datos.

## Fixture canónico

Fixture:

```text
tests/fixtures/latest_air_quality_rpc_valid.json
```

Casos representados:

- Ciudad sana con AQI, contaminante principal, clima, coordenadas y timestamps.
- Ciudad con campos secundarios `null` para validar degradación controlada.
- Ciudad con `aqi_us: null` para mantener visible que una fila así no es lectura sana y debe degradar en frontend/UX.

## Columnas esperadas

La RPC debe conservar estas columnas:

- `city_id`
- `city_name`
- `api_name`
- `latitude`
- `longitude`
- `reading_timestamp`
- `aqi_us`
- `main_pollutant_us`
- `temperature_c`
- `humidity_percent`
- `wind_speed_ms`
- `wind_direction_deg`
- `weather_icon`
- `last_successful_update_at`

## Reglas verificadas

- `city_id`, `city_name`, `api_name` y `reading_timestamp` son requeridos.
- `city_id` debe ser numérico, estable y único por fila.
- Todos los campos canónicos deben estar presentes aunque su valor sea `null`.
- Los campos degradables pueden ser `null`.
- `reading_timestamp` debe ser parseable y tener offset UTC explícito.
- `last_successful_update_at` puede ser `null`; si existe, debe ser parseable con offset UTC explícito.
- `aqi_us: null` queda documentado como caso degradado, no como lectura sana.

## Smoke operativo contra Supabase

El script operativo existente valida la RPC real en modo read-only:

```bash
python scripts/rpc_contract_health.py
```

Este comando sí requiere configuración de Supabase del pipeline y debe usarse para incidentes, runs manuales o verificación operativa. No pertenece al smoke local sin red.

## Rollback

Revertir estos archivos no cambia runtime productivo:

- `tests/fixtures/latest_air_quality_rpc_valid.json`
- `tests/test_latest_air_quality_rpc_contract.py`
- `docs/rpc-contract-smoke.md`

No hay migraciones, cambios de schema, cambios de RPC ni writes live.
