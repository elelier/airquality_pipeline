drop function if exists public.get_latest_air_quality_per_city();

create function public.get_latest_air_quality_per_city()
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
as $function$
  with ranked_readings as (
    select
      aqr.city_id,
      c.name as city_name,
      c.api_name as api_name,
      c.latitude,
      c.longitude,
      c.last_successful_update_at,
      aqr.reading_timestamp,
      aqr.aqi_us,
      aqr.main_pollutant_us,
      aqr.temperature_c,
      aqr.humidity_percent,
      aqr.wind_speed_ms,
      aqr.wind_direction_deg,
      aqr.weather_icon,
      aqr.weather_temperature_c,
      aqr.weather_humidity_percent,
      aqr.weather_wind_speed_kmh,
      aqr.weather_wind_direction_deg,
      aqr.weather_wind_gust_kmh,
      aqr.weather_provider,
      aqr.weather_timestamp,
      row_number() over (
        partition by aqr.city_id
        order by aqr.reading_timestamp desc
      ) as rn
    from public.air_quality_readings aqr
    join public.cities c on aqr.city_id = c.id
    where c.is_active = true
  )
  select
    rr.city_id,
    rr.city_name,
    rr.api_name,
    rr.latitude,
    rr.longitude,
    rr.reading_timestamp,
    rr.aqi_us,
    rr.main_pollutant_us,
    rr.temperature_c,
    rr.humidity_percent,
    rr.wind_speed_ms,
    rr.wind_direction_deg,
    rr.weather_icon,
    rr.last_successful_update_at,
    rr.weather_temperature_c,
    rr.weather_humidity_percent,
    rr.weather_wind_speed_kmh,
    rr.weather_wind_direction_deg,
    rr.weather_wind_gust_kmh,
    rr.weather_provider,
    rr.weather_timestamp
  from ranked_readings rr
  where rr.rn = 1
  order by rr.city_name asc;
$function$;
