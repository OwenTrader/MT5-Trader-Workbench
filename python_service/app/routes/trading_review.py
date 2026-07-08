from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from python_service.app.db.kline_db import (
    create_review_session, get_review_sessions, get_review_session, delete_review_session,
    update_review_session_time, update_review_session_balance,
    open_trade, close_trade, get_session_trades,
    get_next_klines, get_klines
)
from python_service.app.services.mt5_service import _parse_iso_datetime

router = APIRouter(prefix="/trading-review", tags=["Trading Review"])

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
        # Fetch a few initial candles up to current_time
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
            return {"success": True, "klines": [], "finished": True}
            
        latest_time = next_klines[-1]['time']
        if latest_time > session['end_time']:
            # Filter strictly by end_time
            next_klines = [k for k in next_klines if k['time'] <= session['end_time']]
            if not next_klines:
                return {"success": True, "klines": [], "finished": True}
            latest_time = next_klines[-1]['time']
            
        update_review_session_time(session_id, latest_time)
        return {"success": True, "klines": next_klines, "finished": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/trade")
async def execute_trade(session_id: int, req: OpenTradeRequest):
    try:
        trade_id = open_trade(session_id, req.type, req.open_time, req.open_price, req.lots)
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
            
        # Calculate profit
        # Simple forex formula (assuming lot size 100000, margin currency logic is simplified)
        # For simplicity, we just return the raw point difference scaled by lots
        # In a real app, you'd need the contract size and tick value. Here we do a basic approximation.
        diff = req.close_price - trade['open_price'] if trade['type'] == 'buy' else trade['open_price'] - req.close_price
        
        # We assume 1 lot = 100,000 units for standard pairs, but just a generic multiplier for now
        # Let's just use diff * lots * 100000 as a placeholder profit
        profit = diff * trade['lots'] * 100000 
        
        close_trade(req.trade_id, req.close_time, req.close_price, profit)
        
        # Update balance
        new_balance = session['current_balance'] + profit
        update_review_session_balance(session_id, new_balance)
        
        return {"success": True, "profit": profit, "new_balance": new_balance}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
