from datetime import datetime, timezone
from typing import Any

PROVIDER_NAME = "open-meteo"


def parse_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    return None


def parse_int(value: Any) -> int | None:
    parsed = parse_number(value)
    if parsed is None:
        return None
    return int(round(parsed))


def normalize_timestamp(value: Any) -> str | None:
    if not value:
        return None
    clean_value = str(value).strip()
    if not clean_value:
        return None
    if clean_value.endswith("Z"):
        clean_value = f"{clean_value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(clean_value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def build_weather_error(error_type: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "provider": PROVIDER_NAME,
        "errorType": error_type,
        "message": message,
    }
