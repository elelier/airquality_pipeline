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

EXPECTED_STATION_IDS = {
    "Monterrey": "6492",
    "San Nicolas de los Garza": "6493",
    "Guadalupe": "6494",
    "San Pedro Garza Garcia": "8282",
    "Santa Catarina": "6491",
    "General Escobedo": "6496",
    "Garcia": "6495",
    "Ciudad Benito Juarez": "8113",
    "Cadereyta Jimenez": "10950",
}


def test_expected_active_api_names_are_covered_by_mapping_registry():
    assert waqi_api.EXPECTED_ACTIVE_API_NAMES == (
        "Monterrey",
        "San Nicolas de los Garza",
        "Guadalupe",
        "San Pedro Garza Garcia",
        "Santa Catarina",
        "General Escobedo",
        "Garcia",
        "Ciudad Benito Juarez",
        "Cadereyta Jimenez",
    )

    missing_registry_entries = [
        api_name
        for api_name in waqi_api.EXPECTED_ACTIVE_API_NAMES
        if api_name not in waqi_api.WAQI_STATION_BY_API_NAME
    ]

    assert missing_registry_entries == []


def test_station_mapping_snapshot_marks_all_expected_cities_verified():
    snapshot = waqi_api.get_station_mapping_snapshot()

    assert len(snapshot) == len(waqi_api.EXPECTED_ACTIVE_API_NAMES)
    by_api_name = {row["api_name"]: row for row in snapshot}

    for api_name, station_id in EXPECTED_STATION_IDS.items():
        assert by_api_name[api_name]["station_id"] == station_id
        assert by_api_name[api_name]["verified"] is True
        assert by_api_name[api_name]["evidence"]

    assert waqi_api.WAQI_STATION_BY_API_NAME["Ciudad Benito Juárez"] == "8113"


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
    assert result["provider_station_id"] is None


def test_fetch_air_quality_data_unknown_station_fails_closed():
    result = waqi_api.fetch_air_quality_data(
        api_name="Unknown City",
        city_id=999,
        waqi_api_token="token",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "station_not_mapped"
    assert result["provider_station_id"] is None


def test_normalize_waqi_payload_status_not_ok_keeps_station_trace():
    result = waqi_api.normalize_waqi_payload(
        raw_api_data={"status": "error", "data": "Invalid key"},
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "waqi_status_not_ok"
    assert result["provider_station_id"] == "6493"


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
    assert result["provider_station_id"] == "6493"


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


def test_normalize_waqi_payload_rejects_coordinates_outside_nuevo_leon():
    payload = {
        "status": "ok",
        "data": {
            "aqi": 87,
            "time": {"iso": "2026-05-05T12:00:00-06:00"},
            "city": {"geo": [19.4326, -99.1332]},
            "iaqi": {"t": {"v": 28}},
        },
    }

    result = waqi_api.normalize_waqi_payload(
        raw_api_data=payload,
        api_name="San Nicolas de los Garza",
        city_id=11,
        station_id="6493",
    )

    assert result["status"] == "error"
    assert result["errorType"] == "coordinates_out_of_nuevo_leon"
    assert result["provider_station_id"] == "6493"


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
