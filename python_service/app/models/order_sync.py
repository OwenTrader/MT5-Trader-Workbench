from pydantic import BaseModel, field_validator


class TopStepAccountCredential(BaseModel):
    id: str = ''
    name: str = ''
    user_name: str
    api_key: str
    account_id: int
    live: bool = False
    is_active: bool = True


class OrderSymbolMapping(BaseModel):
    id: str = ''
    mt5_symbol: str
    topstep_contract_id: str
    topstep_display_name: str = ''
    quantity_multiplier: float = 1
    mt5_lots: float = 1
    topstep_contracts: int = 1
    is_active: bool = True

    @field_validator('mt5_symbol')
    @classmethod
    def normalize_mt5_symbol(cls, value: str) -> str:
        return value.strip().upper()


class SyncedOrder(BaseModel):
    mt5_ticket: int
    mt5_symbol: str
    mt5_volume: float = 0
    topstep_account_id: int
    topstep_contract_id: str
    topstep_order_id: int | None = None
    side: str
    size: int
    status: str = 'open'
    opened_at: str
    closed_at: str | None = None
    last_error: str | None = None
    blocked_reason: str | None = None


class OrderSyncState(BaseModel):
    enabled: bool = False
    poll_interval_seconds: float = 1
    block_high_frequency_orders: bool = False
    high_frequency_window_seconds: float = 5
    credentials: list[TopStepAccountCredential] = []
    mappings: list[OrderSymbolMapping] = []
    synced_orders: list[SyncedOrder] = []
    last_error: str | None = None
    last_checked_at: str | None = None


class OrderSyncConfigUpdate(BaseModel):
    enabled: bool
    poll_interval_seconds: float = 1
    block_high_frequency_orders: bool = False
    high_frequency_window_seconds: float = 5
    credentials: list[TopStepAccountCredential]
    mappings: list[OrderSymbolMapping]
