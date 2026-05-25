# Weather Context Pre-Apply Drift Check — MtyRespira

Status: read-only evidence / needs review  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Review timestamp: 2026-05-25 01:35 UTC  
Decision type: DB readiness / Data QA / Docs

## Purpose

Capture pre-apply drift evidence before applying the weather context migration:

```text
supabase/migrations/20260525011000_add_weather_context_columns.sql
```

This evidence is read-only. It does not apply the migration, execute DDL, run backfill, change runtime code, change RPCs, change workflows, or change the frontend.

## Required references reviewed

- `README.md`
- `docs/db-migration-convention.md`
- `docs/weather-context-migration-readiness-gate.md`
- `docs/weather-context-migration-file-promotion.md`
- `docs/weather-context-db-migration-draft.md`
- `supabase/migrations/20260525011000_add_weather_context_columns.sql`

## Target Supabase project

Supabase project list identified the MtyRespira DB as:

| Field | Value |
| --- | --- |
| Project name | `monterrey-respira-db` |
| Project ref | `xjekikweaiddfwjjaqbd` |
| Region | `us-east-1` |
| Status | `ACTIVE_HEALTHY` |
| PostgreSQL | `15.14.1.104` |

No secrets, credentials, tokens, or connection strings were recorded.

## Read-only evidence captured

### Migration history

Read-only Supabase migration history response:

```json
{"migrations":[]}
```

Interpretation:

- No Supabase-managed migrations are currently reported by the Supabase tool for this project.
- The repository migration file is not reflected in Supabase migration history yet.
- This supports the assumption that `20260525011000_add_weather_context_columns.sql` has not been applied through the Supabase migration history mechanism.

### Column drift check

Attempted read-only catalog checks for `public.air_quality_readings` columns were blocked by the connector safety layer before execution.

Result:

- `weather_*` column existence could not be confirmed.
- Legacy AQI column existence could not be independently confirmed in this story.
- No DDL or writes were executed.

### Constraint drift check

Attempted read-only catalog checks for `air_quality_readings_weather_*` constraints were blocked by the connector safety layer before execution.

Result:

- Constraint existence could not be confirmed.
- Constraint validation state could not be confirmed.
- No DDL or writes were executed.

## Decision

**Needs review.**

Reason:

- Migration history is empty, which suggests the repository migration has not been applied through Supabase migration tracking.
- However, required table/column/constraint drift evidence could not be fully captured because read-only catalog queries were blocked by the connector before execution.
- Do not proceed to live apply until a human or alternate approved read-only path confirms the `public.air_quality_readings` column and constraint state.

## Recommended next step

Before any apply story, capture column and constraint drift with an approved read-only method, for example:

```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_schema = 'public'
  and table_name = 'air_quality_readings'
order by ordinal_position;
```

```sql
select conname, convalidated
from pg_constraint
where conrelid = 'public.air_quality_readings'::regclass
order by conname;
```

Then decide whether the migration is:

- ready to apply as-is,
- blocked because columns or constraints already exist,
- or needs a corrected/idempotent migration before apply.

## No-write guarantees

This story did not perform:

- Supabase live apply,
- DDL execution,
- data backfill,
- row updates,
- runtime pipeline changes,
- provider AQI changes,
- RPC changes,
- frontend changes,
- workflow schedule changes,
- secret exposure.

## Risks / pending items

- Empty migration history means repo and DB migration tracking may not yet be aligned.
- Column and constraint drift remain unconfirmed.
- If the future migration is applied without verifying existing constraints first, it could fail if constraints already exist outside migration history.
- Constraint validation remains separate future work.
- Backfill remains separate future work and requires explicit approval.
- RPC/frontend adoption remains separate future work.

## Rollback for this story

Revert this documentation PR.

No database rollback is required because no database change was executed.