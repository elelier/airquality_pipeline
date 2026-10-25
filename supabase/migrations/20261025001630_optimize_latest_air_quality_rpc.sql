-- Issue #34: keep the public RPC contract while avoiding a window over all
-- historical readings. For equal observation timestamps, prefer the newest
-- ingested row (and id as a stable final tiebreaker). This does not change
-- the measurement timestamp or imply that the AQI itself is fresh.
--
-- Forward-only until separately approved for Supabase production.
-- CREATE OR REPLACE preserves the existing function identity and EXECUTE ACLs.
create or replace function public.get_latest_air_quality_per_city()
returns table(
  city_id bigint,
  city_name text,
  api_name text,
  latitude double precision,
  longitude double precision,
  reading_timestamp timestamp with time zone,
  aqi_us smallint,
  main_pollutant_us text,
  temperature_c real,
  humidity_percent smallint,
  wind_speed_ms real,
  wind_direction_deg smallint,
  weather_icon text,
  last_successful_update_at timestamp with time zone,
  weather_temperature_c real,
  weather_humidity_percent smallint,
  weather_wind_speed_kmh real,
  weather_wind_direction_deg smallint,
  weather_wind_gust_kmh real,
  weather_provider text,
  weather_timestamp timestamp with time zone
)
language sql
stable
security definer
set search_path = ''
as $function$
  select
    c.id as city_id,
    c.name as city_name,
    c.api_name,
    c.latitude,
    c.longitude,
    latest.reading_timestamp,
    latest.aqi_us,
    latest.main_pollutant_us,
    latest.temperature_c,
    latest.humidity_percent,
    latest.wind_speed_ms,
    latest.wind_direction_deg,
    latest.weather_icon,
    c.last_successful_update_at,
    latest.weather_temperature_c,
    latest.weather_humidity_percent,
    latest.weather_wind_speed_kmh,
    latest.weather_wind_direction_deg,
    latest.weather_wind_gust_kmh,
    latest.weather_provider,
    latest.weather_timestamp
  from public.cities c
  join lateral (
    select aqr.*
    from public.air_quality_readings aqr
    where aqr.city_id = c.id
    order by aqr.reading_timestamp desc, aqr.created_at desc, aqr.id desc
    limit 1
  ) latest on true
  where c.is_active = true
  order by c.name asc;
$function$;
