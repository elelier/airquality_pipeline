"""Protect the public RPC contract before its optimization is deployed.

The runtime SQL behavior is also checked against live data with read-only
queries documented in docs/rpc-optimization-qa.md. These local tests guard
the migration shape without ever connecting to production.
"""

import re
from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
PRIOR_MIGRATION = MIGRATIONS / "20260525045500_update_latest_air_quality_rpc_weather_context.sql"


def optimized_migration() -> str:
    candidates = list(MIGRATIONS.glob("*_optimize_latest_air_quality_rpc.sql"))
    assert len(candidates) == 1, "Expected exactly one versioned optimization migration"
    return candidates[0].read_text(encoding="utf-8")


def normalize_sql(sql: str) -> str:
    without_comments = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"\s+", " ", without_comments.lower()).strip()


def return_contract(sql: str) -> str:
    match = re.search(r"returns\s+table\s*\((.*?)\)\s*language\s+sql", sql, re.I | re.S)
    assert match is not None, "The RPC must retain its explicit return contract"
    return normalize_sql(match.group(1))


def test_optimization_preserves_the_existing_column_types_and_order():
    current_contract = return_contract(PRIOR_MIGRATION.read_text(encoding="utf-8"))
    proposed_contract = return_contract(optimized_migration())
    assert proposed_contract == current_contract


def test_optimization_uses_per_city_index_lookup_and_deterministic_tiebreak():
    sql = normalize_sql(optimized_migration())
    assert "join lateral" in sql
    assert re.search(r"where\s+aqr\.city_id\s*=\s*c\.id", sql)
    assert re.search(
        r"order by\s+aqr\.reading_timestamp\s+desc\s*,\s*"
        r"aqr\.created_at\s+desc\s*,\s*aqr\.id\s+desc\s+limit\s+1",
        sql,
    )
    assert re.search(r"where\s+c\.is_active\s*=\s*true", sql)
    assert "row_number()" not in sql


def test_optimization_replaces_only_existing_stable_definer_function():
    sql = normalize_sql(optimized_migration())
    assert sql.startswith("create or replace function public.get_latest_air_quality_per_city()")
    assert "language sql" in sql
    assert "stable" in sql
    assert "security definer" in sql
    assert "set search_path = ''" in sql
    for unexpected in ("drop function", "drop table", "truncate", "delete from", "update public.", "insert into"):
        assert unexpected not in sql
