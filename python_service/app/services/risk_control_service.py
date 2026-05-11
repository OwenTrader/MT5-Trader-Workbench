import json
from pathlib import Path

from python_service.app.models.risk_control import RiskControlSettings


RISK_CONTROL_FILE = Path('storage/risk-control.json')


def load_risk_control_settings() -> RiskControlSettings:
    if not RISK_CONTROL_FILE.exists():
        return RiskControlSettings()

    with RISK_CONTROL_FILE.open('r', encoding='utf-8') as file:
        return RiskControlSettings(**json.load(file))


def persist_risk_control_settings(settings: RiskControlSettings) -> None:
    RISK_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RISK_CONTROL_FILE.open('w', encoding='utf-8') as file:
        json.dump(settings.model_dump(), file, ensure_ascii=False, indent=2)


def evaluate_risk_thresholds(settings: dict, account: dict) -> list[str]:
    messages = []
    margin_level = account.get('margin_level')
    equity = account.get('equity')

    if margin_level is not None and margin_level <= settings['margin_alert']:
        messages.append(f"Account margin_level reached {margin_level} (Threshold: <= {settings['margin_alert']})")

    if equity is not None and equity <= settings['equity_alert']:
        messages.append(f"Account equity reached {equity} (Threshold: <= {settings['equity_alert']})")

    return messages
