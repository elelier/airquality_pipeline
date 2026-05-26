# Weather Context Live Coverage Evidence — MtyRespira

Status: partial live coverage evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Review timestamp: 2026-05-26 08:20 UTC  
Decision type: Data QA / Architecture validation / Docs

## Summary

This document records read-only live evidence for canonical Open-Meteo weather-context coverage after:

- PR #23: `feat: add Open-Meteo weather context write path`
- PR #26: `fix: use canonical city coordinates for weather context`
- PR #27: `fix: improve retry handling`

The latest active-city readings are post-merge and confirm that AQI inserts continue. Weather context coverage is real but still partial.

Result summary:

| Metric | Result |
| --- | ---: |
| Active cities checked | 9 |
| Active cities with latest reading | 9 |
| Latest readings with AQI | 9 |
| Latest readings with `weather_provider = 'open-meteo'` | 5 |
| Latest readings with complete core weather context | 5 |
| Active cities missing canonical weather context | 4 |

Decision: **partial coverage — investigate missing weather context by city before frontend adoption or backfill.**

## Scope

This story is evidence-only.

It does not change:

- Supabase schema,
- data rows,
- backfill state,
- runtime pipeline code,
- WAQI/AQICN provider behavior,
- RPCs,
- frontend code,
- workflow schedule,
- AQI values,
- `main_pollutant_us`,
- historical AQI,
- city identity,
- city geolocation,
- public frontend contract.

## Evidence query intent

The evidence checks the latest reading for each active city and asks:

1. Does every active city have a recent latest reading?
2. Does every latest reading still have AQI?
3. Which latest readings include canonical Open-Meteo fields?
4. Which cities are still missing canonical weather context?
5. Are the latest rows newer than PR #26 and PR #27 merge times?

PR merge reference:

| PR | Merge time UTC |
| --- | --- |
| PR #26 | 2026-05-25 20:11:50 UTC |
| PR #27 | 2026-05-26 07:25:52 UTC |

The latest rows captured below were created around `2026-05-26 04:55..04:57 UTC`, which is after PR #26 but before PR #27. Therefore this evidence confirms post-coordinate-fix coverage, but not yet a post-PR-27 scheduled insert. The retry fix should still be verified on a later post-PR-27 run if retry behavior is specifically under review.

## Read-only summary query

```sql
with latest as (
  select distinct on (c.id)
    c.id as city_id,
    c.name as city_name,
    c.is_active,
    r.id as reading_id,
    r.created_at,
    r.reading_timestamp,
    r.aqi_us,
    r.main_pollutant_us,
    r.weather_provider,
    r.weather_temperature_c,
    r.weather_humidity_percent,
    r.weather_wind_speed_kmh,
    r.weather_wind_direction_deg,
    r.weather_wind_gust_kmh,
    r.weather_timestamp
  from public.cities c
  left join public.air_quality_readings r on r.city_id = c.id
  where c.is_active = true
  order by c.id, r.created_at desc nulls last
)
select
  count(*) as active_cities,
  count(*) filter (where reading_id is not null) as active_cities_with_latest_reading,
  count(*) filter (where aqi_us is not null) as latest_readings_with_aqi,
  count(*) filter (where weather_provider = 'open-meteo') as latest_readings_with_open_meteo,
  count(*) filter (
    where weather_provider = 'open-meteo'
      and weather_temperature_c is not null
      and weather_humidity_percent is not null
      and weather_wind_speed_kmh is not null
      and weather_timestamp is not null
  ) as latest_readings_with_complete_core_weather,
  max(created_at) as newest_created_at,
  min(created_at) as oldest_latest_created_at
from latest;
```

Result:

```json
[
  {
    "active_cities": 9,
    "active_cities_with_latest_reading": 9,
    "latest_readings_with_aqi": 9,
    "latest_readings_with_open_meteo": 5,
    "latest_readings_with_complete_core_weather": 5,
    "newest_created_at": "2026-05-26 04:57:55.99183+00",
    "oldest_latest_created_at": "2026-05-26 04:55:50.808115+00"
  }
]
```

## Coverage by city

| City | Created at UTC | AQI | Main pollutant | Weather provider | Core weather fields |
| --- | --- | ---: | --- | --- | --- |
| Cadereyta Jimenez | 2026-05-26 04:56:32 | 55 | `pm25` | null | missing |
| Ciudad Benito Juárez | 2026-05-26 04:57:03 | 55 | `pm25` | null | missing |
| Garcia | 2026-05-26 04:56:42 | 33 | `pm25` | `open-meteo` | complete |
| General Escobedo | 2026-05-26 04:57:55 | 46 | `pm25` | `open-meteo` | complete |
| Guadalupe | 2026-05-26 04:57:13 | 31 | `o3` | `open-meteo` | complete |
| Monterrey | 2026-05-26 04:57:45 | 34 | `pm25` | null | missing |
| San Nicolas de los Garza | 2026-05-26 04:56:11 | 58 | `pm25` | null | missing |
| San Pedro Garza Garcia | 2026-05-26 04:57:24 | 46 | `pm25` | `open-meteo` | complete |
| Santa Catarina | 2026-05-26 04:55:50 | 42 | `pm25` | `open-meteo` | complete |

Cities with complete canonical weather context:

- Garcia
- General Escobedo
- Guadalupe
- San Pedro Garza Garcia
- Santa Catarina

Cities still missing canonical weather context on latest reading:

- Cadereyta Jimenez
- Ciudad Benito Juárez
- Monterrey
- San Nicolas de los Garza

## AQI safety check

All 9 active cities have a latest reading with non-null AQI.

This supports the intended behavior that weather context remains separate from AQI and does not block successful AQI inserts.

Observed latest AQI values remain present across both groups:

- Cities with Open-Meteo context: AQI values present.
- Cities without Open-Meteo context: AQI values present.

No AQI rewrite or pollutant rewrite was performed by this evidence story.

## Weather context completeness

For the 5 latest readings with `weather_provider = 'open-meteo'`, the core canonical fields were present:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_timestamp`

Observed complete-weather examples:

| City | Temperature C | Humidity % | Wind km/h | Wind direction deg | Gust km/h | Weather timestamp UTC |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Garcia | 24.5 | 73 | 29.2 | 86 | 48.6 | 2026-05-26 04:45:00 |
| General Escobedo | 25.2 | 76 | 17.9 | 115 | 33.1 | 2026-05-26 04:45:00 |
| Guadalupe | 25.0 | 76 | 17.6 | 125 | 33.5 | 2026-05-26 04:45:00 |
| San Pedro Garza Garcia | 24.9 | 70 | 19.2 | 67 | 29.9 | 2026-05-26 04:45:00 |
| Santa Catarina | 24.2 | 74 | 24.4 | 68 | 36.0 | 2026-05-26 04:45:00 |

## Gaps / cities pending

Coverage is not yet sufficient for frontend adoption because 4 of 9 active cities still have null canonical weather context on latest readings.

Pending investigation should focus on why these cities inserted AQI successfully but did not persist weather context:

- Cadereyta Jimenez
- Ciudad Benito Juárez
- Monterrey
- San Nicolas de los Garza

Likely investigation areas for a future runtime/debug story:

- Confirm whether canonical `cities.latitude` and `cities.longitude` are present and parseable for each missing city.
- Inspect pipeline logs for `[Weather]` errors on these cities.
- Confirm whether Open-Meteo returned non-retryable client errors, retryable server errors, invalid payload, validation failure, or missing coordinates.
- Confirm whether city coordinate updates from WAQI overwrite canonical city coordinates before weather enrichment or after insert.
- Capture a post-PR-27 run to verify the retry handling fix under current production behavior.

## Decision

**Partial coverage. Do not proceed directly to frontend adoption or weather backfill.**

Open-Meteo write path is working for some cities and AQI remains safe, but coverage is incomplete across active municipalities.

## Recommended next step

Create a small runtime/Data QA investigation story:

```text
Story 1.4.11 — Weather Context Missing City Diagnostics
```

Suggested scope:

- Read-only inspect active city coordinates for missing cities.
- Review latest workflow logs for weather error types, without exposing secrets.
- Add non-sensitive structured logging if current logs do not identify weather failure reason per city.
- Add tests if a deterministic bug is found.
- No backfill, no frontend, no DDL, no RPC changes until coverage is understood.

If a post-PR-27 scheduled run later reaches 9/9 Open-Meteo coverage, this document can be superseded by a new coverage evidence note and the next step may shift to RPC live apply verification or frontend adoption.

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

No secret assignment patterns were added for WAQI, AirVisual, or Supabase service-role credentials.

No service-role guidance was added for frontend/app usage.

## Validation performed

- Reviewed current pipeline README and weather-context documentation.
- Reviewed `weather_context.py`, `main.py`, and `update_city.py` read-only to confirm intended non-blocking enrichment/write behavior.
- Ran read-only Supabase evidence queries only.
- Confirmed evidence output shows latest active-city rows and coverage counts.
- Confirmed this PR is docs-only.
- Confirmed no runtime files were modified.
- Confirmed no workflow schedule files were modified.
- Confirmed no DDL was executed.
- Confirmed no backfill was performed.
- Confirmed AQI, `main_pollutant_us`, historical AQI, city identity, geolocation, and public frontend contract were not changed.

## Rollback

Revert this documentation PR.

No database rollback is required because this story is read-only evidence documentation.

No runtime, Cloudflare, workflow, RPC, frontend, AQI, or provider rollback is required.
