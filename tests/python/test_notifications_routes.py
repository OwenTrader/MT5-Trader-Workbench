from fastapi.testclient import TestClient

from python_service.app.main import app
from python_service.app.routes import notifications as notifications_routes


def test_dingtalk_test_endpoint_uses_upstream_status_and_body(monkeypatch):
    client = TestClient(app)

    async def fake_send_dingtalk_notification(message: str):
        return {
            'ok': False,
            'status_code': 400,
            'response_body': '{"errcode":310000,"errmsg":"keywords not in content"}',
        }

    monkeypatch.setattr(notifications_routes, 'send_dingtalk_notification', fake_send_dingtalk_notification)

    response = client.post('/notifications/test_dingtalk')

    assert response.status_code == 400
    assert response.text == '{"errcode":310000,"errmsg":"keywords not in content"}'


def test_wecom_test_endpoint_uses_upstream_status_and_body(monkeypatch):
    client = TestClient(app)

    async def fake_send_wecom_notification(message: str):
        return {
            'ok': False,
            'status_code': 403,
            'response_body': '{"errcode":93000,"errmsg":"invalid webhook"}',
        }

    monkeypatch.setattr(notifications_routes, 'send_wecom_notification', fake_send_wecom_notification)

    response = client.post('/notifications/test_wecom')

    assert response.status_code == 403
    assert response.text == '{"errcode":93000,"errmsg":"invalid webhook"}'


def test_feishu_test_endpoint_uses_upstream_status_and_body(monkeypatch):
    client = TestClient(app)

    async def fake_send_feishu_notification(message: str):
        return {
            'ok': False,
            'status_code': 200,
            'response_body': '{"code":19024,"msg":"Key Words Not Found"}',
        }

    monkeypatch.setattr(notifications_routes, 'send_feishu_notification', fake_send_feishu_notification)

    response = client.post('/notifications/test_feishu')

    assert response.status_code == 200
    assert response.text == '{"code":19024,"msg":"Key Words Not Found"}'
