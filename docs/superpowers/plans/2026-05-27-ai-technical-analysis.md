# AI Technical Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing awakening-based technical analysis flow with an AI-powered workflow that sends the most recent 100 candles as JSON to a configurable OpenAI-compatible endpoint and returns AI-generated analysis inside the current app flow.

**Architecture:** The renderer will expose AI settings fields (`baseUrl`, `apiKey`) in the Settings page and gate the technical analysis action on those fields being present. The backend will replace the current awakening report route/service with a new AI analysis service that fetches recent MT5 candles, normalizes them into a compact JSON payload, builds a carefully designed prompt, calls an OpenAI-compatible API, and returns structured analysis content to the renderer. Existing awakening Python reporting code will be removed from the technical-analysis execution path but left isolated unless explicitly deleted in follow-up cleanup.

**Tech Stack:** Electron, React, Zustand, FastAPI, Python, MT5 Python API, OpenAI-compatible REST API, `@ai-sdk/openai` reference contract, project-local settings JSON storage.

---

## File Structure

### Existing files to modify

- `src/renderer/src/pages/TechnicalAnalysisPage.tsx`
  Purpose: Replace the current "generate and open HTML file" behavior with an in-app AI analysis request/response flow, explicitly load settings through `useSettingsStore`, and show clear empty/loading/error states.

- `src/renderer/src/pages/SettingsPage.tsx`
  Purpose: Add editable fields for AI `baseUrl` and `apiKey`, and persist them through the existing settings flow.

- `src/renderer/src/stores/settings-store.ts`
  Purpose: Extend the typed settings store with the new AI settings fields and defaults.

- `src/renderer/src/i18n/messages.ts`
  Purpose: Add UI copy for AI settings, validation, technical analysis page labels, and request state strings in both Chinese and English.

- `python_service/app/models/settings.py`
  Purpose: Extend backend settings schema with `ai_base_url` and `ai_api_key`.

- `python_service/app/routes/settings.py`
  Purpose: Keep backend settings persistence aligned with the expanded settings schema and existing storage behavior.

- `python_service/app/routes/awakening.py`
  Purpose: Replace the existing single-symbol awakening report route contract with an AI analysis request/response contract.

- `python_service/app/services/mt5_service.py`
  Purpose: Add or expose a reusable helper for fetching the most recent candles from the currently connected MT5 session without introducing a second parallel MT5 access pattern.

- `python_service/app/services/streaming_service.py`
  Purpose: Reuse or align symbol lookup conventions if the new AI analysis candle-fetch path needs suffix-aware symbol resolution.

- `python_service/app/services/awakening_service.py`
  Purpose: Replace the old six-engine HTML-report implementation with the new AI analysis orchestration, or reduce it to a compatibility wrapper that delegates to the new AI service during migration.

- `storage/settings.default.json`
  Purpose: Seed the new AI settings keys in the default settings shape used for first run and packaged copy flows.

- `storage/settings.local.json`
  Purpose: Keep the development local settings shape aligned with the expanded settings contract if the repo currently tracks this file.

- `tests/python/test_settings.py`
  Purpose: Extend backend settings persistence coverage to include `ai_base_url` and `ai_api_key`.

- `tests/python/test_awakening_service.py`
  Purpose: Update, replace, or explicitly retire the old awakening-service tests once the route path is no longer backed by the old six-report pipeline.

### New files to create

- `python_service/app/models/technical_analysis.py`
  Purpose: Hold request/response Pydantic models for AI technical analysis, including candle schema and response shape.

- `python_service/app/services/ai_technical_analysis_service.py`
  Purpose: Fetch candles, format payload, build the prompt, call the OpenAI-compatible endpoint, parse the result, and return structured data.

- `tests/python/test_ai_technical_analysis_service.py`
  Purpose: Focused unit tests for candle normalization, prompt composition, AI request building, settings validation, and response parsing.

- `tests/python/test_technical_analysis_routes.py`
  Purpose: Route-level tests for request validation, missing configuration handling, and happy-path JSON response behavior.

- `src/renderer/src/test/technical-analysis-page.test.tsx`
  Purpose: Renderer tests for disabled button behavior, settings-required messaging, loading state, and successful AI analysis rendering.

- `src/renderer/src/test/settings-page-ai-config.test.tsx`
  Purpose: Renderer tests for the new AI settings fields and persistence flow.

## Prompt Design Requirements

The AI prompt must be treated as product logic, not an afterthought. The implementation should include a dedicated prompt builder that:

- States the AI role as a disciplined single-timeframe technical analyst for the provided timeframe, not a financial advisor.
- Explicitly says the AI must analyze only the provided JSON candles and must not invent unseen prices, indicators, or news.
- Includes symbol, timeframe, candle count, and raw JSON candles.
- Requests output in a predictable structured format with sections such as:
  - Market Structure
  - Trend Bias
  - Key Levels
  - Momentum / Volatility Observations
  - Bullish Scenario
  - Bearish Scenario
  - Invalidation / Risk Notes
  - Short Execution Summary
- Forces concise, action-oriented language.
- Includes a safety note that the output is educational analysis, not trade execution advice.

## API Contract Target

The new backend route should return JSON directly consumable by the renderer instead of a filesystem path:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "candles_count": 100,
  "prompt_version": "v1",
  "analysis_markdown": "## Market Structure\n...",
  "used_model": "gpt-4.1-mini",
  "generated_at": "2026-05-27T12:00:00+00:00"
}
```

The request should remain minimal unless product requirements expand:

```json
{
  "symbol": "XAUUSD"
}
```

If needed, multiple timeframes can be introduced later, but this plan intentionally uses one backend timeframe source (`M15`) and makes that explicit in the prompt and response.

## Task Breakdown

### Task 1: Add AI Settings Schema End-to-End

**Files:**
- Modify: `python_service/app/models/settings.py`
- Modify: `python_service/app/routes/settings.py`
- Modify: `storage/settings.default.json`
- Modify: `storage/settings.local.json`
- Modify: `src/renderer/src/stores/settings-store.ts`
- Modify: `src/renderer/src/pages/SettingsPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/settings-page-ai-config.test.tsx`
- Test: `tests/python/test_settings.py`

- [ ] **Step 1: Write the failing renderer test for AI settings fields**

```tsx
it('renders and saves AI base URL and API key settings', async () => {
  // render settings page
  // type into AI base URL and API key fields
  // save settings
  // assert outgoing payload contains ai_base_url and ai_api_key
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- settings-page-ai-config`
Expected: FAIL because AI settings inputs do not exist yet.

- [ ] **Step 3: Write the failing backend settings persistence test**

```python
def test_settings_persists_ai_base_url_and_api_key(tmp_path):
    ...
    assert loaded['ai_base_url'] == 'https://example.com/v1'
    assert loaded['ai_api_key'] == 'sk-test'
```

- [ ] **Step 4: Run backend settings test to verify it fails**

Run: `pytest tests/python/test_settings.py -v`
Expected: FAIL because the new fields are not in the schema or persisted output yet.

- [ ] **Step 5: Add the new settings fields to backend and frontend models**

```python
class Settings(BaseModel):
    ai_base_url: str = ''
    ai_api_key: str = ''
```

```ts
export interface Settings {
  ai_base_url: string
  ai_api_key: string
}
```

- [ ] **Step 6: Add the new keys to seeded settings JSON files**

```json
"ai_base_url": "",
"ai_api_key": ""
```

- [ ] **Step 7: Add minimal Settings page UI for AI Base URL and API Key**

```tsx
<Label htmlFor="ai-base-url">{t('settings.general.aiBaseUrlLabel')}</Label>
<Input id="ai-base-url" value={localSettings.ai_base_url} />

<Label htmlFor="ai-api-key">{t('settings.general.aiApiKeyLabel')}</Label>
<Input id="ai-api-key" type="password" value={localSettings.ai_api_key} />
```

- [ ] **Step 8: Add i18n strings for the new settings fields**

```ts
aiBaseUrlLabel: 'AI Base URL'
aiApiKeyLabel: 'AI API Key'
```

- [ ] **Step 9: Run the renderer and backend settings tests to verify they pass**

Run: `npm run test:frontend -- settings-page-ai-config && pytest tests/python/test_settings.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/renderer/src/stores/settings-store.ts src/renderer/src/pages/SettingsPage.tsx src/renderer/src/i18n/messages.ts python_service/app/models/settings.py python_service/app/routes/settings.py storage/settings.default.json storage/settings.local.json src/renderer/src/test/settings-page-ai-config.test.tsx tests/python/test_settings.py
git commit -m "feat: add AI analysis settings fields"
```

### Task 2: Define Technical Analysis Request/Response Models

**Files:**
- Create: `python_service/app/models/technical_analysis.py`
- Test: `tests/python/test_technical_analysis_routes.py`

- [ ] **Step 1: Write the failing backend route contract test**

```python
def test_technical_analysis_route_returns_structured_json(client):
    # inject configured settings or mock settings lookup first
    response = client.post('/awakening/report', json={'symbol': 'XAUUSD'})
    assert response.status_code == 200
    assert 'analysis_markdown' in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_technical_analysis_routes.py::test_technical_analysis_route_returns_structured_json -v`
Expected: FAIL because the route still returns the old report shape.

- [ ] **Step 3: Add Pydantic request/response models**

```python
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
```

- [ ] **Step 4: Run the route contract test again**

Run: `pytest tests/python/test_technical_analysis_routes.py::test_technical_analysis_route_returns_structured_json -v`
Expected: still FAIL, but now models exist and route implementation is the next missing piece.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/models/technical_analysis.py tests/python/test_technical_analysis_routes.py
git commit -m "test: define technical analysis route contract"
```

### Task 3: Add Candle Fetch Helper For Recent 100 Bars

**Files:**
- Modify: `python_service/app/services/mt5_service.py`
- Test: `tests/python/test_mt5_service.py`

- [ ] **Step 1: Write the failing unit test for fetching the latest 100 candles**

```python
def test_get_recent_candles_returns_normalized_candle_dicts(monkeypatch):
    candles = get_recent_candles('XAUUSD', count=100)
    assert len(candles) == 100
    assert {'time', 'open', 'high', 'low', 'close', 'volume'} <= candles[0].keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_mt5_service.py::test_get_recent_candles_returns_normalized_candle_dicts -v`
Expected: FAIL because helper does not exist.

- [ ] **Step 3: Implement a minimal reusable candle helper**

```python
def get_recent_candles(symbol: str, timeframe: int = mt5.TIMEFRAME_M15, count: int = 100) -> list[dict]:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    ...
```

- [ ] **Step 4: Normalize timestamps and numeric fields**

```python
return [{
    'time': datetime.fromtimestamp(item['time'], timezone.utc).isoformat(),
    'open': float(item['open']),
    'high': float(item['high']),
    'low': float(item['low']),
    'close': float(item['close']),
    'volume': float(item['tick_volume']),
} for item in rates]
```

- [ ] **Step 5: Run the new unit test to verify it passes**

Run: `pytest tests/python/test_mt5_service.py::test_get_recent_candles_returns_normalized_candle_dicts -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python_service/app/services/mt5_service.py tests/python/test_mt5_service.py
git commit -m "feat: add MT5 candle fetch helper for AI analysis"
```

### Task 4: Implement AI Technical Analysis Service

**Files:**
- Create: `python_service/app/services/ai_technical_analysis_service.py`
- Modify: `python_service/app/services/streaming_service.py` (only if symbol resolution helper reuse is needed)
- Test: `tests/python/test_ai_technical_analysis_service.py`

- [ ] **Step 1: Write the failing service test for missing AI configuration**

```python
def test_generate_ai_analysis_rejects_missing_ai_settings(monkeypatch):
    with pytest.raises(ValueError, match='AI base URL and API key are required'):
        generate_ai_analysis('XAUUSD')
```

- [ ] **Step 2: Write the failing service test for prompt payload generation**

```python
def test_generate_ai_analysis_sends_100_candles_json_to_openai_compatible_endpoint(monkeypatch):
    result = generate_ai_analysis('XAUUSD')
    assert 'Market Structure' in result.analysis_markdown
```

- [ ] **Step 3: Run both tests to verify they fail**

Run: `pytest tests/python/test_ai_technical_analysis_service.py -v`
Expected: FAIL because service file does not exist.

- [ ] **Step 4: Implement prompt builder and request flow**

```python
def build_ai_analysis_prompt(symbol: str, candles: list[dict]) -> str:
    return f"""
You are a disciplined single-timeframe technical analyst reviewing M15 candles.
Analyze only the JSON candle data provided below.
...
Candles JSON:
{json.dumps(candles, ensure_ascii=False)}
""".strip()
```

- [ ] **Step 5: Implement OpenAI-compatible request transport**

Use standard HTTP request logic that targets:

```python
POST {ai_base_url}/chat/completions
Authorization: Bearer {ai_api_key}
```

and includes a model string kept local to the service, e.g. `gpt-4.1-mini`.

- [ ] **Step 6: Return structured analysis response data**

```python
return TechnicalAnalysisResponse(...)
```

- [ ] **Step 7: Run the service tests to verify they pass**

Run: `pytest tests/python/test_ai_technical_analysis_service.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add python_service/app/services/ai_technical_analysis_service.py tests/python/test_ai_technical_analysis_service.py python_service/app/services/streaming_service.py
git commit -m "feat: add AI technical analysis service"
```

### Task 5: Replace Awakening Route Logic With AI Analysis Route

**Files:**
- Modify: `python_service/app/routes/awakening.py`
- Modify: `python_service/app/services/awakening_service.py`
- Test: `tests/python/test_technical_analysis_routes.py`

- [ ] **Step 1: Expand route tests for success and backend validation failure**

```python
def test_route_returns_400_when_ai_config_missing(client):
    response = client.post('/awakening/report', json={'symbol': 'XAUUSD'})
    assert response.status_code == 400

def test_route_returns_analysis_json_on_success(client):
    # inject configured settings or mock service success first
    ...
```

- [ ] **Step 2: Run route tests to verify they fail**

Run: `pytest tests/python/test_technical_analysis_routes.py -v`
Expected: FAIL because route still calls old report generator.

- [ ] **Step 3: Replace route implementation to delegate to AI service**

```python
@router.post('/awakening/report')
def get_report(req: TechnicalAnalysisRequest):
    ...
```

- [ ] **Step 4: Convert the old awakening service into a compatibility wrapper or remove the old `generate_report` logic from the active route path**

Keep this minimal. Do not leave the route executing six report generators.

- [ ] **Step 5: Run route tests to verify they pass**

Run: `pytest tests/python/test_technical_analysis_routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python_service/app/routes/awakening.py python_service/app/services/awakening_service.py tests/python/test_technical_analysis_routes.py
git commit -m "feat: route technical analysis through AI service"
```

### Task 6: Rebuild Technical Analysis Page Around In-App AI Output

**Files:**
- Modify: `src/renderer/src/pages/TechnicalAnalysisPage.tsx`
- Modify: `src/renderer/src/stores/settings-store.ts`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/technical-analysis-page.test.tsx`

- [ ] **Step 1: Write the failing page test for disabled action when AI settings are missing**

```tsx
it('blocks AI analysis when base URL or API key is missing', async () => {
  expect(screen.getByRole('button', { name: /generate/i })).toBeDisabled()
})
```

- [ ] **Step 2: Write the failing page test for rendering returned analysis markdown/text**

```tsx
it('renders AI analysis after successful request', async () => {
  expect(await screen.findByText('Market Structure')).toBeInTheDocument()
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm run test:frontend -- technical-analysis-page`
Expected: FAIL because page only opens external HTML and has no in-app result UI.

- [ ] **Step 4: Implement minimal page state**

```tsx
const [analysis, setAnalysis] = useState<string | null>(null)
const aiConfigured = Boolean(settings.ai_base_url.trim() && settings.ai_api_key.trim())
```

- [ ] **Step 5: Load settings inside the page before evaluating the gate**

```tsx
const { settings, fetchSettings } = useSettingsStore()

useEffect(() => {
  void fetchSettings()
}, [fetchSettings])
```

- [ ] **Step 6: Replace the old external-file open flow with JSON rendering**

```tsx
const response = await fetch('http://127.0.0.1:8765/awakening/report', ...)
setAnalysis(data.analysis_markdown)
```

- [ ] **Step 7: Add loading, error, empty, and result states**

Keep the UI simple and readable. Do not introduce a markdown dependency unless truly necessary; plain pre-wrapped text is acceptable for minimal scope.

- [ ] **Step 8: Run page tests to verify they pass**

Run: `npm run test:frontend -- technical-analysis-page`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/renderer/src/pages/TechnicalAnalysisPage.tsx src/renderer/src/stores/settings-store.ts src/renderer/src/i18n/messages.ts src/renderer/src/test/technical-analysis-page.test.tsx
git commit -m "feat: render AI technical analysis in app"
```

### Task 7: Add Settings-Aware UX Copy And Validation

**Files:**
- Modify: `src/renderer/src/pages/TechnicalAnalysisPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/technical-analysis-page.test.tsx`

- [ ] **Step 1: Write the failing test for settings-required guidance**

```tsx
it('shows a message telling the user to fill AI base URL and API key first', () => {
  expect(screen.getByText(/fill AI base URL and API key/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:frontend -- technical-analysis-page`
Expected: FAIL because guidance text does not exist yet.

- [ ] **Step 3: Add concise UX copy and disabled-button explanation**

```tsx
{!aiConfigured ? <p>{t('technicalAnalysis.missingAiConfig')}</p> : null}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:frontend -- technical-analysis-page`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/pages/TechnicalAnalysisPage.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/technical-analysis-page.test.tsx
git commit -m "feat: add AI analysis configuration guidance"
```

### Task 8: Full Validation And Cleanup

**Files:**
- Modify: `python_service/app/services/awakening_service.py` (cleanup only if still carrying dead route logic)
- Test: `tests/python/test_ai_technical_analysis_service.py`
- Test: `tests/python/test_technical_analysis_routes.py`
- Test: `tests/python/test_awakening_service.py`
- Test: `src/renderer/src/test/technical-analysis-page.test.tsx`
- Test: `src/renderer/src/test/settings-page-ai-config.test.tsx`

- [ ] **Step 1: Run focused Python technical analysis tests**

Run: `pytest tests/python/test_ai_technical_analysis_service.py tests/python/test_technical_analysis_routes.py -v`
Expected: PASS

- [ ] **Step 2: Run focused frontend tests**

Run: `npm run test:frontend -- technical-analysis`
Expected: PASS

- [ ] **Step 3: Run full frontend suite**

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 4: Run full Python suite**

Run: `pytest tests/python`
Expected: PASS

- [ ] **Step 5: Do minimal cleanup of obsolete technical-analysis execution code**

Only remove code that is definitely unused after the route migration. Do not delete awakening docs IPC handlers unless they are proven unrelated and unused.

- [ ] **Step 6: Update or retire the old awakening service tests intentionally**

Run: `pytest tests/python/test_awakening_service.py -v`
Expected: Either PASS after compatibility updates, or replace/remove the file in the same commit with a clear explanation.

- [ ] **Step 7: Commit**

```bash
git add python_service/app/services/awakening_service.py tests/python src/renderer/src/test
git commit -m "refactor: replace awakening analysis flow with AI-based analysis"
```

## Implementation Notes

- Prefer a direct backend HTTP integration first; `@ai-sdk/openai` is a useful reference for OpenAI-compatible request shape, but this repository's active AI execution path is in Python, not Node.
- Keep scope narrow: one symbol request field, one timeframe source, 100 candles, one returned analysis string.
- Do not preserve the old browser-opened HTML report behavior unless product explicitly requires a fallback mode.
- If MT5 cannot provide candles, the backend should return a user-facing 400/503-style error rather than a vague 500.
- If the provided `ai_base_url` lacks a `/chat/completions` suffix, normalize it in one place.
- Store the API key in the same settings mechanism the app already uses, but note in code comments and follow-up documentation that this is local plaintext configuration.

## Review Checklist For The Implementer

- Does the button stay disabled when either `ai_base_url` or `ai_api_key` is blank?
- Does the route stop depending on the old six-report HTML generation path?
- Are exactly 100 candles serialized into the AI prompt payload?
- Is the prompt deterministic and reviewable in code?
- Are network failures turned into user-readable errors?
- Do both `npm run test:frontend` and `pytest tests/python` pass?
