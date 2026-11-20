import pytest
from unittest.mock import patch, MagicMock
from airvisual_api import fetch_cities, fetch_air_quality_data

@pytest.fixture
def mock_requests_get():
    """Fixture to mock requests.get."""
    with patch('requests.get') as mock_get:
        yield mock_get

def test_fetch_cities_success(mock_requests_get):
    """Test successful fetching of cities."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": [{"city": "Test City 1"}, {"city": "Test City 2"}]}
    mock_requests_get.return_value = mock_response

    cities = fetch_cities('fake_api_key')
    assert mock_requests_get.call_args.args[0] == 'https://api.airvisual.com/v2/cities'
    assert len(cities) == 2
    assert cities[0]['city'] == 'Test City 1'

def test_fetch_cities_api_error(mock_requests_get):
    """Test API error during fetch_cities."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_requests_get.return_value = mock_response

    with pytest.raises(Exception, match="Max retries reached"):
        fetch_cities('fake_api_key')

def test_fetch_air_quality_data_success(mock_requests_get):
    """Test successful fetching of air quality data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.return_value = {
        "status": "success",
        "data": {
            "current": {
                "pollution": {"aqius": 50, "ts": "2026-11-19T22:00:00Z"},
                "weather": {"tp": 25}
            },
            "location": {
                "coordinates": [ -100.0, 25.0]
            }
        }
    }
    mock_requests_get.return_value = mock_response

    data = fetch_air_quality_data('Test City', 1, 'Nuevo Leon', 'Mexico', 'fake_api_key')
    assert data['status'] == 'success'
    assert mock_requests_get.call_args.args[0] == 'https://api.airvisual.com/v2/city'
    assert data['calidad_aire']['aqi_us'] == 50
    assert data['reading_timestamp_iso'] == '2026-11-19T22:00:00Z'


@pytest.mark.parametrize('pollution_timestamp', [None, '2026-11-19T22:00:00'])
def test_rejects_missing_or_timezone_free_pollution_timestamp(mock_requests_get, pollution_timestamp):
    mock_requests_get.return_value.json.return_value = {
        "status": "success",
        "data": {
            "current": {
                "pollution": {"aqius": 50, "ts": pollution_timestamp},
                "weather": {"ts": "2026-11-19T23:00:00Z"},
            },
            "location": {"coordinates": [-100.0, 25.0]},
        },
    }

    data = fetch_air_quality_data('Test City', 1, 'Nuevo Leon', 'Mexico', 'fake_api_key')

    assert data['status'] == 'error'
    assert data['errorType'] == 'invalid_reading_timestamp'


def test_fetch_air_quality_data_fetch_failed(mock_requests_get):
    """Test fetch_failed error during fetch_air_quality_data."""
    mock_requests_get.side_effect = Exception("Test error")

    data = fetch_air_quality_data('Test City', 1, 'Nuevo Leon', 'Mexico', 'fake_api_key')
    assert data['status'] == 'error'
    assert data['errorType'] == 'fetch_failed'
