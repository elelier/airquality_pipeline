import pytest
from unittest.mock import MagicMock, patch
from sync_cities import sync_cities

@pytest.fixture
def mock_supabase_client():
    """Fixture to mock the Supabase client with more realistic responses."""
    with patch('sync_cities.get_supabase_client') as mock_get_client:
        mock_client = MagicMock()

        # Default mock for the final select call
        mock_select_response = MagicMock()
        mock_select_response.data = []
        mock_client.table.return_value.select.return_value.execute.return_value = mock_select_response

        # Mock for insert
        mock_insert_response = MagicMock()
        mock_insert_response.error = None
        mock_insert_response.data = [{'id': 100}] # Simulate one row inserted
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert_response

        # Mock for update
        mock_update_response = MagicMock()
        mock_update_response.error = None
        mock_update_response.data = [{'id': 1}] # Simulate one row updated
        mock_client.table.return_value.update.return_value.in_.return_value.execute.return_value = mock_update_response

        mock_get_client.return_value = mock_client
        yield mock_client

def test_sync_cities_add_new(mock_supabase_client):
    """Test adding a new city."""
    api_cities = [{'city': 'New City'}]
    db_cities = []
    summary, _ = sync_cities(api_cities, db_cities)
    
    assert summary['newCitiesAdded'] == 1
    mock_supabase_client.table.return_value.insert.assert_called_once_with([{'name': 'New City', 'api_name': 'New City'}])

def test_sync_cities_deactivate_old(mock_supabase_client):
    """Test deactivating a city that is no longer in the API list."""
    api_cities = []
    db_cities = [{'id': 1, 'api_name': 'Old City', 'is_active': True}]
    summary, _ = sync_cities(api_cities, db_cities)

    assert summary['citiesDeactivated'] == 1
    update_call = mock_supabase_client.table.return_value.update.call_args
    assert update_call[0][0]['is_active'] == False

def test_sync_cities_no_changes(mock_supabase_client):
    """Test sync with no new or deactivated cities."""
    api_cities = [{'city': 'Existing City'}]
    db_cities = [{'id': 1, 'api_name': 'Existing City', 'is_active': True}]
    summary, _ = sync_cities(api_cities, db_cities)

    assert summary['newCitiesAdded'] == 0
    assert summary['citiesDeactivated'] == 0
    mock_supabase_client.table.return_value.insert.assert_not_called()
    # The update call is now mocked, so we need to check it was not called
    mock_supabase_client.table.return_value.update.assert_not_called()

def test_sync_cities_reactivate_inactive(mock_supabase_client):
    """Test that an inactive city in DB that is present in API is not deactivated."""
    api_cities = [{'city': 'Reactivated City'}]
    db_cities = [{'id': 1, 'api_name': 'Reactivated City', 'is_active': False}]
    summary, _ = sync_cities(api_cities, db_cities)

    assert summary['citiesDeactivated'] == 0
    mock_supabase_client.table.return_value.update.assert_not_called()
