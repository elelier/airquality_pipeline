# Weather History Backfill Runbook

Status: controlled/manual utility.

## Goal

Backfill canonical Open-Meteo weather fields for existing `air_quality_readings` rows so historical charts can show real temperature, humidity, and wind series instead of gaps.

This utility updates only canonical weather columns:

- `weather_temperature_c`
- `weather_humidity_percent`
- `weather_wind_speed_kmh`
- `weather_wind_direction_deg`
- `weather_wind_gust_kmh`
- `weather_timestamp`
- `weather_provider`

## Non-goals / forbidden changes

The backfill must not update:

- `aqi_us`
- `main_pollutant_us`
- `temperature_c`
- `humidity_percent`
- `wind_speed_ms`
- `wind_direction_deg`
- `raw_api_response`
- `city_id`
- coordinates/geolocation

## Default safety behavior

`scripts/weather_history_backfill.py` runs in dry-run mode by default.

Dry-run example:

```bash
python scripts/weather_history_backfill.py --days 90 --batch-size 100
```

Single-city dry-run example:

```bash
python scripts/weather_history_backfill.py --city-id 9 --days 90 --batch-size 100
```

Apply mode requires the explicit `--apply` flag:

```bash
python scripts/weather_history_backfill.py --city-id 9 --days 90 --batch-size 100 --apply
```

## Recommended rollout

1. Run dry-run for Monterrey only:
   ```bash
   python scripts/weather_history_backfill.py --city-id 9 --days 90 --batch-size 100
   ```
2. Review report summary:
   - `candidate_rows`
   - `matched_rows`
   - `unmatched_rows`
   - `invalid_weather_rows`
   - `fetch_errors`
3. Apply Monterrey only if dry-run has no fetch/range errors:
   ```bash
   python scripts/weather_history_backfill.py --city-id 9 --days 90 --batch-size 100 --apply
   ```
4. Re-run dry-run/apply per city or with all active cities in small batches.
5. Validate public app chart behavior after Cloudflare deploy.

## Matching rule

Open-Meteo Archive returns hourly weather buckets. Each AQI reading is matched to the nearest Open-Meteo hour within 30 minutes.

Rows outside this threshold are left unchanged and reported as `unmatched_rows`.

## Environment

Requires existing pipeline secrets/config:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

The service role remains pipeline-only. Do not use it in frontend/app code.

## Rollback

Rollback clears only canonical weather columns for the intended range/city. Example for Monterrey last 90 days:

```sql
update public.air_quality_readings
set
  weather_temperature_c = null,
  weather_humidity_percent = null,
  weather_wind_speed_kmh = null,
  weather_wind_direction_deg = null,
  weather_wind_gust_kmh = null,
  weather_timestamp = null,
  weather_provider = null
where city_id = 9
  and reading_timestamp >= now() - interval '90 days';
```

Do not clear AQI, pollutant, legacy weather, raw payload, or city identity fields.

## Evidence query

```sql
select
  c.id as city_id,
  c.name as city_name,
  count(*) filter (where r.reading_timestamp >= now() - interval '90 days') as rows_90d,
  count(*) filter (
    where r.reading_timestamp >= now() - interval '90 days'
      and r.weather_temperature_c is not null
      and r.weather_humidity_percent is not null
      and r.weather_wind_speed_kmh is not null
  ) as rows_90d_with_core_weather,
  min(r.weather_temperature_c) as min_weather_temperature_c,
  max(r.weather_temperature_c) as max_weather_temperature_c
from public.cities c
left join public.air_quality_readings r on r.city_id = c.id
where c.is_active = true
group by c.id, c.name
order by c.id;
```
