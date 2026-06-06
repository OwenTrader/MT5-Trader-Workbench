from fastapi import APIRouter, HTTPException

from python_service.app.quant import runtime as quant_runtime
from python_service.app.quant.backtest_models import BacktestRunRequest
from python_service.app.quant.backtest_service import run_backtest


router = APIRouter(prefix='/python-quant/backtests')


@router.get('/strategies')
def get_backtest_strategies():
    return quant_runtime.list_available_strategies()


@router.post('/run')
def run_quant_backtest(payload: BacktestRunRequest):
    try:
        quant_runtime.get_account_by_id(payload.account_id)
        return run_backtest(**payload.model_dump())
    except (LookupError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
