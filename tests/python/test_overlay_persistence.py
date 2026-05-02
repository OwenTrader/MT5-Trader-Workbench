from fastapi.testclient import TestClient
import pytest
import os
import json

from python_service.app.main import app

def test_overlay_import_export():
    client = TestClient(app)
    
    test_config = {
        'name': 'Test Strategy',
        'alerts': [
            {'symbol': 'EURUSD', 'target_price': 1.1, 'direction': 'above'}
        ]
    }
    
    # Export current (should be empty or last saved)
    response = client.get('/overlay/export')
    assert response.status_code == 200
    
    # Import
    response = client.post('/overlay/import', json=test_config)
    assert response.status_code == 200
    
    # Verify via export
    response = client.get('/overlay/export')
    assert response.status_code == 200
    exported = response.json()
    assert exported['name'] == 'Test Strategy'
    assert len(exported['alerts']) == 1
