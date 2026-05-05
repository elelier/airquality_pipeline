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

Verified initial mappings:

- `San Nicolas de los Garza` -> `@6493`
- `Guadalupe` -> `@6494`
- `San Pedro Garza Garcia` -> `@8282`

Unverified cities fail closed with `error: station_not_mapped` until mapped explicitly.

Do not guess stations silently.

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
- any city update fails,
- updates were attempted but zero readings were inserted, or
- no active city was updated or skipped.

## Summary block

`main.py` emits a final `[SUMMARY] Pipeline operacional` block with:

- provider
- active cities
- updates attempted
- readings inserted
- skipped cities
- failed updates
- fetch errors
- validation failures
- insert errors
- update errors
- per-city results

## Common stale-data causes

- GitHub disabled the scheduled workflow after repository inactivity.
- A required GitHub Actions secret is missing or stale.
- WAQI token is invalid or missing.
- A city has no verified WAQI station mapping.
- WAQI payload is missing AQI, timestamp, coordinates, or required weather fields.
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
