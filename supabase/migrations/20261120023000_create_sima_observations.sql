create table public.sima_observations (
    station_id text not null check (station_id ~ '^[a-z0-9]+$'),
    station_name text not null,
    municipality text not null,
    observed_at timestamptz not null,
    pollutant text not null check (pollutant in ('PM2.5', 'PM10', 'O3', 'NO2', 'SO2', 'CO')),
    concentration numeric not null check (concentration >= 0 and concentration < 'Infinity'::numeric),
    unit text not null check (unit in ('µg/m³', 'ppb', 'ppm')),
    primary key (station_id, observed_at)
);

create index sima_observations_recent_idx on public.sima_observations (observed_at desc);

alter table public.sima_observations enable row level security;
revoke all on public.sima_observations from anon, authenticated;
grant select on public.sima_observations to anon, authenticated;
grant select, insert, update on public.sima_observations to service_role;
create policy "Public read of SIMA observations"
    on public.sima_observations for select to anon, authenticated using (true);
