# Weather Context Migration File Promotion — MtyRespira

Status: migration file promoted / not applied  
Scope: `elelier/airquality_pipeline`  
Decision type: DB migration preparation / Data QA / Docs

## Purpose

Record the promotion of the Story 1.4.6 weather context SQL draft into a versioned migration file.

This story prepares migration history only. It does not apply the migration to Supabase, run backfill, change runtime pipeline behavior, change RPCs, or change the frontend.

## Promoted migration file

```text
supabase/migrations/20260525011000_add_weather_context_columns.sql
```

## Source draft retained

The source draft remains in place for historical review:

```text
docs/sql/add-weather-context-columns.sql.md
```

The draft was not moved or deleted.

## What changed

The migration file adds nullable canonical weather-context columns to `public.air_quality_readings`:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_provider`
- `weather_timestamp`
- `weather_source_payload`
- `weather_backfilled_at`

The migration also adds range/metadata constraints as `NOT VALID` so validation can happen in a later controlled story after production evidence review.

## Intentional differences from the draft document

The versioned migration file includes only the forward migration body.

It intentionally excludes:

- future validation SQL,
- conceptual rollback SQL,
- markdown explanation from the draft.

Rollback expectations remain documented in:

- `docs/db-migration-convention.md`
- `docs/weather-context-migration-readiness-gate.md`
- `docs/weather-context-db-migration-draft.md`

## No-write guarantees

This story did not perform:

- Supabase live apply,
- DDL execution against any live DB,
- weather backfill,
- RPC changes,
- frontend changes,
- provider AQI changes,
- runtime pipeline changes,
- workflow schedule changes.

## Contract preserved

The promoted migration does not rewrite or redefine:

- AQI values,
- `main_pollutant_us`,
- `reading_timestamp`,
- historical AQI rows,
- city identity,
- city geolocation,
- legacy provider weather-like fields,
- public frontend contract.

## Pending before live apply

Before any future apply story:

1. Capture pre-apply drift evidence against the target Supabase project.
2. Confirm target columns and constraints do not already exist.
3. Confirm migration ordering is correct.
4. Confirm no backfill is in scope unless explicitly approved.
5. Confirm no RPC/frontend change is bundled with DDL.
6. Confirm rollback expectations for the exact target state.
7. Capture post-apply evidence after execution.

## Validation note

This promotion remains file-only until a separate apply story explicitly authorizes database execution.

## Rollback for this story

Revert the PR that added the versioned migration file and this document.

No database rollback is required because the migration was not applied.