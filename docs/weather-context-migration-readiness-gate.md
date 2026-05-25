# Weather Context Migration Readiness Gate — MtyRespira

Status: readiness gate / not applied  
Scope: promotion criteria for `docs/sql/add-weather-context-columns.sql.md`  
Decision type: Architecture / DB planning / Data QA / Docs

## Purpose

Define the gate that must pass before the Story 1.4.6 SQL draft can be promoted into a real Supabase migration.

This gate does not promote the draft, create a migration directory, apply DDL, run backfill, change runtime pipeline behavior, change RPCs, or change the frontend.

## Source draft

The current draft remains here:

```text
docs/sql/add-weather-context-columns.sql.md
```

It must stay a documentation draft until a future story explicitly promotes it under the accepted migration convention.

## Promotion decision

The draft may be promoted only when all gate checks below are satisfied.

### 1. Convention accepted

- `docs/db-migration-convention.md` has been reviewed and accepted, or superseded by a clearly documented project decision.
- The accepted migration route is known before any production migration directory is created.
- `docs/sql/` is still understood as draft-only, not applied migration history.

### 2. Dedicated implementation branch

- A new branch is created specifically for migration promotion.
- The branch name makes the DDL scope clear.
- No unrelated runtime, provider, frontend, workflow schedule, or backfill changes are included.

### 3. SQL reviewed before promotion

Review the draft SQL again before copying it into a real migration file.

Required review points:

- Columns are nullable and additive.
- Existing AQI, pollutant, city identity, geolocation, and historical fields are not rewritten.
- `reading_timestamp` remains AQI measurement time.
- `weather_timestamp` remains weather provider bucket time.
- `weather_wind_speed_kmh` remains km/h.
- No km/h value is written to `wind_speed_ms` or any field named `*_ms`.
- `temperature_c` remains legacy provider weather-like data and is not redefined as canonical weather.
- `weather_source_payload` is traceability data and is not exposed to public frontend contracts by default.

### 4. Fresh dry-run evidence updated

Before promotion, update dry-run evidence for Open-Meteo/weather context using current provider behavior.

Evidence must confirm:

- Weather provider response is available for target city coordinates or stations.
- Weather values are plausible for Monterrey-area context.
- Weather provider failure remains non-blocking for AQI.
- Weather validation failure remains non-blocking for AQI.
- No AQI provider change is required.
- No historical AQI rewrite is required.

### 5. No backfill in the DDL story unless explicitly approved

The migration promotion story should only add schema.

Do not run a 60-day or any historical weather backfill in the same story unless the prompt explicitly approves it.

If a backfill is approved in a later story, it must have its own dry-run evidence, row-count expectations, rollback/repair plan, and no AQI rewrite guarantee.

### 6. No RPC or frontend changes in the DDL story

Do not modify:

- `get_latest_air_quality_per_city` or any other RPC.
- Frontend context, cards, charts, labels, or unit display.
- Public app contract.
- Cloudflare configuration.

RPC and frontend adoption must be separate additive stories after the columns exist and are verified.

### 7. Rollback documented

Before apply, document rollback expectations for the exact promoted migration.

Minimum rollback expectations:

- Drop weather constraints before dropping weather columns.
- Do not drop legacy weather-like provider fields.
- Do not touch AQI, `main_pollutant_us`, historical readings, city identity, geolocation, or `reading_timestamp`.
- Confirm no RPC/frontend consumer depends on the new `weather_*` columns before rollback.

### 8. `NOT VALID` constraint strategy confirmed

The promoted migration should preserve `NOT VALID` for check constraints on the existing table unless a future story gives evidence that immediate validation is safe.

Reason:

- Existing rows may need review before constraint validation.
- Validation can be scheduled separately to reduce risk and isolate failures.

### 9. Post-apply validation separated

Initial DDL apply and constraint validation should be separate unless explicitly approved.

A later validation story should confirm:

- Constraints are validatable against production data.
- No weather backfill violates range checks.
- No public contract changed unexpectedly.
- AQI freshness and historical views still behave as expected.

### 10. Drift and no-secret checks pass

Before opening the promotion PR, include read-only checks for:

- Existing columns and constraints on `public.air_quality_readings`.
- Existing migration history in Supabase.
- Unexpected manual schema drift.
- Secret assignment patterns in changed files.
- Privileged service-role guidance in frontend/app contexts.

Do not expose secrets in the evidence.

## Required no-write guarantees for the promotion PR

The promotion PR must state whether it does or does not perform live apply.

For the default migration-file PR, expected guarantees are:

- No Supabase live apply in the PR.
- No DDL executed from the PR.
- No backfill executed.
- No runtime pipeline changes.
- No workflow schedule changes.
- No frontend changes.
- No AQI provider changes.
- No changes to AQI, `main_pollutant_us`, historical AQI, geolocation, or public contract.
- No service role key exposure.

## Apply readiness checklist

A future operator may apply only after these are true:

- [ ] Migration convention accepted.
- [ ] SQL promoted to a versioned migration file under the accepted route.
- [ ] PR reviewed and merged, or an explicitly approved apply workflow references the exact commit.
- [ ] Target Supabase project confirmed.
- [ ] Pre-apply drift evidence captured.
- [ ] Rollback expectations captured.
- [ ] Apply authorization is explicit.
- [ ] Post-apply verification plan ready.

## Post-apply evidence checklist

After a future approved apply, capture:

- [ ] Migration filename and commit SHA.
- [ ] Apply timestamp.
- [ ] Target environment/project identifier without secrets.
- [ ] Columns exist and are nullable.
- [ ] Constraints exist as expected.
- [ ] Constraints remain `NOT VALID` if validation is out of scope.
- [ ] AQI columns still exist.
- [ ] `reading_timestamp` values remain AQI measurement timestamps.
- [ ] `main_pollutant_us` values remain untouched.
- [ ] City geolocation remains untouched.
- [ ] Latest RPC remains compatible with current frontend expectations.
- [ ] Weather fields remain null unless a separate approved write path populated them.
- [ ] No backfill occurred unless explicitly approved.

## Exit criteria for this gate

This readiness gate is satisfied when a reviewer can point to:

1. Accepted migration convention.
2. Fresh weather dry-run evidence.
3. Reviewed SQL.
4. Dedicated migration branch.
5. Explicit no-backfill or approved-backfill scope.
6. Explicit no-RPC/frontend scope.
7. Rollback notes.
8. Drift check evidence.
9. No-secret/no-frontend-service-role evidence.
10. A clear post-apply verification plan.

Until then, `docs/sql/add-weather-context-columns.sql.md` must remain a draft.