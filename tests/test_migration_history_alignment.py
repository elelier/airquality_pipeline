"""Guard immutable migrations already applied to the environmental Supabase DB.

Source: supabase_migrations.schema_migrations in project xjekikweaiddfwjjaqbd,
verified read-only on 2026-10-27. New forward migrations are allowed.
"""

import hashlib
from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"

APPLIED_SNAPSHOT_MD5 = {
    "20260525013516_add_weather_context_columns.sql": "c2b72fd68c1a175c8f8555dae9d6b493",
    "20260525125515_update_latest_air_quality_rpc_weather_context.sql": "f14831e4684911daefb87a6b1f00b99e",
    "20260530200307_recreate_historical_weather_rpc_canonical_fields.sql": "879dd9cdda890ff6d529ae0ea7720b18",
    "20260530200420_recreate_daily_weather_rpc_canonical_fields.sql": "174fd37df904c4648a08b80e03b283be",
}

UNAPPLIED_LEGACY_NAMES = (
    "20260525011000_add_weather_context_columns.sql",
    "20260525045500_update_latest_air_quality_rpc_weather_context.sql",
)


def test_applied_supabase_migrations_match_verified_remote_sql():
    for filename, expected_md5 in APPLIED_SNAPSHOT_MD5.items():
        sql = (MIGRATIONS / filename).read_bytes()
        assert hashlib.md5(sql, usedforsecurity=False).hexdigest() == expected_md5, filename


def test_unapplied_legacy_timestamp_aliases_are_not_in_executable_history():
    for filename in UNAPPLIED_LEGACY_NAMES:
        assert not (MIGRATIONS / filename).exists(), filename
