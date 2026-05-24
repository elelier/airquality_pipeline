# Weather Context DB Migration Draft — MtyRespira

Status: Story 1.4.6 draft / not applied  
Scope: `elelier/airquality_pipeline`  
Reference app repo: `elelier/monterrey-respira` read-only  
Decision type: Architecture / Data QA / DB migration draft / Docs

## Purpose

This document records the DB migration draft for adding canonical meteorological context to MtyRespira without changing production behavior in this story.

The draft follows Story 1.4.5's recommendation: **Option A — additive canonical `weather_*` columns on `air_quality_readings`** for MtyRespira v1.

The SQL draft lives at:

```text
docs/sql/add-weather-context-columns.sql.md
```

It is a documented SQL draft, not an applied migration.

## Repository migration convention check

Before creating this draft, the repo was checked for a clear migration convention:

- `supabase/migrations`: not present.
- `migrations`: not present.
- `sql`: not present.
- Existing weather contract docs only included conceptual SQL, not an applied migration convention.

Decision: do **not** invent a production migration structure in this story. Store the draft under `docs/sql/` until a future DB story defines the migration workflow.

## What the draft adds

The draft adds nullable canonical weather-context columns to `public.air_quality_readings`:

| Column | Purpose |
| --- | --- |
| `weather_temperature_c` | Canonical weather temperature in Celsius. |
| `weather_humidity_percent` | Canonical relative humidity percentage. |
| `weather_wind_speed_kmh` | Canonical wind speed in km/h. |
| `weather_wind_direction_deg` | Canonical wind direction in degrees. |
| `weather_wind_gust_kmh` | Canonical wind gust in km/h. |
| `weather_provider` | Weather provider identifier, for example `open-meteo`. |
| `weather_timestamp` | Weather provider bucket timestamp. |
| `weather_source_payload` | Selected provider payload slice for traceability. |
| `weather_backfilled_at` | Timestamp for a future approved weather backfill. |

## Constraints included

The draft includes safe check constraints as `NOT VALID` because the table already exists and production rows may need evidence review before validation.

Included checks:

- `weather_temperature_c` must be null or within `-50..60`.
- `weather_humidity_percent` must be null or within `0..100`.
- `weather_wind_speed_kmh` must be null or non-negative.
- `weather_wind_direction_deg` must be null or within `0..360`.
- `weather_wind_gust_kmh` must be null or non-negative.
- If any canonical weather value, source payload, or backfill marker is present, `weather_provider` and `weather_timestamp` must also be present.

## Contract rules preserved

This story does not change the current production contract.

The draft explicitly preserves these rules:

- `reading_timestamp` remains AQI measurement time.
- `weather_timestamp` is the selected weather bucket time.
- `weather_wind_speed_kmh` is km/h.
- Do not write km/h values into `wind_speed_ms` or any field named `*_ms`.
- `temperature_c` remains legacy provider weather-like data and is not canonical weather context.
- Weather provider failure must not invalidate AQI.
- Weather validation failure must not invalidate AQI.
- AQI, `main_pollutant_us`, historical AQI, geolocation, latest RPC behavior, and frontend runtime remain unchanged.

## What this story does not change

No changes were made to:

- Supabase live DB.
- DB migration history.
- `main.py`.
- `update_city.py`.
- `waqi_api.py`.
- `utils.py`.
- workflow schedule.
- AQI provider selection.
- AQI values.
- `main_pollutant_us`.
- historical AQI.
- city geolocation.
- RPCs.
- frontend code.
- public UI copy.
- Core DB.
- Cloudflare.

## Why this was not applied

This story is intentionally no-write.

The repo has no clear DB migration convention to safely place a production migration file. Creating `supabase/migrations` here would silently introduce a migration workflow without a project decision.

A future DB implementation story should first confirm:

1. where migrations live,
2. how migration ordering is controlled,
3. how DB drift is reviewed,
4. how future constraint validation is scheduled,
5. whether the SQL should remain Option A or be promoted to a versioned migration.

## How to validate in branch/local

Recommended branch review checks:

```bash
# Confirm touched files are docs/SQL-draft only.
git diff --name-only main...HEAD

# Confirm no runtime files changed.
git diff --name-only main...HEAD -- main.py update_city.py waqi_api.py utils.py .github/workflows

# Confirm no live-write command wording was introduced.
grep -RniE "apply_migration|supabase db push|psql" docs/weather-context-db-migration-draft.md docs/sql/add-weather-context-columns.sql.md || true

# Confirm no secret assignments were introduced.
grep -RniE "WAQI_API_TOKEN=|AIRVISUAL_API_KEY=|SUPABASE_SERVICE_ROLE_KEY=" docs/weather-context-db-migration-draft.md docs/sql/add-weather-context-columns.sql.md || true

# Confirm no privileged DB guidance was added to frontend/app contexts.
grep -RniE "frontend.*service_role|app.*service_role|VITE_.*SERVICE|public.*service_role" docs/weather-context-db-migration-draft.md docs/sql/add-weather-context-columns.sql.md || true
```

Expected result:

- Only `docs/weather-context-db-migration-draft.md` and `docs/sql/add-weather-context-columns.sql.md` are changed.
- Runtime diff is empty.
- The live-write grep returns no matching instructions in the new docs.
- The secret grep returns no secret assignments.
- The frontend/app privileged credential grep returns no matches.

## How to validate after a future approved DB apply

A later story that is explicitly approved to apply DB changes should produce evidence for:

- Columns exist and are nullable.
- Legacy AQI columns still exist.
- `reading_timestamp` values remain unchanged.
- `aqi_us` values remain unchanged.
- `main_pollutant_us` values remain unchanged.
- City coordinates remain unchanged.
- Latest RPC remains compatible with current frontend expectations.
- Constraint validation is reviewed separately from column creation.
- Weather fields are null before any approved backfill unless a controlled canary update is part of that future story.
- No canonical km/h value is written to `wind_speed_ms`.

Future post-apply verification should be read-only evidence and should avoid exposing raw provider payloads in public frontend contracts by default.

## Rollback concept

For this story:

1. Revert this PR.
2. No DB rollback is needed.
3. No runtime rollback is needed.
4. No Cloudflare rollback is needed.
5. No frontend rollback is needed.

For a future story that actually applies the columns:

1. First confirm no RPC/frontend consumer depends on the canonical `weather_*` columns.
2. Drop the weather constraints.
3. Drop only the newly added canonical `weather_*` columns.
4. Do not drop or rewrite legacy `temperature_c`, `humidity_percent`, `wind_speed_ms`, `wind_direction_deg`, AQI fields, pollutant fields, timestamps, city identity, or geolocation.

The SQL rollback draft is included in `docs/sql/add-weather-context-columns.sql.md` for planning only.

## Risks / pending items

- A production migration convention is still pending.
- A future live DB story must not skip drift review.
- Constraint validation should be separated from column creation if table size or existing data quality is uncertain.
- Backfill remains pending and must start with dry-run evidence and explicit approval.
- RPC extension remains pending and must be additive.
- Frontend migration remains pending and must consume `weather_wind_speed_kmh` for km/h display.
- The legacy `wind_speed_ms` unit-display risk remains until the app migrates away from legacy weather fields.
