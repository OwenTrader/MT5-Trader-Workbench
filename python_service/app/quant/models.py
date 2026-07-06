from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


Timeframe = Literal['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
QuantJobStatus = Literal['stopped', 'running', 'error']
SignalAction = Literal['buy', 'sell', 'close', 'hold']
ExecutionMode = Literal['paper', 'live']
QuantJobEventType = Literal['signal_generated', 'order_skipped_paper', 'order_sent', 'strategy_error']


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuantJob(BaseModel):
    id: str = Field(default_factory=lambda: f'job-{uuid4().hex[:12]}')
    name: str
    account_id: str
    strategy_id: str
    symbol: str
    timeframe: Timeframe
    lot: float
    execution_mode: ExecutionMode = 'paper'
    enabled: bool = False
    status: QuantJobStatus = 'stopped'
    last_signal: SignalAction | None = None
    last_error: str | None = None
    last_bar_time: str | None = None
    updated_at: str = Field(default_factory=utc_now_iso)


class QuantJobEvent(BaseModel):
    id: str = Field(default_factory=lambda: f'event-{uuid4().hex[:12]}')
    job_id: str
    event_type: QuantJobEventType
    message: str
    details: dict[str, object] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)
