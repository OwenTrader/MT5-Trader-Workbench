from python_service.app.models.monitoring import AccountCondition
from python_service.app.services.monitoring_service import evaluate_account
import pytest

def test_account_margin_trigger():
    condition = AccountCondition(
        metric='margin_level',
        threshold=100.0,
        direction='below',
        is_active=True
    )
    
    # Margin level 99.0 should trigger
    trigger, message = evaluate_account([condition], {'margin_level': 99.0})
    assert len(trigger) == 1
    assert 'margin_level' in message[0]

def test_account_equity_no_trigger():
    condition = AccountCondition(
        metric='equity',
        threshold=5000.0,
        direction='below',
        is_active=True
    )
    
    # Equity 5001.0 should NOT trigger
    trigger, message = evaluate_account([condition], {'equity': 5001.0})
    assert len(trigger) == 0
