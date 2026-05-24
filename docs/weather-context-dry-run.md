# Weather Context Dry-Run — MtyRespira

Status: Story 1.4.4 dry-run evidence tooling  
Scope: `elelier/airquality_pipeline`  
Reference app repo: `elelier/monterrey-respira` remains read-only for this story

## Purpose

This document explains how to run `scripts/weather_backfill_dry_run.py` to evaluate Open-Meteo as a separate meteorological context provider for MtyRespira.

The script creates local evidence only. It does not change `main.py`, `update_city.py`, the hourly workflow, the frontend, Supabase schema, RPCs, AQI fields, city geolocation, historical AQI, or the WAQI/AQICN provider contract.

## No-write guarantees

The dry-run uses local JSON/CSV input files. Without `--output`, it prints the full JSON report to stdout. With `--output`, it writes the full JSON report to the local report path and prints only a short confirmation.

It does not require:

- Supabase credentials.
- `SUPABASE_SERVICE_ROLE_KEY`.
- WAQI credentials.
- Production database access.
- DDL or migration permissions.

The script does not import the Supabase client and has a regression test that scans the script source for mutation/client tokens.

## Input files

### Active cities file

JSON or CSV is accepted. Required columns/keys:

| Field | Required | Notes |
| --- | --- | --- |
| `city_id` | yes | Stable numeric MtyRespira city id. |
| `api_name` | yes | City/provider display name used for reporting. |
| `latitude` | yes | City latitude used for Open-Meteo lookup. |
| `longitude` | yes | City longitude used for Open-Meteo lookup. |

Example JSON:

```json
[
  {
    "city_id": 9,
    "api_name": "Monterrey",
    "latitude": 25.6866,
    "longitude": -100.3161
  }
]
```

### Candidate AQI readings file

JSON or CSV is accepted. Required columns/keys:

| Field | Required | Notes |
| --- | --- | --- |
| `city_id` | yes | Stable numeric id. Must match the active cities file. |
| `reading_timestamp` | yes | AQI measurement timestamp. UTC is recommended. |
| `temperature_c` | no | Legacy WAQI weather field for QA delta only. |
| `humidity_percent` | no | Legacy WAQI weather field for QA delta only. |
| `wind_speed_ms` | no | Legacy field. The dry-run does not store Open-Meteo km/h here. |
| `wind_direction_deg` | no | Legacy WAQI weather field for QA context. |

Example JSON:

```json
[
  {
    "city_id": 9,
    "reading_timestamp": "2026-05-24T18:00:00Z",
    "temperature_c": 15.5,
    "humidity_percent": 40,
    "wind_speed_ms": 2.5,
    "wind_direction_deg": 90
  }
]
```

## How to run

Default stdout JSON report:

```bash
python scripts/weather_backfill_dry_run.py \
  --cities ./local/active-cities.json \
  --readings ./local/aqi-candidate-readings.json
```

Save a local report file. This writes the full JSON report to disk and prints only a short confirmation to stdout:

```bash
python scripts/weather_backfill_dry_run.py \
  --cities ./local/active-cities.json \
  --readings ./local/aqi-candidate-readings.json \
  --window-days 60 \
  --output reports/weather-backfill-dry-run.json
```

## Open-Meteo request contract

The script calls the Open-Meteo Historical Weather API by city coordinates and candidate reading dates.

It requests:

```text
hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m
timezone=UTC
wind_speed_unit=kmh
temperature_unit=celsius
```

The report uses explicit weather field names:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_provider`
- `weather_timestamp`

`reading_timestamp` is never changed or reused as the weather timestamp.

## Matching logic

For each candidate AQI row:

1. Match by numeric `city_id`.
2. Use the city's `latitude` and `longitude`.
3. Fetch hourly Open-Meteo weather for the candidate date range.
4. Choose the weather hour nearest to `reading_timestamp`.
5. Accept the match only when the absolute delta is `<= 30` minutes.
6. If there is an exact tie, choose the previous hour.
7. Leave unmatched rows in the report as validation issues.

## Report format

The JSON report contains:

| Field | Meaning |
| --- | --- |
| `mode` | Always `dry_run`. |
| `provider` | Always `open-meteo`. |
| `window_days` | Evidence window label from CLI input. |
| `generated_at` | UTC report generation timestamp. |
| `summary` | Aggregate counts and validation counts. |
| `city_results` | Per-city target rows, matched rows, max alignment delta, sampled matches, and range summaries. |
| `validation_issues` | Missing input, unmatched hour, range, delta, and provider fetch issues. |
| `unit_contract` | Explicit wind-unit guardrail for `weather_wind_speed_kmh`. |

## Validation rules

The dry-run reports the following issues:

- Expected row count vs matched count.
- Missing coordinates.
- Missing `reading_timestamp`.
- Unmatched weather hour.
- Weather metadata nullability:
  - if any `weather_*` value is present, `weather_provider` and `weather_timestamp` must exist in the matched report row.
- Physical ranges:
  - `weather_temperature_c` hard reject outside `-50..60`.
  - Monterrey QA warning below `-20`.
  - `weather_humidity_percent` must be `0..100`.
  - `weather_wind_speed_kmh` must be `>= 0`; warning above `160`.
  - `weather_wind_gust_kmh` must be `>= 0`; warning above `220`.
  - `weather_wind_direction_deg` must be `0..360`.
- Delta against WAQI legacy fields:
  - temperature delta `>= 8 °C`.
  - humidity delta `>= 25` points.
  - wind is not compared unless a future story explicitly defines unit normalization.
- Wind unit guardrail:
  - Open-Meteo km/h values must be reported as `weather_wind_speed_kmh`, never as a `*_ms` weather field.

## Interpreting results

Use the report to answer these questions before any contract or migration story:

- Are all active cities present with coordinates?
- Do all candidate AQI rows have a valid timestamp?
- Does Open-Meteo provide hourly data for the candidate windows?
- Are matched rows close enough to AQI readings under the `<= 30 min` rule?
- Are physical ranges reasonable for Monterrey and the metropolitan area?
- Do deltas against WAQI legacy weather fields confirm the need for a separate weather provider?
- Does the wind unit remain explicitly `weather_wind_speed_kmh`?

Warnings do not invalidate AQI. They help decide whether weather context should be stored, how it should be named, and how UI copy should explain source/timestamp.

## Tests

Run:

```bash
pytest tests/test_weather_backfill_dry_run.py
pytest
```

The tests avoid real network calls by injecting a fake weather fetcher. They cover:

- nearest-hour matching.
- threshold rejection above 30 minutes.
- previous-hour tie breaker.
- range validation.
- temperature and humidity deltas against WAQI legacy fields.
- weather metadata nullability on matched report rows.
- wind-unit field naming and violation detection.
- report summary and per-city results.
- no Supabase client or mutation tokens in the dry-run script.

## Next steps

Story 1.4.5 should use dry-run evidence to decide the production weather contract:

- additive weather columns on `air_quality_readings`, or
- separate `weather_context_readings` table.

That future story must still avoid live apply unless explicitly approved. It should preserve AQI, main pollutant, historical AQI, geolocation, `reading_timestamp`, and the public RPC contract until a coordinated migration/RPC/app rollout exists.
