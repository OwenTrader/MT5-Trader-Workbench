from python_service.app.models.alerts import VolatilityAlert
from python_service.app.services.alert_service import evaluate_volatility


def test_volatility_trigger():
    # threshold_points is in POINTS: 500 points on 5-digit EURUSD = 50 pips.
    alert = VolatilityAlert(
        id='',
        symbol='EURUSD',
        threshold_points=500,
        timeframe_seconds=60,
        is_active=True
    )

    # 60-pip move (0.0060 = 600 points) in 60 seconds should trigger
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
        id='',
        symbol='EURUSD',
        threshold_points=500,
        timeframe_seconds=60,
        is_active=True
    )

    # 40-pip move (0.0040 = 400 points) in 60 seconds should NOT trigger
    price_history = {
        'EURUSD': [
            {'timestamp': 1000, 'price': 1.1000},
            {'timestamp': 1060, 'price': 1.1040}
        ]
    }

    trigger, messages = evaluate_volatility([alert], price_history)
    assert len(trigger) == 0
