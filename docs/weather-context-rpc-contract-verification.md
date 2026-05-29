# Weather Context RPC Contract Verification — MtyRespira

Status: ready as data-source gate for separate frontend adoption story  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Verification date: 2026-05-29  
Decision type: Data QA / Architecture validation / Docs only

## Summary

This document verifies the public Supabase RPC contract exposed by `public.get_latest_air_quality_per_city()` for canonical Open-Meteo weather context fields.

Decision: **RPC contract is ready as a data-source gate for a separate frontend adoption story.**

This verification does not authorize frontend UI adoption, a production backfill, schema changes, runtime changes, workflow changes, or any change to AQI/provider behavior.

## Sources reviewed

Reviewed:

- `README.md`
- `docs/weather-context-live-coverage-evidence.md`
- `docs/weather-contract-migration-proposal.md`
- `supabase/migrations/20260525045500_update_latest_air_quality_rpc_weather_context.sql`

Expected but not present on `main` at verification time:

- `AGENTS.md`
- `docs/roadmap.md`
- `ROADMAP.md`
- `docs/PRD.md`
- `docs/architecture.md`

The absence of those canonical files is documented here but does not block this docs-only gate because the target contract is explicitly defined in the migration and prior weather-context evidence documents.

## Contract boundary

MtyRespira remains AQI-first:

- WAQI/AQICN remains the active AQI provider.
- Open-Meteo weather fields are secondary meteorological context.
- Weather context must not replace or reinterpret AQI.
- `reading_timestamp` remains AQI provider measurement time.
- `weather_timestamp` remains the selected Open-Meteo weather bucket time.
- Legacy fields such as `temperature_c`, `humidity_percent`, `wind_speed_ms`, and `wind_direction_deg` are not the canonical Open-Meteo weather contract.
- No frontend/app guide may use `service_role` or privileged secrets.

## RPC definition check

Read-only catalog query used:

```sql
select
  p.proname as function_name,
  n.nspname as schema_name,
  pg_get_function_result(p.oid) as function_result,
  pg_get_function_arguments(p.oid) as function_arguments,
  p.provolatile as volatility,
  p.prosecdef as security_definer
from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public'
  and p.proname = 'get_latest_air_quality_per_city';
```

Result:

```json
[
  {
    "function_name": "get_latest_air_quality_per_city",
    "schema_name": "public",
    "function_result": "TABLE(city_id bigint, city_name text, api_name text, latitude double precision, longitude double precision, reading_timestamp timestamp with time zone, aqi_us smallint, main_pollutant_us text, temperature_c real, humidity_percent smallint, wind_speed_ms real, wind_direction_deg smallint, weather_icon text, last_successful_update_at timestamp with time zone, weather_temperature_c real, weather_humidity_percent smallint, weather_wind_speed_kmh real, weather_wind_direction_deg smallint, weather_wind_gust_kmh real, weather_provider text, weather_timestamp timestamp with time zone)",
    "function_arguments": "",
    "volatility": "s",
    "security_definer": true
  }
]
```

The live RPC signature matches the migration contract and exposes these canonical weather-context fields:

| Field | Postgres type | Frontend TypeScript-compatible type | Required for core completeness |
| --- | --- | --- | --- |
| `weather_temperature_c` | `real` | `number | null` | yes |
| `weather_humidity_percent` | `smallint` | `number | null` | yes |
| `weather_wind_speed_kmh` | `real` | `number | null` | yes |
| `weather_wind_direction_deg` | `smallint` | `number | null` | no, but exposed |
| `weather_wind_gust_kmh` | `real` | `number | null` | no, but exposed |
| `weather_provider` | `text` | `string | null` | yes |
| `weather_timestamp` | `timestamp with time zone` | `string | null` | yes |

TypeScript compatibility decision:

- `bigint` IDs should be handled as `number` only if the generated client/runtime currently serializes them safely within JavaScript safe integer range; otherwise use `string | number` in a future frontend contract review.
- `real`, `smallint`, and `double precision` map naturally to JSON numbers in frontend consumption.
- `timestamp with time zone` maps to ISO-like timestamp strings from Supabase/PostgREST consumption.
- Nullable weather fields must remain nullable because weather context is secondary and must not invalidate AQI rows.

## Live read-only coverage check

Read-only aggregate query used:

```sql
with active_cities as (
  select count(*)::int as active_cities
  from public.cities
  where is_active = true
), rpc_rows as (
  select *
  from public.get_latest_air_quality_per_city()
)
select
  ac.active_cities,
  count(*)::int as rpc_rows,
  count(*) filter (where aqi_us is not null)::int as rpc_rows_with_aqi,
  count(*) filter (where weather_provider = 'open-meteo')::int as rpc_rows_with_open_meteo,
  count(*) filter (
    where weather_provider = 'open-meteo'
      and weather_temperature_c is not null
      and weather_humidity_percent is not null
      and weather_wind_speed_kmh is not null
      and weather_timestamp is not null
  )::int as rpc_rows_with_complete_core_weather,
  max(reading_timestamp) as newest_reading_timestamp,
  min(reading_timestamp) as oldest_latest_reading_timestamp
from rpc_rows rr
cross join active_cities ac
group by ac.active_cities;
```

Result:

```json
[
  {
    "active_cities": 9,
    "rpc_rows": 9,
    "rpc_rows_with_aqi": 9,
    "rpc_rows_with_open_meteo": 9,
    "rpc_rows_with_complete_core_weather": 9,
    "newest_reading_timestamp": "2026-05-29 18:00:00+00",
    "oldest_latest_reading_timestamp": "2026-05-29 18:00:00+00"
  }
]
```

Result summary:

| Metric | Result |
| --- | ---: |
| Active cities | 9 |
| RPC rows returned | 9 |
| Rows with AQI | 9/9 |
| Rows with `weather_provider = 'open-meteo'` | 9/9 |
| Rows with complete core weather fields | 9/9 |
| Active/RPC row-count mismatch | 0 |

## Live RPC detail rows

Read-only detail query used:

```sql
select
  city_name,
  reading_timestamp,
  aqi_us,
  main_pollutant_us,
  weather_provider,
  weather_temperature_c,
  weather_humidity_percent,
  weather_wind_speed_kmh,
  weather_wind_direction_deg,
  weather_wind_gust_kmh,
  weather_timestamp
from public.get_latest_air_quality_per_city()
order by city_name asc;
```

| City | Reading timestamp UTC | AQI | Main pollutant | Weather provider | Temperature C | Humidity % | Wind km/h | Wind direction deg | Gust km/h | Weather timestamp UTC | Core weather fields |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Cadereyta Jimenez | 2026-05-29 18:00:00 | 30 | `o3` | `open-meteo` | 34.3 | 46 | 16.1 | 114 | 19.8 | 2026-05-29 20:15:00 | complete |
| Ciudad Benito Juárez | 2026-05-29 18:00:00 | 42 | `pm25` | `open-meteo` | 34.1 | 44 | 18.0 | 110 | 20.5 | 2026-05-29 20:15:00 | complete |
| Garcia | 2026-05-29 18:00:00 | 76 | `o3` | `open-meteo` | 33.7 | 37 | 27.0 | 111 | 29.5 | 2026-05-29 20:15:00 | complete |
| General Escobedo | 2026-05-29 18:00:00 | 61 | `o3` | `open-meteo` | 34.3 | 38 | 17.1 | 105 | 20.5 | 2026-05-29 20:15:00 | complete |
| Guadalupe | 2026-05-29 18:00:00 | 40 | `pm10` | `open-meteo` | 33.8 | 42 | 16.3 | 108 | 20.9 | 2026-05-29 20:15:00 | complete |
| Monterrey | 2026-05-29 18:00:00 | 76 | `o3` | `open-meteo` | 33.6 | 40 | 18.3 | 80 | 22.3 | 2026-05-29 20:15:00 | complete |
| San Nicolas de los Garza | 2026-05-29 18:00:00 | 58 | `pm25` | `open-meteo` | 34.1 | 39 | 16.3 | 108 | 20.9 | 2026-05-29 20:15:00 | complete |
| San Pedro Garza Garcia | 2026-05-29 18:00:00 | 96 | `o3` | `open-meteo` | 33.4 | 40 | 18.2 | 72 | 22.3 | 2026-05-29 20:15:00 | complete |
| Santa Catarina | 2026-05-29 18:00:00 | 68 | `pm25` | `open-meteo` | 33.1 | 41 | 16.6 | 92 | 22.0 | 2026-05-29 20:15:00 | complete |

Direct RPC-output rows missing canonical core weather context: **none**.

## Frontend adoption risks still pending

This gate only verifies that the RPC can serve as a data source. A separate frontend adoption story must still decide and test:

1. Exact TypeScript model updates for nullable canonical weather fields.
2. Copy/UX hierarchy so AQI remains primary and weather remains context.
3. Unit label correctness, especially `weather_wind_speed_kmh` vs legacy `wind_speed_ms`.
4. Timestamp labeling so `reading_timestamp` and `weather_timestamp` are not merged into one freshness claim.
5. Fallback UI for null weather context even though current RPC coverage is 9/9.
6. Public-client access pattern using anon/RLS-safe RPC consumption only; no `service_role`, no privileged keys, and no secrets in frontend code or docs.
7. Regression check that AQI cards, pollutant labels, map/list ordering, and station attribution remain unchanged.

## Readiness decision

**RPC contract is ready as a data-source gate for a separate frontend adoption story.**

Rationale:

- The live RPC exposes all expected canonical weather fields.
- Field names match the documented weather-context contract.
- Postgres types are compatible with a nullable TypeScript frontend model.
- Live RPC output returns one row per active city.
- Live RPC output has 9/9 rows with AQI.
- Live RPC output has 9/9 rows with `weather_provider = 'open-meteo'`.
- Live RPC output has 9/9 rows with complete core weather context.
- Weather fields remain secondary context and do not replace AQI.
- No frontend service-role or secret-based consumption guidance was added.

## Explicit non-authorization

This document does **not** authorize:

- Frontend UI adoption.
- Runtime pipeline changes.
- Workflow schedule changes.
- Supabase DDL.
- Supabase writes.
- Migration apply.
- Backfill.
- AQI/provider changes.
- Secret exposure.
- Use of `service_role` in frontend/app consumption.

## Validation performed

- Confirmed repository connector returned `elelier/airquality_pipeline` before any work.
- Reviewed README provider and security boundaries.
- Reviewed prior weather coverage evidence.
- Reviewed weather contract proposal.
- Reviewed the RPC migration that defines `public.get_latest_air_quality_per_city()`.
- Ran read-only Supabase aggregate query against direct RPC output.
- Ran read-only Supabase catalog query for RPC signature.
- Ran read-only Supabase detail query against direct RPC output.
- Confirmed 9 active cities and 9 RPC rows.
- Confirmed 9/9 RPC rows with AQI.
- Confirmed 9/9 RPC rows with `weather_provider = 'open-meteo'`.
- Confirmed 9/9 RPC rows with complete core weather context.
- Confirmed this story is documentation-only.
- Confirmed no runtime files, workflow files, frontend files, migrations, DDL, writes, or backfill were changed.

## Rollback

Revert this documentation PR.

No database, runtime, workflow, frontend, AQI/provider, Cloudflare, or Supabase rollback is required.
