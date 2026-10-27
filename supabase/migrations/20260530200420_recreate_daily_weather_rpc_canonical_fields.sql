drop function if exists public.get_daily_air_quality_history_for_city(bigint, integer);

create function public.get_daily_air_quality_history_for_city(
  p_city_id bigint,
  p_days integer default 183
)
returns table (
  city_id bigint,
  city_name text,
  reading_date date,
  avg_aqi_us numeric,
  max_aqi_us smallint,
  avg_temperature_c numeric,
  avg_humidity_percent numeric,
  avg_weather_temperature_c numeric,
  avg_weather_humidity_percent numeric,
  avg_weather_wind_speed_kmh numeric,
  dominant_pollutant_us text,
  reading_count bigint,
  weather_reading_count bigint
)
language sql
stable
security definer
set search_path = public
as $$
  with base as (
    select
      c.id as city_id,
      c.name as city_name,
      r.reading_timestamp::date as reading_date,
      r.aqi_us,
      r.main_pollutant_us,
      r.temperature_c,
      r.humidity_percent,
      r.weather_temperature_c,
      r.weather_humidity_percent,
      r.weather_wind_speed_kmh
    from public.air_quality_readings r
    join public.cities c on c.id = r.city_id
    where c.id = p_city_id
      and c.is_active = true
      and r.reading_timestamp >= now() - make_interval(days => greatest(1, least(coalesce(p_days, 183), 366)))
  ), pollutant_counts as (
    select
      city_id,
      reading_date,
      main_pollutant_us,
      count(*) as pollutant_count,
      row_number() over (
        partition by city_id, reading_date
        order by count(*) desc, main_pollutant_us asc
      ) as pollutant_rank
    from base
    where main_pollutant_us is not null
    group by city_id, reading_date, main_pollutant_us
  )
  select
    b.city_id,
    max(b.city_name) as city_name,
    b.reading_date,
    round(avg(b.aqi_us)::numeric, 1) as avg_aqi_us,
    max(b.aqi_us) as max_aqi_us,
    round(avg(b.temperature_c)::numeric, 1) as avg_temperature_c,
    round(avg(b.humidity_percent)::numeric, 1) as avg_humidity_percent,
    round(avg(b.weather_temperature_c)::numeric, 1) as avg_weather_temperature_c,
    round(avg(b.weather_humidity_percent)::numeric, 1) as avg_weather_humidity_percent,
    round(avg(b.weather_wind_speed_kmh)::numeric, 1) as avg_weather_wind_speed_kmh,
    max(pc.main_pollutant_us) filter (where pc.pollutant_rank = 1) as dominant_pollutant_us,
    count(*) as reading_count,
    count(*) filter (where b.weather_temperature_c is not null or b.weather_humidity_percent is not null or b.weather_wind_speed_kmh is not null) as weather_reading_count
  from base b
  left join pollutant_counts pc
    on pc.city_id = b.city_id
   and pc.reading_date = b.reading_date
   and pc.pollutant_rank = 1
  group by b.city_id, b.reading_date
  order by b.reading_date asc;
$$;

grant execute on function public.get_daily_air_quality_history_for_city(bigint, integer) to anon, authenticated;