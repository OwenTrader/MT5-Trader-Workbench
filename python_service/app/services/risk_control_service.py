import json
from pathlib import Path

from python_service.app.models.risk_control import RiskControlSettings


from python_service.app.services.storage_paths import risk_control_file


def load_risk_control_settings() -> RiskControlSettings:
    if not risk_control_file().exists():
        return RiskControlSettings()

    with risk_control_file().open('r', encoding='utf-8') as file:
        return RiskControlSettings(**json.load(file))


def persist_risk_control_settings(settings: RiskControlSettings) -> None:
    risk_control_file().parent.mkdir(parents=True, exist_ok=True)
    with risk_control_file().open('w', encoding='utf-8') as file:
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
