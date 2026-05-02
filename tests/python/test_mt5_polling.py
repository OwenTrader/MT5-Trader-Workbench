from fastapi.testclient import TestClient
import pytest
from unittest.mock import patch, MagicMock

from python_service.app.main import app

def test_account_info_endpoint():
    client = TestClient(app)
    
    # Patch where it's used in the route
    with patch('python_service.app.routes.mt5.get_account_info') as mock_get_account:
        mock_get_account.return_value = {
            'balance': 10000.0,
            'equity': 10500.0,
            'margin_level': 500.0,
            'currency': 'USD'
        }
        
        response = client.get('/mt5/account')
        assert response.status_code == 200
        data = response.json()
        assert data['balance'] == 10000.0
        assert data['equity'] == 10500.0

def test_positions_endpoint():
    client = TestClient(app)
    
    with patch('python_service.app.routes.mt5.get_positions') as mock_get_positions:
        mock_get_positions.return_value = [
            {'ticket': 12345, 'symbol': 'EURUSD', 'volume': 0.01, 'profit': 10.5}
        ]
        
        response = client.get('/mt5/positions')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['symbol'] == 'EURUSD'
