"""Operational smoke check for get_latest_air_quality_per_city.

Read-only CLI intended for manual GitHub Actions runs and local incident checks.
It validates the public RPC contract shape and freshness without writing to Supabase.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from supabase_client import get_supabase_client

RPC_NAME = "get_latest_air_quality_per_city"
EXPECTED_COLUMNS = {
    "city_id",
    "city_name",
    "api_name",
    "latitude",
    "longitude",
    "reading_timestamp",
    "aqi_us",
    "main_pollutant_us",
    "temperature_c",
    "humidity_percent",
    "wind_speed_ms",
    "wind_direction_deg",
    "weather_icon",
    "last_successful_update_at",
}
DEFAULT_EXPECTED_ACTIVE_CITY_IDS = {1, 4, 5, 6, 7, 9, 11, 12, 13}
DEFAULT_WARN_HOURS = 2.0
DEFAULT_FAIL_HOURS = 6.0


@dataclass(frozen=True)
class FreshnessThresholds:
    warn_hours: float = DEFAULT_WARN_HOURS
    fail_hours: float = DEFAULT_FAIL_HOURS


def parse_expected_city_ids(value: str | None) -> set[int]:
    if not value:
        return set(DEFAULT_EXPECTED_ACTIVE_CITY_IDS)

    expected: set[int] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        expected.add(int(item))
    return expected


def parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")

    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include UTC offset")
    return parsed.astimezone(timezone.utc)


def _freshness_hours(reading_timestamp: datetime, now_utc: datetime) -> float:
    return (now_utc - reading_timestamp).total_seconds() / 3600


def fetch_rpc_rows() -> list[dict[str, Any]]:
    response = get_supabase_client().rpc(RPC_NAME).execute()
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        raise ValueError("Supabase RPC response is not an array")
    return data


def evaluate_rpc_contract(
    rows: Any,
    *,
    expected_city_ids: set[int] | None = None,
    thresholds: FreshnessThresholds | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    expected_ids = expected_city_ids or set(DEFAULT_EXPECTED_ACTIVE_CITY_IDS)
    freshness_thresholds = thresholds or FreshnessThresholds()
    checked_at = now_utc or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)

    errors: list[str] = []
    warnings: list[str] = []
    city_ids: list[int] = []
    freshness_by_city: dict[str, float] = {}

    if not isinstance(rows, list):
        return {
            "status": "unhealthy",
            "rpc": RPC_NAME,
            "checked_at_utc": checked_at.isoformat(),
            "expected_city_ids": sorted(expected_ids),
            "returned_city_ids": [],
            "errors": ["RPC response must be an array"],
            "warnings": [],
            "freshness_hours_by_city_id": {},
        }

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row[{index}] is not an object")
            continue

        missing_columns = sorted(EXPECTED_COLUMNS - set(row.keys()))
        if missing_columns:
            errors.append(f"row[{index}] missing columns: {', '.join(missing_columns)}")

        city_id = row.get("city_id")
        if isinstance(city_id, bool) or not isinstance(city_id, int):
            errors.append(f"row[{index}] city_id must be numeric")
            continue
        city_ids.append(city_id)

        if row.get("aqi_us") is None:
            errors.append(f"city_id {city_id} has null aqi_us")

        try:
            reading_timestamp = parse_utc_timestamp(row.get("reading_timestamp"))
            age_hours = _freshness_hours(reading_timestamp, checked_at)
            freshness_by_city[str(city_id)] = round(age_hours, 3)
            if age_hours > freshness_thresholds.fail_hours:
                errors.append(
                    f"city_id {city_id} reading_timestamp is stale: "
                    f"{age_hours:.2f}h > {freshness_thresholds.fail_hours:.2f}h"
                )
            elif age_hours > freshness_thresholds.warn_hours:
                warnings.append(
                    f"city_id {city_id} reading_timestamp is degraded: "
                    f"{age_hours:.2f}h > {freshness_thresholds.warn_hours:.2f}h"
                )
        except Exception as exc:  # noqa: BLE001 - surface parse cause in operator output.
            errors.append(f"city_id {city_id} has invalid reading_timestamp: {exc}")

        try:
            if row.get("last_successful_update_at") is not None:
                parse_utc_timestamp(row.get("last_successful_update_at"))
        except Exception as exc:  # noqa: BLE001 - surface parse cause in operator output.
            errors.append(f"city_id {city_id} has invalid last_successful_update_at: {exc}")

    duplicate_ids = sorted({city_id for city_id in city_ids if city_ids.count(city_id) > 1})
    if duplicate_ids:
        errors.append(f"duplicate city_id values: {duplicate_ids}")

    returned_ids = set(city_ids)
    missing_expected_ids = sorted(expected_ids - returned_ids)
    if missing_expected_ids:
        errors.append(f"missing expected active city_ids: {missing_expected_ids}")

    status = "healthy"
    if errors:
        status = "unhealthy"
    elif warnings:
        status = "degraded"

    return {
        "status": status,
        "rpc": RPC_NAME,
        "checked_at_utc": checked_at.isoformat(),
        "expected_city_ids": sorted(expected_ids),
        "returned_city_ids": sorted(returned_ids),
        "row_count": len(rows),
        "errors": errors,
        "warnings": warnings,
        "freshness_hours_by_city_id": freshness_by_city,
        "thresholds": {
            "warn_hours": freshness_thresholds.warn_hours,
            "fail_hours": freshness_thresholds.fail_hours,
        },
    }


def build_human_summary(result: dict[str, Any]) -> str:
    status = str(result.get("status", "unknown")).upper()
    returned = result.get("returned_city_ids", [])
    expected = result.get("expected_city_ids", [])
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])

    lines = [
        f"RPC contract health: {status}",
        f"RPC: {result.get('rpc', RPC_NAME)}",
        f"Expected city IDs: {expected}",
        f"Returned city IDs: {returned}",
    ]
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)
    if errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def _thresholds_from_env() -> FreshnessThresholds:
    return FreshnessThresholds(
        warn_hours=float(os.getenv("RPC_FRESHNESS_WARN_HOURS", DEFAULT_WARN_HOURS)),
        fail_hours=float(os.getenv("RPC_FRESHNESS_FAIL_HOURS", DEFAULT_FAIL_HOURS)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check MtyRespira RPC contract and freshness.")
    parser.add_argument(
        "--expected-city-ids",
        default=os.getenv("EXPECTED_ACTIVE_CITY_IDS"),
        help="Comma-separated active city IDs. Defaults to current 9 active municipalities.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON output.",
    )
    args = parser.parse_args(argv)

    try:
        rows = fetch_rpc_rows()
        result = evaluate_rpc_contract(
            rows,
            expected_city_ids=parse_expected_city_ids(args.expected_city_ids),
            thresholds=_thresholds_from_env(),
        )
    except Exception as exc:  # noqa: BLE001 - operational CLI must classify connection/config failures.
        result = {
            "status": "config_error",
            "rpc": RPC_NAME,
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "errors": [str(exc)],
            "warnings": [],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if not args.json_only:
            print("\nRPC contract health: CONFIG_ERROR")
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    if not args.json_only:
        print("\n" + build_human_summary(result))

    if result["status"] == "unhealthy":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
