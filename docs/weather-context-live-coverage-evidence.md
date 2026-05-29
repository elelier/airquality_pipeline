# Weather Context Live Coverage Evidence — MtyRespira

Status: complete RPC-aligned follow-up live coverage evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Initial review timestamp: 2026-05-26 08:20 UTC  
RPC-aligned follow-up review timestamp: 2026-05-29 14:45 UTC  
Decision type: Data QA / Architecture validation / Docs

## Summary

This document records read-only live evidence for canonical Open-Meteo weather-context coverage after:

- PR #23: `feat: add Open-Meteo weather context write path`
- PR #26: `fix: use canonical city coordinates for weather context`
- PR #27: `fix: improve retry handling`

Initial evidence captured from latest active-city readings created around `2026-05-26 04:55..04:57 UTC` showed partial coverage: 5 of 9 latest active-city readings had canonical Open-Meteo context. Those rows were after PR #26 merged and before PR #27 merged, so they confirmed post-coordinate-fix coverage but did not validate post-PR-27 retry behavior.

A follow-up on `2026-05-29` originally used insertion order. Review feedback correctly noted that evidence intended to support RPC/frontend readiness must mirror the production `get_latest_air_quality_per_city` freshness order.

This document now uses RPC-aligned evidence: latest rows are selected by `reading_timestamp desc`, with `created_at desc` only as a deterministic tie-breaker for evidence stability. The RPC-aligned follow-up confirms complete canonical Open-Meteo coverage across all active cities.

Result summary:

| Metric | Initial result | RPC-aligned follow-up result |
| --- | ---: | ---: |
| Active cities checked | 9 | 9 |
| Active cities with latest reading | 9 | 9 |
| Latest readings with AQI | 9 | 9 |
| Latest readings with `weather_provider = 'open-meteo'` | 5 | 9 |
| Latest readings with complete core weather context | 5 | 9 |
| Active cities missing canonical weather context | 4 | 0 |

Decision: **initial evidence was partial; RPC-aligned follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

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

## Production RPC freshness contract

The production `get_latest_air_quality_per_city` migration ranks readings per city by measurement freshness:

```sql
row_number() over (
  partition by aqr.city_id
  order by aqr.reading_timestamp desc
) as rn
```

Because the frontend consumes this RPC, coverage evidence must validate the same row set the public contract exposes. The evidence query therefore selects one latest row per active city using `reading_timestamp desc`; `created_at desc` is used only as a deterministic tie-breaker for the evidence query.

## Read-only RPC-aligned summary query

```sql
with latest as (
  select *
  from (
    select
      c.id as city_id,
      c.name as city_name,
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
      r.weather_timestamp,
      row_number() over (
        partition by r.city_id
        order by r.reading_timestamp desc, r.created_at desc
      ) as rn
    from public.air_quality_readings r
    join public.cities c on r.city_id = c.id
    where c.is_active = true
  ) ranked
  where rn = 1
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
  max(reading_timestamp) as newest_reading_timestamp,
  min(reading_timestamp) as oldest_latest_reading_timestamp,
  max(created_at) as newest_created_at,
  min(created_at) as oldest_latest_created_at
from latest;
```

RPC-aligned follow-up result:

```json
[
  {
    "active_cities": 9,
    "active_cities_with_latest_reading": 9,
    "latest_readings_with_aqi": 9,
    "latest_readings_with_open_meteo": 9,
    "latest_readings_with_complete_core_weather": 9,
    "newest_reading_timestamp": "2026-05-29 13:00:00+00",
    "oldest_latest_reading_timestamp": "2026-05-29 08:00:00+00",
    "newest_created_at": "2026-05-29 14:36:18.822865+00",
    "oldest_latest_created_at": "2026-05-29 11:20:50.860009+00"
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

## Follow-up evidence — 2026-05-29, RPC-aligned

Follow-up coverage by city using `reading_timestamp desc`, with `created_at desc` as tie-breaker:

| City | Created at UTC | Reading timestamp UTC | AQI | Main pollutant | Weather provider | Temperature C | Humidity % | Wind km/h | Wind direction deg | Gust km/h | Weather timestamp UTC | Core weather fields |
| --- | --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Cadereyta Jimenez | 2026-05-29 14:36:43 | 2026-05-29 12:00:00 | 21 | `pm25` | `open-meteo` | 25.4 | 81 | 4.9 | 107 | 10.8 | 2026-05-29 14:30:00 | complete |
| Ciudad Benito Juárez | 2026-05-29 14:35:02 | 2026-05-29 12:00:00 | 21 | `pm10` | `open-meteo` | 25.2 | 84 | 4.7 | 113 | 11.2 | 2026-05-29 14:30:00 | complete |
| Garcia | 2026-05-29 14:34:52 | 2026-05-29 12:00:00 | 52 | `pm25` | `open-meteo` | 25.0 | 76 | 4.1 | 135 | 4.3 | 2026-05-29 14:30:00 | complete |
| General Escobedo | 2026-05-29 14:35:57 | 2026-05-29 12:00:00 | 56 | `pm25` | `open-meteo` | 24.3 | 86 | 4.2 | 70 | 9.0 | 2026-05-29 14:30:00 | complete |
| Guadalupe | 2026-05-29 14:35:12 | 2026-05-29 12:00:00 | 22 | `pm10` | `open-meteo` | 25.4 | 82 | 4.7 | 81 | 10.8 | 2026-05-29 14:30:00 | complete |
| Monterrey | 2026-05-29 14:35:33 | 2026-05-29 12:00:00 | 49 | `pm25` | `open-meteo` | 24.6 | 83 | 2.9 | 30 | 6.5 | 2026-05-29 14:30:00 | complete |
| San Nicolas de los Garza | 2026-05-29 14:36:18 | 2026-05-29 13:00:00 | 54 | `pm25` | `open-meteo` | 24.7 | 84 | 2.7 | 23 | 8.6 | 2026-05-29 14:30:00 | complete |
| San Pedro Garza Garcia | 2026-05-29 14:35:23 | 2026-05-29 12:00:00 | 16 | `o3` | `open-meteo` | 25.0 | 78 | 2.5 | 82 | 3.6 | 2026-05-29 14:30:00 | complete |
| Santa Catarina | 2026-05-29 14:36:08 | 2026-05-29 13:00:00 | 42 | `pm25` | `open-meteo` | 25.3 | 80 | 7.6 | 177 | 7.6 | 2026-05-29 14:30:00 | complete |

RPC-aligned follow-up cities missing canonical weather context on latest reading: **none**.

## AQI safety check

All 9 active cities have a latest reading with non-null AQI in both the initial and RPC-aligned follow-up evidence sets.

This supports the intended behavior that weather context remains separate from AQI and does not block successful AQI inserts.

No AQI rewrite or pollutant rewrite was performed by this evidence story.

## Weather context completeness

Initial evidence showed canonical Open-Meteo weather context on 5 of 9 latest active-city readings.

RPC-aligned follow-up evidence shows canonical Open-Meteo weather context on 9 of 9 latest active-city readings, including these core canonical fields:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_timestamp`

## Decision

**Initial evidence was partial; RPC-aligned follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

This evidence supports treating the missing-city coverage gap observed on `2026-05-26` as superseded by the `2026-05-29` read-only RPC-aligned follow-up snapshot.

This documentation update does not authorize frontend adoption, backfill, RPC changes, workflow changes, or runtime changes by itself. Those should remain separate stories with their own validation gates.

## Review comment resolution

Resolved P2 `Match the evidence query to the RPC freshness order` by changing the evidence selection from `created_at desc` to an RPC-aligned `reading_timestamp desc` order, with `created_at desc` retained only as a deterministic tie-breaker for evidence reproducibility.

The recaptured read-only evidence still confirms 9/9 canonical Open-Meteo coverage for the rows the frontend/RPC contract would expose.

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
- Reviewed the migration defining `get_latest_air_quality_per_city` and confirmed the RPC freshness order is `reading_timestamp desc`.
- Updated the evidence query to mirror the RPC freshness order.
- Ran read-only Supabase RPC-aligned summary evidence query only.
- Ran read-only Supabase RPC-aligned latest active-city details query only.
- Confirmed follow-up evidence output shows 9 active cities.
- Confirmed follow-up evidence output shows 9/9 RPC-selected latest active-city readings with AQI.
- Confirmed follow-up evidence output shows 9/9 RPC-selected latest active-city readings with `weather_provider = 'open-meteo'`.
- Confirmed follow-up evidence output shows 9/9 RPC-selected latest active-city readings with complete core weather context.
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
