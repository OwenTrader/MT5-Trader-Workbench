from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from python_service.app.db.kline_db import (
    create_review_session, get_review_sessions, get_review_session, delete_review_session,
    update_review_session_time, update_review_session_balance,
    open_trade, close_trade, get_session_trades,
    get_next_klines, get_klines
)
from python_service.app.services.mt5_service import _parse_iso_datetime

router = APIRouter(prefix="/trading-review", tags=["Trading Review"])


def get_contract_multiplier(symbol: str) -> float:
    """Contract size for the symbol, straight from the terminal when live.

    The heuristic table below is only the offline fallback; real symbols
    (broker suffixes, indices, CFDs) routinely differ from the guesses.
    """
    try:
        from python_service.app.services.mt5_service import mt5

        info = mt5.symbol_info(symbol)
        if info is not None:
            size = float(getattr(info, 'trade_contract_size', 0) or 0)
            if size > 0:
                return size
    except Exception:
        pass

    s = (symbol or "").upper()
    if "XAU" in s or "GOLD" in s:
        return 100.0
    if "XAG" in s or "SILVER" in s:
        return 5000.0
    if "BTC" in s or "ETH" in s or "SOL" in s or "CRYPTO" in s:
        return 1.0
    if "US30" in s or "NAS100" in s or "USTEC" in s or "SPX500" in s or "WS30" in s:
        return 1.0
    if "OIL" in s or "WTI" in s or "BRENT" in s:
        return 1000.0
    # Standard forex pairs (EURUSD, GBPUSD, USDJPY, AUDUSD, etc.)
    return 100000.0


def calculate_trade_profit(symbol: str, trade_type: str, open_price: float, close_price: float, lots: float) -> float:
    mult = get_contract_multiplier(symbol)
    diff = (close_price - open_price) if trade_type.lower() == 'buy' else (open_price - close_price)
    return diff * lots * mult


class CreateSessionRequest(BaseModel):
    symbol: str
    timeframe: str
    start_at: str
    end_at: str
    initial_balance: float

class NextCandleRequest(BaseModel):
    limit: int = 1

class OpenTradeRequest(BaseModel):
    type: str  # 'buy' or 'sell'
    open_price: float
    lots: float
    open_time: int
    sl: Optional[float] = None
    tp: Optional[float] = None

class CloseTradeRequest(BaseModel):
    trade_id: int
    close_price: float
    close_time: int

@router.get("/sessions")
async def list_sessions():
    try:
        return get_review_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions")
async def create_session(req: CreateSessionRequest):
    try:
        start_ts = int(_parse_iso_datetime(req.start_at).timestamp())
        end_ts = int(_parse_iso_datetime(req.end_at).timestamp())
        
        session_id = create_review_session(
            req.symbol, req.timeframe, start_ts, end_ts, req.initial_balance
        )
        return {"success": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int):
    try:
        delete_review_session(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: int):
    try:
        session = get_review_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        trades = get_session_trades(session_id)
        # Fetch initial candles up to current_time
        klines = get_klines(session['symbol'], session['timeframe'], session['start_time'], session['current_time'])
        
        return {
            "session": session,
            "trades": trades,
            "klines": klines
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/next")
async def next_candle(session_id: int, req: NextCandleRequest):
    try:
        session = get_review_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        next_klines = get_next_klines(session['symbol'], session['timeframe'], session['current_time'], req.limit)
        
        if not next_klines:
            return {"success": True, "klines": [], "finished": True, "triggered_trades": []}
            
        latest_time = next_klines[-1]['time']
        if latest_time > session['end_time']:
            # Filter strictly by end_time
            next_klines = [k for k in next_klines if k['time'] <= session['end_time']]
            if not next_klines:
                return {"success": True, "klines": [], "finished": True, "triggered_trades": []}
            latest_time = next_klines[-1]['time']
            
        # Check SL and TP triggers on incoming candles
        triggered_trades: List[Dict[str, Any]] = []
        trades = get_session_trades(session_id)
        current_balance = session['current_balance']

        for candle in next_klines:
            active_trades = [t for t in trades if t['close_time'] is None]
            for trade in active_trades:
                triggered = False
                close_price = 0.0

                if trade['type'] == 'buy':
                    if trade.get('sl') is not None and candle['low'] <= trade['sl']:
                        triggered = True
                        close_price = trade['sl']
                    elif trade.get('tp') is not None and candle['high'] >= trade['tp']:
                        triggered = True
                        close_price = trade['tp']
                elif trade['type'] == 'sell':
                    if trade.get('sl') is not None and candle['high'] >= trade['sl']:
                        triggered = True
                        close_price = trade['sl']
                    elif trade.get('tp') is not None and candle['low'] <= trade['tp']:
                        triggered = True
                        close_price = trade['tp']

                if triggered:
                    profit = calculate_trade_profit(
                        session['symbol'], trade['type'], trade['open_price'], close_price, trade['lots']
                    )
                    close_trade(trade['id'], candle['time'], close_price, profit)
                    current_balance += profit
                    trade['close_time'] = candle['time']
                    trade['close_price'] = close_price
                    trade['profit'] = profit
                    triggered_trades.append({
                        "id": trade['id'],
                        "type": trade['type'],
                        "close_time": candle['time'],
                        "close_price": close_price,
                        "profit": profit
                    })

        if triggered_trades:
            update_review_session_balance(session_id, current_balance)

        update_review_session_time(session_id, latest_time)
        return {
            "success": True,
            "klines": next_klines,
            "finished": False,
            "triggered_trades": triggered_trades,
            "current_balance": current_balance
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/trade")
async def execute_trade(session_id: int, req: OpenTradeRequest):
    try:
        trade_id = open_trade(
            session_id, req.type, req.open_time, req.open_price, req.lots, req.sl, req.tp
        )
        return {"success": True, "trade_id": trade_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/close")
async def execute_close_trade(session_id: int, req: CloseTradeRequest):
    try:
        session = get_review_session(session_id)
        trades = get_session_trades(session_id)
        trade = next((t for t in trades if t['id'] == req.trade_id), None)
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
            
        profit = calculate_trade_profit(
            session['symbol'], trade['type'], trade['open_price'], req.close_price, trade['lots']
        )
        
        close_trade(req.trade_id, req.close_time, req.close_price, profit)
        
        # Update balance
        new_balance = session['current_balance'] + profit
        update_review_session_balance(session_id, new_balance)
        
        return {"success": True, "profit": profit, "new_balance": new_balance}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
