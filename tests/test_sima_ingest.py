from datetime import datetime, timezone

from scripts.sima_ingest import parse_observations


def test_parses_named_observations_and_preserves_local_measurement_time():
    html = """<script>var arrayIMKTodo11 = [
      {"Estacion":"centro","contaminante":"O3","HrAveData":22,"concentracion":"24","Date":"2026-11-19 20:00"},
      {"Estacion":"sureste","contaminante":"PM25","HrAveData":0,"concentracion":"0","Date":"2026-11-19 20:00"},
      {"Estacion":"norte","contaminante":"PM25","HrAveData":null,"concentracion":null,"Date":"2026-11-19 20:00"},
      {"Estacion":"sur","contaminante":"O3","HrAveData":22,"concentracion":"24","Date":"2026-10-19 20:00"}
    ] </script>"""
    rows = parse_observations(html, datetime(2026, 11, 20, 3, tzinfo=timezone.utc))
    assert [(r["station_id"], r["observed_at"], r["concentration"], r["unit"]) for r in rows] == [
        ("centro", "2026-11-20T02:00:00+00:00", 24, "ppb"),
        ("sureste", "2026-11-20T02:00:00+00:00", 0, "µg/m³"),
    ]
