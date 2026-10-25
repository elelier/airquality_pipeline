# RPC latest-per-city optimization — Issue #34

Status: **PR candidate only. NOT applied to Supabase.**

## Scope and ownership

- Owner: `elelier/airquality_pipeline`, migration directory `supabase/migrations/`.
- Target after separate deployment approval: environmental Supabase project
  `xjekikweaiddfwjjaqbd` (`monterrey-respira-db`).
- Consumer: `elelier/monterrey-respira` via
  `public.get_latest_air_quality_per_city()`.
- Unchanged: WAQI/US AQI calculation, Open-Meteo weather source, app code,
  historical rows, permissions, RPC name/signature (21 columns), and `elelier-core-db`.

## Root-cause evidence (24 Oct 2026, read-only)

- PostgREST reported an intermittent `57014` statement timeout for
  `POST /rpc/get_latest_air_quality_per_city` at 23:29:40 UTC. A later
  request completed successfully: contention may contribute; the query rewrite
  alone is **not proven** to eliminate all timeouts.
- Existing SQL ranks *all* historical readings using
  `row_number() over (partition by city_id order by reading_timestamp desc)`.
  It does not define which row wins when timestamps tie.
- Nine active cities each had 29 readings tied at
  `2026-10-19 14:00:00+00`. Within a city the AQI and pollutant were equal,
  but the 29 records held different weather timestamps.
- Index already exists: `idx_aqr_orig_city_timestamp_desc` on
  `(city_id, reading_timestamp DESC)`.
- One production read-only `EXPLAIN (ANALYZE, BUFFERS)` comparison:

  | Query | Execution | Shared buffer hits | Rows |
  | --- | ---: | ---: | ---: |
  | Existing RPC | 65.649 ms | 24,699 | 9 |
  | `JOIN LATERAL` + timestamp/ingestion/id tie-break | 0.691 ms | 298 | 9 |

  These are point measurements, **not** a production throughput/SLA claim.

## Deterministic behavior

For each active city having at least one reading:

1. Choose the greatest `reading_timestamp` (actual measurement time).
2. For exact ties, choose the greatest `created_at` (ingestion time).
3. For residual ties, choose the greatest `id` (unique bigint).

An active city without readings remains absent, matching the original inner
join semantics. Inactive cities remain excluded. The function still sorts
the returned rows by city name. The additional tie-break only chooses which
historical row supplies weather fields; it **never advances the AQI timestamp**.

Security boundary: preserve `STABLE SECURITY DEFINER`, owner, and function
`EXECUTE` grants through `CREATE OR REPLACE`, with
`SET search_path = ''` and fully qualified table references. Public callers
receive only the existing 21 projected fields. Review the intentional
`SECURITY DEFINER` exposure during PR review; do not silently alter grants.

## Read-only verification performed

- Supabase query implementing the candidate was compared by full JSON row
  projection against an independently written `DISTINCT ON (city_id)`
  reference using the same explicit ordering: **9 versus 9 rows, 0 missing,
  0 extra**.
- Historical `reading_timestamp` remains exactly the original latest value
  for **9/9** active cities. No historical update or synthetic timestamp.
- Local PostgreSQL grammar parse of the new migration: **PASS**.
- Isolated PostgreSQL WASM (PGlite) smoke applied the *whole new migration*
  to synthetic tables and confirmed: **2 expected rows / 21 columns**,
  inactive and no-reading cities omitted, greatest observation timestamp,
  latest ingestion timestamp then highest `id` winning ties, nullable
  AQI/weather fields retained, and `STABLE SECURITY DEFINER` with locked
  `search_path`. This used an ephemeral local database only.
- Local unit tests should run with:

  `uv run --no-project --with-requirements requirements.txt python -m pytest -q -p no:cacheprovider`

These checks do not prove that the deployed RPC runs correctly until the
versioned migration is applied and inspected in the approved environment.

## Pre-apply gate (requires separate PO GO)

1. Ensure PR is reviewed/merged and read its exact SHA.
2. Confirm the target project ref and original RPC function definition,
   owner, `proacl`, security mode, row type, current indexes, and migration
   history. Preserve this definition for recovery.
3. Check the new SQL against the current remote schema and indexes.
4. Test against an isolated Postgres/Supabase environment before a live apply,
   including 0 rows, inactive city, equal measurement timestamp, equal
   ingestion timestamp, `NULL` optional weather fields, and privilege checks.
5. Apply **only this forward migration** through the approved migration
   workflow, during a controlled window. No data backfill or deletion.
6. Verify `pg_get_functiondef`, `proowner`, `proacl`, 21-column types,
   `anon` RPC access, 9-city results, no new PostgREST errors, and a sample
   of `EXPLAIN ANALYZE BUFFERS` runs under comparable load.

## Recovery

If the new RPC fails the agreed contract or latency gate:

- Stop rollout and capture evidence. Recreate the previous SQL function body
  from `20260525045500_update_latest_air_quality_rpc_weather_context.sql`
  using **`CREATE OR REPLACE FUNCTION`** and the preserved signature.
- **Do not rerun that historical file verbatim:** it starts with
  `DROP FUNCTION`, which would replace the function object and risk grants.
- Preserve the existing ACL/owner and revalidate PostgREST, public client,
  and 21 output columns. Record a forward recovery migration after review.

## Out of scope

Provider freshness/recovery belongs to
[`airquality_pipeline#33`](https://github.com/elelier/airquality_pipeline/issues/33).
The WAQI reject-stale guard from
[`#32`](https://github.com/elelier/airquality_pipeline/pull/32) stays active.
This performance optimization neither fixes provider outages nor licenses
displaying stale data as current.
