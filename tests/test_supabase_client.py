import pytest
from unittest.mock import patch, MagicMock
import supabase_client

@patch('supabase_client.create_client')
def test_get_supabase_client(mock_create_client):
    """Test that get_supabase_client calls create_client with the correct credentials."""
    supabase_client.get_supabase_client()
    mock_create_client.assert_called_once_with(supabase_client.SUPABASE_URL, supabase_client.SUPABASE_SERVICE_ROLE_KEY)

@patch('supabase_client.get_supabase_client')
def test_get_existing_cities_success(mock_get_supabase_client):
    """Test successful fetching of existing cities from Supabase."""
    mock_supabase = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": 1, "api_name": "Test City", "is_active": True}]
    mock_supabase.table.return_value.select.return_value.execute.return_value = mock_response
    mock_get_supabase_client.return_value = mock_supabase

    cities = supabase_client.get_existing_cities()
    assert len(cities) == 1
    assert cities[0]['id'] == 1

@patch('supabase_client.get_supabase_client')
def test_get_existing_cities_error(mock_get_supabase_client):
    """Test an error during fetching of existing cities."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.execute.side_effect = Exception("DB Error")
    mock_get_supabase_client.return_value = mock_supabase

    with pytest.raises(Exception, match="Failed to get existing cities from Supabase: DB Error"):
        supabase_client.get_existing_cities()
