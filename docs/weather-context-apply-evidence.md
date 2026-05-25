# Weather Context Apply Evidence — MtyRespira

Status: applied / evidence captured  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Apply timestamp: 2026-05-25 01:35 UTC  
Catalog verification timestamp: 2026-05-25 01:40 UTC  
Decision type: DB apply / Data QA / Docs

## Purpose

Record the live Supabase apply evidence for the weather context columns migration.

Migration source file in repository:

```text
supabase/migrations/20260525011000_add_weather_context_columns.sql
```

## What was applied

Applied migration name:

```text
add_weather_context_columns
```

Target project:

| Field | Value |
| --- | --- |
| Project name | `monterrey-respira-db` |
| Project ref | `xjekikweaiddfwjjaqbd` |
| Region | `us-east-1` |
| PostgreSQL | `15.14.1.104` |

No secrets, credentials, tokens, service keys, or connection strings are included in this evidence.

## Apply result

Supabase apply result:

```json
{"success":true}
```

Supabase migration history after apply:

```json
{
  "migrations": [
    {
      "version": "20260525013516",
      "name": "add_weather_context_columns"
    }
  ]
}
```

## Catalog verification

Supabase read-only table inspection succeeded after retry.

Target table:

| Field | Value |
| --- | --- |
| Table | `public.air_quality_readings` |
| RLS | enabled |
| Approx rows reported | `1766` |

Legacy AQI/data-contract columns still present:

- `id`
- `city_id`
- `reading_timestamp`
- `aqi_us`
- `main_pollutant_us`
- `temperature_c`
- `pressure_hpa`
- `humidity_percent`
- `wind_speed_ms`
- `wind_direction_deg`
- `weather_icon`
- `raw_api_response`
- `created_at`

New canonical weather-context columns present and nullable:

| Column | Type | Nullable | Comment present |
| --- | --- | --- | --- |
| `weather_temperature_c` | `real` | yes | yes |
| `weather_humidity_percent` | `smallint` | yes | yes |
| `weather_wind_speed_kmh` | `real` | yes | yes |
| `weather_wind_direction_deg` | `smallint` | yes | yes |
| `weather_wind_gust_kmh` | `real` | yes | yes |
| `weather_provider` | `text` | yes | yes |
| `weather_timestamp` | `timestamp with time zone` | yes | yes |
| `weather_source_payload` | `jsonb` | yes | yes |
| `weather_backfilled_at` | `timestamp with time zone` | yes | yes |

Constraint evidence from read-only table inspection:

- Weather range checks are present on the relevant `weather_*` columns.
- The checks are reported as `NOT VALID`, matching the migration strategy.
- The connector output exposes check snippets attached to columns, not a full constraint-by-constraint catalog listing.

Primary and foreign key evidence remained intact:

- Primary key: `id`.
- Foreign key: `air_quality_readings.city_id` → `cities.id`.

## Verification status

Confirmed:

- The migration was accepted by Supabase.
- The migration is registered as `20260525013516 / add_weather_context_columns`.
- The `public.air_quality_readings` table contains the new nullable canonical `weather_*` columns.
- Legacy AQI contract columns remain present.
- Weather range checks appear as `NOT VALID`, as intended.
- No backfill was performed as part of this apply.

Still not confirmed in this evidence:

- Full `pg_constraint` row-by-row catalog output.
- Whether every named constraint exactly matches the repository migration name list.

Reason: direct SQL read-only verification through the connector remained blocked, but structured table inspection provided enough catalog evidence to confirm the schema change at table level.

## No-write boundaries preserved

This apply did not include:

- weather backfill,
- AQI rewrite,
- `main_pollutant_us` changes,
- historical AQI rewrite,
- city geolocation changes,
- RPC changes,
- frontend changes,
- runtime pipeline changes,
- workflow schedule changes,
- provider AQI changes.

## Pending follow-up

Before backfill, RPC exposure, frontend consumption, or constraint validation, create separate stories for:

1. Weather write-path implementation using Open-Meteo as separate weather provider.
2. Dry-run and then controlled weather backfill if explicitly approved.
3. Additive RPC/frontend adoption after data is verified.
4. Full named-constraint catalog verification if an approved read-only SQL path is available.
5. Constraint validation only after production evidence confirms data quality.

## Rollback expectations

If rollback is ever required, follow the rollback expectations already documented in:

- `docs/db-migration-convention.md`
- `docs/weather-context-migration-readiness-gate.md`
- `docs/weather-context-db-migration-draft.md`

At a minimum, rollback should not touch AQI fields, pollutant fields, `reading_timestamp`, city identity, city geolocation, legacy provider weather-like fields, or public frontend contract.

Do not roll back if any RPC/frontend/runtime consumer already depends on the new `weather_*` fields without first removing that dependency.