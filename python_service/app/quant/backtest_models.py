from pydantic import BaseModel

from python_service.app.quant.models import Timeframe


class BacktestRunRequest(BaseModel):
    account_id: str
    strategy_id: str
    symbol: str
    timeframe: Timeframe
    start_at: str
    end_at: str


class BacktestStrategyRef(BaseModel):
    id: str
    name: str


class BacktestRange(BaseModel):
    start_at: str
    end_at: str


class BacktestSummary(BaseModel):
    total_return_pct: float
    trade_count: int
    win_rate_pct: float
    max_drawdown_pct: float


class BacktestEquityPoint(BaseModel):
    time: str
    equity: float


class BacktestTrade(BaseModel):
    entry_time: str
    exit_time: str
    side: str
    pnl: float


class BacktestResult(BaseModel):
    strategy: BacktestStrategyRef
    symbol: str
    timeframe: Timeframe
    range: BacktestRange
    summary: BacktestSummary
    equity_curve: list[BacktestEquityPoint]
    trades: list[BacktestTrade]
