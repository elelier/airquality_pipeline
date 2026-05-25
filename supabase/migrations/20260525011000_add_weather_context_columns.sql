-- Story 1.4.8 migration file promotion only. Not applied in this story.
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

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_temperature_c_range
  check (
    weather_temperature_c is null
    or weather_temperature_c between -50 and 60
  ) not valid;

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_humidity_percent_range
  check (
    weather_humidity_percent is null
    or weather_humidity_percent between 0 and 100
  ) not valid;

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_wind_speed_kmh_nonnegative
  check (
    weather_wind_speed_kmh is null
    or weather_wind_speed_kmh >= 0
  ) not valid;

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_wind_direction_deg_range
  check (
    weather_wind_direction_deg is null
    or weather_wind_direction_deg between 0 and 360
  ) not valid;

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_wind_gust_kmh_nonnegative
  check (
    weather_wind_gust_kmh is null
    or weather_wind_gust_kmh >= 0
  ) not valid;

alter table public.air_quality_readings
  add constraint if not exists air_quality_readings_weather_metadata_required
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
