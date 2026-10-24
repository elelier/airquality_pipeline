import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from update_city import update_city

@pytest.fixture(autouse=True)
def disable_delays(monkeypatch):
    monkeypatch.setenv('SKIP_PIPELINE_DELAYS', '1')


@pytest.fixture
def mock_supabase_client():
    """Fixture to mock the Supabase client and logging for update_city tests."""
    with patch('update_city.get_supabase_client') as mock_get_client, \
         patch('update_city.log_pipeline_event'):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        mock_get_client.return_value = mock_client
        yield mock_client

@pytest.fixture
def success_fetch_result():
    """Provide a sample successful fetch result."""
    return {
        'city_id': 1,
        'status': 'success',
        'reading_timestamp_iso': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        'calidad_aire': {'aqi_us': 50},
        'clima': {'temperatura_c': 25},
        'coordenadas': {'lat': 25.0, 'lon': -100.0},
        'api_raw_response': {}
    }

def test_update_city_success(mock_supabase_client, success_fetch_result):
    """Test a successful update_city run where a new reading is inserted and city is updated."""
    result = update_city(success_fetch_result)

    assert result['readingInserted'] == True
    assert result['cityStatusUpdated'] == True
    assert result['insertError'] is None
    assert result['updateError'] is None
    mock_supabase_client.table.return_value.insert.assert_called_once()
    mock_supabase_client.table.return_value.update.return_value.eq.assert_called_once_with('id', 1)


def test_update_city_maps_successful_weather_context(mock_supabase_client, success_fetch_result):
    success_fetch_result['weather_context'] = {
        'status': 'success',
        'weather_temperature_c': 28,
        'weather_humidity_percent': 50,
        'weather_wind_speed_kmh': 12.5,
        'weather_wind_direction_deg': 180,
        'weather_wind_gust_kmh': 22.1,
        'weather_provider': 'open-meteo',
        'weather_timestamp': '2026-05-25T01:00:00+00:00',
        'weather_source_payload': {'current': {'temperature_2m': 28}},
    }

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is True
    inserted_payload = mock_supabase_client.table.return_value.insert.call_args.args[0]
    assert inserted_payload['weather_temperature_c'] == 28
    assert inserted_payload['weather_humidity_percent'] == 50
    assert inserted_payload['weather_wind_speed_kmh'] == 12.5
    assert inserted_payload['weather_wind_direction_deg'] == 180
    assert inserted_payload['weather_wind_gust_kmh'] == 22.1
    assert inserted_payload['weather_provider'] == 'open-meteo'
    assert inserted_payload['weather_timestamp'] == '2026-05-25T01:00:00+00:00'
    assert inserted_payload['weather_source_payload'] == {'current': {'temperature_2m': 28}}


def test_update_city_ignores_failed_weather_context(mock_supabase_client, success_fetch_result):
    success_fetch_result['weather_context'] = {
        'status': 'error',
        'provider': 'open-meteo',
        'errorType': 'fetch_failed',
    }

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is True
    inserted_payload = mock_supabase_client.table.return_value.insert.call_args.args[0]
    assert 'weather_temperature_c' not in inserted_payload
    assert 'weather_provider' not in inserted_payload

def test_update_city_fetch_error(mock_supabase_client):
    """Test update_city when the fetch result indicates an error."""
    error_result = {
        'city_id': 2,
        'status': 'error',
        'errorType': 'fetch_failed'
    }
    result = update_city(error_result)

    assert result['readingInserted'] == False
    assert result['cityStatusUpdated'] == True # Status is updated to error
    assert result['insertError'] is None
    assert result['updateError'] is None
    mock_supabase_client.table.return_value.insert.assert_not_called()
    mock_supabase_client.table.return_value.update.return_value.eq.assert_called_once_with('id', 2)


def test_update_city_validation_failure(mock_supabase_client, success_fetch_result):
    """Reject out-of-range readings and do not insert."""
    success_fetch_result['calidad_aire']['aqi_us'] = 999

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is False
    assert result['cityStatusUpdated'] is True
    assert result['validationErrors'] is not None
    mock_supabase_client.table.return_value.insert.assert_not_called()

def test_update_city_skip(mock_supabase_client):
    """Test update_city when the result indicates a skip."""
    skip_result = {
        'id': 3,
        'needsUpdate': False
    }
    result = update_city(skip_result)

    assert result['readingInserted'] == False
    assert result['cityStatusUpdated'] == True # Status is updated to skipped
    assert result['insertError'] is None
    assert result['updateError'] is None
    mock_supabase_client.table.return_value.insert.assert_not_called()
    mock_supabase_client.table.return_value.update.return_value.eq.assert_called_once_with('id', 3)


def test_update_city_rejects_stale_measurement_without_refreshing_success(mock_supabase_client, success_fetch_result):
    success_fetch_result['reading_timestamp_iso'] = (
        datetime.now(timezone.utc) - timedelta(days=5)
    ).isoformat()

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is False
    assert 'stale_reading_timestamp' in result['validationErrors']
    assert mock_supabase_client.table.return_value.update.call_args.args[0]['last_update_status'] == 'error: stale_reading'
    assert 'last_successful_update_at' not in mock_supabase_client.table.return_value.update.call_args.args[0]
    mock_supabase_client.table.return_value.insert.assert_not_called()


def test_update_city_skips_duplicate_recent_measurement(mock_supabase_client, success_fetch_result):
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {'reading_timestamp': success_fetch_result['reading_timestamp_iso']}
    ]

    result = update_city(success_fetch_result)

    assert result['unchangedReading'] is True
    assert result['readingInserted'] is False
    assert mock_supabase_client.table.return_value.update.call_args.args[0]['last_update_status'] == 'skipped: unchanged_reading'
    mock_supabase_client.table.return_value.insert.assert_not_called()


def test_update_city_fails_closed_if_latest_reading_lookup_fails(mock_supabase_client, success_fetch_result):
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = RuntimeError('read unavailable')

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is False
    assert result['lookupError'] is not None
    assert mock_supabase_client.table.return_value.update.call_args.args[0]['last_update_status'] == 'error: latest_reading_lookup_failed'
    mock_supabase_client.table.return_value.insert.assert_not_called()


def test_update_city_rejects_out_of_order_measurement(mock_supabase_client, success_fetch_result):
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {'reading_timestamp': datetime.now(timezone.utc).isoformat()}
    ]

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is False
    assert result['unchangedReading'] is False
    status = mock_supabase_client.table.return_value.update.call_args.args[0]
    assert status['last_update_status'] == 'error: out_of_order_reading'
    assert 'last_successful_update_at' not in status
    mock_supabase_client.table.return_value.insert.assert_not_called()


def test_update_city_does_not_mark_success_on_insert_error(mock_supabase_client, success_fetch_result):
    mock_supabase_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError('database insert failed')

    result = update_city(success_fetch_result)

    assert result['readingInserted'] is False
    assert result['insertError'] is not None
    status = mock_supabase_client.table.return_value.update.call_args.args[0]
    assert status['last_update_status'] == 'error: insert_failed'
    assert 'last_successful_update_at' not in status
