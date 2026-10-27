drop function if exists public.get_air_quality_history_for_city(bigint, integer);

create function public.get_air_quality_history_for_city(
  p_city_id bigint,
  p_hours integer default 24
)
returns table (
  city_id bigint,
  city_name text,
  reading_timestamp timestamptz,
  aqi_us smallint,
  main_pollutant_us text,
  temperature_c real,
  humidity_percent smallint,
  weather_temperature_c real,
  weather_humidity_percent smallint,
  weather_wind_speed_kmh real,
  weather_timestamp timestamptz,
  weather_provider text
)
language sql
stable
security definer
set search_path = public
as $$
  select
    c.id as city_id,
    c.name as city_name,
    r.reading_timestamp,
    r.aqi_us,
    r.main_pollutant_us,
    r.temperature_c,
    r.humidity_percent,
    r.weather_temperature_c,
    r.weather_humidity_percent,
    r.weather_wind_speed_kmh,
    r.weather_timestamp,
    r.weather_provider
  from public.air_quality_readings r
  join public.cities c on c.id = r.city_id
  where c.id = p_city_id
    and c.is_active = true
    and r.reading_timestamp >= now() - make_interval(hours => greatest(1, least(coalesce(p_hours, 24), 24 * 31)))
  order by r.reading_timestamp asc;
$$;

grant execute on function public.get_air_quality_history_for_city(bigint, integer) to anon, authenticated;