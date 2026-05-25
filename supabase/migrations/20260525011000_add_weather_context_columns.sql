-- Story 1.4.8 migration file promotion only. Not applied in this story.

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

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_temperature_c_range
  check (weather_temperature_c is null or weather_temperature_c between -50 and 60)
  not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_humidity_percent_range
  check (weather_humidity_percent is null or weather_humidity_percent between 0 and 100)
  not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_speed_kmh_nonnegative
  check (weather_wind_speed_kmh is null or weather_wind_speed_kmh >= 0)
  not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_direction_deg_range
  check (weather_wind_direction_deg is null or weather_wind_direction_deg between 0 and 360)
  not valid;

alter table public.air_quality_readings
  add constraint air_quality_readings_weather_wind_gust_kmh_nonnegative
  check (weather_wind_gust_kmh is null or weather_wind_gust_kmh >= 0)
  not valid;

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
    or (weather_provider is not null and weather_timestamp is not null)
  )
  not valid;
