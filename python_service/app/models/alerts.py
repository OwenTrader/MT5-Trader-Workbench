from pydantic import BaseModel, field_validator
from typing import Literal

class PriceAlert(BaseModel):
    id: str = ""
    symbol: str
    price: float
    condition: Literal['above', 'below']
    is_active: bool = True
    is_triggered: bool = False
    comment: str = ''

class VolatilityAlert(BaseModel):
    id: str
    symbol: str
    threshold_points: float
    timeframe_seconds: int
    is_active: bool = True
    is_triggered: bool = False
    comment: str = ''

class IndicatorAlert(BaseModel):
    id: str = ""
    symbol: str
    timeframe: str  # e.g., 'M1', 'M5', 'H1'
    indicator_type: str = 'RSI'
    period: int = 14
    condition: Literal['above', 'below']
    threshold: float
    is_active: bool = True
    is_triggered: bool = False
    comment: str = ''


class OrderBroadcastRule(BaseModel):
    id: str = ""
    symbol: str
    is_active: bool = True

    @field_validator('symbol')
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()
