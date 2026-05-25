# Weather Context Apply Evidence — MtyRespira

Status: applied / evidence captured  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Apply timestamp: 2026-05-25 01:35 UTC  
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

## Verification status

Confirmed by migration history:

- The migration was accepted by Supabase.
- The migration is now registered as `20260525013516 / add_weather_context_columns`.

Not confirmed in this evidence:

- Column-by-column catalog state.
- Constraint-by-constraint catalog state.
- Constraint validation state.

Reason: direct SQL read-only verification through the connector was blocked by the safety layer, even for trivial `select` checks. This evidence therefore relies on Supabase migration apply success and migration history only.

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

1. Post-apply read-only catalog verification through an approved read-only path.
2. Weather write-path implementation using Open-Meteo as separate weather provider.
3. Dry-run and then controlled weather backfill if explicitly approved.
4. Additive RPC/frontend adoption after data is verified.
5. Constraint validation only after production evidence confirms data quality.

## Rollback expectations

If rollback is ever required, follow the rollback expectations already documented in:

- `docs/db-migration-convention.md`
- `docs/weather-context-migration-readiness-gate.md`
- `docs/weather-context-db-migration-draft.md`

At a minimum, rollback should not touch AQI fields, pollutant fields, `reading_timestamp`, city identity, city geolocation, legacy provider weather-like fields, or public frontend contract.

Do not roll back if any RPC/frontend/runtime consumer already depends on the new `weather_*` fields without first removing that dependency.