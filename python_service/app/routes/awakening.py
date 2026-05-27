from fastapi import APIRouter, HTTPException
from python_service.app.models.technical_analysis import TechnicalAnalysisRequest
from python_service.app.services.awakening_service import generate_report

router = APIRouter()

@router.post('/awakening/report')
def get_report(req: TechnicalAnalysisRequest):
    try:
        data = generate_report(req.symbol)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
