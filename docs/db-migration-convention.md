# DB Migration Convention — MtyRespira Pipeline

Status: proposed convention / not yet applied  
Scope: `elelier/airquality_pipeline`  
Decision type: Architecture / DB planning / Data QA / Docs

## Purpose

Define the minimum safe convention for future Supabase PostgreSQL migrations owned by the MtyRespira pipeline repository.

This document does not create a production migration directory, move draft SQL, apply DDL, run backfills, or change runtime behavior.

## Current repository finding

As of Story 1.4.7, no accepted production migration convention was found in this repository.

Checked locations and signals:

- `supabase/migrations`: not present.
- `migrations`: not present.
- Top-level production `sql/`: not present.
- Existing `docs/sql/` content is treated as documented SQL draft material, not a migration mechanism.
- README and workflow documentation describe the pipeline and Supabase usage, but do not define versioned DB migration ownership or apply procedure.
- No repository `AGENTS.md` was found in `elelier/airquality_pipeline` during this review.

## Recommended future route

When the project explicitly accepts a versioned DB migration convention, use:

```text
supabase/migrations/
```

Rationale:

- It is recognizable as the Supabase migration directory.
- It separates production migration files from documentation drafts.
- It avoids treating `docs/sql/` as executable migration history.

Do not create `supabase/migrations/` until a future implementation story is explicitly approved to promote a draft into a real migration.

## Naming convention

Use timestamp-prefixed snake_case names:

```text
YYYYMMDDHHMMSS_short_snake_case_description.sql
```

Example format only:

```text
20260524170000_add_weather_context_columns.sql
```

Rules:

- Timestamp must represent when the migration file is authored, in UTC if the toolchain supports it.
- Description must be lowercase snake_case.
- One migration should do one coherent schema change.
- Do not combine DDL, backfill, RPC changes, frontend changes, and provider runtime changes in the same migration story unless explicitly approved.

## Review checklist for DB migration PRs

Before opening a PR that adds a real migration file, confirm:

- The migration directory convention has already been accepted.
- The migration is on a dedicated branch.
- SQL is additive when possible.
- Existing AQI fields, `reading_timestamp`, `main_pollutant_us`, city identity, geolocation, and historical readings are not rewritten.
- Constraints on existing tables are introduced with a safe strategy such as `NOT VALID` when appropriate.
- Constraint validation is separated from initial DDL unless the story explicitly approves validation in the same PR.
- Backfill is separated from DDL unless explicitly approved.
- RPC or frontend contract changes are separated from DDL unless explicitly approved.
- Rollback expectations are documented.
- Drift checks are documented before and after apply.
- No secrets are committed.
- No privileged key guidance is added to frontend or public app code.

## No live apply from docs-only PRs

Documentation-only PRs must not apply migrations to Supabase.

A docs-only PR may include:

- Migration convention proposals.
- SQL drafts under `docs/sql/`.
- Readiness gates.
- Review checklists.
- Apply evidence templates.

A docs-only PR must not include:

- Live DDL execution.
- Backfill execution.
- Supabase write operations.
- Runtime pipeline changes.
- Frontend/app changes.
- Workflow schedule changes.

## When applying to Supabase is allowed

A future Supabase apply is allowed only when all are true:

1. A story explicitly authorizes DB apply.
2. The target Supabase project is clearly identified.
3. The migration file is versioned under the accepted migration directory.
4. The SQL has been reviewed in PR.
5. Drift evidence is captured before apply.
6. Rollback expectations are documented.
7. Apply evidence is captured after execution.
8. No secrets are exposed in logs, docs, screenshots, artifacts, or PR comments.

## Apply evidence expectations

A future apply PR or follow-up evidence document should record:

- Migration filename.
- Commit SHA containing the migration.
- Target environment and project identifier, without secrets.
- Operator or automation used to apply.
- Timestamp of apply.
- Pre-apply drift check summary.
- Post-apply schema verification summary.
- Any warnings, locks, failures, retries, or manual interventions.
- Confirmation that no AQI, pollutant, geolocation, historical reading, RPC, frontend, or provider behavior was changed unless explicitly in scope.

Do not paste provider tokens, service keys, raw credentials, or full sensitive environment dumps into evidence.

## Rollback expectations

Every real migration PR must include rollback expectations.

Minimum rollback notes:

- Whether rollback is safe after consumers depend on the new schema.
- Which constraints would be dropped first.
- Which columns, indexes, or comments would be removed.
- Which existing legacy columns must never be dropped by the rollback.
- Whether rollback requires first removing RPC/frontend/runtime dependencies.

For additive weather context migrations, rollback must not touch AQI fields, pollutant fields, `reading_timestamp`, city identity, city coordinates, or legacy provider fields unless a separate approved story explicitly scopes that work.

## Drift checks

Future DB migration stories should perform read-only drift checks before apply and after apply.

Minimum pre-apply checks:

- Confirm whether the target columns, constraints, indexes, RPCs, or comments already exist.
- Confirm whether pending migrations exist outside repository history.
- Confirm whether the target table shape matches the migration assumptions.

Minimum post-apply checks:

- Confirm expected columns or constraints exist.
- Confirm unexpected runtime contract changes did not occur.
- Confirm no public RPC output changed unless explicitly scoped.
- Confirm no backfill happened unless explicitly approved.

## Secrets and privileged access boundary

Secrets must stay in local `.env` files or GitHub Actions Secrets.

Do not commit secret assignment patterns or real values for:

- `WAQI_API_TOKEN`
- `AIRVISUAL_API_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

The Supabase service role key is a pipeline/server-side secret boundary only. It must never be added to frontend app code, public runtime configuration, documentation that instructs frontend usage, screenshots, or public artifacts.

## Relationship to existing SQL drafts

`docs/sql/` may continue to hold SQL drafts while a migration is still being designed.

A file under `docs/sql/` is not migration history and must not be treated as applied. Promotion from draft to production migration requires a future story and the readiness gate defined for that migration.