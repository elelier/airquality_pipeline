# Weather Context Live Coverage Evidence — MtyRespira

Status: complete RPC-aligned follow-up live coverage evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Initial review timestamp: 2026-05-26 08:20 UTC  
RPC-aligned follow-up review timestamp: 2026-05-29 14:45 UTC  
Decision type: Data QA / Architecture validation / Docs

## Summary

Initial evidence from `2026-05-26 04:55..04:57 UTC` showed partial canonical Open-Meteo coverage: 5 of 9 latest active-city readings had complete weather context. Those rows were after PR #26 and before PR #27, so they validated post-coordinate-fix behavior but not post-PR-27 retry behavior.

The follow-up evidence now uses a single RPC-aligned query pattern that:

- starts from active `cities`,
- uses `left join lateral` to keep active cities visible even if they have no reading,
- selects each city's latest reading by `reading_timestamp desc`,
- uses `created_at desc` only as a deterministic tie-breaker,
- uses the same `latest` CTE for the aggregate and detail table.

Decision: **initial evidence was partial; RPC-aligned follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

## Result summary

| Metric | Initial result | RPC-aligned follow-up result |
| --- | ---: | ---: |
| Active cities checked | 9 | 9 |
| Active cities with latest reading | 9 | 9 |
| Latest readings with AQI | 9 | 9 |
| Latest readings with `weather_provider = 'open-meteo'` | 5 | 9 |
| Latest readings with complete core weather context | 5 | 9 |
| Active cities missing canonical weather context | 4 | 0 |

## Production RPC freshness contract

The production `get_latest_air_quality_per_city` migration ranks readings per city by measurement freshness:

```sql
row_number() over (
  partition by aqr.city_id
  order by aqr.reading_timestamp desc
) as rn
```

The evidence query mirrors that public contract and adds `created_at desc` only as a tie-breaker.

## Read-only RPC-aligned evidence query

```sql
with latest as (
  select
    c.id as city_id,
    c.name as city_name,
    lr.created_at,
    lr.reading_timestamp,
    lr.aqi_us,
    lr.main_pollutant_us,
    lr.weather_provider,
    lr.weather_temperature_c,
    lr.weather_humidity_percent,
    lr.weather_wind_speed_kmh,
    lr.weather_wind_direction_deg,
    lr.weather_wind_gust_kmh,
    lr.weather_timestamp
  from public.cities c
  left join lateral (
    select
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
    from public.air_quality_readings r
    where r.city_id = c.id
    order by r.reading_timestamp desc nulls last, r.created_at desc nulls last
    limit 1
  ) lr on true
  where c.is_active = true
)
select
  count(*) as active_cities,
  count(*) filter (where reading_timestamp is not null) as active_cities_with_latest_reading,
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

RPC-aligned follow-up aggregate result:

```json
[
  {
    "active_cities": 9,
    "active_cities_with_latest_reading": 9,
    "latest_readings_with_aqi": 9,
    "latest_readings_with_open_meteo": 9,
    "latest_readings_with_complete_core_weather": 9,
    "newest_reading_timestamp": "2026-05-29 13:00:00+00",
    "oldest_latest_reading_timestamp": "2026-05-29 12:00:00+00",
    "newest_created_at": "2026-05-29 14:36:43.815507+00",
    "oldest_latest_created_at": "2026-05-29 14:34:52.144581+00"
  }
]
```

## Follow-up detail rows — 2026-05-29, RPC-aligned

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

## Review comment resolution

Resolved P2 `Reconcile the follow-up aggregate with the detail rows` by regenerating the aggregate and detail table from the same `latest` CTE and evidence window.

Resolved P2 `Count active cities from the cities table` by changing the evidence query to start from active `cities` and use `left join lateral`, so an active city with no reading would still be counted in `active_cities` but not in `active_cities_with_latest_reading`.

Previously resolved P2 `Match the evidence query to the RPC freshness order` remains addressed by the `reading_timestamp desc` selection.

## No-write guarantees

This story did not perform Supabase DDL, Supabase data mutation, backfill, runtime code changes, workflow schedule changes, RPC changes, frontend changes, AQI provider changes, or secret exposure.

No AQI, `main_pollutant_us`, historical AQI, city identity, geolocation, or public frontend contract values were changed.

## Validation performed

- Ran read-only Supabase RPC-aligned summary evidence query.
- Ran read-only Supabase RPC-aligned details query using the same `latest` CTE shape.
- Confirmed 9 active cities.
- Confirmed 9/9 latest active-city readings with AQI.
- Confirmed 9/9 latest active-city readings with `weather_provider = 'open-meteo'`.
- Confirmed 9/9 latest active-city readings with complete core weather context.
- Confirmed aggregate/detail consistency:
  - oldest latest `reading_timestamp`: `2026-05-29 12:00:00+00`
  - newest latest `reading_timestamp`: `2026-05-29 13:00:00+00`
  - oldest latest `created_at`: `2026-05-29 14:34:52.144581+00`
  - newest latest `created_at`: `2026-05-29 14:36:43.815507+00`
- Confirmed this PR remains docs-only.
- Confirmed no runtime files, workflow files, frontend files, or DB migrations were modified.

## Rollback

Revert this documentation PR.

No database, runtime, Cloudflare, workflow, RPC, frontend, AQI, or provider rollback is required.
