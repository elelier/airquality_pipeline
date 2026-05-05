import pytest
from datetime import datetime, timedelta, timezone
from utils import check_if_update_needed, UPDATE_INTERVAL_MINUTES, compute_inter_city_delay, validate_reading_payload

@pytest.fixture
def base_city():
    """Provide a base city dictionary for tests."""
    return {
        'id': 1,
        'api_name': 'Test City',
        'is_active': True,
        'last_successful_update_at': None,
        'last_update_status': None
    }

def test_needs_update_force_update(base_city):
    """Test that force_update=True always results in needing an update."""
    result = check_if_update_needed(base_city, force_update=True)
    assert result['needsUpdate'] == True

def test_needs_update_no_last_update(base_city):
    """Test that a city with no last_successful_update_at needs an update."""
    base_city['last_update_status'] = 'success'
    result = check_if_update_needed(base_city)
    assert result['needsUpdate'] == True

def test_needs_update_last_update_failed(base_city):
    """Test that a city with a failed last_update_status needs an update."""
    base_city['last_update_status'] = 'error: some_error'
    base_city['last_successful_update_at'] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = check_if_update_needed(base_city)
    assert result['needsUpdate'] == True

def test_needs_update_interval_passed(base_city):
    """Test that a city needs an update if the interval has passed."""
    base_city['last_update_status'] = 'success'
    base_city['last_successful_update_at'] = (datetime.now(timezone.utc) - timedelta(minutes=UPDATE_INTERVAL_MINUTES + 1)).isoformat()
    result = check_if_update_needed(base_city)
    assert result['needsUpdate'] == True

def test_no_update_needed_interval_not_passed(base_city):
    """Test that a city does not need an update if the interval has not passed."""
    base_city['last_update_status'] = 'success'
    base_city['last_successful_update_at'] = (datetime.now(timezone.utc) - timedelta(minutes=UPDATE_INTERVAL_MINUTES - 1)).isoformat()
    result = check_if_update_needed(base_city)
    assert result['needsUpdate'] == False

def test_invalid_city_input():
    """Test that invalid city input is handled gracefully."""
    invalid_city = {'id': 1} # Missing api_name
    result = check_if_update_needed(invalid_city)
    assert result['needsUpdate'] == False
    assert result['error'] == True


def test_compute_inter_city_delay_bounds():
    """Ensure inter-city delay stays within configured bounds."""
    for failures in range(0, 5):
        delay_value = compute_inter_city_delay(failures)
        assert 8.0 <= delay_value <= 15.0


def test_validate_reading_payload_success():
    reading = {
        'calidad_aire': {'aqi_us': 75},
        'clima': {'temperatura_c': 22},
        'coordenadas': {'lat': 25.5, 'lon': -99.5}
    }
    result = validate_reading_payload(reading)
    assert result['valid'] is True


def test_validate_reading_payload_failure():
    reading = {
        'calidad_aire': {'aqi_us': 800},
        'clima': {'temperatura_c': -80},
        'coordenadas': {'lat': 24.0, 'lon': -101.0}
    }
    result = validate_reading_payload(reading)
    assert result['valid'] is False
    assert 'aqi_us_out_of_range' in result['reasons']
