# Draft SQL — Add canonical weather context columns

Status: Story 1.4.6 draft only / not applied  
Scope: `air_quality_readings` additive canonical weather context columns  
Decision source: `docs/weather-contract-migration-proposal.md`, Option A  

This file is intentionally stored under `docs/sql/` because this repository does not currently expose a clear `supabase/migrations`, `migrations`, or `sql` migration convention in version control.

Do not treat this file as an applied production migration. A future approved DB story must decide how this draft is promoted into the repository's migration mechanism.

## Contract notes

- `reading_timestamp` remains the AQI provider measurement time.
- `weather_timestamp` is the selected Open-Meteo hourly weather bucket.
- `weather_wind_speed_kmh` is kilometers per hour.
- Do not write km/h values into legacy fields named `*_ms`, including `wind_speed_ms`.
- `temperature_c` remains legacy provider weather-like data and is not canonical weather context.
- Weather provider failure or range validation failure must not invalidate AQI.
- AQI, `main_pollutant_us`, historical AQI, geolocation, RPC contract, and frontend runtime stay unchanged by this draft.

## Forward draft

```sql
-- Story 1.4.6 draft only. Not applied in this story.
-- Purpose: add nullable canonical weather context columns without changing AQI fields.

alter table public.air_quality_readings
  add column if not exists weather_temperature_c real,
  add column if not exists weather_humidity_percent smallint,
  add column if not exists weather_wind_speed_kmh real,
  add column if not exists weather_wind_direction_deg smallint,
  add column if not exists weather_wind_gust_kmh real,
  add column if not exists weather_provider text,
  add column if not exists weather_timestamp timestamptz,
  add column if not exists weather_source_payload jsonb,
  add column if not exists weather_backfilled_at timestamptz;

comment on column public.air_quality_readings.weather_temperature_c is
  'Canonical weather-context temperature in Celsius from the selected weather provider bucket. Legacy temperature_c is not canonical weather.';

comment on column public.air_quality_readings.weather_humidity_percent is
  'Canonical relative humidity percentage from the selected weather provider bucket. Valid range: 0..100.';

comment on column public.air_quality_readings.weather_wind_speed_kmh is
  'Canonical weather wind speed in kilometers per hour. Do not write km/h values into wind_speed_ms or any *_ms field.';

comment on column public.air_quality_readings.weather_wind_direction_deg is
  'Canonical weather wind direction in degrees from the selected weather provider bucket. Valid range: 0..360.';

comment on column public.air_quality_readings.weather_wind_gust_kmh is
  'Canonical weather wind gust in kilometers per hour from the selected weather provider bucket. Must be non-negative when present.';

comment on column public.air_quality_readings.weather_provider is
  'Canonical weather provider identifier, for example open-meteo. Required when canonical weather values are present.';

comment on column public.air_quality_readings.weather_timestamp is
  'Weather provider bucket timestamp. This is separate from reading_timestamp, which remains AQI measurement time.';

comment on column public.air_quality_readings.weather_source_payload is
  'Selected weather provider payload slice for traceability. Do not expose this payload directly in public frontend RPCs by default.';

comment on column public.air_quality_readings.weather_backfilled_at is
  'Timestamp set by a future approved weather backfill for rows enriched with canonical weather context.';

-- Existing table safety: add checks as NOT VALID first, then validate later after
-- production evidence confirms legacy rows and candidate backfill rows satisfy them.

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_temperature_c_range'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_temperature_c_range
      check (
        weather_temperature_c is null
        or weather_temperature_c between -50 and 60
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_humidity_percent_range'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_humidity_percent_range
      check (
        weather_humidity_percent is null
        or weather_humidity_percent between 0 and 100
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_wind_speed_kmh_nonnegative'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_wind_speed_kmh_nonnegative
      check (
        weather_wind_speed_kmh is null
        or weather_wind_speed_kmh >= 0
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_wind_direction_deg_range'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_wind_direction_deg_range
      check (
        weather_wind_direction_deg is null
        or weather_wind_direction_deg between 0 and 360
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_wind_gust_kmh_nonnegative'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_wind_gust_kmh_nonnegative
      check (
        weather_wind_gust_kmh is null
        or weather_wind_gust_kmh >= 0
      ) not valid;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'air_quality_readings_weather_metadata_required'
  ) then
    alter table public.air_quality_readings
      add constraint air_quality_readings_weather_metadata_required
      check (
        (
          weather_temperature_c is null
          and weather_humidity_percent is null
          and weather_wind_speed_kmh is null
          and weather_wind_direction_deg is null
          and weather_wind_gust_kmh is null
          and weather_source_payload is null
          and weather_backfilled_at is null
        )
        or (
          weather_provider is not null
          and weather_timestamp is not null
        )
      ) not valid;
  end if;
end $$;
```

## Future validation draft

Run validation only in a future explicitly approved DB story after production evidence review:

```sql
-- Draft only. Validate each constraint separately in a controlled future DB story.

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_temperature_c_range;

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_humidity_percent_range;

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_wind_speed_kmh_nonnegative;

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_wind_direction_deg_range;

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_wind_gust_kmh_nonnegative;

alter table public.air_quality_readings
  validate constraint air_quality_readings_weather_metadata_required;
```

## Conceptual rollback draft

Rollback must be coordinated with RPC/frontend consumers if these columns are ever exposed. Do not drop canonical weather columns after a consumer depends on them without first removing that dependency.

```sql
-- Story 1.4.6 rollback draft only. Not used in this story.

alter table public.air_quality_readings
  drop constraint if exists air_quality_readings_weather_metadata_required,
  drop constraint if exists air_quality_readings_weather_wind_gust_kmh_nonnegative,
  drop constraint if exists air_quality_readings_weather_wind_direction_deg_range,
  drop constraint if exists air_quality_readings_weather_wind_speed_kmh_nonnegative,
  drop constraint if exists air_quality_readings_weather_humidity_percent_range,
  drop constraint if exists air_quality_readings_weather_temperature_c_range;

alter table public.air_quality_readings
  drop column if exists weather_backfilled_at,
  drop column if exists weather_source_payload,
  drop column if exists weather_timestamp,
  drop column if exists weather_provider,
  drop column if exists weather_wind_gust_kmh,
  drop column if exists weather_wind_direction_deg,
  drop column if exists weather_wind_speed_kmh,
  drop column if exists weather_humidity_percent,
  drop column if exists weather_temperature_c;
```
