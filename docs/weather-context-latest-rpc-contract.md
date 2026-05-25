# Weather Context Latest RPC Contract — MtyRespira

Status: migration drafted / not applied  
Scope: `get_latest_air_quality_per_city`  
Decision type: DB contract / Data QA / Docs

## Purpose

Expose canonical weather context fields through the existing public latest-air-quality RPC so the frontend can stop reading unreliable legacy weather-like fields for current weather display.

Migration file:

```text
supabase/migrations/20260525045500_update_latest_air_quality_rpc_weather_context.sql
```

## Current problem

Production still shows unrealistic temperature because the app receives and maps legacy fields such as `temperature_c` from the existing latest RPC.

The canonical weather context columns already exist in `public.air_quality_readings`, but the latest RPC does not expose them yet.

## Contract change

The migration preserves all existing returned columns and appends these nullable fields:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_provider`
- `weather_timestamp`

The RPC intentionally does not expose `weather_source_payload`.

## Migration strategy

PostgreSQL does not allow changing an existing function return signature with `create or replace function` alone.

Because this migration appends returned columns to `get_latest_air_quality_per_city()`, it intentionally uses:

```sql
drop function if exists public.get_latest_air_quality_per_city();
create function public.get_latest_air_quality_per_city() ...
```

This is required so the updated `RETURNS TABLE` signature can be recreated cleanly.

## Compatibility

Existing columns remain in the same order before the appended weather fields:

- AQI fields remain unchanged.
- `reading_timestamp` remains AQI measurement time.
- Legacy weather-like fields remain available for backward compatibility.
- New canonical weather fields are nullable because not every row has Open-Meteo context yet.

## No-write guarantees for this PR

This PR does not perform:

- Supabase live apply,
- backfill,
- data updates,
- frontend changes,
- runtime pipeline changes,
- workflow schedule changes,
- AQI provider changes.

## Required follow-up

After this migration is reviewed and applied, the frontend should update its `CityAirQualityData` type and prefer canonical weather fields for display:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`

If canonical weather is missing, the frontend should display weather as unavailable instead of falling back to unreliable legacy fields.

## Rollback

Rollback by restoring the previous `get_latest_air_quality_per_city` function definition captured before this migration.

Rollback should not touch AQI readings, historical rows, city geolocation, or canonical weather columns.