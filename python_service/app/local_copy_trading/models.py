from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class SourceAccount(BaseModel):
    id: str = ''
    name: str
    connection_type: Literal['mt5_terminal', 'mt5_api', 'simulated'] = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True


class FollowerAccount(BaseModel):
    id: str = ''
    name: str
    connection_type: Literal['mt5_terminal', 'mt5_api', 'simulated'] = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True


class CopyRelationship(BaseModel):
    id: str = ''
    source_account_id: str
    follower_account_id: str
    symbol: str = ''
    source_symbol: str = ''
    follower_symbol: str = ''
    lot_multiplier: float = 1
    is_active: bool = True

    @field_validator('symbol', 'source_symbol', 'follower_symbol')
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip()

    @field_validator('lot_multiplier')
    @classmethod
    def validate_lot_multiplier(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('lot_multiplier must be greater than 0')
        return value

    @model_validator(mode='after')
    def fill_symbol_mapping_defaults(self):
        if not self.source_symbol:
            self.source_symbol = self.symbol
        if not self.symbol:
            self.symbol = self.source_symbol
        if not self.follower_symbol:
            self.follower_symbol = self.source_symbol
        return self


class SyncEvent(BaseModel):
    id: str = ''
    relationship_id: str
    source_account_id: str
    follower_account_id: str
    position_id: str = ''
    follower_position_id: str = ''
    follower_order_id: str = ''
    symbol: str
    status: Literal['queued', 'copied', 'closed', 'failed', 'skipped'] = 'queued'
    message: str = ''
    created_at: str


class LocalCopyTradingState(BaseModel):
    enabled: bool = False
    poll_interval_seconds: float = 1
    source_accounts: list[SourceAccount] = []
    follower_accounts: list[FollowerAccount] = []
    relationships: list[CopyRelationship] = []
    events: list[SyncEvent] = []
    last_error: str | None = None
    last_checked_at: str | None = None


class LocalCopyTradingRuntimeUpdate(BaseModel):
    enabled: bool | None = None
    poll_interval_seconds: float | None = None
