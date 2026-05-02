from python_service.app.models.alerts import VolatilityAlert
from python_service.app.services.alert_service import evaluate_volatility
import pytest

def test_volatility_trigger():
    alert = VolatilityAlert(
        symbol='EURUSD',
        threshold_pips=50,
        timeframe_seconds=60,
        is_active=True
    )
    
    # 60 pips move in 60 seconds should trigger
    # We'll pass price history
    price_history = {
        'EURUSD': [
            {'timestamp': 1000, 'price': 1.1000},
            {'timestamp': 1060, 'price': 1.1060}
        ]
    }
    
    trigger, messages = evaluate_volatility([alert], price_history)
    assert len(trigger) == 1
    assert 'EURUSD' in messages[0]

def test_volatility_no_trigger():
    alert = VolatilityAlert(
        symbol='EURUSD',
        threshold_pips=50,
        timeframe_seconds=60,
        is_active=True
    )
    
    # 40 pips move in 60 seconds should NOT trigger
    price_history = {
        'EURUSD': [
            {'timestamp': 1000, 'price': 1.1000},
            {'timestamp': 1060, 'price': 1.1040}
        ]
    }
    
    trigger, messages = evaluate_volatility([alert], price_history)
    assert len(trigger) == 0
