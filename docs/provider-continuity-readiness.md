# Provider Continuity Readiness — MtyRespira

Status: Story 1.3 operational docs baseline  
Scope: `elelier/airquality_pipeline`  
Reference app repo: `elelier/monterrey-respira` read-only for this PR

## 1. Purpose

This document prepares provider continuity for MtyRespira without changing runtime behavior.

MtyRespira must keep the public experience honest when upstream data acquisition fails. The goal is not to add a new provider or invent fallback readings. The goal is to document the current provider state, classify failures, preserve city-level traceability, and define fail-closed rules that protect the public app.

## 2. Preconditions checked

Story 1.3 was allowed to start because the app repo now has the required canonical basics:

- `AGENTS.md`
- `docs/PRD.md`
- `docs/architecture.md`
- `docs/roadmap.md`

Reference checks from `elelier/monterrey-respira`:

- `AGENTS.md` defines WAQI/AQICN as active when confirmed by pipeline/runtime evidence and AirVisual/IQAir as legacy/fallback when confirmed.
- `docs/PRD.md` requires provider continuity work to classify upstream failures without unverified fallback providers.
- `docs/architecture.md` still shows the end-to-end diagram as `AirVisual / IQAir -> airquality_pipeline`, which conflicts with current pipeline evidence and needs a separate app-docs follow-up.
- `docs/roadmap.md` still says Story 1.2.1 is in progress and Story 1.3 is blocked. PR #24 has been reported merged, so this is drift and needs a separate app-docs follow-up.

This PR does not edit the app repo.

## 3. Provider matrix

| Provider | Runtime role | Selection | Secret | Current state | Allowed use |
| --- | --- | --- | --- | --- | --- |
| WAQI/AQICN | Active provider | `AIR_QUALITY_PROVIDER=waqi` | `WAQI_API_TOKEN` | Default provider in `main.py` and GitHub Actions. Uses explicit city-to-station mapping in `waqi_api.py`. | Normal scheduled runs and manual `workflow_dispatch` when the goal is to refresh/readiness-check active production data. |
| IQAir/AirVisual | Legacy/fallback adapter | `AIR_QUALITY_PROVIDER=airvisual` | `AIRVISUAL_API_KEY` | Kept for explicit fallback only. README documents current key behavior as HTTP 402 Payment Required. | Do not use in normal operations. Only use for a controlled rollback/recovery test if IQAir access is confirmed healthy first. |
| Any other provider | Not supported | n/a | n/a | No hidden provider exists in current code. | Do not add or simulate a provider in this story. |

Provider selection evidence:

- `DEFAULT_PROVIDER = "waqi"` in `main.py`.
- GitHub Actions `workflow_dispatch.provider` allows only `waqi` or `airvisual`, defaulting to `waqi`.
- Scheduled workflow uses `${{ github.event.inputs.provider || 'waqi' }}`.
- `get_provider()` rejects unsupported provider names.

## 4. WAQI/AQICN continuity model

WAQI continuity depends on a fixed station registry, not an upstream city-list sync.

Current model:

- `waqi_api.EXPECTED_ACTIVE_API_NAMES` lists the expected active municipalities.
- `waqi_api.WAQI_STATION_BY_API_NAME` maps each supported `api_name` or known alias to a station id.
- WAQI city sync is intentionally disabled; the pipeline preserves existing Supabase city rows.
- Runtime still validates `status=ok`, AQI, timestamp, and coordinates before a reading can be inserted.

Expected active coverage:

| API name | WAQI station | Continuity status |
| --- | --- | --- |
| Monterrey | `@6492` | mapped and verified by registry |
| San Nicolas de los Garza | `@6493` | mapped and verified by registry |
| Guadalupe | `@6494` | mapped and verified by registry |
| San Pedro Garza Garcia | `@8282` | mapped and verified by registry |
| Santa Catarina | `@6491` | mapped and verified by registry |
| General Escobedo | `@6496` | mapped and verified by registry |
| Garcia | `@6495` | mapped and verified by registry |
| Ciudad Benito Juarez | `@8113` | mapped and verified by registry |
| Cadereyta Jimenez | `@10950` | mapped and verified by registry |

## 5. Error taxonomy

| Class | Code / symptom | Source | Fatal to run? | City state | Insert reading? | Public UX implication |
| --- | --- | --- | --- | --- | --- | --- |
| Missing WAQI token | `missing_token` or env validation failure for `WAQI_API_TOKEN` | config | Yes | no reliable new status if the run fails before city processing; otherwise `error: missing_token` | No | App keeps last valid RPC data if present; freshness may become stale/old. Do not claim live/current refresh. |
| Invalid provider selection | unsupported `AIR_QUALITY_PROVIDER` | config | Yes | no city update | No | Operational misconfig. Fix workflow/env, do not change public claims. |
| HTTP/provider failure | `fetch_failed` | upstream/network/rate/provider | Yes for attempted mapped city if not recovered | `error: fetch_failed` | No | Latest row remains old if one exists; UI must show stale/old/degraded based on `reading_timestamp`. |
| WAQI status not ok | `waqi_status_not_ok` | upstream/API payload | Yes for attempted mapped city | `error: waqi_status_not_ok` | No | Same as upstream failure. Do not invent AQI. |
| City without station mapping | `station_not_mapped` | registry/config | Non-fatal operational skip | `error: station_not_mapped` | No | City may be missing/stale; follow station checklist before mapping. |
| Invalid payload shape | `invalid_payload` | upstream/API payload | Yes for attempted mapped city | `error: invalid_payload` | No | Degraded public state; keep traceability. |
| Missing AQI | `missing_aqi` or validation `missing_or_invalid_aqi_us` | upstream/API payload | Yes for attempted mapped city | `error: missing_aqi` or `error: validation_failed` | No | AQI must become unavailable/unknown; never convert to AQI `0`. |
| Missing timestamp | `missing_reading_ts` | upstream/API payload | Yes for attempted mapped city | `error: missing_reading_ts` | No | Cannot trust freshness; UI must degrade. |
| Missing coordinates | `missing_coordinates` | upstream/API payload | Yes for attempted mapped city | `error: missing_coordinates` | No | No insertion; station cannot be trusted for city placement. |
| Coordinates outside Nuevo León | `coordinates_out_of_nuevo_leon` or validation latitude/longitude range errors | upstream/API payload or bad mapping | Yes for attempted mapped city | `error: coordinates_out_of_nuevo_leon` or `error: validation_failed` | No | Treat as unsafe mapping; do not change station without evidence. |
| Temperature invalid | validation `invalid_temperature` / `temperature_out_of_range` | upstream/API payload | Yes for attempted city if temperature is present and invalid | `error: validation_failed` | No | Reject payload; do not silently drop the invalid value after fetch. |
| Optional weather missing | null temperature/humidity/wind/pressure/weather icon | upstream/API payload | No when mandatory AQI/timestamp/coords are valid | `success` | Yes, with nullable weather fields | App should show `N/D` for missing secondary fields. |
| Recently updated city | `skipped: up_to_date` decision | pipeline cadence | No | Usually no write for skipped path in current main loop; summary records `up_to_date` | No | Public latest row remains valid if freshness thresholds allow it. |

## 6. Fail-closed rules

The pipeline must fail closed when provider confidence is not enough to create a trustworthy environmental reading.

Required for insert:

- Provider result status is `success`.
- AQI is present, numeric, and in range `0..500`.
- `reading_timestamp_iso` is present and parseable by downstream contract.
- Coordinates are present and inside Nuevo León bounds: lat `25.0..26.5`, lon `-101.0..-99.0`.
- Optional weather may be null, but present temperature must be within `-50..60` C.

Never do this:

- Do not synthesize AQI, pollutant, weather, coordinates, timestamps, or city mappings.
- Do not treat missing AQI as `0`.
- Do not overwrite provider failure with `success` to keep the app green.
- Do not use AirVisual as normal fallback while the known key/access state is unhealthy.
- Do not add a provider without a contract, rollout plan, and tests.

## 7. City/station continuity checklist

Use this checklist before changing any WAQI station id:

- [ ] Confirm the city is an active Supabase city and capture its stable `city_id`.
- [ ] Confirm exact `api_name` used by Supabase.
- [ ] Confirm a candidate WAQI station page or Cloud API station id.
- [ ] Run a controlled WAQI fetch with token available.
- [ ] Confirm payload `status=ok`.
- [ ] Confirm payload includes AQI.
- [ ] Confirm payload includes timestamp.
- [ ] Confirm station coordinates are inside Nuevo León bounds.
- [ ] Confirm station location reasonably represents the municipality, not only a nearby city.
- [ ] Add/update tests for the mapping registry and aliases.
- [ ] Document evidence in code comments or docs.

If any item is uncertain, keep the station unmapped or revert to the last verified mapping.

## 8. Manual validation without destructive writes

Preferred non-destructive checks:

1. Pull request CI: `pytest` only; no Supabase writes.
2. Local unit tests with mocked provider/Supabase dependencies.
3. Read-only RPC health workflow:
   - `workflow_dispatch`
   - `rpc_contract_health=true`
   - does not run `main.py`
   - runs `scripts/rpc_contract_health.py`

Manual provider validation can call WAQI externally, but do not run `main.py --force-update` unless an operator intentionally wants live writes.

## 9. Public UX implications

When provider continuity fails, the app should not claim new data exists.

Expected public behavior is governed by the frontend freshness rules:

- `reading_timestamp` drives environmental freshness.
- `last_successful_update_at` is pipeline traceability only.
- Old but valid latest readings may remain visible with stale/old/degraded copy.
- Missing AQI, missing timestamp, missing latest row, or invalid payload must become unknown/unavailable/degraded.
- Public copy must avoid “tiempo real”. Prefer “lecturas disponibles”, “medición reportada”, or “actualización por pipeline horario”.

## 10. Rollback procedure

Documentation-only rollback:

1. Revert the docs PR.
2. Keep runtime unchanged.
3. Re-open the story with corrected evidence if the rollback removed useful operational guidance.

Runtime rollback if a future provider change breaks continuity:

1. Stop further runtime changes and inspect the latest workflow logs.
2. Keep `get_latest_air_quality_per_city` unchanged.
3. Revert the provider/mapping commit that introduced the failure.
4. Prefer restoring the last verified WAQI mapping over switching providers.
5. Only use `AIR_QUALITY_PROVIDER=airvisual` after IQAir access is proven healthy; otherwise it is a false fallback.
6. Validate with `pytest`, then a controlled scheduled/manual run as appropriate.
7. Validate public app freshness/degradation after the next successful pipeline cycle.

## 11. Follow-up app docs

The app repo has drift that should be corrected separately in `elelier/monterrey-respira`:

### `docs/roadmap.md`

Current drift:

- Story 1.2.1 still says `Estado: en curso`.
- Story 1.3 still says `Estado: bloqueada hasta merge de Story 1.2.1`.

Suggested patch:

```diff
- Estado: en curso.
+ Estado: completada por PR #24 — docs: add canonical MtyRespira project docs baseline.

- Estado: bloqueada hasta merge de Story 1.2.1.
+ Estado: desbloqueada tras PR #24; ejecución principal en `elelier/airquality_pipeline`.
```

### `docs/architecture.md`

Current drift:

- The end-to-end diagram starts with `AirVisual / IQAir`, but pipeline evidence now confirms WAQI/AQICN as active provider and AirVisual as legacy/fallback.

Suggested patch:

```diff
-AirVisual / IQAir
+WAQI / AQICN (active) or IQAir / AirVisual (legacy/fallback only when explicitly selected and healthy)
```

Do not make these app-doc updates inside the pipeline PR.
