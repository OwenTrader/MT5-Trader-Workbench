from pydantic import BaseModel


class RiskControlSettings(BaseModel):
    margin_alert: float = 200
    equity_alert: float = 1000
