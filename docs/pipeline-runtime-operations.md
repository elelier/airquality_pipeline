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

## WAQI station mapping

The expected active municipality coverage is defined in `waqi_api.EXPECTED_ACTIVE_API_NAMES` and guarded by tests. WAQI sync does not deactivate cities.

| API name | Runtime status | WAQI station | Action |
| --- | --- | --- | --- |
| `Monterrey` | pending | `None` | Verify feed before enabling. |
| `San Nicolas de los Garza` | verified | `@6493` | Keep enabled. |
| `Guadalupe` | verified | `@6494` | Keep enabled. |
| `San Pedro Garza Garcia` | verified | `@8282` | Keep enabled. |
| `Santa Catarina` | pending | `None` | Verify feed before enabling. |
| `General Escobedo` | pending | `None` | Verify feed before enabling. |
| `Garcia` | pending | `None` | Verify feed before enabling. |
| `Ciudad Benito Juarez` | pending | `None` | Verify feed before enabling. |
| `Cadereyta Jimenez` | pending | `None` | Verify feed before enabling. |

Unverified cities fail closed with `error: station_not_mapped` until mapped explicitly.

Do not guess stations silently.

## Station verification criteria

Before enabling a station in `waqi_api.WAQI_STATION_BY_API_NAME`, verify with a real manual/runtime WAQI feed request using `WAQI_API_TOKEN`:

- `status=ok`
- AQI exists and is numeric
- timestamp exists and parses
- coordinates exist and are inside Nuevo León: lat `25.0..26.5`, lon `-101.0..-99.0`
- station is reasonable for the target municipality, not only a nearby city fallback

If any criterion is uncertain, keep the mapping as `None` and leave the city visible as `error: station_not_mapped`.

## Manual recovery

When data is stale, run the workflow manually with:

- `force_update=true`
- `provider=waqi`

This bypasses the timestamp interval check and attempts to refresh all active cities.

## Healthy run criteria

A run is healthy when:

- at least one update was attempted and at least one reading was inserted, or
- no updates were needed and at least one active city was skipped as up-to-date.

A run is unhealthy when:

- there are no active cities,
- any fatal city update fails,
- updates were attempted but zero readings were inserted, or
- no active city was updated or skipped.

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
- WAQI token is invalid or missing.
- A city has no verified WAQI station mapping.
- WAQI payload is missing AQI, timestamp, coordinates, or required weather fields.
- WAQI station coordinates are outside Nuevo León.
- Supabase insert or update failed.

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

The frontend only consumes the data. Pipeline health must be validated from this repo and Supabase.

## Attribution

WAQI/AQICN data usage requires attribution to the World Air Quality Index Project and the originating EPA/source. Keep this attribution in documentation and product surfaces as needed.
