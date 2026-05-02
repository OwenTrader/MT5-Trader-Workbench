from pydantic import BaseModel
from typing import Literal

class AccountCondition(BaseModel):
    metric: Literal['margin_level', 'equity', 'balance', 'margin']
    threshold: float
    direction: Literal['above', 'below']
    is_active: bool = True
    comment: str = ''
