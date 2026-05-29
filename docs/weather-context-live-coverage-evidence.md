# Weather Context Live Coverage Evidence — MtyRespira

Status: complete RPC-output follow-up live coverage evidence  
Scope: `elelier/airquality_pipeline`  
Target DB: `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`)  
Initial review timestamp: 2026-05-26 08:20 UTC  
RPC-output follow-up review timestamp: 2026-05-29 15:35 UTC  
Decision type: Data QA / Architecture validation / Docs

## Summary

Initial evidence from `2026-05-26 04:55..04:57 UTC` showed partial canonical Open-Meteo coverage: 5 of 9 latest active-city readings had complete weather context. Those rows were after PR #26 and before PR #27, so they validated post-coordinate-fix behavior but not post-PR-27 retry behavior.

Follow-up evidence now uses the actual production public contract: `public.get_latest_air_quality_per_city()`.

This avoids selecting rows with a documentary approximation of the RPC order. A prior evidence query added `created_at desc` and `NULLS LAST` as deterministic tie-breakers, but the RPC itself ranks rows only by `reading_timestamp desc`. For RPC/frontend readiness evidence, the safest docs-only validation is to inspect the RPC output directly.

Decision: **initial evidence was partial; direct RPC-output follow-up evidence confirms complete 9/9 canonical Open-Meteo coverage.**

## Result summary

| Metric | Initial result | Direct RPC-output follow-up result |
| --- | ---: | ---: |
| Active cities checked | 9 | 9 |
| RPC rows returned | n/a | 9 |
| Rows with AQI | 9 | 9 |
| Rows with `weather_provider = 'open-meteo'` | 5 | 9 |
| Rows with complete core weather context | 5 | 9 |
| Active/RPC row count mismatch | n/a | 0 |

## Production RPC freshness contract

The production `get_latest_air_quality_per_city` migration ranks readings per city by measurement freshness:

```sql
row_number() over (
  partition by aqr.city_id
  order by aqr.reading_timestamp desc
) as rn
```

Because the frontend consumes this RPC, this evidence validates the RPC output directly instead of using a separate latest-row query with additional tie-breakers.

## Read-only direct RPC-output summary query

```sql
with rpc_rows as (
  select *
  from public.get_latest_air_quality_per_city()
), active_cities as (
  select count(*) as active_cities
  from public.cities
  where is_active = true
)
select
  ac.active_cities,
  count(*) as rpc_rows,
  count(*) filter (where aqi_us is not null) as rpc_rows_with_aqi,
  count(*) filter (where weather_provider = 'open-meteo') as rpc_rows_with_open_meteo,
  count(*) filter (
    where weather_provider = 'open-meteo'
      and weather_temperature_c is not null
      and weather_humidity_percent is not null
      and weather_wind_speed_kmh is not null
      and weather_timestamp is not null
  ) as rpc_rows_with_complete_core_weather,
  max(reading_timestamp) as newest_reading_timestamp,
  min(reading_timestamp) as oldest_latest_reading_timestamp
from rpc_rows rr
cross join active_cities ac
group by ac.active_cities;
```

Direct RPC-output follow-up aggregate result:

```json
[
  {
    "active_cities": 9,
    "rpc_rows": 9,
    "rpc_rows_with_aqi": 9,
    "rpc_rows_with_open_meteo": 9,
    "rpc_rows_with_complete_core_weather": 9,
    "newest_reading_timestamp": "2026-05-29 13:00:00+00",
    "oldest_latest_reading_timestamp": "2026-05-29 12:00:00+00"
  }
]
```

## Direct RPC-output detail rows — 2026-05-29

```sql
select
  city_name,
  reading_timestamp,
  aqi_us,
  main_pollutant_us,
  weather_provider,
  weather_temperature_c,
  weather_humidity_percent,
  weather_wind_speed_kmh,
  weather_wind_direction_deg,
  weather_wind_gust_kmh,
  weather_timestamp
from public.get_latest_air_quality_per_city()
order by city_name asc;
```

| City | Reading timestamp UTC | AQI | Main pollutant | Weather provider | Temperature C | Humidity % | Wind km/h | Wind direction deg | Gust km/h | Weather timestamp UTC | Core weather fields |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Cadereyta Jimenez | 2026-05-29 12:00:00 | 21 | `pm25` | `open-meteo` | 25.4 | 81 | 4.9 | 107 | 10.8 | 2026-05-29 14:30:00 | complete |
| Ciudad Benito Juárez | 2026-05-29 12:00:00 | 21 | `pm10` | `open-meteo` | 25.2 | 84 | 4.7 | 113 | 11.2 | 2026-05-29 14:30:00 | complete |
| Garcia | 2026-05-29 12:00:00 | 52 | `pm25` | `open-meteo` | 25.0 | 76 | 4.1 | 135 | 4.3 | 2026-05-29 14:30:00 | complete |
| General Escobedo | 2026-05-29 12:00:00 | 56 | `pm25` | `open-meteo` | 24.3 | 86 | 4.2 | 70 | 9.0 | 2026-05-29 14:30:00 | complete |
| Guadalupe | 2026-05-29 12:00:00 | 22 | `pm10` | `open-meteo` | 25.4 | 82 | 4.7 | 81 | 10.8 | 2026-05-29 14:30:00 | complete |
| Monterrey | 2026-05-29 12:00:00 | 49 | `pm25` | `open-meteo` | 24.6 | 83 | 2.9 | 30 | 6.5 | 2026-05-29 14:30:00 | complete |
| San Nicolas de los Garza | 2026-05-29 13:00:00 | 54 | `pm25` | `open-meteo` | 24.7 | 84 | 2.7 | 23 | 8.6 | 2026-05-29 14:30:00 | complete |
| San Pedro Garza Garcia | 2026-05-29 12:00:00 | 16 | `o3` | `open-meteo` | 25.0 | 78 | 2.5 | 82 | 3.6 | 2026-05-29 14:30:00 | complete |
| Santa Catarina | 2026-05-29 13:00:00 | 42 | `pm25` | `open-meteo` | 25.3 | 80 | 7.6 | 177 | 7.6 | 2026-05-29 14:30:00 | complete |

Direct RPC-output rows missing canonical weather context: **none**.

## Duplicate latest timestamp check

The P1 review noted that duplicate provider timestamps could make a documentary query with tie-breakers select a different row from the RPC. Current evidence therefore uses the RPC output directly.

As an additional read-only diagnostic, the current dataset was checked for duplicate rows at recent latest timestamps. No duplicate rows were found for active-city readings at or after `2026-05-29 12:00:00+00`.

## Review comment resolution

Resolved P1 `Preserve the RPC's actual row ordering` by removing documentary reliance on `created_at desc` / `NULLS LAST` tie-breakers for readiness evidence and validating the output of `public.get_latest_air_quality_per_city()` directly.

Previously resolved P2 comments remain addressed:

- Initial timing is documented as post-PR #26 / pre-PR #27.
- The evidence now validates the public RPC output directly.
- Active cities are counted from `public.cities` and compared against RPC row count.
- Aggregate and detail rows are both generated from the direct RPC output.

## No-write guarantees

This story did not perform Supabase DDL, Supabase data mutation, backfill, runtime code changes, workflow schedule changes, RPC changes, frontend changes, AQI provider changes, or secret exposure.

No AQI, `main_pollutant_us`, historical AQI, city identity, geolocation, or public frontend contract values were changed.

## Validation performed

- Reviewed current PR #28 state.
- Reviewed the P1 review thread.
- Reviewed the migration defining `get_latest_air_quality_per_city` and confirmed the RPC freshness order is `reading_timestamp desc` only.
- Ran read-only `public.get_latest_air_quality_per_city()` aggregate evidence query.
- Ran read-only `public.get_latest_air_quality_per_city()` detail evidence query.
- Ran read-only active-city count query.
- Ran read-only recent duplicate timestamp diagnostic.
- Confirmed 9 active cities and 9 RPC rows.
- Confirmed 9/9 RPC rows with AQI.
- Confirmed 9/9 RPC rows with `weather_provider = 'open-meteo'`.
- Confirmed 9/9 RPC rows with complete core weather context.
- Confirmed this PR remains docs-only.
- Confirmed no runtime files, workflow files, frontend files, or DB migrations were modified.

## Rollback

Revert this documentation PR.

No database, runtime, Cloudflare, workflow, RPC, frontend, AQI, or provider rollback is required.
