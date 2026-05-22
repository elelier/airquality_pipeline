# Provider Continuity Runbook — MtyRespira

Status: Story 1.3 operational runbook  
Scope: `elelier/airquality_pipeline`

## 1. When to use this runbook

Use this runbook when:

- The scheduled pipeline fails.
- Public readings become stale or old.
- A city stops updating.
- WAQI/AQICN returns an unexpected response.
- A maintainer needs to decide whether a manual run is safe.

Do not use this runbook to justify a new provider, schema change, RPC change, or frontend runtime change.

## 2. Fast triage

1. Open the latest GitHub Actions run for `Air Quality Pipeline`.
2. Confirm whether it was:
   - scheduled hourly run,
   - manual `workflow_dispatch`, or
   - pull request test run.
3. Check whether the run executed `main.py` or only tests/RPC health.
4. Open the uploaded `pipeline-log` artifact when available.
5. Search for these markers:
   - `[CONFIG] Air quality provider:`
   - `[WAQI] HTTP GET`
   - `[SUMMARY] Pipeline operacional`
   - `City result:`
   - `[FAIL] Pipeline terminado con error operativo`
6. Classify the failure using the taxonomy below.

## 3. How to review the latest workflow

Expected healthy scheduled behavior:

- Trigger: schedule `0 * * * *`.
- Provider: `waqi`.
- Tests run first with `AIR_QUALITY_PROVIDER=waqi`.
- Environment is configured from GitHub Actions secrets.
- `python main.py` runs and writes `pipeline.log`.
- `pipeline-log` artifact is uploaded even on failure.

Manual checks:

- Use `workflow_dispatch` with `provider=waqi` for normal manual recovery runs.
- Use `force_update=true` only when you intentionally want to bypass the 59-minute skip decision and write live readings if payloads validate.
- Use `rpc_contract_health=true` when you need read-only RPC/freshness evidence and do not want to run `main.py`.

## 4. How to read `pipeline.log`

### Provider and configuration

Look for:

```text
[CONFIG] Air quality provider: waqi
```

If provider is not `waqi`, confirm the run was intentionally manual. Scheduled production behavior should default to `waqi`.

### City-level decisions

Look for:

```text
[UPDATE] Ciudad <api_name> necesita actualizacion.
[SKIP] Ciudad <api_name> no necesita actualizacion.
[NEEDS_MAPPING] Ciudad <api_name> sin mapping verificado
[WARN] Update con alertas para <api_name>
City result: {...}
```

The `City result` entries are the fastest way to identify affected city, fetch status, error type, insertion result, and validation errors.

### Summary

Look for:

```text
[SUMMARY] Pipeline operacional
Provider: waqi
Ciudades activas: ...
Updates intentados: ...
Lecturas insertadas: ...
Ciudades sin mapping WAQI: ...
Updates fallidos: ...
Errores de fetch: ...
Fallos de validacion: ...
```

If `updates_attempted > 0` and `readings_inserted == 0`, the run should fail unhealthy. That protects the product from silently accepting a fully failed update cycle.

## 5. Failure classification guide

### Missing or invalid token

Symptoms:

- `Variables de entorno faltantes... WAQI_API_TOKEN`
- `missing_token`
- WAQI response indicates invalid key/token through `waqi_status_not_ok`

Meaning:

- Pipeline cannot trust provider access.
- No AQI should be inserted.

Action:

- Verify GitHub Actions secret presence and spelling.
- Do not paste tokens into logs, docs, PRs, or issues.
- Re-run with `provider=waqi` only after secret state is fixed.

### HTTP, rate, or provider failure

Symptoms:

- `fetch_failed`
- HTTP status in `[WAQI] HTTP GET ... status=<code>`
- Request timeout or network exception
- `waqi_status_not_ok`

Meaning:

- Upstream failed or could not be trusted for that city.

Action:

- Check whether failure is isolated to one station or all stations.
- If all stations fail, assume provider/token/network incident.
- Do not switch to AirVisual unless IQAir access has been proven healthy.
- Let public UX degrade through freshness states.

### City without `station_id`

Symptoms:

- `station_not_mapped`
- `[NEEDS_MAPPING] Ciudad ... sin mapping verificado`

Meaning:

- The city exists in Supabase but has no verified WAQI station mapping.
- This is non-fatal for the whole run but no reading is inserted for that city.

Action:

- Use the city/station continuity checklist before adding a mapping.
- Do not map to a nearby station just to make the run green.

### Payload without AQI

Symptoms:

- `missing_aqi`
- `missing_or_invalid_aqi_us`
- `aqi_us_out_of_range`

Meaning:

- The payload is not safe as an environmental reading.

Action:

- Do not insert.
- Do not coerce missing AQI to `0`.
- Treat as provider/payload issue and let UI show unavailable/degraded.

### Payload without timestamp

Symptoms:

- `missing_reading_ts`
- `Error: Falta 'reading_timestamp_iso'`
- invalid `reading_timestamp` in RPC health

Meaning:

- Freshness cannot be trusted.

Action:

- Do not insert.
- Do not reuse pipeline time as measurement time.
- Investigate provider payload.

### Coordinates outside Nuevo León

Symptoms:

- `coordinates_out_of_nuevo_leon`
- `latitude_out_of_range`
- `longitude_out_of_range`

Meaning:

- Station mapping or upstream payload is unsafe for MtyRespira.

Action:

- Do not insert.
- Re-check station mapping evidence.
- Revert any recent station change if applicable.

### Skipped because data is recent

Symptoms:

- `[SKIP] Ciudad ... no necesita actualizacion.`
- Summary increments `skipped_up_to_date`.
- City result reason is `up_to_date`.

Meaning:

- The city had a successful update within the configured 59-minute interval.

Action:

- No incident by itself.
- Use `force_update=true` only for intentional live-write validation.

## 6. When to run `workflow_dispatch` with `provider=waqi`

Safe reasons:

- Recover after a transient WAQI/network failure.
- Validate provider continuity after secret fix.
- Confirm station mapping after a reviewed PR.
- Manually refresh after the schedule was missed.

Recommended settings:

- `provider=waqi`
- `force_update=false` for normal manual check.
- `force_update=true` only if you intentionally want live writes for all active cities that pass validation.
- `rpc_contract_health=false` unless you are intentionally running the read-only health job instead of `main.py`.

## 7. When not to run `provider=airvisual`

Do not run AirVisual when:

- The goal is normal production refresh.
- WAQI has only a transient failure.
- IQAir access has not been proven healthy.
- You are trying to bypass a WAQI mapping/payload validation failure.
- You do not have evidence that AirVisual returns valid city payloads for the current active cities.

AirVisual is legacy/fallback code. The current README documents IQAir/AirVisual as HTTP 402 Payment Required with the existing key. Running it without fresh evidence is likely to create noise, fail the pipeline, or produce misleading expectations.

## 8. Read-only RPC health check

Use this path when you need public data contract/freshness evidence without pipeline writes.

Manual run:

- Trigger `workflow_dispatch`.
- Set `rpc_contract_health=true`.
- Keep provider/force settings irrelevant because `main.py` will not run in the health job.

Expected output:

- `rpc-contract-health-log` artifact.
- JSON with `status` as `healthy`, `degraded`, `unhealthy`, or `config_error`.

Interpretation:

- `healthy`: contract shape and freshness thresholds pass.
- `degraded`: shape is okay but one or more readings exceed warning freshness threshold.
- `unhealthy`: missing city, invalid timestamp, null AQI, stale beyond fail threshold, duplicate city, or missing columns.
- `config_error`: Supabase env/config/connectivity issue.

This check is read-only but uses Supabase service role inside the pipeline environment. Do not move service role into frontend/app.

## 9. How to communicate degradation

Allowed language:

- “lecturas disponibles”
- “medición reportada”
- “actualización por pipeline horario”
- “la última medición disponible presenta retraso”
- “sin lectura disponible para esta ciudad”

Do not say:

- “tiempo real”
- “live”
- “actualizado al minuto”
- “dato actual” when `reading_timestamp` is stale/old/unknown

Public communication should distinguish:

- Measurement time: `reading_timestamp`.
- Pipeline traceability: `last_successful_update_at`.
- Workflow status: GitHub Actions run health.

## 10. Rollback

For docs-only changes:

```bash
git revert <docs_commit_sha>
```

For future runtime provider/mapping changes:

1. Revert the provider/mapping commit.
2. Keep the RPC unchanged.
3. Keep Supabase schema unchanged unless a separate rollback plan exists.
4. Run `pytest`.
5. Run read-only RPC health if the question is contract/freshness.
6. Use `workflow_dispatch provider=waqi` only when ready for controlled live writes.
7. Validate public app behavior after the next healthy reading cycle.

## 11. What not to do

- Do not change station ids during an incident without evidence.
- Do not add unsupported cities to fix a stale public screen.
- Do not use Core DB for environmental readings.
- Do not write directly to Supabase to patch AQI values.
- Do not alter `get_latest_air_quality_per_city` as part of provider triage.
- Do not expose or echo secrets.
- Do not convert missing fields into invented values for UI convenience.
