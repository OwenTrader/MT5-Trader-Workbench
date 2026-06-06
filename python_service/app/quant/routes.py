from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from python_service.app.quant import runtime as quant_runtime
from python_service.app.quant.market_data import backfill_from_mt5
from python_service.app.quant.models import Timeframe


router = APIRouter(prefix='/python-quant')
DEFAULT_MARKET_DATA_PATH = Path('storage/python_quant/market_data.sqlite3')


class QuantJobCreateRequest(BaseModel):
    name: str
    account_id: str
    strategy_id: str
    symbol: str
    timeframe: Timeframe
    lot: float

    @field_validator('symbol')
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return quant_runtime.normalize_symbol(value)

    @field_validator('lot')
    @classmethod
    def validate_lot(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('lot must be greater than 0')
        return value


class QuantJobUpdateRequest(QuantJobCreateRequest):
    enabled: bool | None = None


class QuantBackfillRequest(BaseModel):
    account_id: str
    symbol: str
    timeframe: Timeframe
    bars: int = Field(default=500, ge=1)

    @field_validator('symbol')
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return quant_runtime.normalize_symbol(value)


@router.get('/overview')
def get_overview():
    return quant_runtime.build_overview()


@router.post('/jobs')
def create_job(payload: QuantJobCreateRequest):
    _require_account(payload.account_id)
    _require_strategy(payload.strategy_id)
    new_job = quant_runtime.add_job(payload.model_dump())
    return new_job.model_dump()


@router.put('/jobs/{job_id}')
def update_job(job_id: str, payload: QuantJobUpdateRequest):
    try:
        existing_job = quant_runtime.get_job(job_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    _require_account(payload.account_id)
    _require_strategy(payload.strategy_id)

    enabled = existing_job.enabled if payload.enabled is None else payload.enabled
    if enabled:
        try:
            quant_runtime.validate_unique_account_symbol(
                quant_runtime.load_all_jobs(),
                payload.account_id,
                payload.symbol,
                ignore_job_id=job_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        updated_job = quant_runtime.replace_job(job_id, payload.model_dump(exclude_none=True))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return updated_job.model_dump()


@router.delete('/jobs/{job_id}')
def delete_job(job_id: str):
    try:
        deleted_job = quant_runtime.remove_job(job_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return deleted_job.model_dump()


@router.post('/jobs/{job_id}/start')
def start_job(job_id: str):
    try:
        job = quant_runtime.get_job(job_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    _require_account(job.account_id)
    _require_strategy(job.strategy_id)

    try:
        quant_runtime.validate_unique_account_symbol(
            quant_runtime.load_all_jobs(),
            job.account_id,
            job.symbol,
            ignore_job_id=job_id,
        )
        updated_job = quant_runtime.set_job_enabled(job_id, True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return updated_job.model_dump()


@router.post('/jobs/{job_id}/stop')
def stop_job(job_id: str):
    try:
        updated_job = quant_runtime.set_job_enabled(job_id, False)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return updated_job.model_dump()


@router.post('/data/backfill')
def backfill_data(payload: QuantBackfillRequest):
    try:
        inserted_rows = request_backfill(
            account_id=payload.account_id,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            bars=payload.bars,
        )
    except LookupError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {'inserted_rows': inserted_rows}


def request_backfill(account_id: str, symbol: str, timeframe: Timeframe, bars: int) -> int:
    account = quant_runtime.get_account_by_id(account_id)
    return backfill_from_mt5(DEFAULT_MARKET_DATA_PATH, account, account_id, symbol, timeframe, bars)


def _require_account(account_id: str) -> dict:
    try:
        return quant_runtime.get_account_by_id(account_id)
    except LookupError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _require_strategy(strategy_id: str) -> None:
    try:
        quant_runtime.ensure_strategy_exists(strategy_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
