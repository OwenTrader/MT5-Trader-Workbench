from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime, timezone
import MetaTrader5 as mt5

from python_service.app.db.kline_db import save_klines, get_kline_summary, delete_klines
from python_service.app.services.mt5_service import get_mt5_client, mt5_connection_lock, _resolve_mt5_timeframe, _parse_iso_datetime

router = APIRouter(prefix="/data-management", tags=["Data Management"])

class SyncRequest(BaseModel):
    symbol: str
    timeframe: str
    start_at: str
    end_at: str

@router.get("/summary")
def get_summary():
    try:
        return get_kline_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{symbol}/{timeframe}")
def delete_data(symbol: str, timeframe: str):
    try:
        delete_klines(symbol, timeframe)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
def sync_data(req: SyncRequest):
    client = get_mt5_client(allow_launch=False)
    if client is None:
        raise HTTPException(status_code=400, detail="MT5 is not connected.")

    try:
        tf = _resolve_mt5_timeframe(req.timeframe)
        start_dt = _parse_iso_datetime(req.start_at)
        end_dt = _parse_iso_datetime(req.end_at)

        # copy_rates_range talks to the process-wide MT5 connection; it must
        # run under the connection lock like every other MT5 call.
        with mt5_connection_lock():
            rates = client.copy_rates_range(req.symbol, tf, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            return {"success": True, "count": 0, "message": "No data found for the given range."}

        klines_data = []
        for rate in rates:
            payload = rate._asdict() if hasattr(rate, '_asdict') else dict(rate)
            klines_data.append({
                'time': int(payload['time']),
                'open': float(payload['open']),
                'high': float(payload['high']),
                'low': float(payload['low']),
                'close': float(payload['close']),
                'tick_volume': int(payload.get('tick_volume', 0)),
            })

        save_klines(req.symbol, req.timeframe, klines_data)

        return {"success": True, "count": len(klines_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
