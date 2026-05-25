# Weather Context Live Run Evidence — MtyRespira

Status: pending live run evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Review timestamp: 2026-05-25 04:05 UTC  
Decision type: Data QA / post-merge observation / Docs

## Purpose

Check whether the Open-Meteo weather context write path merged in PR #23 has produced new rows with canonical `weather_*` values.

## Context

Merged implementation:

- PR #23: `feat: add Open-Meteo weather context write path`
- Merge commit: `983cabf0db5987c2f1f832e45311e038c803710e`
- Merge time: 2026-05-25 03:59:44 UTC

Workflow behavior:

- Scheduled run: hourly at `0 * * * *`.
- Manual run: supported through `workflow_dispatch`.
- Default provider: `waqi`.

## Read-only query used

```sql
select
  count(*) as total_readings,
  count(*) filter (where weather_provider = 'open-meteo') as open_meteo_readings,
  max(created_at) as latest_created_at,
  max(created_at) filter (where weather_provider = 'open-meteo') as latest_open_meteo_created_at
from public.air_quality_readings;
```

## Result

```json
[
  {
    "total_readings": 20232,
    "open_meteo_readings": 0,
    "latest_created_at": "2026-05-25 02:08:55.365259+00",
    "latest_open_meteo_created_at": null
  }
]
```

## Interpretation

No live Open-Meteo write-path evidence exists yet.

Reasons:

- `open_meteo_readings = 0`.
- The latest row timestamp is `2026-05-25 02:08:55 UTC`, which is before PR #23 merged at `2026-05-25 03:59:44 UTC`.
- Therefore, the production pipeline has not inserted a post-merge row yet, or a post-merge run has not completed with new inserts.

## Decision

**Pending live evidence.**

Do not proceed to backfill, RPC exposure, frontend adoption, or constraint validation based on this check alone.

## Next step

Wait for the next scheduled workflow run or manually dispatch the pipeline with:

- provider: `waqi`
- force_update: `true` only if intentionally forcing all active cities to create fresh readings
- rpc_contract_health: `false`

After the run completes, repeat the read-only query above and inspect a small sample of the newest rows with `weather_provider = 'open-meteo'`.

## No-write guarantees

This story did not perform:

- Supabase DDL,
- Supabase data mutation,
- backfill,
- runtime code changes,
- workflow schedule changes,
- RPC changes,
- frontend changes,
- AQI provider changes,
- secret exposure.

## Risks / pending items

- If the next scheduled run skips all cities as up to date, no new evidence will be produced until the update interval is exceeded or a force update is run.
- If Open-Meteo fails, AQI inserts should remain non-blocking and weather context counters should record errors.
- Live evidence must confirm actual inserted `weather_*` fields before any RPC/frontend adoption.

## Rollback

Revert this documentation PR if needed.

No DB rollback is required because this check was read-only.