import socket
from unittest.mock import MagicMock, patch

import pytest

import supabase_client


@patch('supabase_client.socket.getaddrinfo')
@patch('supabase_client.create_client')
def test_get_supabase_client(mock_create_client, mock_getaddrinfo, monkeypatch):
    """Test that get_supabase_client validates URL and calls create_client."""
    monkeypatch.setenv('SUPABASE_URL', 'https://example-project.supabase.co')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'test_key')

    supabase_client.get_supabase_client()

    mock_getaddrinfo.assert_called_once_with('example-project.supabase.co', 443)
    mock_create_client.assert_called_once_with('https://example-project.supabase.co', 'test_key')


@patch('supabase_client.socket.getaddrinfo')
def test_validate_supabase_url_rejects_postgres_host(mock_getaddrinfo):
    with pytest.raises(ValueError, match='no parece una API URL de Supabase'):
        supabase_client.validate_supabase_url('https://db.example-project.supabase.co')

    mock_getaddrinfo.assert_not_called()


@patch('supabase_client.socket.getaddrinfo', side_effect=socket.gaierror('dns failed'))
def test_validate_supabase_url_rejects_unresolvable_host(mock_getaddrinfo):
    with pytest.raises(ValueError, match='no resuelve por DNS'):
        supabase_client.validate_supabase_url('https://example-project.supabase.co')

    mock_getaddrinfo.assert_called_once_with('example-project.supabase.co', 443)


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
    mock_supabase.table.return_value.select.return_value.execute.side_effect = Exception('DB Error')
    mock_get_supabase_client.return_value = mock_supabase

    with pytest.raises(Exception, match='Failed to get existing cities from Supabase: DB Error'):
        supabase_client.get_existing_cities()
