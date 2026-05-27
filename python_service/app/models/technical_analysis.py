from pydantic import BaseModel


class TechnicalAnalysisRequest(BaseModel):
    symbol: str


class CandlePayload(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class TechnicalAnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    candles_count: int
    prompt_version: str
    analysis_markdown: str
    used_model: str
    generated_at: str
