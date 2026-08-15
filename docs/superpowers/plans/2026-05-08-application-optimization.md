# Application Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the app's delivery safety, alerting maintainability, navigation correctness, and incomplete product areas in the highest-value order.

**Architecture:** Start by fixing the test harness so backend work is verifiable without manual shell tweaks. Then split the highest-risk monolith (`streaming_service.py`) and the duplicated renderer alert behavior into small shared units, before tightening navigation state and completing the currently stubbed risk-control flow.

**Tech Stack:** Electron, React 18, TypeScript, Zustand, React Router, FastAPI, Pydantic, MetaTrader5 Python SDK, Vitest, Playwright, Pytest

---

## Priority Order

1. Stabilize Python test execution so backend changes are safely testable.
2. Decompose backend alert streaming logic to reduce regression risk in the polling loop.
3. Consolidate duplicated renderer alert-page behavior to reduce drift across modules.
4. Make navigation route-driven instead of local-state-driven to remove hidden UI state bugs.
5. Complete the risk-control feature end-to-end so the UI stops being a dead form.

## File Structure

- Create: `tests/python/conftest.py`
  Responsibility: Ensure `python_service` is importable from pytest without requiring manual `PYTHONPATH` in PowerShell.
- Modify: `README.md`
  Responsibility: Document the correct Python test command and remove the current gap between docs and reality.
- Modify: `python_service/app/services/streaming_service.py`
  Responsibility: Keep only the loop, websocket manager, and top-level orchestration.
- Create: `python_service/app/services/alert_dispatch_service.py`
  Responsibility: Build and send triggered alert notifications for price, volatility, indicator, and order broadcast flows.
- Create: `python_service/app/services/quote_snapshot_service.py`
  Responsibility: Collect MT5 quote snapshots and daily-open derived metadata.
- Create: `tests/python/test_alert_dispatch_service.py`
  Responsibility: Unit-test backend alert dispatch behavior without running the full streaming loop.
- Create: `tests/python/test_quote_snapshot_service.py`
  Responsibility: Unit-test quote collection and history trimming behavior.
- Create: `src/renderer/src/hooks/use-alert-trigger-effects.ts`
  Responsibility: Centralize sound playback and desktop-notification behavior shared by price, volatility, and indicator pages.
- Modify: `src/renderer/src/pages/PriceAlertsPage.tsx`
  Responsibility: Consume the shared alert-effect hook and keep page-specific form/list behavior only.
- Modify: `src/renderer/src/pages/VolatilityPage.tsx`
  Responsibility: Consume the shared alert-effect hook and keep page-specific form/list behavior only.
- Modify: `src/renderer/src/pages/IndicatorAlertsPage.tsx`
  Responsibility: Consume the shared alert-effect hook and keep page-specific form/list behavior only.
- Create: `src/renderer/src/test/use-alert-trigger-effects.test.tsx`
  Responsibility: Verify shared renderer alert side effects in one place.
- Modify: `src/renderer/src/App.tsx`
  Responsibility: Replace local `activeModule` branching with route-driven rendering.
- Modify: `src/renderer/src/layouts/workbench-shell.tsx`
  Responsibility: Read and update the active module from router location/navigation instead of local props.
- Modify: `src/renderer/src/components/module-nav.tsx`
  Responsibility: Emit route navigation instead of opaque string-only state changes.
- Modify: `src/renderer/src/pages/overlay-display-page.tsx`
  Responsibility: Remove route-adjacent debug logging and preserve overlay-only rendering behavior while navigation changes land.
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`
  Responsibility: Assert route-based navigation instead of local-state-only rendering.
- Modify: `src/renderer/src/pages/RiskControlPage.tsx`
  Responsibility: Consume persisted risk-control settings and submit updates.
- Create: `python_service/app/models/risk_control.py`
  Responsibility: Define persisted risk-control settings and runtime condition schema.
- Create: `python_service/app/routes/risk_control.py`
  Responsibility: Add backend load/save endpoints for risk-control settings.
- Create: `python_service/app/services/risk_control_service.py`
  Responsibility: Load, save, and evaluate risk-control conditions.
- Create: `storage/risk-control.json`
  Responsibility: Persist user-defined risk-control thresholds once backend save support is added.
- Modify: `python_service/app/main.py`
  Responsibility: Register the new risk-control routes and lifecycle usage if needed.
- Create: `tests/python/test_risk_control_routes.py`
  Responsibility: Verify backend CRUD behavior for risk-control settings.
- Create: `tests/python/test_risk_control_service.py`
  Responsibility: Verify risk threshold evaluation behavior.
- Create: `src/renderer/src/test/risk-control-page.test.tsx`
  Responsibility: Verify frontend risk-control load and save behavior with mocked backend responses.

### Task 1: Stabilize Python Test Entry Point

**Files:**
- Create: `tests/python/conftest.py`
- Modify: `README.md`
- Test: `tests/python/test_backend_lifespan.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app import main as backend_main

def test_backend_module_imports_from_pytest_process():
    assert backend_main.app is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH=''; pytest tests/python/test_backend_lifespan.py -v`
Expected: FAIL during collection with `ModuleNotFoundError: No module named 'python_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# tests/python/conftest.py
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

Also update `README.md` so the Python test section says to run `pytest tests/python` directly, without requiring manual `PYTHONPATH`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/python/test_backend_lifespan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/python/conftest.py README.md
git commit -m "test: make python suite runnable from pytest"
```

### Task 2: Extract Quote History Trimming And Quote Snapshot Assembly

**Files:**
- Create: `python_service/app/services/quote_snapshot_service.py`
- Modify: `python_service/app/services/streaming_service.py`
- Test: `tests/python/test_quote_snapshot_service.py`
- Test: `tests/python/test_streaming_service.py`

- [ ] **Step 1: Write the failing tests**

```python
from python_service.app.services.quote_snapshot_service import trim_price_history, append_quote_to_history

def test_append_quote_to_history_adds_entry_for_symbol():
    history = {}
    append_quote_to_history(history, 'XAUUSD', 3300.5, 100.0)
    assert history == {'XAUUSD': [{'price': 3300.5, 'timestamp': 100.0}]}

def test_trim_price_history_keeps_only_recent_entries():
    history = {'XAUUSD': [{'price': 1, 'timestamp': 10}, {'price': 2, 'timestamp': 5000}]}
    trim_price_history(history, now_ts=5001, max_history_seconds=3600)
    assert history == {'XAUUSD': [{'price': 2, 'timestamp': 5000}]}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_quote_snapshot_service.py tests/python/test_streaming_service.py -v`
Expected: FAIL with missing module/function errors for the new quote snapshot helpers

- [ ] **Step 3: Write minimal implementation**

```python
# python_service/app/services/quote_snapshot_service.py
def append_quote_to_history(price_history: dict[str, list[dict]], symbol: str, price: float, now_ts: float) -> None:
    if symbol not in price_history:
        price_history[symbol] = []
    price_history[symbol].append({'price': price, 'timestamp': now_ts})

def trim_price_history(price_history: dict[str, list[dict]], now_ts: float, max_history_seconds: int) -> None:
    for symbol, entries in price_history.items():
        price_history[symbol] = [entry for entry in entries if now_ts - entry['timestamp'] <= max_history_seconds]
```

Then update only the history-maintenance block in `streaming_service.py` to call these helpers. Do not move alert dispatch yet.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/python/test_quote_snapshot_service.py tests/python/test_streaming_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/services/quote_snapshot_service.py python_service/app/services/streaming_service.py tests/python/test_quote_snapshot_service.py tests/python/test_streaming_service.py
git commit -m "refactor: extract quote history helpers"
```

### Task 3: Extract Backend Alert Dispatch Helpers

**Files:**
- Create: `python_service/app/services/alert_dispatch_service.py`
- Modify: `python_service/app/services/streaming_service.py`
- Test: `tests/python/test_alert_dispatch_service.py`
- Test: `tests/python/test_streaming_service.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from python_service.app.models.alerts import PriceAlert
from python_service.app.services.alert_dispatch_service import dispatch_price_alerts

@pytest.mark.asyncio
async def test_dispatch_price_alerts_notifies_each_triggered_message(monkeypatch):
    sent = []

    async def fake_notify_all(title, message):
        sent.append((title, message))

    monkeypatch.setattr(
        'python_service.app.services.alert_dispatch_service.notify_all',
        fake_notify_all,
    )

    alerts = [PriceAlert(symbol='XAUUSD', price=3300, condition='above', is_active=True)]
    await dispatch_price_alerts(alerts, {'XAUUSD': 3301})

    assert sent == [('价格预警触发', 'XAUUSD reached 3301 (Target: >= 3300.0)')]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_alert_dispatch_service.py tests/python/test_streaming_service.py -v`
Expected: FAIL with missing module/function errors for the new dispatch helpers

- [ ] **Step 3: Write minimal implementation**

```python
# python_service/app/services/alert_dispatch_service.py
from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert
from python_service.app.services.alert_service import evaluate_alerts, evaluate_volatility, evaluate_indicator_alerts
from python_service.app.services.notifier_service import notify_all

async def dispatch_price_alerts(price_rules: list[PriceAlert], current_prices: dict[str, float]) -> None:
    _, messages = evaluate_alerts(price_rules, current_prices)
    for message in messages:
        await notify_all('价格预警触发', message)
```

Then update only the price-alert notification block in `streaming_service.py` to use the new helper. Add volatility and indicator dispatch helpers in follow-up red/green steps inside the same file only after the first helper passes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/python/test_alert_dispatch_service.py tests/python/test_streaming_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/services/alert_dispatch_service.py python_service/app/services/streaming_service.py tests/python/test_alert_dispatch_service.py tests/python/test_streaming_service.py
git commit -m "refactor: extract alert dispatch helpers"
```

### Task 4: Consolidate Renderer Alert Trigger Effects

**Files:**
- Create: `src/renderer/src/hooks/use-alert-trigger-effects.ts`
- Modify: `src/renderer/src/pages/PriceAlertsPage.tsx`
- Modify: `src/renderer/src/pages/VolatilityPage.tsx`
- Modify: `src/renderer/src/pages/IndicatorAlertsPage.tsx`
- Test: `src/renderer/src/test/use-alert-trigger-effects.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useAlertTriggerEffects } from '@/hooks/use-alert-trigger-effects'

describe('useAlertTriggerEffects', () => {
  it('shows a notification only for newly triggered alerts', () => {
    const notify = vi.fn()
    vi.stubGlobal('Notification', class {
      static permission = 'granted'
      constructor(_title: string, options: NotificationOptions) {
        notify(options.body)
      }
    } as any)

    const { rerender } = renderHook(({ alerts }) => useAlertTriggerEffects({ alerts, isSoundEnabled: false, buildBody: (alert) => alert.body }), {
      initialProps: { alerts: [{ id: '1', is_triggered: false, body: 'first' }] }
    })

    rerender({ alerts: [{ id: '1', is_triggered: true, body: 'first' }] })
    rerender({ alerts: [{ id: '1', is_triggered: true, body: 'first' }] })

    expect(notify).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/use-alert-trigger-effects.test.tsx`
Expected: FAIL with missing hook/module error

- [ ] **Step 3: Write minimal implementation**

```tsx
import { useEffect, useRef } from 'react'

export function useAlertTriggerEffects<T extends { id: string; is_triggered: boolean }>({
  alerts,
  isSoundEnabled,
  soundPath,
  soundVolume,
  notificationTitle,
  buildBody,
}: {
  alerts: T[]
  isSoundEnabled: boolean
  soundPath?: string
  soundVolume?: number
  notificationTitle?: string
  buildBody: (alert: T) => string
}) {
  const prevTriggeredRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const newlyTriggered = alerts.filter((alert) => alert.is_triggered && !prevTriggeredRef.current.has(alert.id))

    if (newlyTriggered.length > 0 && isSoundEnabled && soundPath) {
      const audio = new Audio(`local-file://${soundPath}`)
      audio.volume = soundVolume || 0.5
      void audio.play().catch(console.error)
    }

    if (Notification.permission === 'granted' && notificationTitle) {
      for (const alert of newlyTriggered) {
        new Notification(notificationTitle, { body: buildBody(alert), silent: true })
      }
    }

    prevTriggeredRef.current = new Set(alerts.filter((alert) => alert.is_triggered).map((alert) => alert.id))
  }, [alerts, isSoundEnabled, soundPath, soundVolume, notificationTitle, buildBody])
}
```

Then replace the duplicated `useEffect` blocks in all three alert pages with calls to this hook.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/hooks/use-alert-trigger-effects.ts src/renderer/src/pages/PriceAlertsPage.tsx src/renderer/src/pages/VolatilityPage.tsx src/renderer/src/pages/IndicatorAlertsPage.tsx src/renderer/src/test/use-alert-trigger-effects.test.tsx
git commit -m "refactor: share renderer alert trigger effects"
```

### Task 5: Make Module Navigation Route-Driven

**Files:**
- Modify: `src/renderer/src/App.tsx`
- Modify: `src/renderer/src/layouts/workbench-shell.tsx`
- Modify: `src/renderer/src/components/module-nav.tsx`
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it('navigates to technical analysis via router location', async () => {
  const user = userEvent.setup()
  render(<TestRoot />)

  await user.click(await within(getSidebarNav()!).findByRole('button', { name: 'Technical Analysis' }))

  expect(window.location.hash).toContain('/tech-analysis')
  expect(await screen.findByText('Generate Technical Analysis')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: FAIL because current navigation is driven by local React state, not route state

- [ ] **Step 3: Write minimal implementation**

```tsx
// src/renderer/src/App.tsx
<Routes>
  <Route path="/" element={<Navigate to="/dashboard" replace />} />
  <Route path="/:module" element={<WorkbenchShell />} />
  <Route path="/overlay-display" element={<OverlayDisplayPage />} />
</Routes>
```

```tsx
// inside WorkbenchShell
const { module } = useParams()
const navigate = useNavigate()
const activeModule = module ?? 'dashboard'
const onModuleChange = (nextModule: string) => navigate(`/${nextModule}`)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/App.tsx src/renderer/src/layouts/workbench-shell.tsx src/renderer/src/components/module-nav.tsx src/renderer/src/test/dashboard-page.test.tsx
git commit -m "refactor: drive module navigation from routes"
```

### Task 6: Remove Debug Logging From Router-Adjacent UI Paths

**Files:**
- Modify: `src/renderer/src/App.tsx`
- Modify: `src/renderer/src/pages/overlay-display-page.tsx`
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`
- Modify: `tests/e2e/app-launch.spec.ts`

- [ ] **Step 1: Write the failing test**

```tsx
it('does not write debug logs during normal app render', async () => {
  const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
  render(<TestRoot />)
  expect(logSpy).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: FAIL because `App.tsx` currently logs active module changes

- [ ] **Step 3: Write minimal implementation**

Remove the unconditional `console.log` statements from:

```tsx
// src/renderer/src/App.tsx
React.useEffect(() => {
  console.log('activeModule CHANGED to:', activeModule)
}, [activeModule])
```

```tsx
// src/renderer/src/pages/overlay-display-page.tsx
console.log('Settings changed notification received, fetching...')
```

```ts
// tests/e2e/app-launch.spec.ts
console.log('FULL PAGE TEXT:', pageText)
console.log('Title found:', dashboardTitle)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend && npm run build && npm run test:electron`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/App.tsx src/renderer/src/pages/overlay-display-page.tsx src/renderer/src/test/dashboard-page.test.tsx tests/e2e/app-launch.spec.ts
git commit -m "chore: remove debug logging"
```

### Task 7: Add Backend Risk Control Settings Persistence

**Files:**
- Create: `python_service/app/models/risk_control.py`
- Create: `python_service/app/services/risk_control_service.py`
- Create: `python_service/app/routes/risk_control.py`
- Modify: `python_service/app/main.py`
- Create: `storage/risk-control.json`
- Create: `tests/python/test_risk_control_service.py`
- Create: `tests/python/test_risk_control_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
from python_service.app.services.risk_control_service import load_risk_control_settings

def test_load_risk_control_settings_returns_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr('python_service.app.services.risk_control_service.RISK_CONTROL_FILE', tmp_path / 'risk-control.json')
    settings = load_risk_control_settings()
    assert settings.margin_alert == 200
    assert settings.equity_alert == 1000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_risk_control_service.py tests/python/test_risk_control_routes.py -v`
Expected: FAIL with missing route/service/module errors

- [ ] **Step 3: Write minimal implementation**

```python
# python_service/app/models/risk_control.py
from pydantic import BaseModel

class RiskControlSettings(BaseModel):
    margin_alert: float = 200
    equity_alert: float = 1000
```

```python
# python_service/app/services/risk_control_service.py
from pathlib import Path
import json

from python_service.app.models.risk_control import RiskControlSettings

RISK_CONTROL_FILE = Path('storage/risk-control.json')

def load_risk_control_settings() -> RiskControlSettings:
    if not RISK_CONTROL_FILE.exists():
        return RiskControlSettings()
    with RISK_CONTROL_FILE.open('r', encoding='utf-8') as file:
        return RiskControlSettings(**json.load(file))

def persist_risk_control_settings(settings: RiskControlSettings) -> None:
    RISK_CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RISK_CONTROL_FILE.open('w', encoding='utf-8') as file:
        json.dump(settings.model_dump(), file, ensure_ascii=False, indent=2)
```

```python
# python_service/app/routes/risk_control.py
from fastapi import APIRouter
from python_service.app.models.risk_control import RiskControlSettings
from python_service.app.services.risk_control_service import load_risk_control_settings, persist_risk_control_settings

router = APIRouter(prefix='/risk-control')

@router.get('')
async def get_risk_control_settings() -> RiskControlSettings:
    return load_risk_control_settings()

@router.post('')
async def save_risk_control_settings(settings: RiskControlSettings):
    persist_risk_control_settings(settings)
    return {'status': 'ok'}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/python/test_risk_control_service.py tests/python/test_risk_control_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/models/risk_control.py python_service/app/services/risk_control_service.py python_service/app/routes/risk_control.py python_service/app/main.py tests/python/test_risk_control_service.py tests/python/test_risk_control_routes.py
git commit -m "feat: add backend risk control settings"
```

### Task 8: Add Risk Control Threshold Evaluation

**Files:**
- Modify: `python_service/app/services/risk_control_service.py`
- Modify: `tests/python/test_risk_control_service.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.services.risk_control_service import evaluate_risk_thresholds

def test_evaluate_risk_thresholds_returns_equity_breach_message():
    settings = {'margin_alert': 200, 'equity_alert': 1000}
    account = {'margin_level': 180, 'equity': 950}

    messages = evaluate_risk_thresholds(settings, account)

    assert messages == [
        'Account margin_level reached 180 (Threshold: <= 200)',
        'Account equity reached 950 (Threshold: <= 1000)',
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_risk_control_service.py -v`
Expected: FAIL with missing `evaluate_risk_thresholds`

- [ ] **Step 3: Write minimal implementation**

```python
def evaluate_risk_thresholds(settings: dict, account: dict) -> list[str]:
    messages = []
    if account.get('margin_level') is not None and account['margin_level'] <= settings['margin_alert']:
        messages.append(f"Account margin_level reached {account['margin_level']} (Threshold: <= {settings['margin_alert']})")
    if account.get('equity') is not None and account['equity'] <= settings['equity_alert']:
        messages.append(f"Account equity reached {account['equity']} (Threshold: <= {settings['equity_alert']})")
    return messages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/python/test_risk_control_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/services/risk_control_service.py tests/python/test_risk_control_service.py
git commit -m "feat: evaluate risk control thresholds"
```

### Task 9: Connect Risk Control Page To Backend Persistence

**Files:**
- Modify: `src/renderer/src/pages/RiskControlPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Create: `src/renderer/src/test/risk-control-page.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it('loads saved risk settings and posts updates', async () => {
  global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/risk-control') && (!init || init.method === undefined)) {
      return { ok: true, json: async () => ({ margin_alert: 200, equity_alert: 1000 }) } as Response
    }
    if (url.endsWith('/risk-control') && init?.method === 'POST') {
      return { ok: true, json: async () => ({ status: 'ok' }) } as Response
    }
    throw new Error(`Unexpected request: ${url}`)
  }) as any

  render(<RiskControlPage />)

  expect(await screen.findByDisplayValue('200')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/risk-control-page.test.tsx`
Expected: FAIL because the page is currently hardcoded and not connected to backend state

- [ ] **Step 3: Write minimal implementation**

```tsx
const [formData, setFormData] = useState({ margin_alert: 200, equity_alert: 1000 })

useEffect(() => {
  fetch('http://127.0.0.1:8765/risk-control')
    .then((response) => response.json())
    .then((data) => setFormData(data))
}, [])

const handleSave = async () => {
  await fetch('http://127.0.0.1:8765/risk-control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(formData),
  })
}
```

Also add the minimal new i18n strings required for loading/saving feedback if the page shows them.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/renderer/src/test/risk-control-page.test.tsx`
Expected: PASS

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/pages/RiskControlPage.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/risk-control-page.test.tsx
git commit -m "feat: connect risk control page to backend"
```

## Validation Checklist

- Run: `pytest tests/python -v`
  Expected: Python suite collects and runs without manual `PYTHONPATH` changes.
- Run: `npm run test:frontend`
  Expected: Renderer and main-process Vitest suites pass.
- Run: `npm run build`
  Expected: Electron main, preload, and renderer bundles build successfully.
- Run: `npm run test:electron`
  Expected: Smoke test still launches the packaged Electron output.

`npm run test:electron` depends on a successful prior `npm run build`, because the smoke test launches `out/main/index.js`.

## Notes For The Implementer

- Preserve existing API URLs and current storage locations unless a task explicitly changes them.
- Do not invent lint or typecheck commands; this repo does not provide them.
- Keep changes small and commit after each task.
- Prefer extraction over large rewrites. For `streaming_service.py`, move logic out one seam at a time.
- When touching alert pages, do not change user-visible behavior except where the task explicitly requires it.
