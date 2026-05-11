from fastapi.testclient import TestClient

from python_service.app.main import app


def test_risk_control_load_save(tmp_path, monkeypatch):
    monkeypatch.setattr(
        'python_service.app.services.risk_control_service.RISK_CONTROL_FILE',
        tmp_path / 'risk-control.json',
    )
    client = TestClient(app)

    response = client.get('/risk-control')
    assert response.status_code == 200
    assert response.json() == {'margin_alert': 200.0, 'equity_alert': 1000.0}

    response = client.post('/risk-control', json={'margin_alert': 150, 'equity_alert': 900})
    assert response.status_code == 200

    response = client.get('/risk-control')
    assert response.json() == {'margin_alert': 150.0, 'equity_alert': 900.0}
