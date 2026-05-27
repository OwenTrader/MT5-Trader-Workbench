from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Literal, Any
import MetaTrader5 as mt5
from python_service.app.services.mt5_service import is_mt5_running, launch_mt5, init_mt5, get_account_info, get_positions, verify_mt5_path_connection
from python_service.app.routes.settings import get_settings

router = APIRouter()

class VerifyPathRequest(BaseModel):
    path: str

@router.post('/mt5/verify_path')
def verify_mt5_path(req: VerifyPathRequest):
    if not req.path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    success, message, terminal_info = verify_mt5_path_connection(req.path)
    if success:
        return {
            'status': 'ok',
            'message': 'Connected successfully',
            'terminal_info': terminal_info,
        }

    return {
        'status': 'error',
        'message': message,
    }

@router.get('/mt5/status')
def get_mt5_status():
    return {
        'is_running': is_mt5_running(),
        'is_connected': mt5.terminal_info() is not None if is_mt5_running() else False
    }

@router.get('/mt5/account')
def get_mt5_account():
    return get_account_info(allow_launch=False)

@router.get('/mt5/positions')
def get_mt5_positions():
    return get_positions(allow_launch=False)

@router.post('/mt5/launch')
def mt5_launch():
    settings = get_settings()
    # init_mt5 now handles the logic: first check open, then try from path
    success = init_mt5(path=settings.mt5_path, allow_launch=True, prefer_existing=False)
    
    if success:
        return {'status': 'ok', 'message': 'MT5 connected successfully'}
    else:
        return {
            'status': 'error', 
            'message': '检测到MT5未启动，请手动设置mt5路径后重试'
        }
class VerifyAlertRequest(BaseModel):
    symbol: str
    price: float
    condition: Literal['above', 'below']

@router.post('/mt5/verify_alert')
def verify_alert(req: VerifyAlertRequest):
    if not is_mt5_running():
        raise HTTPException(status_code=503, detail="MT5 is not running")
    
    # Ensure symbol is selected/exists
    symbol_info = mt5.symbol_info(req.symbol)
    if symbol_info is None:
        if not mt5.symbol_select(req.symbol, True):
            return {
                'status': 'error',
                'type': 'symbol',
                'message': f"品种无效: 找不到符号 '{req.symbol}'"
            }
        symbol_info = mt5.symbol_info(req.symbol)

    # Get latest price
    tick = mt5.symbol_info_tick(req.symbol)
    if tick is None:
        return {
            'status': 'error',
            'type': 'price',
            'message': f"无法获取 '{req.symbol}' 的现价，请检查网络或品种设置"
        }
    
    current_price = tick.bid
    
    # 1. Directional Validation
    if req.condition == 'above' and req.price <= current_price:
        return {
            'status': 'error',
            'type': 'price',
            'message': f"价格设置无效: 涨破预警的目标价 ({req.price}) 必须高于当前价 ({current_price:.5f})"
        }
    if req.condition == 'below' and req.price >= current_price:
        return {
            'status': 'error',
            'type': 'price',
            'message': f"价格设置无效: 跌破预警的目标价 ({req.price}) 必须低于当前价 ({current_price:.5f})"
        }

    # 2. 10% Range Validation
    diff_pct = abs(req.price - current_price) / current_price
    if diff_pct > 0.1:
        return {
            'status': 'error',
            'type': 'price',
            'message': f"价格偏离过大: 目标价 {req.price} 与现价 {current_price:.5f} 相差超过 10% (当前差值: {diff_pct*100:.1f}%)"
        }
    
    return {
        'status': 'ok',
        'current_price': current_price
    }

VerifyPathRequest.model_rebuild()
VerifyAlertRequest.model_rebuild()
