from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Account(BaseModel):
    id: str = ''
    name: str
    connection_type: Literal['mt5_terminal', 'mt5_api', 'simulated'] = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True


SourceAccount = Account
FollowerAccount = Account


class CopyRelationship(BaseModel):
    id: str = ''
    source_account_id: str
    follower_account_id: str
    symbol: str = ''
    source_symbol: str = ''
    follower_symbol: str = ''
    lot_multiplier: float = 1
    volume_mode: Literal['multiplier', 'fixed', 'equity_ratio', 'risk_percent'] = 'multiplier'
    max_lot: float = 0
    risk_percent: float = 1
    sync_sl_tp: bool = False
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

    @field_validator('max_lot')
    @classmethod
    def validate_max_lot(cls, value: float) -> float:
        if value < 0:
            raise ValueError('max_lot must not be negative')
        return value

    @field_validator('risk_percent')
    @classmethod
    def validate_risk_percent(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('risk_percent must be greater than 0')
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


@dataclass(frozen=True)
class CopyResult:
    """Outcome of one copy action.

    ``status`` separates the three things that can happen to a copy, because
    they must be handled differently downstream:

    ``copied``
        An order was accepted (or the position already matched).
    ``failed``
        The broker or the session refused. Retried on the next tick.
    ``skipped``
        A pre-trade guard refused. Not a failure, so it must not count towards
        the consecutive-failure breaker, and the copy is retried on a later tick
        once the limit that fired no longer applies.
    """

    success: bool
    status: Literal['copied', 'failed', 'skipped'] = 'copied'
    message: str = ''
    follower_position_id: str = ''
    follower_order_id: str = ''


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
    accounts: list[Account] = Field(default_factory=list)
    relationships: list[CopyRelationship] = Field(default_factory=list)
    events: list[SyncEvent] = Field(default_factory=list)
    last_error: str | None = None
    last_checked_at: str | None = None

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_account_lists(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        merged_accounts: list[Any] = []
        seen_ids: set[str] = set()

        for item in [
            *(normalized.get('accounts') or []),
            *(normalized.get('source_accounts') or []),
            *(normalized.get('follower_accounts') or []),
        ]:
            account_id = ''
            if isinstance(item, dict):
                account_id = str(item.get('id') or '')
            else:
                account_id = str(getattr(item, 'id', '') or '')

            if account_id and account_id in seen_ids:
                continue

            if account_id:
                seen_ids.add(account_id)
            merged_accounts.append(item)

        normalized['accounts'] = merged_accounts
        normalized.pop('source_accounts', None)
        normalized.pop('follower_accounts', None)
        return normalized


class LocalCopyTradingRuntimeUpdate(BaseModel):
    enabled: bool | None = None
    poll_interval_seconds: float | None = None


class CopyTradingRiskSettings(BaseModel):
    """Optional pre-trade limits.

    A value of 0 disables the corresponding rule, so the default settings impose
    no restrictions and an existing install keeps behaving as before.
    """

    max_volume_per_symbol: float = 0
    max_positions_per_symbol: int = 0
    max_daily_open_count: int = 0
    max_daily_loss: float = 0
    min_margin_level: float = 0
    max_consecutive_failures: int = 3

    @field_validator(
        'max_volume_per_symbol',
        'max_positions_per_symbol',
        'max_daily_open_count',
        'max_daily_loss',
        'min_margin_level',
        'max_consecutive_failures',
    )
    @classmethod
    def validate_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError('risk limits must not be negative; 0 disables the rule')
        return value
