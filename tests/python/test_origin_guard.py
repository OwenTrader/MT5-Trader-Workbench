from fastapi.testclient import TestClient

from python_service.app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_requests_without_origin_are_allowed():
    response = _client().get('/health')

    assert response.status_code == 200


def test_local_dev_origins_are_allowed_and_get_cors_headers():
    response = _client().get('/health', headers={'Origin': 'http://localhost:5173'})

    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_file_origin_null_is_allowed():
    response = _client().get('/health', headers={'Origin': 'null'})

    assert response.status_code == 200


def test_foreign_web_page_origins_are_rejected():
    """A malicious site must not be able to call the local trading API."""
    response = _client().get('/health', headers={'Origin': 'https://evil.example.com'})

    assert response.status_code == 403
    assert 'access-control-allow-origin' not in response.headers


def test_foreign_origin_is_rejected_before_the_request_body_executes():
    response = _client().post(
        '/local-copy-trading/runtime',
        json={'enabled': True},
        headers={'Origin': 'https://evil.example.com'},
    )

    assert response.status_code == 403


def test_preflight_from_foreign_origin_gets_no_cors_headers():
    response = _client().options('/health', headers={'Origin': 'https://evil.example.com'})

    assert response.status_code == 200
    assert 'access-control-allow-origin' not in response.headers
