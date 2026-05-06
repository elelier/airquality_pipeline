from unittest.mock import MagicMock, patch

import waqi_api


SUCCESS_WAQI_PAYLOAD = {
    "status": "ok",
    "data": {
        "aqi": 87,
        "dominentpol": "pm25",
        "time": {"iso": "2026-05-05T12:00:00-06:00"},
        "city": {"geo": [25.74167, -100.30222]},
        "iaqi": {
            "t": {"v": 28},
            "p": {"v": 1012},
            "h": {"v": 46},
            "w": {"v": 2.1},
            "wd": {"v": 90},
        },
    },
}


def test_normalize_waqi_payload_success():
    result = waqi_api.normalize_waqi_payload(
        raw_api_data=SUCCESS_WAQI_PAYLOAD,
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "success"
    assert result["provider"] == "waqi"
    assert result["provider_station_id"] == "6493"
    assert result["city_id"] == 11
    assert result["calidad_aire"]["aqi_us"] == 87
    assert result["calidad_aire"]["contaminante_principal_us"] == "pm25"
    assert result["reading_timestamp_iso"] == "2026-05-05T12:00:00-06:00"
    assert result["coordenadas"] == {"lat": 25.74167, "lon": -100.30222}
    assert result["clima"]["temperatura_c"] == 28
    assert result["clima"]["presion_hpa"] == 1012
    assert result["clima"]["humedad_relativa"] == 46
    assert result["clima"]["velocidad_viento_ms"] == 2.1
    assert result["clima"]["direccion_viento_deg"] == 90
    assert result["api_raw_response"] == SUCCESS_WAQI_PAYLOAD["data"]


def test_fetch_air_quality_data_missing_token_fails_closed():
    result = waqi_api.fetch_air_quality_data(
        api_name="San Nicolas de los Garza",
        city_id=11,
        waqi_api_token=None,
    )

    assert result["status"] == "error"
    assert result["errorType"] == "missing_token"


def test_fetch_air_quality_data_unmapped_station_fails_closed():
    result = waqi_api.fetch_air_quality_data(
        api_name="Monterrey",
        city_id=9,
        waqi_api_token="token",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "station_not_mapped"


def test_normalize_waqi_payload_status_not_ok():
    result = waqi_api.normalize_waqi_payload(
        raw_api_data={"status": "error", "data": "Invalid key"},
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "waqi_status_not_ok"


def test_normalize_waqi_payload_missing_aqi():
    payload = {
        "status": "ok",
        "data": {
            "time": {"iso": "2026-05-05T12:00:00-06:00"},
            "city": {"geo": [25.74167, -100.30222]},
        },
    }

    result = waqi_api.normalize_waqi_payload(
        raw_api_data=payload,
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "missing_aqi"


def test_normalize_waqi_payload_missing_timestamp():
    payload = {
        "status": "ok",
        "data": {
            "aqi": 87,
            "city": {"geo": [25.74167, -100.30222]},
        },
    }

    result = waqi_api.normalize_waqi_payload(
        raw_api_data=payload,
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "missing_reading_ts"


def test_normalize_waqi_payload_missing_coordinates():
    payload = {
        "status": "ok",
        "data": {
            "aqi": 87,
            "time": {"iso": "2026-05-05T12:00:00-06:00"},
            "city": {},
        },
    }

    result = waqi_api.normalize_waqi_payload(
        raw_api_data=payload,
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "missing_coordinates"


def test_fetch_air_quality_data_success_does_not_log_token():
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = SUCCESS_WAQI_PAYLOAD

    with patch("waqi_api.requests.get", return_value=response) as mock_get:
        result = waqi_api.fetch_air_quality_data(
            api_name="San Nicolas de los Garza",
            city_id=11,
            waqi_api_token="secret-token",
        )

    assert result["status"] == "success"
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["params"] == {"token": "secret-token"}
