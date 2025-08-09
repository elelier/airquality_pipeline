import pytest
from unittest.mock import MagicMock, patch
from update_city import update_city

@pytest.fixture
def mock_supabase_client():
    """Fixture to mock the Supabase client for update_city tests."""
    with patch('update_city.get_supabase_client') as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client

@pytest.fixture
def success_fetch_result():
    """Provide a sample successful fetch result."""
    return {
        'city_id': 1,
        'status': 'success',
        'reading_timestamp_iso': '2025-08-09T12:00:00+00:00',
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
