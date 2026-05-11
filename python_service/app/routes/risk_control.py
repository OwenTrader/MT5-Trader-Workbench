from fastapi import APIRouter

from python_service.app.models.risk_control import RiskControlSettings
from python_service.app.services.risk_control_service import load_risk_control_settings, persist_risk_control_settings


router = APIRouter(prefix='/risk-control')


@router.get('')
async def get_risk_control_settings() -> RiskControlSettings:
    return load_risk_control_settings()


@router.post('')
async def save_risk_control_settings(settings: RiskControlSettings):
    persist_risk_control_settings(settings)
    return {'status': 'ok'}
