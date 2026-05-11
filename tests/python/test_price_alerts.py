from python_service.app.models.alerts import PriceAlert
from python_service.app.services.alert_service import evaluate_alerts

def test_price_alert_triggers_above():
    alert = PriceAlert(
        symbol='EURUSD',
        price=1.1000,
        condition='above',
        is_active=True
    )
    
    # Current price 1.1001 should trigger
    trigger, messages = evaluate_alerts([alert], {'EURUSD': 1.1001})
    assert len(trigger) == 1
    assert trigger[0].symbol == 'EURUSD'
    assert messages == ['EURUSD reached 1.1001 (Target: >= 1.1)']

def test_price_alert_no_trigger_below():
    alert = PriceAlert(
        symbol='EURUSD',
        price=1.1000,
        condition='above',
        is_active=True
    )
    
    # Current price 1.0999 should NOT trigger
    trigger, messages = evaluate_alerts([alert], {'EURUSD': 1.0999})
    assert len(trigger) == 0
    assert messages == []

def test_price_alert_appends_comment_to_message():
    alert = PriceAlert(
        symbol='XAUUSD',
        price=3300.0,
        condition='below',
        is_active=True,
        comment='关注反弹确认'
    )

    trigger, messages = evaluate_alerts([alert], {'XAUUSD': 3299.5})
    assert len(trigger) == 1
    assert messages == ['XAUUSD reached 3299.5 (Target: <= 3300.0)\n备注: 关注反弹确认']
