# Weather Context Provider Spike — MtyRespira

Status: Story 1.4.3 spike / contract decision  
Scope: `elelier/airquality_pipeline`  
Reference app repo: `elelier/monterrey-respira` read-only for this story  
Decision type: planning / data QA / docs only

## 1. Purpose

This spike documents the observed weather-context data quality issue and proposes a safe provider/data-contract direction before any Supabase write, DDL, migration, runtime app change, AQI provider change, or AQI contract change.

The goal is to separate meteorological context from air-quality readings. AQI, main pollutant, station mapping, coordinates, reading freshness, and historical AQI must remain governed by the existing WAQI/AQICN pipeline contract until a later implementation story explicitly changes that contract.

## 2. Non-goals and hard boundaries

This story does not implement runtime behavior.

Do not do any of the following in this story:

- Write to Supabase.
- Apply DDL or migrations.
- Backfill production rows.
- Change `main.py` runtime flow.
- Change WAQI/AQICN as AQI provider.
- Change AQI, main pollutant, AQI historical rows, city geolocation, or public RPC behavior.
- Change frontend UI/UX runtime code.
- Add `service_role` to the frontend/app.
- Add secrets or real credentials to docs, tests, scripts, or workflow files.

## 3. Current state checked

### Pipeline

- `README.md` confirms WAQI/AQICN as the active provider and IQAir/AirVisual as legacy/fallback.
- `.github/workflows/air-quality-workflow.yml` runs PR tests only on pull requests and runs `main.py` only for scheduled/manual non-PR runs.
- `main.py` defaults `AIR_QUALITY_PROVIDER` to `waqi` and rejects unsupported providers.
- `waqi_api.py` maps active cities to explicit WAQI station ids and normalizes `iaqi` weather fields into a `clima` object.
- `update_city.py` persists WAQI-derived weather context into `temperature_c`, `humidity_percent`, `wind_speed_ms`, `wind_direction_deg`, and `weather_icon` together with the AQI reading.
- `utils.py` validates AQI, coordinates, and only a broad optional temperature range. Humidity/wind units are not contract-validated today.
- Provider continuity docs already require fail-closed behavior for AQI/timestamp/coordinates and warn not to synthesize data.

### App reference, read-only

- `docs/shared-data-contract.md` freezes the current provider-to-RPC-to-frontend boundary and lists `temperature_c`, `humidity_percent`, `wind_speed_ms`, and `wind_direction_deg` in the latest RPC payload.
- `src/context/AirQualityContext.tsx` maps `cityData.wind_speed_ms` directly into `data.wind.speed`.
- `src/components/AirQualityCard.tsx` renders `data.wind.speed` with `km/h`, which creates a unit-risk because the field name says `wind_speed_ms`.
- The same card renders `Temperatura` as an environmental detail without clarifying that the value comes from a secondary WAQI `iaqi` field rather than a dedicated weather provider.

## 4. Problem observed

A runtime observation showed Monterrey/Obispado WAQI `iaqi.t.v` around `15.5` °C at local midday while weather references for Monterrey were around `30` °C. The database preserved `temperature_c = 15.5`, consistent with raw WAQI, and the public app displayed that value directly as °C.

This means the pipeline likely behaved as coded, but the weather-context source is not trustworthy enough to present as real local meteorological conditions for every station.

Important distinction:

- This does not invalidate AQI from WAQI/AQICN.
- This does not imply the WAQI station mapping is wrong for AQI.
- This does show that WAQI `iaqi` weather fields should not be treated as canonical weather context without a separate decision.

## 5. Provider decision

Recommended decision: keep WAQI/AQICN as the AQI provider and add Open-Meteo as a separate meteorological context provider in a future implementation story.

Reasoning:

- MtyRespira needs air-quality data and meteorological context, but those are different trust domains.
- WAQI station payloads are suitable for AQI only when they pass the existing fail-closed checks.
- Weather context should be coordinate-based by city and explicitly attributed to a weather provider.
- Open-Meteo supports coordinate-based weather endpoints and the needed variables: temperature, relative humidity, wind speed, wind direction, and wind gusts.
- Open-Meteo supports `wind_speed_unit=kmh`, reducing ambiguity with the current app copy.
- Open-Meteo historical weather/archive endpoints can support a dry-run design for a 60-day weather backfill before any write decision.

Primary references to validate before implementation:

- Weather Forecast API: https://open-meteo.com/en/docs
- Historical Weather API: https://open-meteo.com/en/docs/historical-weather-api

## 6. Recommended data contract

Recommended additive fields for weather context:

| Field | Type | Nullable | Source | Notes |
| --- | --- | --- | --- | --- |
| `weather_temperature_c` | numeric / real | yes | Open-Meteo | Canonical weather-context temperature in Celsius. Do not reuse WAQI `temperature_c` semantics. |
| `weather_humidity_percent` | numeric / smallint | yes | Open-Meteo | Relative humidity percent. Validate `0..100`. |
| `weather_wind_speed_kmh` | numeric / real | yes | Open-Meteo | Canonical weather wind speed in km/h. Avoid `ms` naming if value is km/h. |
| `weather_wind_direction_deg` | numeric / smallint | yes | Open-Meteo | Validate `0..360`. |
| `weather_wind_gust_kmh` | numeric / real | yes | Open-Meteo | Optional, useful for public weather context and QA deltas. |
| `weather_provider` | text | yes | Open-Meteo | Example: `open-meteo`. Required when any weather_* field is present. |
| `weather_timestamp` | timestamptz | yes | Open-Meteo | Timestamp for selected hourly weather bucket. Must not replace `reading_timestamp`. |
| `weather_raw_response` or `weather_source_payload` | jsonb | yes | Open-Meteo | Prefer trimmed provider payload or per-hour selected payload. Avoid storing excessive response volume if not needed. |
| `weather_backfilled_at` | timestamptz | yes | pipeline | Only populated for rows created/updated by a future approved backfill. |

Contract principles:

- Additive only: do not rename or remove existing RPC fields in the same rollout.
- Keep `reading_timestamp` as AQI measurement timestamp.
- Keep `last_successful_update_at` as pipeline traceability.
- Keep current AQI fields independent from weather context.
- Keep legacy WAQI weather fields available only as legacy/diagnostic data until deprecated through a coordinated app contract.
- Do not expose provider raw payload internals to the frontend.

## 7. Suggested storage rollout options

### Option A — Additive columns on `air_quality_readings`

Pros:

- Simple alignment with each AQI reading row.
- Easy latest RPC extension.
- Easy historical AQI chart enrichment.

Cons:

- Requires DDL and migration in a future story.
- Backfill updates existing historical rows, so it needs a strict dry-run and rollback plan.
- Multiple AQI readings in the same city/hour may duplicate identical weather payloads.

### Option B — Separate `weather_context_readings` table

Pros:

- Cleaner provider separation.
- Weather can refresh independently from AQI.
- Easier retention and provenance control.

Cons:

- Requires new table, join/RPC logic, and more contract work.
- More moving parts for app consumption.
- Future UI must handle unmatched AQI/weather timestamps.

### Recommendation

Prefer Option A for the first production rollout only if the team wants minimal complexity and per-AQI-row weather context. Prefer Option B if the product direction expects weather to become an independent feature, not just a supporting context.

This spike does not choose schema implementation. It recommends that the next implementation story make the final storage decision after dry-run evidence.

## 8. Open-Meteo request design

### Current/latest weather context

Use city coordinates from `cities` or the normalized active city list. Request hourly or current variables with explicit units.

Candidate variables:

```text
latitude=<city_lat>
longitude=<city_lon>
hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m
timezone=UTC
wind_speed_unit=kmh
temperature_unit=celsius
```

For a current-weather-only future story, `current=` can be evaluated, but hourly data is preferred for alignment to an AQI `reading_timestamp`.

### Historical / 60-day backfill dry-run

Use the Historical Weather API for each active city coordinate and request hourly variables for the desired date window.

Candidate variables:

```text
latitude=<city_lat>
longitude=<city_lon>
start_date=<YYYY-MM-DD>
end_date=<YYYY-MM-DD>
hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m
timezone=UTC
wind_speed_unit=kmh
temperature_unit=celsius
```

No production credentials are needed for the dry-run design unless a future script calls Supabase read-only to count target rows. The safe default is to read exported/sample input, not connect to production.

## 9. Timestamp alignment strategy

Weather context must align to AQI readings without rewriting AQI time semantics.

Recommended alignment:

1. For each active city, use its stable `city_id`, `api_name`, latitude, and longitude from `cities`.
2. For each target AQI row, read `reading_timestamp` as UTC.
3. Find the nearest Open-Meteo hourly timestamp for the same city coordinates.
4. Accept the match only when absolute delta is within a strict threshold, recommended `<= 30 minutes` for hourly data.
5. Store or report the selected `weather_timestamp` separately from `reading_timestamp`.
6. If no acceptable weather hour exists, leave weather fields null and record a dry-run validation issue.

Tie-breaker:

- If two hourly buckets are equally close, choose the earlier bucket and record the delta.

## 10. 60-day backfill dry-run design

The dry-run must not write to Supabase.

Suggested future script name:

```text
scripts/weather_backfill_dry_run.py
```

Allowed behavior:

- Read active cities and candidate AQI rows using a read-only path or sample export.
- Fetch Open-Meteo historical hourly data by city coordinate.
- Match each AQI `reading_timestamp` to nearest hourly weather timestamp.
- Print or export a local report only.
- Exit non-zero if configured validation thresholds fail.

Forbidden behavior:

- No `insert`, `update`, `upsert`, `delete`, DDL, migrations, or live apply.
- No service-role requirement unless future maintainers explicitly accept read-only production access risk; prefer anon/RPC or static export for dry-run.
- No mutation of `air_quality_readings`, `cities`, RPCs, or app code.

Suggested report shape:

```jsonc
{
  "mode": "dry_run",
  "provider": "open-meteo",
  "window_days": 60,
  "generated_at": "2026-05-24T00:00:00Z",
  "summary": {
    "active_cities": 9,
    "target_aqi_rows": 0,
    "matched_rows": 0,
    "unmatched_rows": 0,
    "null_weather_rows": 0,
    "unit_violations": 0,
    "range_violations": 0,
    "large_delta_vs_waqi_rows": 0
  },
  "city_results": [
    {
      "city_id": 9,
      "api_name": "Monterrey",
      "target_rows": 0,
      "matched_rows": 0,
      "max_alignment_delta_minutes": 0,
      "temperature_min_c": null,
      "temperature_max_c": null,
      "wind_speed_max_kmh": null
    }
  ]
}
```

## 11. Validation plan

### Expected row counts

- Count active cities before dry-run.
- Count target AQI readings for the last 60 days per active city.
- Expected matched weather rows should equal target AQI rows unless there are missing coordinates or missing Open-Meteo hours.
- Any mismatch must be listed by city and reason.

### Nullability

- `weather_provider` and `weather_timestamp` must be present when any `weather_*` value is present.
- Weather values may be null when provider data is unavailable or fails validation.
- AQI fields must not become null or modified due to weather validation.

### Physical ranges

Recommended validation thresholds:

| Field | Valid range | Severity |
| --- | --- | --- |
| `weather_temperature_c` | `-20..60` for Monterrey QA guard, hard reject outside `-50..60` | warning/reject depending rollout |
| `weather_humidity_percent` | `0..100` | reject field |
| `weather_wind_speed_kmh` | `0..160` | warning above local sanity threshold; reject if negative |
| `weather_wind_gust_kmh` | `0..220` | warning above local sanity threshold; reject if negative |
| `weather_wind_direction_deg` | `0..360` | reject field |
| timestamp alignment delta | `<= 30 minutes` | reject match |

### Delta against WAQI weather fields

For QA only, compare Open-Meteo values against legacy WAQI weather fields when both exist.

Recommended flags:

- Temperature absolute delta `>= 8` °C: flag as `large_temperature_delta_vs_waqi`.
- Humidity absolute delta `>= 25` percentage points: flag as `large_humidity_delta_vs_waqi`.
- Wind speed: first normalize units before comparing. Do not compare `wind_speed_ms` directly to km/h.

Delta flags must not invalidate AQI. They exist to prove why weather context needs a separate provider.

### Wind unit validation

Current risk:

- Pipeline field name: `wind_speed_ms`.
- App display copy: `km/h`.
- Open-Meteo recommendation: request/store `weather_wind_speed_kmh` explicitly.

Validation:

- Never write km/h values into a `*_ms` field.
- If using Open-Meteo with `wind_speed_unit=kmh`, target field must be `weather_wind_speed_kmh`.
- If a future legacy transform still uses `wind_speed_ms`, the frontend must either convert `m/s * 3.6` or display `m/s`. Do not silently label one as the other.

## 12. UX copy proposal for future app story

Recommended public copy:

- Section label: `Condiciones meteorológicas`
- Source label: `Fuente meteorológica: Open-Meteo`
- Timestamp label: `Clima estimado para <hora>` or `Condición meteorológica <hora>`
- AQI label remains separate: `Medición AQI <hora>`

Avoid:

- `Temperatura` without source/context if the value comes from WAQI `iaqi`.
- Any copy implying weather values come from the AQI station unless proven.
- Any copy that merges AQI freshness and weather freshness into one timestamp.
- Any claim of real-time weather unless a future contract explicitly supports it.

## 13. Proposed follow-up stories

### Story 1.4.4 — Weather Context Dry-Run Script

Implement a dry-run-only script and local report generation for the last 60 days. No Supabase writes. No DDL. No frontend runtime changes.

Acceptance outline:

- Script can run without production write credentials.
- Produces per-city match/null/range/delta summary.
- Requests Open-Meteo with explicit `wind_speed_unit=kmh`.
- Has tests for timestamp matching and unit handling.

### Story 1.4.5 — Weather Contract Migration Proposal

Based on dry-run evidence, decide Option A vs Option B and document a migration/RPC rollout plan. No live apply unless separately approved.

### Story 1.4.6 — Weather Context UI Copy Rollout

After backend contract exists, update the public app copy to separate AQI and weather context.

## 14. Rollback

Because this story is docs-only:

1. Revert the docs PR.
2. Keep runtime pipeline unchanged.
3. Keep Supabase unchanged.
4. Keep app unchanged.

Future implementation rollback must be defined in the implementation PR and must preserve AQI readings, `get_latest_air_quality_per_city`, city geolocation, and historical AQI semantics.

## 15. Final recommendation

Proceed with Open-Meteo as a separate weather-context provider, but only through a staged rollout:

1. Dry-run evidence.
2. Contract/storage decision.
3. Migration proposal.
4. Backend implementation.
5. RPC/app contract extension.
6. UX copy update.

Do not backfill production weather fields until the dry-run proves row counts, timestamp alignment, physical ranges, null handling, and wind-unit semantics are safe.