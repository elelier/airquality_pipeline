# Pipeline Runtime Operations

## Runtime

Workflow: `.github/workflows/air-quality-workflow.yml`

Triggers:

- Scheduled hourly: `0 * * * *`
- Manual: `workflow_dispatch`
- Pull request: tests only

## Active provider

The active provider is WAQI/AQICN.

Default runtime value:

```text
AIR_QUALITY_PROVIDER=waqi
```

IQAir/AirVisual remains as legacy fallback only:

```text
AIR_QUALITY_PROVIDER=airvisual
```

Use AirVisual only if the IQAir API key/plan is restored. The previous AirVisual run failed with HTTP 402 Payment Required.

## Required GitHub Actions secrets

For WAQI runs:

- `WAQI_API_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

For AirVisual fallback runs:

- `AIRVISUAL_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

For the read-only RPC contract health check:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

`SUPABASE_URL` must be the public API URL:

```text
https://<project-ref>.supabase.co
```

Do not use the Postgres host (`db.<project-ref>.supabase.co`), Studio URL, project dashboard URL, or any old project URL.

## WAQI station mapping

The expected active municipality coverage is defined in `waqi_api.EXPECTED_ACTIVE_API_NAMES` and guarded by tests. WAQI sync does not deactivate cities.

| API name | Runtime status | WAQI station | Evidence |
| --- | --- | --- | --- |
| `Monterrey` | mapped | `@6492` | AQICN public station page: Obispado, Nuevo Leon / Cloud API H6492. |
| `San Nicolas de los Garza` | mapped | `@6493` | Initial verified WAQI mapping from PR #3. |
| `Guadalupe` | mapped | `@6494` | Initial verified WAQI mapping from PR #3. |
| `San Pedro Garza Garcia` | mapped | `@8282` | Initial verified WAQI mapping from PR #3. |
| `Santa Catarina` | mapped | `@6491` | AQICN public station page: S. Catarina, Nuevo Leon / Cloud API H6491. |
| `General Escobedo` | mapped | `@6496` | AQICN public station page: Escobedo, Nuevo Leon / Cloud API H6496. |
| `Garcia` | mapped | `@6495` | AQICN public station page: Garcia, Nuevo Leon / Cloud API H6495. |
| `Ciudad Benito Juarez` | mapped | `@8113` | AQICN public station page: Juarez, Nuevo Leon / Cloud API H8113. |
| `Cadereyta Jimenez` | mapped | `@10950` | AQICN public station page: Cadereyta, Monterrey, Nuevo Leon / Cloud API H10950. |

Mappings are explicit, but every runtime fetch still fails closed before insert if WAQI does not return `status=ok`, AQI, timestamp, and coordinates inside Nuevo Leon.

Weather fields are secondary. WAQI can omit `iaqi.t`, pressure, humidity, wind, or weather icon. Missing weather fields must be persisted as null instead of blocking an otherwise valid AQI reading. If temperature is present, range validation still applies.

Do not guess stations silently.

## Station verification criteria

Before changing a station in `waqi_api.WAQI_STATION_BY_API_NAME`, verify with a real manual/runtime WAQI feed request using `WAQI_API_TOKEN`:

- `status=ok`
- AQI exists and is numeric
- timestamp exists and parses
- coordinates exist and are inside Nuevo León: lat `25.0..26.5`, lon `-101.0..-99.0`
- station is reasonable for the target municipality, not only a nearby city fallback

If any criterion is uncertain, set the mapping to `None` and leave the city visible as `error: station_not_mapped`.

## Manual recovery

When data is stale, run the workflow manually with:

- `force_update=true`
- `provider=waqi`

This bypasses the timestamp interval check and attempts to refresh all active cities.

## RPC contract health check

Use `scripts/rpc_contract_health.py` to verify the shared read contract exposed by `get_latest_air_quality_per_city` without writing to Supabase.

The check validates:

- RPC response is an array.
- Expected columns are present.
- `city_id` is numeric and unique.
- The current expected active city IDs are present: `1,4,5,6,7,9,11,12,13`.
- Healthy rows have non-null `aqi_us`.
- `reading_timestamp` parses as an offset-aware UTC timestamp.
- `last_successful_update_at` parses as an offset-aware UTC timestamp when present.
- Freshness is degraded after 2 hours and unhealthy after 6 hours by default.

Run locally with production credentials already available in the environment:

```bash
python scripts/rpc_contract_health.py
```

Optional overrides:

```bash
EXPECTED_ACTIVE_CITY_IDS=1,4,5,6,7,9,11,12,13 \
RPC_FRESHNESS_WARN_HOURS=2 \
RPC_FRESHNESS_FAIL_HOURS=6 \
python scripts/rpc_contract_health.py
```

Run from GitHub Actions manually:

- Open **Air Quality Pipeline** workflow.
- Use **Run workflow**.
- Set `rpc_contract_health=true`.
- Leave `force_update=false` unless doing a separate recovery run.

The manual health job runs tests first, then runs the read-only RPC check and uploads `rpc-contract-health.log`.

Exit codes:

- `0`: healthy or degraded. Degraded means contract is intact, but one or more readings are older than the warning threshold.
- `1`: unhealthy contract/freshness. Examples: missing expected city ID, duplicate `city_id`, null `aqi_us`, invalid timestamp, or stale reading beyond the fail threshold.
- `2`: configuration or connection failure. Examples: missing Supabase env vars, wrong `SUPABASE_URL`, DNS failure, or RPC call failure.

Sample healthy output shape:

```json
{
  "status": "healthy",
  "rpc": "get_latest_air_quality_per_city",
  "expected_city_ids": [1, 4, 5, 6, 7, 9, 11, 12, 13],
  "returned_city_ids": [1, 4, 5, 6, 7, 9, 11, 12, 13],
  "errors": [],
  "warnings": []
}
```

Rollback:

- Revert the PR that introduced `scripts/rpc_contract_health.py`, its tests, docs, and workflow job.
- No Supabase schema, RPC shape, table data, or frontend runtime change is required to roll back this check.
- If this check fails after rollback, continue using the SQL post-run checks below because they query the same contract boundary manually.

## Healthy run criteria

A run is healthy when:

- at least one update was attempted and at least one reading was inserted, or
- no updates were needed and at least one active city was skipped as up-to-date.

A run is unhealthy when:

- there are no active cities,
- any fatal city update fails,
- updates were attempted but zero readings were inserted,
- no active city was updated or skipped,
- AQI, timestamp, or coordinates are missing/invalid for all attempted cities.

`station_not_mapped` is non-fatal only when at least one mapped city inserts a reading or all healthy mapped cities are up-to-date.

## Summary block

`main.py` emits a final `[SUMMARY] Pipeline operacional` block with:

- provider
- active cities
- updates attempted
- readings inserted
- skipped cities
- skipped unmapped cities
- failed updates
- fetch errors
- validation failures
- insert errors
- update errors
- per-city results

For WAQI, each fetch also logs the mapped station as `@station_id` or `unmapped`. Tokens must never be logged.

## Common stale-data causes

- GitHub disabled the scheduled workflow after repository inactivity.
- A required GitHub Actions secret is missing or stale.
- `SUPABASE_URL` points to a wrong, old, or DNS-unresolvable Supabase host.
- WAQI token is invalid or missing.
- A city has no verified WAQI station mapping.
- WAQI payload is missing AQI, timestamp, or coordinates.
- WAQI station coordinates are outside Nuevo León.
- Supabase insert or update failed.
- RPC health check fails because an expected active city is missing, duplicated, stale, or has null AQI.
- Frontend reads a valid RPC response but rejects or hides rows because of stale-data thresholds or cache.

## Incident note: public data missing after WAQI coverage rollout

Observed risk after the complete WAQI coverage rollout: the WAQI adapter correctly treats weather fields as optional, but shared payload validation still required `temperature_c`. If WAQI returned valid AQI, timestamp, and Nuevo León coordinates without `iaqi.t`, the pipeline rejected the reading with `validation_failed`, inserted nothing, and the public frontend had no fresh data to show.

Recovery rule:

- Keep AQI, timestamp, and coordinates mandatory.
- Keep temperature range validation when temperature is present.
- Allow null weather fields to flow into nullable `air_quality_readings` columns.
- Run manual recovery with `force_update=true`, `provider=waqi`.
- Verify SQL freshness and `get_latest_air_quality_per_city` after the run.

## Incident note: Supabase DNS/connectivity failure

If the run fails before WAQI fetch with an error like:

```text
Failed to get existing cities from Supabase: [Errno 11001] getaddrinfo failed
```

then the pipeline cannot resolve the Supabase API host from `SUPABASE_URL`.

Recovery rule:

- Check GitHub Actions secret `SUPABASE_URL`.
- It must be `https://<project-ref>.supabase.co`.
- Confirm the project is active in Supabase.
- Confirm the same project hosts `cities`, `air_quality_readings`, and `get_latest_air_quality_per_city`.
- Re-run manual recovery after correcting the secret.

## Post-run checks

After a manual recovery run, check the latest reading timestamp in Supabase and review each city status.

```sql
select
  now() as checked_at_utc,
  count(*) as total_readings,
  max(reading_timestamp) as latest_reading_timestamp,
  now() - max(reading_timestamp)::timestamptz as latest_reading_age
from air_quality_readings;
```

```sql
select
  c.id,
  c.api_name,
  c.is_active,
  c.last_update_status,
  c.last_successful_update_at,
  max(r.reading_timestamp) as latest_reading_timestamp,
  now() - max(r.reading_timestamp)::timestamptz as latest_reading_age
from cities c
left join air_quality_readings r
  on r.city_id = c.id
group by
  c.id,
  c.api_name,
  c.is_active,
  c.last_update_status,
  c.last_successful_update_at
order by c.is_active desc, latest_reading_timestamp desc nulls last;
```

```sql
select * from public.get_latest_air_quality_per_city();
```

The frontend only consumes the data. Pipeline health must be validated from this repo and Supabase.

## Attribution

WAQI/AQICN data usage requires attribution to the World Air Quality Index Project and the originating EPA/source. Keep this attribution in documentation and product surfaces as needed.
