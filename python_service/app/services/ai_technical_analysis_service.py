from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from python_service.app.models.technical_analysis import TechnicalAnalysisResponse
from python_service.app.routes.settings import get_settings
from python_service.app.services.mt5_service import get_recent_candles, mt5


DEFAULT_AI_MODEL = 'gpt-4.1-mini'
DEFAULT_TIMEFRAME_LABEL = 'M15'
PROMPT_VERSION = 'v1'
TIMEFRAME_MAP = {
    'M1': ('M1', getattr(mt5, 'TIMEFRAME_M1', 1)),
    'M5': ('M5', getattr(mt5, 'TIMEFRAME_M5', 5)),
    'M15': ('M15', getattr(mt5, 'TIMEFRAME_M15', 15)),
    'M30': ('M30', getattr(mt5, 'TIMEFRAME_M30', 30)),
    'H1': ('H1', getattr(mt5, 'TIMEFRAME_H1', 16385)),
    'H4': ('H4', getattr(mt5, 'TIMEFRAME_H4', 16388)),
    'D1': ('D1', getattr(mt5, 'TIMEFRAME_D1', 16408)),
}


def normalize_ai_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip('/')
    if normalized.endswith('/chat/completions'):
        return normalized
    if normalized.endswith('/v1'):
        return f'{normalized}/chat/completions'
    return f'{normalized}/chat/completions'


def build_ai_analysis_prompt(symbol: str, timeframe: str, candles: list[dict], extra_system_prompt: str = '') -> str:
    candles_json = json.dumps(candles, ensure_ascii=False, separators=(',', ':'))
    custom_prompt = f'Additional user instructions:\n{extra_system_prompt.strip()}\n\n' if extra_system_prompt.strip() else ''
    return (
        'You are a disciplined single-timeframe technical analyst. '
        'Analyze only the provided JSON candle data and do not invent news, indicators, or unseen prices.\n\n'
        f'Symbol: {symbol}\n'
        f'Timeframe: {timeframe}\n'
        f'Candle count: {len(candles)}\n\n'
        'Return concise markdown with these sections exactly:\n'
        '## Market Structure\n'
        '## Trend Bias\n'
        '## Key Levels\n'
        '## Momentum / Volatility Observations\n'
        '## Bullish Scenario\n'
        '## Bearish Scenario\n'
        '## Invalidation / Risk Notes\n'
        '## Short Execution Summary\n\n'
        f'{custom_prompt}'
        'End with a short educational disclaimer that this is analysis, not financial advice.\n\n'
        f'Candles JSON:\n{candles_json}'
    )


def resolve_timeframe(value: str) -> tuple[str, int]:
    normalized = value.strip().upper() if value.strip() else DEFAULT_TIMEFRAME_LABEL
    return TIMEFRAME_MAP.get(normalized, TIMEFRAME_MAP[DEFAULT_TIMEFRAME_LABEL])


def _read_openai_response(response_body: str) -> str:
    payload = json.loads(response_body) if response_body else {}
    choices = payload.get('choices') or []
    if not choices:
        raise ValueError('AI response did not include choices')

    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text_parts = [item.get('text', '') for item in content if isinstance(item, dict)]
        combined = ''.join(text_parts).strip()
        if combined:
            return combined
    raise ValueError('AI response did not include message content')


def generate_ai_analysis(symbol: str) -> TechnicalAnalysisResponse:
    settings = get_settings()
    ai_base_url = settings.ai_base_url.strip()
    ai_api_key = settings.ai_api_key.strip()
    model_name = settings.ai_model.strip() or DEFAULT_AI_MODEL
    timeframe_label, timeframe_value = resolve_timeframe(settings.ai_timeframe)
    candles_count = max(20, min(int(settings.ai_candles_count or 100), 300))
    temperature = min(max(float(settings.ai_temperature), 0.0), 2.0)
    system_prompt = settings.ai_system_prompt or ''
    if not ai_base_url or not ai_api_key:
        raise ValueError('AI base URL and API key are required')

    normalized_symbol = symbol.strip().upper()
    candles = get_recent_candles(normalized_symbol, timeframe=timeframe_value, count=candles_count, allow_launch=True)
    if len(candles) < candles_count:
        raise ValueError(f'Unable to fetch the latest {candles_count} candles from MT5')

    prompt = build_ai_analysis_prompt(normalized_symbol, timeframe_label, candles, system_prompt)
    body = json.dumps({
        'model': model_name,
        'messages': [
            {'role': 'system', 'content': 'You produce disciplined, structured technical analysis.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': temperature,
    }).encode('utf-8')
    request = urllib.request.Request(
        normalize_ai_base_url(ai_base_url),
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {ai_api_key}',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise ValueError(f'AI provider HTTP {exc.code}: {detail}') from exc
    except urllib.error.URLError as exc:
        raise ValueError(f'AI provider request failed: {exc.reason}') from exc

    analysis_markdown = _read_openai_response(response_body)
    return TechnicalAnalysisResponse(
        symbol=normalized_symbol,
        timeframe=timeframe_label,
        candles_count=len(candles),
        prompt_version=PROMPT_VERSION,
        analysis_markdown=analysis_markdown,
        used_model=model_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
