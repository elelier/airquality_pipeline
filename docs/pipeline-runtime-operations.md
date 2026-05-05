# Pipeline Runtime Operations

## Runtime

Workflow: `.github/workflows/air-quality-workflow.yml`

Triggers:

- Scheduled hourly: `0 * * * *`
- Manual: `workflow_dispatch`
- Pull request: tests only

## Manual recovery

When data is stale, run the workflow manually with `force_update=true`.

This bypasses the timestamp interval check and attempts to refresh all active cities.

## Healthy run criteria

A run is healthy when:

- at least one update was attempted and at least one reading was inserted, or
- no updates were needed and at least one active city was skipped as up-to-date.

A run is unhealthy when:

- there are no active cities,
- any city update fails,
- updates were attempted but zero readings were inserted, or
- no active city was updated or skipped.

## Summary block

`main.py` emits a final `[SUMMARY] Pipeline operacional` block with:

- active cities
- updates attempted
- readings inserted
- skipped cities
- failed updates
- fetch errors
- validation failures
- insert errors
- update errors
- per-city results

## Common stale-data causes

- GitHub disabled the scheduled workflow after repository inactivity.
- A required GitHub Actions secret is missing or stale.
- AirVisual returned errors or rate limits.
- Supabase insert or update failed.

## Post-run checks

After a manual recovery run, check the latest reading timestamp in Supabase and review each city status.

The frontend only consumes the data. Pipeline health must be validated from this repo and Supabase.
