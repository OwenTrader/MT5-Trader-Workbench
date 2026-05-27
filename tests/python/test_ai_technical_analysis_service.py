import io
import json
import urllib.error

import pytest

from python_service.app.models.settings import Settings
from python_service.app.services import ai_technical_analysis_service


class FakeHttpResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_generate_ai_analysis_rejects_missing_ai_settings(monkeypatch):
    monkeypatch.setattr(ai_technical_analysis_service, 'get_settings', lambda: Settings())

    with pytest.raises(ValueError, match='AI base URL and API key are required'):
        ai_technical_analysis_service.generate_ai_analysis('XAUUSD')


def test_generate_ai_analysis_sends_100_candles_json_to_openai_compatible_endpoint(monkeypatch):
    captured = {}
    monkeypatch.setattr(ai_technical_analysis_service, 'get_settings', lambda: Settings(ai_base_url='https://example.test/v1', ai_api_key='sk-test', ai_model='gpt-4o-mini', ai_timeframe='H1', ai_candles_count=120, ai_temperature=0.4, ai_system_prompt='Focus on trend continuation.'))
    monkeypatch.setattr(ai_technical_analysis_service, 'get_recent_candles', lambda symbol, timeframe=None, count=100, allow_launch=False: [
        {
            'time': '2026-05-27T00:00:00+00:00',
            'open': 1.0,
            'high': 1.1,
            'low': 0.9,
            'close': 1.05,
            'volume': 10.0,
        }
        for _ in range(count)
    ])

    def fake_urlopen(request, timeout=30):
        captured['url'] = request.full_url
        captured['headers'] = dict(request.header_items())
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return FakeHttpResponse({'choices': [{'message': {'content': '## Market Structure\nBullish'}}]})

    monkeypatch.setattr(ai_technical_analysis_service.urllib.request, 'urlopen', fake_urlopen)

    result = ai_technical_analysis_service.generate_ai_analysis('XAUUSD')

    assert result.symbol == 'XAUUSD'
    assert result.timeframe == 'H1'
    assert result.candles_count == 120
    assert result.analysis_markdown == '## Market Structure\nBullish'
    assert result.used_model == 'gpt-4o-mini'
    assert captured['url'] == 'https://example.test/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer sk-test'
    assert captured['body']['model'] == 'gpt-4o-mini'
    assert captured['body']['temperature'] == 0.4
    assert 'Candles JSON' in captured['body']['messages'][1]['content']
    assert 'Additional user instructions' in captured['body']['messages'][1]['content']


def test_generate_ai_analysis_surfaces_provider_http_errors(monkeypatch):
    monkeypatch.setattr(ai_technical_analysis_service, 'get_settings', lambda: Settings(ai_base_url='https://example.test/v1', ai_api_key='sk-test'))
    monkeypatch.setattr(ai_technical_analysis_service, 'get_recent_candles', lambda symbol, timeframe=None, count=100, allow_launch=False: [
        {'time': '2026-05-27T00:00:00+00:00', 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.05, 'volume': 10.0}
        for _ in range(count)
    ])

    def fake_urlopen(request, timeout=30):
        raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', hdrs=None, fp=io.BytesIO(b'bad key'))

    monkeypatch.setattr(ai_technical_analysis_service.urllib.request, 'urlopen', fake_urlopen)

    with pytest.raises(ValueError, match='AI provider HTTP 401: bad key'):
        ai_technical_analysis_service.generate_ai_analysis('XAUUSD')


def test_generate_ai_analysis_allows_mt5_launch_for_candle_fetch(monkeypatch):
    seen = {}
    monkeypatch.setattr(ai_technical_analysis_service, 'get_settings', lambda: Settings(ai_base_url='https://example.test/v1', ai_api_key='sk-test', ai_timeframe='M15'))

    def fake_get_recent_candles(symbol, timeframe=None, count=100, allow_launch=False):
        seen['allow_launch'] = allow_launch
        seen['timeframe'] = timeframe
        seen['count'] = count
        return [
            {'time': '2026-05-27T00:00:00+00:00', 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.05, 'volume': 10.0}
            for _ in range(count)
        ]

    monkeypatch.setattr(ai_technical_analysis_service, 'get_recent_candles', fake_get_recent_candles)
    monkeypatch.setattr(ai_technical_analysis_service.urllib.request, 'urlopen', lambda request, timeout=30: FakeHttpResponse({'choices': [{'message': {'content': 'ok'}}]}))

    ai_technical_analysis_service.generate_ai_analysis('XAUUSD')

    assert seen['allow_launch'] is True
    assert seen['timeframe'] == ai_technical_analysis_service.TIMEFRAME_MAP['M15'][1]
    assert seen['count'] == 100


def test_generate_ai_analysis_uses_mt5_timeframe_constants_for_higher_frames(monkeypatch):
    seen = {}
    monkeypatch.setattr(ai_technical_analysis_service, 'get_settings', lambda: Settings(ai_base_url='https://example.test/v1', ai_api_key='sk-test', ai_timeframe='H1'))

    def fake_get_recent_candles(symbol, timeframe=None, count=100, allow_launch=False):
        seen['timeframe'] = timeframe
        return [
            {'time': '2026-05-27T00:00:00+00:00', 'open': 1.0, 'high': 1.1, 'low': 0.9, 'close': 1.05, 'volume': 10.0}
            for _ in range(count)
        ]

    monkeypatch.setattr(ai_technical_analysis_service, 'get_recent_candles', fake_get_recent_candles)
    monkeypatch.setattr(ai_technical_analysis_service.urllib.request, 'urlopen', lambda request, timeout=30: FakeHttpResponse({'choices': [{'message': {'content': 'ok'}}]}))

    ai_technical_analysis_service.generate_ai_analysis('XAUUSD')

    assert seen['timeframe'] == ai_technical_analysis_service.TIMEFRAME_MAP['H1'][1]
