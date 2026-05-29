# Weather Context Live Coverage Evidence — MtyRespira

Status: complete follow-up live coverage evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Initial review timestamp: 2026-05-26 08:20 UTC  
Follow-up review timestamp: 2026-05-29 00:10 UTC  
Decision type: Data QA / Architecture validation / Docs

## Summary

This document records read-only live evidence for canonical Open-Meteo weather-context coverage after:

- PR #23: `feat: add Open-Meteo weather context write path`
- PR #26: `fix: use canonical city coordinates for weather context`
- PR #27: `fix: improve retry handling`

Initial evidence captured from latest active-city readings created around `2026-05-26 04:55..04:57 UTC` showed partial coverage: 5 of 9 latest active-city readings had canonical Open-Meteo context. Those rows were after PR #26 merged and before PR #27 merged, so they confirmed post-coordinate-fix coverage but did not validate post-PR-27 retry behavior.

Follow-up evidence captured on `2026-05-29` from latest active-city readings created around `2026-05-29 00:00..00:02 UTC` confirms complete canonical Open-Meteo coverage across all active cities.

Result summary:

| Metric | Initial result | Follow-up result |
| --- | ---: | ---: |
| Active cities checked | 9 | 9 |
| Active cities with latest reading | 9 | 9 |
| Latest readings with AQI | 9 | 9 |
| Latest readings with `weather_provider = 'open-meteo'` | 5 | 9 |
| Latest readings with complete core weather context | 5 | 9 |
| Active cities missing canonical weather context | 4 | 0 |

Decision: **initial evidence was partial; follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

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
5. Do follow-up latest rows confirm complete post-PR-27 Open-Meteo coverage?

PR merge reference:

| PR | Merge time UTC |
| --- | --- |
| PR #26 | 2026-05-25 20:11:50 UTC |
| PR #27 | 2026-05-26 07:25:52 UTC |

The initial rows captured below were created around `2026-05-26 04:55..04:57 UTC`, which is after PR #26 but before PR #27. Therefore the initial evidence confirmed post-coordinate-fix coverage, but not a post-PR-27 scheduled insert.

The follow-up rows captured below were created around `2026-05-29 00:00..00:02 UTC`, which is after PR #27. Therefore this follow-up evidence confirms complete current canonical Open-Meteo coverage for latest active-city readings.

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

Initial result:

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

## Initial coverage by city — 2026-05-26

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

Initial cities with complete canonical weather context:

- Garcia
- General Escobedo
- Guadalupe
- San Pedro Garza Garcia
- Santa Catarina

Initial cities missing canonical weather context on latest reading:

- Cadereyta Jimenez
- Ciudad Benito Juárez
- Monterrey
- San Nicolas de los Garza

## Follow-up evidence — 2026-05-29

Read-only summary result:

```json
[
  {
    "active_cities": 9,
    "active_cities_with_latest_reading": 9,
    "latest_readings_with_aqi": 9,
    "latest_readings_with_open_meteo": 9,
    "latest_readings_with_complete_core_weather": 9,
    "newest_created_at": "2026-05-29 00:02:41.016918+00",
    "oldest_latest_created_at": "2026-05-29 00:00:24.009169+00"
  }
]
```

Follow-up coverage by city:

| City | Created at UTC | Reading timestamp UTC | AQI | Main pollutant | Weather provider | Temperature C | Humidity % | Wind km/h | Wind direction deg | Gust km/h | Weather timestamp UTC | Core weather fields |
| --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Cadereyta Jimenez | 2026-05-29 00:01:14 | 2026-05-28 22:00:00 | 42 | `pm25` | `open-meteo` | 31.6 | 51 | 15.3 | 117 | 20.9 | 2026-05-29 00:00:00 | complete |
| Ciudad Benito Juárez | 2026-05-29 00:02:09 | 2026-05-28 22:00:00 | 28 | `o3` | `open-meteo` | 31.3 | 52 | 18.2 | 120 | 22.7 | 2026-05-29 00:00:00 | complete |
| Garcia | 2026-05-29 00:01:24 | 2026-05-28 22:00:00 | 47 | `o3` | `open-meteo` | 30.1 | 50 | 30.9 | 107 | 38.9 | 2026-05-29 00:00:00 | complete |
| General Escobedo | 2026-05-29 00:00:24 | 2026-05-28 22:00:00 | 55 | `pm25` | `open-meteo` | 31.1 | 50 | 20.0 | 116 | 27.4 | 2026-05-29 00:00:00 | complete |
| Guadalupe | 2026-05-29 00:02:20 | 2026-05-28 21:00:00 | 30 | `o3` | `open-meteo` | 30.8 | 52 | 18.8 | 119 | 27.0 | 2026-05-29 00:00:00 | complete |
| Monterrey | 2026-05-29 00:02:41 | 2026-05-28 22:00:00 | 45 | `pm25` | `open-meteo` | 30.5 | 51 | 19.1 | 106 | 26.6 | 2026-05-29 00:00:00 | complete |
| San Nicolas de los Garza | 2026-05-29 00:01:03 | 2026-05-28 22:00:00 | 58 | `pm25` | `open-meteo` | 31.0 | 51 | 18.4 | 116 | 27.4 | 2026-05-29 00:00:00 | complete |
| San Pedro Garza Garcia | 2026-05-29 00:02:30 | 2026-05-28 22:00:00 | 42 | `o3` | `open-meteo` | 30.2 | 51 | 21.1 | 99 | 29.5 | 2026-05-29 00:00:00 | complete |
| Santa Catarina | 2026-05-29 00:00:52 | 2026-05-28 22:00:00 | 34 | `pm25` | `open-meteo` | 29.8 | 52 | 21.3 | 95 | 32.0 | 2026-05-29 00:00:00 | complete |

Follow-up cities with complete canonical weather context:

- Cadereyta Jimenez
- Ciudad Benito Juárez
- Garcia
- General Escobedo
- Guadalupe
- Monterrey
- San Nicolas de los Garza
- San Pedro Garza Garcia
- Santa Catarina

Follow-up cities missing canonical weather context on latest reading: **none**.

## AQI safety check

All 9 active cities have a latest reading with non-null AQI in both the initial and follow-up evidence sets.

This supports the intended behavior that weather context remains separate from AQI and does not block successful AQI inserts.

No AQI rewrite or pollutant rewrite was performed by this evidence story.

## Weather context completeness

Initial evidence showed canonical Open-Meteo weather context on 5 of 9 latest active-city readings.

Follow-up evidence shows canonical Open-Meteo weather context on 9 of 9 latest active-city readings, including these core canonical fields:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_timestamp`

## Decision

**Initial evidence was partial; follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

This evidence supports treating the missing-city coverage gap observed on `2026-05-26` as superseded by the `2026-05-29` read-only follow-up snapshot.

This documentation update does not authorize frontend adoption, backfill, RPC changes, workflow changes, or runtime changes by itself. Those should remain separate stories with their own validation gates.

## Recommended next step

Use this complete-coverage evidence as an input for the next small gated story, likely one of:

```text
Story 1.4.11 — Weather Context RPC Contract Verification
```

or

```text
Story 1.4.11 — Weather Context Frontend Adoption Readiness
```

Suggested scope for the next story:

- Verify the RPC/public contract path exposes only intended weather fields.
- Confirm UI adoption remains explicit, guarded, and truthful.
- Avoid backfill, DDL, workflow, AQI provider, or frontend changes unless specifically scoped.

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

- Reviewed current PR #28 state.
- Reviewed current `docs/weather-context-live-coverage-evidence.md` from branch `docs/story-1-4-10-weather-live-coverage-evidence`.
- Ran read-only Supabase summary evidence query only.
- Ran read-only Supabase latest active-city details query only.
- Confirmed follow-up evidence output shows 9 active cities.
- Confirmed follow-up evidence output shows 9/9 latest active-city readings with AQI.
- Confirmed follow-up evidence output shows 9/9 latest active-city readings with `weather_provider = 'open-meteo'`.
- Confirmed follow-up evidence output shows 9/9 latest active-city readings with complete core weather context.
- Confirmed this PR remains docs-only.
- Confirmed no runtime files were modified.
- Confirmed no workflow schedule files were modified.
- Confirmed no DDL was executed.
- Confirmed no backfill was performed.
- Confirmed AQI, `main_pollutant_us`, historical AQI, city identity, geolocation, and public frontend contract were not changed.

## Rollback

Revert this documentation PR.

No database rollback is required because this story is read-only evidence documentation.

No runtime, Cloudflare, workflow, RPC, frontend, AQI, or provider rollback is required.
