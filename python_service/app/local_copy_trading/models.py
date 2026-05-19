from typing import Literal

from pydantic import BaseModel, field_validator


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
    symbol: str
    lot_multiplier: float = 1
    is_active: bool = True

    @field_validator('symbol')
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class SyncEvent(BaseModel):
    id: str = ''
    relationship_id: str
    source_account_id: str
    follower_account_id: str
    position_id: str = ''
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
