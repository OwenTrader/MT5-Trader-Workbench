from python_service.app.services.risk_control_service import load_risk_control_settings
from python_service.app.services.risk_control_service import evaluate_risk_thresholds


def test_load_risk_control_settings_returns_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        'python_service.app.services.risk_control_service.RISK_CONTROL_FILE',
        tmp_path / 'risk-control.json',
    )

    settings = load_risk_control_settings()

    assert settings.margin_alert == 200
    assert settings.equity_alert == 1000


def test_evaluate_risk_thresholds_returns_breach_messages():
    settings = {'margin_alert': 200, 'equity_alert': 1000}
    account = {'margin_level': 180, 'equity': 950}

    messages = evaluate_risk_thresholds(settings, account)

    assert messages == [
        'Account margin_level reached 180 (Threshold: <= 200)',
        'Account equity reached 950 (Threshold: <= 1000)',
    ]
