from fastapi import APIRouter, HTTPException
from datetime import datetime
from python_service.app.services.history_service import get_performance_overview, get_daily_aggregated_stats

router = APIRouter()

@router.get("/overview")
async def overview():
    try:
        return get_performance_overview()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/daily")
async def daily_stats(from_date: str = None, to_date: str = None):
    try:
        # Default to last 30 days if not provided
        if from_date:
            start = datetime.fromisoformat(from_date)
        else:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() - (30 * 86400)
            start = datetime.fromtimestamp(start)
            
        if to_date:
            end = datetime.fromisoformat(to_date).replace(hour=23, minute=59, second=59)
        else:
            end = datetime.now()
            
        return get_daily_aggregated_stats(start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
