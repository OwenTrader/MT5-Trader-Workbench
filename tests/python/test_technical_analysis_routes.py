from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.routes import awakening as awakening_route
from python_service.app.routes.awakening import router as awakening_router


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(awakening_router)
    return app


def test_technical_analysis_route_returns_structured_json(monkeypatch):
    monkeypatch.setattr(awakening_route, 'generate_report', lambda symbol: {
        'symbol': symbol,
        'timeframe': 'M15',
        'candles_count': 100,
        'prompt_version': 'v1',
        'analysis_markdown': '## Market Structure\nTest',
        'used_model': 'test-model',
        'generated_at': '2026-05-27T00:00:00+00:00',
    })
    client = TestClient(build_test_app())

    response = client.post('/awakening/report', json={'symbol': 'XAUUSD'})

    assert response.status_code == 200
    assert response.json()['analysis_markdown'].startswith('## Market Structure')


def test_technical_analysis_route_returns_400_when_ai_config_missing(monkeypatch):
    monkeypatch.setattr(awakening_route, 'generate_report', lambda symbol: (_ for _ in ()).throw(ValueError('AI base URL and API key are required')))
    client = TestClient(build_test_app())

    response = client.post('/awakening/report', json={'symbol': 'XAUUSD'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'AI base URL and API key are required'
