# Weather Contract Migration Proposal — MtyRespira

Status: Story 1.4.5 proposal / no-write contract decision  
Scope: `elelier/airquality_pipeline`  
Reference app repo: `elelier/monterrey-respira` read-only  
Decision type: Planning / Data QA / Architecture / Docs only

## 1. Purpose

This document proposes the production contract and migration path for weather context in MtyRespira after:

- PR #15: `docs: add weather context provider spike`.
- PR #16: `feat: add weather context dry-run report`.

The goal is to separate meteorological context from AQI ingestion without changing current production behavior in this story.

This proposal does not apply DDL, does not write to Supabase, does not run a real backfill, does not change runtime pipeline ingestion, does not change the public frontend, and does not change WAQI/AQICN as the active AQI provider.

## 2. Current state summary

### Pipeline state

- WAQI/AQICN remains the active AQI provider.
- IQAir/AirVisual remains legacy/fallback only.
- Current runtime writes AQI readings to `air_quality_readings`.
- Current runtime also persists WAQI `iaqi` weather-like values into legacy columns:
  - `temperature_c`
  - `humidity_percent`
  - `wind_speed_ms`
  - `wind_direction_deg`
  - `weather_icon`
- `reading_timestamp` represents the AQI provider measurement time.
- `cities.last_successful_update_at` represents pipeline write traceability.

### Dry-run tooling state

The dry-run script already exists:

```text
scripts/weather_backfill_dry_run.py
```

The dry-run guide already exists:

```text
docs/weather-context-dry-run.md
```

The script reads local JSON/CSV exports, calls Open-Meteo historical weather by city coordinates, matches each candidate AQI row to the nearest hourly weather bucket, and emits local JSON evidence only. It does not import Supabase clients and does not mutate database state.

### App contract state, read-only

The app consumes normalized RPC output from `get_latest_air_quality_per_city`. The current shared contract still includes legacy weather fields such as `temperature_c`, `humidity_percent`, `wind_speed_ms`, and `wind_direction_deg` in the latest payload.

Important risk:

- The legacy field name `wind_speed_ms` implies meters per second.
- The public app has displayed wind speed as `km/h`.
- Therefore, any Open-Meteo weather rollout must not write km/h values into any `*_ms` field.

## 3. Non-goals and hard boundaries

This story must not do any of the following:

- Write to Supabase.
- Apply DDL.
- Apply migrations.
- Create or replace RPCs.
- Run a production backfill.
- Change `main.py` runtime flow.
- Change `update_city.py` productive writes.
- Change workflow schedule.
- Change WAQI/AQICN AQI provider behavior.
- Change AQI, `main_pollutant_us`, historical AQI, city geolocation, or public contract semantics.
- Change frontend code or public copy.
- Add secrets to docs, tests, scripts, or workflows.
- Add privileged database credentials to the frontend/app.

## 4. Decision options

### Option A — Additive columns on `air_quality_readings`

Add canonical weather-context columns directly to each AQI reading row.

Candidate additive columns:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_provider`
- `weather_timestamp`
- `weather_source_payload` or `weather_raw_response`
- `weather_backfilled_at`

#### Pros

- Lowest implementation complexity for MtyRespira v1.
- Weather context travels with the AQI row already consumed by latest/history RPCs.
- Easier additive extension of `get_latest_air_quality_per_city`.
- Easier historical display alignment: each AQI row can have its selected weather bucket.
- Avoids introducing an additional table and join path during the first rollout.
- Easier rollback for RPC/frontend because legacy fields can remain unchanged while new fields are additive.

#### Cons

- Duplicates the same hourly weather bucket if a city has multiple AQI readings in the same hour.
- Requires updates to existing rows during a future backfill, which needs explicit approval and rollback evidence.
- Couples weather context retention to AQI reading retention.
- May become less clean if weather becomes an independent product feature later.

#### Best fit

Option A is best if weather is supporting context for AQI, not a standalone weather product.

### Option B — Separate `weather_context_readings` table

Create a dedicated table for weather context by city/hour/provider, then join it to AQI readings through RPC logic.

Candidate table concept:

```text
weather_context_readings
- id
- city_id
- weather_timestamp
- weather_temperature_c
- weather_humidity_percent
- weather_wind_speed_kmh
- weather_wind_direction_deg
- weather_wind_gust_kmh
- weather_provider
- weather_source_payload or weather_raw_response
- weather_backfilled_at
- created_at
- updated_at
```

#### Pros

- Cleaner separation of AQI trust domain and weather trust domain.
- Avoids duplicated weather rows for repeated AQI readings in the same city/hour.
- Allows weather to refresh independently from AQI.
- Cleaner provenance and retention model if weather later becomes a standalone feature.
- Better normalization if multiple weather providers are evaluated later.

#### Cons

- Higher implementation complexity.
- Requires a new table, indexes, RLS/grants review, RPC joins, and query-performance validation.
- The frontend contract must handle unmatched AQI/weather rows more explicitly.
- Timestamp join semantics become a production concern instead of a simple row-level enrichment.
- More rollback surfaces: table, RPC, indexes, grants, and consumer mapping.

#### Best fit

Option B is best if MtyRespira plans to evolve weather into an independent feature, support multiple weather providers, or query weather without AQI rows.

## 5. Recommendation for MtyRespira v1

Recommended decision for MtyRespira v1: **Option A — additive columns on `air_quality_readings`**.

Reasoning:

1. MtyRespira's current public product is AQI-first. Weather is contextual support, not the primary product.
2. The existing RPC and frontend already center on one latest AQI row per active city.
3. The dry-run tooling already matches weather context to candidate AQI rows by `city_id` and `reading_timestamp`.
4. Additive columns let the team preserve the legacy public contract while adding safer canonical `weather_*` fields.
5. The highest current user-facing risk is not table normalization; it is semantic ambiguity between legacy WAQI weather fields and canonical weather context.
6. Option A reduces rollout complexity and makes it easier to stage: DB columns first, dry-run evidence, approved backfill, additive RPC extension, then UI copy.

Architectural reservation:

- If weather becomes a standalone feature, Option B can be introduced later as a v2 weather model.
- Do not migrate to Option B prematurely until dry-run evidence shows Option A cannot satisfy product or performance needs.

## 6. Proposed data contract

### Canonical weather context fields

| Field | Type concept | Nullable | Source | Contract rule |
| --- | --- | --- | --- | --- |
| `weather_temperature_c` | numeric / real | yes | Open-Meteo | Canonical weather temperature in Celsius. Do not reuse legacy `temperature_c` semantics. |
| `weather_humidity_percent` | numeric / smallint | yes | Open-Meteo | Relative humidity percent. Valid range `0..100`. |
| `weather_wind_speed_kmh` | numeric / real | yes | Open-Meteo | Canonical wind speed in km/h. Never write km/h into `*_ms`. |
| `weather_wind_direction_deg` | numeric / smallint | yes | Open-Meteo | Wind direction degrees. Valid range `0..360`. |
| `weather_wind_gust_kmh` | numeric / real | yes | Open-Meteo | Wind gust in km/h. Must be non-negative. |
| `weather_provider` | text | yes | Open-Meteo | Example value: `open-meteo`. Required when any canonical weather value is present. |
| `weather_timestamp` | timestamptz | yes | Open-Meteo hourly bucket | Weather bucket timestamp. Must not replace `reading_timestamp`. |
| `weather_source_payload` | jsonb | yes | Open-Meteo | Preferred name for selected provider payload or minimal response slice. |
| `weather_raw_response` | jsonb | yes | Open-Meteo | Alternative name only if the team wants naming symmetry with `raw_api_response`. Choose one, not both. |
| `weather_backfilled_at` | timestamptz | yes | pipeline | Populated only by future approved backfill rows. Null for non-backfilled or not-yet-processed rows. |

Recommended payload column name: **`weather_source_payload`**.

Reason:

- It avoids confusion with `raw_api_response`, which currently belongs to the AQI provider payload.
- It can store only the selected hourly weather slice instead of the full upstream response.
- It makes the provider boundary explicit.

Acceptable alternative:

- Use `weather_raw_response` if maintainers strongly prefer raw-response naming consistency.
- Do not create both fields in v1.

### Timestamp contract

- `reading_timestamp` remains AQI measurement time.
- `weather_timestamp` is the Open-Meteo hourly weather bucket time selected for the AQI reading.
- `last_successful_update_at` remains pipeline traceability time on `cities`.
- UI must not merge AQI freshness and weather freshness into one timestamp.

### Validation contract

Canonical weather fields must obey these rules before being written in a future implementation story:

| Field | Rule | Failure behavior |
| --- | --- | --- |
| `weather_temperature_c` | hard range `-50..60`; QA warning outside local Monterrey expected range such as below `-20` | reject field or row per future implementation policy; never invalidate AQI |
| `weather_humidity_percent` | `0..100` | reject weather field/row; never invalidate AQI |
| `weather_wind_speed_kmh` | `>= 0`; warning above `160` | reject negative; warn high outlier |
| `weather_wind_gust_kmh` | `>= 0`; warning above `220` | reject negative; warn high outlier |
| `weather_wind_direction_deg` | `0..360` | reject weather field/row |
| `weather_provider` | required when any `weather_*` value is present | reject weather context row/update |
| `weather_timestamp` | required when any `weather_*` value is present | reject weather context row/update |
| timestamp match delta | recommended `<= 30 minutes` from AQI `reading_timestamp` | leave weather null/unmatched |

Weather validation failure must not invalidate AQI. AQI, main pollutant, AQI historical rows, city geolocation, and provider station mapping remain governed by the existing WAQI/AQICN fail-closed contract.

## 7. Mandatory rules

These rules are non-negotiable for future implementation:

1. `reading_timestamp` remains AQI measurement time.
2. `weather_timestamp` is the selected weather bucket time.
3. Do not write km/h values into fields named `*_ms`.
4. Do not reuse `temperature_c` as canonical weather context.
5. Do not reinterpret legacy `humidity_percent`, `wind_speed_ms`, or `wind_direction_deg` as Open-Meteo canonical fields.
6. AQI, `main_pollutant_us`, geolocation, and historical AQI remain intact.
7. Weather validation failure must not invalidate AQI.
8. Weather provider failure must produce null/degraded weather context, not synthetic weather.
9. Do not expose provider raw payload internals directly to the frontend.
10. Open-Meteo weather context must be attributed in future public copy once exposed.

## 8. Future migration proposal

This section is conceptual. It is not a migration file and must not be applied from this story.

### Tentative migration file name

If the repo later stores Supabase migrations in version control, use a new migration in a separate implementation PR, for example:

```text
supabase/migrations/YYYYMMDDHHMMSS_add_weather_context_columns.sql
```

If the repo does not yet manage SQL migrations, first create a migration strategy/story before applying any DB change.

### Conceptual SQL for Option A

```sql
-- CONCEPTUAL ONLY — not applied in Story 1.4.5.
-- Add canonical weather context columns without changing legacy AQI fields.

alter table public.air_quality_readings
  add column if not exists weather_temperature_c real,
  add column if not exists weather_humidity_percent smallint,
  add column if not exists weather_wind_speed_kmh real,
  add column if not exists weather_wind_direction_deg smallint,
  add column if not exists weather_wind_gust_kmh real,
  add column if not exists weather_provider text,
  add column if not exists weather_timestamp timestamptz,
  add column if not exists weather_source_payload jsonb,
  add column if not exists weather_backfilled_at timestamptz;

-- Optional constraints should be evaluated after dry-run evidence.
-- Prefer NOT VALID check constraints first if adding to an existing large table.

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_humidity_percent_range
  check (weather_humidity_percent is null or weather_humidity_percent between 0 and 100) not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_direction_deg_range
  check (weather_wind_direction_deg is null or weather_wind_direction_deg between 0 and 360) not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_speed_kmh_nonnegative
  check (weather_wind_speed_kmh is null or weather_wind_speed_kmh >= 0) not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_gust_kmh_nonnegative
  check (weather_wind_gust_kmh is null or weather_wind_gust_kmh >= 0) not valid;
```

### Conceptual rollback for Option A

Rollback must be evaluated against whether production has already exposed the new columns through RPC/UI. Conceptually:

```sql
-- CONCEPTUAL ONLY — not applied in Story 1.4.5.

alter table public.air_quality_readings
  drop constraint if exists air_quality_readings_weather_humidity_percent_range,
  drop constraint if exists air_quality_readings_weather_wind_direction_deg_range,
  drop constraint if exists air_quality_readings_weather_wind_speed_kmh_nonnegative,
  drop constraint if exists air_quality_readings_weather_wind_gust_kmh_nonnegative;

alter table public.air_quality_readings
  drop column if exists weather_backfilled_at,
  drop column if exists weather_source_payload,
  drop column if exists weather_timestamp,
  drop column if exists weather_provider,
  drop column if exists weather_wind_gust_kmh,
  drop column if exists weather_wind_direction_deg,
  drop column if exists weather_wind_speed_kmh,
  drop column if exists weather_humidity_percent,
  drop column if exists weather_temperature_c;
```

Rollback guard:

- Do not drop columns after UI/RPC consumes them without first removing consumer references.
- Do not drop legacy AQI/weather fields in the same rollout.

### Conceptual SQL for Option B

```sql
-- CONCEPTUAL ONLY — not applied in Story 1.4.5.

create table if not exists public.weather_context_readings (
  id bigserial primary key,
  city_id bigint not null references public.cities(id),
  weather_timestamp timestamptz not null,
  weather_temperature_c real,
  weather_humidity_percent smallint,
  weather_wind_speed_kmh real,
  weather_wind_direction_deg smallint,
  weather_wind_gust_kmh real,
  weather_provider text not null,
  weather_source_payload jsonb,
  weather_backfilled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (city_id, weather_provider, weather_timestamp)
);

create index if not exists weather_context_readings_city_time_idx
  on public.weather_context_readings (city_id, weather_timestamp desc);
```

Option B requires additional RLS/grants/RPC review and performance evidence before production.

## 9. Backfill strategy after approval

Future backfill must be staged and explicitly approved.

### Dry-run first

Before any write, produce local evidence with:

```text
scripts/weather_backfill_dry_run.py
```

Required evidence exports:

- active cities input export;
- candidate AQI readings input export;
- generated dry-run JSON report;
- per-city summary;
- validation issues summary;
- sample matched rows;
- unmatched rows by city/reason.

### Write plan only after approval

A future write-capable backfill story must:

- require explicit user approval for production writes;
- use the same matching and validation contract as dry-run;
- write only canonical `weather_*` fields;
- never write Open-Meteo km/h values into `wind_speed_ms`;
- never update AQI, `main_pollutant_us`, `reading_timestamp`, city coordinates, or `raw_api_response`;
- populate `weather_backfilled_at` for affected rows;
- produce before/after counts;
- support rollback by clearing only newly added canonical weather fields if needed.

### Write scope suggestion

Initial production write should be limited to a small canary window before any 60-day backfill, for example:

- one city;
- one day;
- verified row count;
- verified latest RPC remains compatible;
- no public UI dependency yet.

Then expand only after evidence review.

## 10. RPC strategy after DB migration

RPC changes must happen in a separate PR after DB migration exists.

### Latest RPC

`get_latest_air_quality_per_city` should be extended additively. It must not remove or rename existing fields.

Additive candidate output fields:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_provider`
- `weather_timestamp`

Do not expose `weather_source_payload` to the public frontend RPC unless a specific debug/admin use case exists.

### History RPCs

Existing history RPCs may later add weather fields additively, but this should be evaluated separately because mobile chart performance and payload size matter.

Recommended v1:

- Extend latest RPC first.
- Keep history weather extension out of scope unless product copy requires historical weather context.

### Compatibility rules

- Existing frontend must continue to work if it ignores new fields.
- Existing legacy fields must remain present until the UI is migrated.
- New fields are nullable.
- Missing weather context must not make city AQI unknown if AQI is valid.

## 11. Frontend strategy after RPC extension

Frontend changes must happen in a separate app PR after backend/RPC contract exists.

Recommended UI behavior:

- Keep AQI measurement timestamp separate from weather timestamp.
- Show weather section as contextual, not as AQI station measurement.
- Use source copy such as `Fuente meteorológica: Open-Meteo`.
- Render wind speed from `weather_wind_speed_kmh` as `km/h`.
- Avoid rendering `wind_speed_ms` as `km/h` unless it is converted or relabeled.
- Keep `temperature_c` legacy hidden or marked legacy until deprecation.

Recommended public copy:

- `Condiciones meteorológicas`
- `Clima estimado para <hora>`
- `Fuente meteorológica: Open-Meteo`
- `Medición AQI <hora>` for AQI timestamp

Avoid:

- implying real-time weather;
- implying weather values come from the AQI station;
- mixing AQI freshness with weather freshness;
- silently replacing legacy values without source/timestamp context.

## 12. Criteria required before production

Production migration/backfill must not proceed until the team has evidence for all of these:

### Dry-run evidence

- Dry-run was run against real local exports.
- Report was saved as a local artifact.
- No production writes occurred.
- Input files and report shape were reviewed.

### Row counts

- Active city count matches expected production cities.
- Target AQI row count for the selected window is known.
- Matched row count is reported.
- Unmatched row count is reported.
- Expected vs matched count is explained.

### Unmatched analysis

- Unmatched rows are grouped by city.
- Unmatched reasons are classified:
  - missing city coordinates;
  - missing `reading_timestamp`;
  - Open-Meteo fetch issue;
  - no hourly bucket within threshold;
  - range validation failure.

### Physical ranges

- Temperature min/max are plausible.
- Humidity stays within `0..100`.
- Wind speed/gusts are non-negative.
- Wind direction stays within `0..360`.
- Outliers are listed and reviewed.

### Deltas against WAQI legacy

- Temperature deltas against legacy `temperature_c` are summarized.
- Humidity deltas against legacy `humidity_percent` are summarized.
- Wind speed is not compared until units are normalized.
- Large deltas are treated as weather-provider evidence, not AQI invalidation.

### Wind unit validation

- Open-Meteo request uses `wind_speed_unit=kmh`.
- Output target field is `weather_wind_speed_kmh`.
- No Open-Meteo km/h value is assigned to `wind_speed_ms` or any `*_ms` field.
- Frontend plan explicitly consumes `weather_wind_speed_kmh` for `km/h` display.

### Performance and RPC impact

If Option A is selected:

- Confirm additive columns do not materially change existing latest RPC performance.
- Avoid exposing heavy JSON payload in public RPC.

If Option B is selected later:

- Explain join strategy.
- Add index plan.
- Measure latest RPC performance with the join.
- Confirm one-row-per-active-city behavior remains intact.

## 13. Rollout plan by phases

1. **Evidence dry-run local**
   - Use local exports and `scripts/weather_backfill_dry_run.py`.
   - Produce JSON evidence only.

2. **Contract proposal**
   - Review this document.
   - Choose Option A or Option B.
   - Confirm no-write boundaries.

3. **DB migration in separate PR**
   - Add canonical weather fields or table.
   - Include conceptual rollback as real migration rollback guidance.
   - No backfill in the same PR unless explicitly approved.

4. **Backfill dry-run with evidence**
   - Re-run dry-run with production-representative exports.
   - Attach evidence to PR or issue.

5. **Real backfill only with explicit approval**
   - Start with canary scope.
   - Expand only after counts and validation are reviewed.

6. **RPC additive extension**
   - Add nullable canonical weather fields to latest RPC.
   - Keep legacy fields intact.
   - Do not expose raw weather payload publicly.

7. **UI copy/runtime update**
   - Consume `weather_*` fields.
   - Separate AQI timestamp from weather timestamp.
   - Correct wind unit display.
   - Add provider attribution.

8. **Gradual deprecation of legacy weather fields if applicable**
   - Stop showing legacy WAQI weather fields after canonical weather is stable.
   - Keep fields in DB/RPC until compatibility risk is gone.
   - Remove only through a later coordinated deprecation story.

## 14. Documentation validation for this PR

Because this story is proposal-only, no tests are added.

Recommended local validation commands for reviewers:

```bash
# Ensure this PR did not add direct production live-apply instructions.
grep -RniE "apply_migration|supabase db push|psql .*air_quality_readings|backfill real" docs/weather-contract-migration-proposal.md README.md || true

# Ensure no secrets were added.
grep -RniE "WAQI_API_TOKEN=|AIRVISUAL_API_KEY=|SUPABASE_SERVICE_ROLE_KEY=|service_role key" docs/weather-contract-migration-proposal.md README.md || true

# Ensure there is no instruction to use privileged credentials in frontend/app.
grep -RniE "frontend.*service_role|app.*service_role|VITE_.*SERVICE|public.*service_role" docs/weather-contract-migration-proposal.md README.md || true
```

Expected interpretation:

- Mentions of `SUPABASE_SERVICE_ROLE_KEY` may exist in baseline README security sections or as forbidden tokens, but this proposal must not instruct adding it to frontend/app.
- SQL blocks in this document are conceptual only and must not be applied from this story.

## 15. Rollback for this story

This story is docs-only.

Rollback:

1. Revert this docs PR.
2. Remove the README link if included.
3. Keep pipeline runtime unchanged.
4. Keep Supabase unchanged.
5. Keep frontend unchanged.
6. Keep WAQI/AQICN AQI provider unchanged.

No runtime rollback, migration rollback, DB restore, or Cloudflare rollback is required for this story.

## 16. Final recommendation

Proceed with **Option A: additive canonical weather columns on `air_quality_readings`** for MtyRespira v1, but only through a separate DB migration PR after dry-run evidence is reviewed.

Do not backfill production data until dry-run evidence proves:

- expected row counts vs matched rows;
- unmatched rows by city/reason;
- physical ranges;
- delta analysis against WAQI legacy weather fields;
- wind unit correctness;
- no AQI contract regression.

Keep WAQI/AQICN as AQI provider. Treat Open-Meteo only as a separate weather-context provider.