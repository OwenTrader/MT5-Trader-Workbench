from python_service.app.models.alerts import PriceAlert
from python_service.app.services.alert_service import evaluate_alerts
import pytest

def test_price_alert_triggers_above():
    alert = PriceAlert(
        symbol='EURUSD',
        target_price=1.1000,
        direction='above',
        is_active=True
    )
    
    # Current price 1.1001 should trigger
    trigger, type = evaluate_alerts([alert], {'EURUSD': 1.1001})
    assert len(trigger) == 1
    assert trigger[0].symbol == 'EURUSD'

def test_price_alert_no_trigger_below():
    alert = PriceAlert(
        symbol='EURUSD',
        target_price=1.1000,
        direction='above',
        is_active=True
    )
    
    # Current price 1.0999 should NOT trigger
    trigger, type = evaluate_alerts([alert], {'EURUSD': 1.0999})
    assert len(trigger) == 0
