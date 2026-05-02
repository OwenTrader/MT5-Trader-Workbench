from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from python_service.app.services.awakening_service import generate_report

router = APIRouter()

class ReportRequest(BaseModel):
    symbol: str

@router.post('/awakening/report')
def get_report(req: ReportRequest):
    try:
        data = generate_report(req.symbol)
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
