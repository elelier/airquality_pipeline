# RPC Health Evidence

This document captures the post-merge operating evidence for the read-only RPC contract health check introduced in PR #9.

## Scope

Product boundary:

`WAQI/AQICN -> airquality_pipeline -> Supabase tables -> get_latest_air_quality_per_city -> monterrey-respira`

This evidence covers only the read-only RPC contract/freshness check. It must not be used as evidence of a live write, schema migration, RPC shape change, or frontend deployment change.

## Current post-merge state

- PR #9 is merged into `main`.
- `.github/workflows/air-quality-workflow.yml` contains the manual `rpc-contract-health` job gated by `workflow_dispatch` input `rpc_contract_health=true`.
- The hourly `build` job is skipped when `rpc_contract_health=true`, so a manual RPC health run does not block or replace the normal hourly pipeline.
- This PR does not execute live writes and does not require any Supabase schema/RPC/frontend change.

## How to run the production RPC health check

Use GitHub Actions manually:

1. Open **Actions -> Air Quality Pipeline**.
2. Select **Run workflow** from `main`.
3. Set:
   - `rpc_contract_health=true`
   - `force_update=false`
   - `provider=waqi`
4. Wait for the `rpc-contract-health` job to finish.
5. Open the run artifacts and download `rpc-contract-health-log`.
6. Confirm the JSON output status and preserve the run URL in the evidence table below.

Required secrets for this read-only check:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Do not paste secret values into this document, PR comments, screenshots, or logs.

## Evidence table

| Check | Evidence |
| --- | --- |
| Workflow | Air Quality Pipeline / manual `workflow_dispatch` |
| Inputs | `rpc_contract_health=true`, `force_update=false`, `provider=waqi` |
| Run URL | `TODO: paste GitHub Actions run URL after manual dispatch` |
| Artifact | `rpc-contract-health-log` |
| Observed status | `TODO: healthy / degraded / unhealthy / config_error` |
| Checked at UTC | `TODO: timestamp from run/log` |
| Contract shape | `TODO: pass/fail based on log` |
| Freshness interpretation | `TODO: healthy, degraded warning, or unhealthy fail threshold` |
| Next action | `TODO: none / recovery / config fix / investigation` |

## How to interpret status

`healthy` means the RPC contract is intact and freshness is inside the configured warning threshold.

`degraded` means the RPC contract is intact, but one or more readings are older than the warning threshold. This is not the same as a contract break. If the site is showing stale data, run manual recovery separately with `force_update=true` and `provider=waqi`, then rerun this health check.

`unhealthy` means the contract or freshness failed hard. Examples include missing expected city IDs, duplicate `city_id`, null `aqi_us` for a required healthy row, invalid timestamps, or readings older than the fail threshold. Do not change the RPC or database manually from this evidence doc; diagnose from the log first.

`config_error` or exit code `2` means the check could not validate production. Common causes are missing secrets, an invalid `SUPABASE_URL`, DNS failure, or RPC call failure. Fix configuration first; do not treat this as proof that the RPC payload is broken.

## Recovery rule

Only run manual recovery when the contract is intact but data is stale or missing due to pipeline freshness/upstream issues:

- `force_update=true`
- `provider=waqi`
- `rpc_contract_health=false`

After recovery completes, run the RPC health check again with:

- `force_update=false`
- `provider=waqi`
- `rpc_contract_health=true`

## Rollback

Revert this docs PR if the evidence process needs to be removed. No Supabase schema, RPC shape, table data, workflow schedule, or frontend rollback is required.
