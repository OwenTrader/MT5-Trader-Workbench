import asyncio

from python_service.app.models.alerts import PriceAlert
from python_service.app.services.alert_dispatch_service import dispatch_price_alerts


def test_dispatch_price_alerts_notifies_each_triggered_message(monkeypatch):
    sent = []

    async def fake_notify_all(title, message):
        sent.append((title, message))

    monkeypatch.setattr(
        'python_service.app.services.alert_dispatch_service.notify_all',
        fake_notify_all,
    )

    alerts = [PriceAlert(symbol='XAUUSD', price=3300, condition='above', is_active=True)]

    asyncio.run(dispatch_price_alerts(alerts, {'XAUUSD': 3301}))

    assert sent == [('价格预警触发', 'XAUUSD reached 3301 (Target: >= 3300.0)')]
