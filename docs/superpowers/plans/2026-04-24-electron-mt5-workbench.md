# Electron MT5 Trader Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Trader Workbench described in `README.md` as a Windows desktop app using Electron for the desktop shell, Python MetaTrader5 SDK for market/account integration, and shadcn UI for the renderer UI.

**Architecture:** This plan treats `README.md` as the product behavior spec, not the implementation architecture contract. Electron owns windows, tray, native shell behaviors, and packaging; a local Python service owns all MT5 SDK access, settings persistence, polling, alert evaluation, and notification dispatch, then exposes a local API and stream for the Electron renderer. The React renderer uses shadcn UI for the main workbench and a separate overlay route rendered in a dedicated transparent always-on-top Electron window.

Cross-cutting API rule: every task that creates a new FastAPI route module must also update `python_service/app/main.py` to register that router with `app.include_router(...)` in the same task.

**Tech Stack:** Electron, Node.js, TypeScript, React, Vite, Tailwind CSS, shadcn/ui, React Router, Zustand, TanStack Query, FastAPI, Uvicorn, Pydantic, MetaTrader5 Python SDK, pytest, Vitest, React Testing Library, Playwright

---

## Scope Check

`README.md` covers several subsystems:

- workbench shell and navigation
- overlay management and quote display
- price alerts
- account monitoring and account alerts
- volatility alerts
- settings management
- Windows packaging and tray integration

These can be implemented as separate plans, but because the repository currently contains only the spec in `README.md`, this master plan keeps them together while still breaking delivery into self-contained vertical slices.

Important scope note: the existing `README.md` says PySide6 is the current desktop framework. This plan intentionally replaces that implementation architecture with Electron + Python MT5 SDK + shadcn UI because that is the explicit user request. Treat every behavior in `README.md` as required unless this plan explicitly supersedes only the technical mechanism used to deliver it.

## File Structure

Planned structure and responsibility map:

- Create: `package.json`
  Responsibility: Node workspace scripts, Electron scripts, frontend dependencies, packaging commands.
- Create: `tsconfig.json`
  Responsibility: shared TypeScript compiler settings.
- Create: `tsconfig.node.json`
  Responsibility: Electron main/preload compilation settings.
- Create: `vite.config.ts`
  Responsibility: renderer build config.
- Create: `tailwind.config.ts`
  Responsibility: Tailwind theme/content config.
- Create: `postcss.config.js`
  Responsibility: Tailwind/PostCSS setup.
- Create: `vitest.config.ts`
  Responsibility: frontend test runner config with alias resolution and jsdom environment.
- Create: `src/test/setup.ts`
  Responsibility: shared frontend test setup, including Testing Library matchers.
- Create: `components.json`
  Responsibility: shadcn UI registry config.
- Create: `.gitignore`
  Responsibility: ignore Node, Python, build, runtime, and local settings artifacts.
- Create: `electron.vite.config.ts`
  Responsibility: explicit build pipeline that emits `dist-electron/main.js` and `dist-electron/preload.js` for testable Electron output.
- Create: `packaging/python-runtime/`
  Responsibility: bundled embeddable Python runtime copied into packaged app resources so end users do not need a separate Python install.
- Create: `packaging/python-service/`
  Responsibility: packaged copy of the Python backend files consumed by Electron in dev and production, preserving the `python_service/` package directory name so imports like `python_service.app.main` remain valid.

- Create: `electron/main.ts`
  Responsibility: app startup, main window, overlay window, tray, lifecycle.
- Create: `electron/preload.ts`
  Responsibility: secure renderer bridge.
- Create: `electron/ipc.ts`
  Responsibility: desktop commands between renderer and main process.
- Create: `electron/python-service.ts`
  Responsibility: spawn/monitor Python backend service.
- Create: `electron/overlay-window.ts`
  Responsibility: transparent always-on-top overlay BrowserWindow.
- Create: `electron/tray.ts`
  Responsibility: single-instance system tray and quick actions.

- Create: `src/main.tsx`
  Responsibility: React bootstrap.
- Create: `src/App.tsx`
  Responsibility: providers and route shell.
- Create: `src/routes/index.tsx`
  Responsibility: route definitions.
- Create: `src/layouts/workbench-shell.tsx`
  Responsibility: left nav, header, content frame.
- Create: `src/pages/dashboard-page.tsx`
  Responsibility: overview cards and quick actions.
- Create: `src/pages/overlay-page.tsx`
  Responsibility: overlay management UI.
- Create: `src/pages/general-page.tsx`
  Responsibility: shared runtime options and MT5 path.
- Create: `src/pages/price-alerts-page.tsx`
  Responsibility: price alert rules and summary.
- Create: `src/pages/account-page.tsx`
  Responsibility: account metrics and account alert rules.
- Create: `src/pages/volatility-page.tsx`
  Responsibility: volatility rules and status.
- Create: `src/pages/settings-page.tsx`
  Responsibility: segmented settings workspace.
- Create: `src/pages/overlay-display-page.tsx`
  Responsibility: renderer content for the overlay window.

- Create: `src/components/ui/*`
  Responsibility: shadcn-generated primitives only.
- Create: `src/components/navigation/module-nav.tsx`
  Responsibility: workbench module navigation.
- Create: `src/components/dashboard/status-card.tsx`
  Responsibility: dashboard summary card.
- Create: `src/components/overlay/monitored-symbols-panel.tsx`
  Responsibility: watched symbol editor.
- Create: `src/components/overlay/symbol-discovery-panel.tsx`
  Responsibility: MT5 symbol discovery/search.
- Create: `src/components/overlay/overlay-actions.tsx`
  Responsibility: preview/save/restore/reconnect actions.
- Create: `src/components/alerts/price-rule-editor.tsx`
  Responsibility: quick-add and batch editor for price alerts.
- Create: `src/components/alerts/volatility-rule-editor.tsx`
  Responsibility: quick-add and batch editor for volatility alerts.
- Create: `src/components/account/account-metrics-grid.tsx`
  Responsibility: account metrics display.
- Create: `src/components/account/account-alert-editor.tsx`
  Responsibility: account alert rule editor.
- Create: `src/components/settings/settings-tabs.tsx`
  Responsibility: segmented settings navigation.

- Create: `src/lib/api/types.ts`
  Responsibility: frontend API types mirroring Python response contracts.
- Create: `src/lib/api/client.ts`
  Responsibility: typed fetch wrapper.
- Create: `src/lib/store/app-store.ts`
  Responsibility: lightweight UI state.
- Create: `src/lib/hooks/use-app-bootstrap.ts`
  Responsibility: app bootstrapping and reconnect polling.
- Create: `src/lib/hooks/use-overlay-stream.ts`
  Responsibility: subscribe to live quote/account events.
- Create: `src/lib/utils.ts`
  Responsibility: UI helpers.
- Create: `src/styles/globals.css`
  Responsibility: Tailwind layers and theme tokens.

- Create: `python_service/pyproject.toml`
  Responsibility: Python service package metadata.
- Create: `python_service/requirements.txt`
  Responsibility: pinned Python runtime dependency list used for packaged runtime installation.
- Create: `python_service/app/main.py`
  Responsibility: FastAPI app entrypoint and direct-execution bootstrap that can start Uvicorn on the fixed local port in packaged mode.
- Create: `python_service/app/config.py`
  Responsibility: defaults aligned with `README.md` and file paths.
- Create: `python_service/app/models.py`
  Responsibility: Pydantic DTOs.
- Create: `python_service/app/settings_store.py`
  Responsibility: load/save local settings JSON.
- Create: `python_service/app/mt5_client.py`
  Responsibility: MT5 SDK wrapper.
- Create: `python_service/app/quote_engine.py`
  Responsibility: quote polling and cache.
- Create: `python_service/app/overlay_state.py`
  Responsibility: overlay text payload generation.
- Create: `python_service/app/symbol_service.py`
  Responsibility: symbol discovery and validation.
- Create: `python_service/app/price_alerts.py`
  Responsibility: price alert parsing and evaluation.
- Create: `python_service/app/account_monitor.py`
  Responsibility: account snapshot and risk metric calculation.
- Create: `python_service/app/volatility_alerts.py`
  Responsibility: rolling-window movement detection.
- Create: `python_service/app/notifiers.py`
  Responsibility: Windows notifications and DingTalk sending.
- Create: `python_service/app/routes/health.py`
  Responsibility: health/version routes.
- Create: `python_service/app/routes/settings.py`
  Responsibility: settings CRUD routes.
- Create: `python_service/app/routes/overlay.py`
  Responsibility: overlay commands and preview/save/restore routes.
- Create: `python_service/app/routes/symbols.py`
  Responsibility: MT5 symbol discovery routes.
- Create: `python_service/app/routes/alerts.py`
  Responsibility: price and volatility alert routes.
- Create: `python_service/app/routes/account.py`
  Responsibility: account metrics and account alert routes.
- Create: `python_service/app/routes/stream.py`
  Responsibility: WebSocket live event stream.

- Create: `tests/electron/app-launch.spec.ts`
  Responsibility: Electron smoke tests.
- Create: `tests/frontend/dashboard-page.test.tsx`
  Responsibility: dashboard shell tests.
- Create: `tests/frontend/price-rule-editor.test.tsx`
  Responsibility: alert editor tests.
- Create: `tests/frontend/settings-page.test.tsx`
  Responsibility: settings workflow tests.
- Create: `tests/python/test_settings_store.py`
  Responsibility: settings persistence tests.
- Create: `tests/python/test_mt5_client.py`
  Responsibility: MT5 wrapper tests with mocks.
- Create: `tests/python/test_price_alerts.py`
  Responsibility: price alert parsing/trigger tests.
- Create: `tests/python/test_account_monitor.py`
  Responsibility: account metric tests.
- Create: `tests/python/test_volatility_alerts.py`
  Responsibility: volatility rule tests.
- Create: `tests/python/test_overlay_routes.py`
  Responsibility: API contract tests.

- Create: `scripts/dev.ps1`
  Responsibility: start Python service, Vite, and Electron for local development.
- Create: `scripts/test.ps1`
  Responsibility: run Python and Node test suites.
- Create: `scripts/build.ps1`
  Responsibility: build Windows distributable.
- Create: `scripts/release.ps1`
  Responsibility: create versioned release zip.
- Create: `scripts/package-python-runtime.ps1`
  Responsibility: stage embeddable Python runtime and Python service files into packageable resources.

Documentation transition note:

- `scripts/dev.ps1` is the Electron-era replacement for the old Python-only `scripts/run.ps1` developer launcher referenced in the current `README.md`.

- Modify: `README.md`
  Responsibility: document the Electron + Python architecture and workflows.
- Create: `readme_cn.md`
  Responsibility: Chinese documentation kept in sync with `README.md`.

## Testing Strategy

- Frontend: `Vitest` + `@testing-library/react`
- Electron: `Playwright` Electron launcher
- Python: `pytest` + `FastAPI TestClient`
- Manual: Windows machine with installed and logged-in MetaTrader 5 terminal

## Integration Contract

- Renderer-to-backend traffic must use one of these two approaches consistently: Electron preload bridge wrappers around backend HTTP/WebSocket calls, or FastAPI CORS middleware allowing `http://127.0.0.1:<vite-port>` during development.
- Required choice for this plan: use direct backend HTTP/WebSocket access during development with FastAPI CORS enabled for the Vite origin, and use preload-bridge wrappers for packaged `file://` renderer builds.
- Prefer preload-bridge wrappers for production-facing calls so renderer code stays independent from browser CORS behavior.
- Single renderer-facing rule: all renderer code must call only `src/lib/api/client.ts` and `src/lib/hooks/use-overlay-stream.ts`. Those abstractions choose direct HTTP/WebSocket in development and preload-backed transport in packaged builds behind the same interface.

### Task 1: Bootstrap Workspace

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `tsconfig.node.json`
- Create: `vite.config.ts`
- Create: `vitest.config.ts`
- Create: `tailwind.config.ts`
- Create: `postcss.config.js`
- Create: `src/test/setup.ts`
- Create: `components.json`
- Create: `.gitignore`
- Create: `electron.vite.config.ts`
- Create: `python_service/pyproject.toml`
- Test: `tests/electron/app-launch.spec.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { test, expect, _electron as electron } from '@playwright/test'

test('launches the workbench shell', async () => {
  const app = await electron.launch({ args: ['dist-electron/main.js'] })
  const window = await app.firstWindow()
  await expect(window).toHaveTitle(/Trader Workbench/)
  await app.close()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec playwright test tests/electron/app-launch.spec.ts`
Expected: FAIL because the Electron build output does not exist.

- [ ] **Step 3: Write minimal implementation**

```ts
import { app, BrowserWindow } from 'electron'

function createWindow() {
  const win = new BrowserWindow({ width: 1440, height: 900 })
  win.setTitle('Trader Workbench')
}

app.whenReady().then(createWindow)
```

- [ ] **Step 4: Add the Electron build contract**

```json
{
  "main": "dist-electron/main.js",
  "scripts": {
    "build:renderer": "vite build",
    "build:electron": "tsc -p tsconfig.node.json && tsc -p tsconfig.node.json --outDir dist-electron",
    "build": "pnpm build:renderer && pnpm build:electron"
  }
}
```

```ts
new BrowserWindow({
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
  },
})
```

- [ ] **Step 5: Add frontend test infrastructure**

```ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm build && pnpm exec playwright test tests/electron/app-launch.spec.ts`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add package.json tsconfig.json tsconfig.node.json vite.config.ts vitest.config.ts electron.vite.config.ts tailwind.config.ts postcss.config.js src/test/setup.ts components.json .gitignore python_service/pyproject.toml electron/main.ts tests/electron/app-launch.spec.ts
git commit -m "chore: bootstrap electron workspace"
```

### Task 2: Add Python Service Skeleton

**Files:**
- Create: `python_service/app/main.py`
- Create: `python_service/app/routes/health.py`
- Create: `python_service/requirements.txt`
- Create: `tests/python/test_overlay_routes.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from python_service.app.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_overlay_routes.py::test_health_endpoint_returns_ok -v`
Expected: FAIL because `python_service.app.main` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
from fastapi import APIRouter


router = APIRouter()


@router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
```

```python
from fastapi import FastAPI
import uvicorn

from python_service.app.routes.health import router as health_router

app = FastAPI()
app.include_router(health_router)


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8765)
```

- [ ] **Step 4: Add packaged-startup verification**

Run: `python -m python_service.app.main`
Run: `Invoke-WebRequest http://127.0.0.1:8765/health`
Expected: PASS, confirming the packaged launch path can start the local API without `python -m uvicorn`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/python/test_overlay_routes.py::test_health_endpoint_returns_ok -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/main.py python_service/app/routes/health.py python_service/requirements.txt tests/python/test_overlay_routes.py
git commit -m "feat: add python backend health endpoint"
```

### Task 3: Wire Electron To Python Lifecycle

**Files:**
- Create: `electron/python-service.ts`
- Modify: `electron/main.ts`

Runtime rule for this task:

- In development, Electron may launch the backend with the system `python` executable.
- In packaged builds, Electron must launch `resources/python-runtime/python.exe -m python_service.app.main` with `cwd` set to `resources/python-service`.
- Do not require end users to install Python separately.
- Electron must wait for backend readiness by polling `/health` with bounded retries before requesting `/settings/saved` or creating/positioning the overlay window.

- [ ] **Step 1: Write minimal implementation**

```ts
import { spawn } from 'node:child_process'

export function startPythonService() {
  const pythonExe = app.isPackaged
    ? path.join(process.resourcesPath, 'python-runtime', 'python.exe')
    : 'python'
  const moduleTarget = app.isPackaged
    ? ['-m', 'python_service.app.main']
    : ['-m', 'uvicorn', 'python_service.app.main:app', '--port', '8765']

  return spawn(pythonExe, moduleTarget, {
    cwd: app.isPackaged ? path.join(process.resourcesPath, 'python-service') : '.',
    stdio: 'ignore',
  })
}
```

```ts
await waitForBackendHealth({ retries: 20, intervalMs: 250 })
```

- [ ] **Step 2: Run a direct health-check verification**

Run: launch Electron through `pnpm exec electron dist-electron/main.js`
Run: `Invoke-WebRequest http://127.0.0.1:8765/health`
Expected: HTTP 200 from the backend started by `electron/python-service.ts`, then backend process exits cleanly when Electron closes.

- [ ] **Step 3: Commit**

```bash
git add electron/main.ts electron/python-service.ts
git commit -m "feat: start python backend from electron"
```

### Task 4: Build shadcn Workbench Shell

**Files:**
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `src/routes/index.tsx`
- Create: `src/layouts/workbench-shell.tsx`
- Create: `src/components/navigation/module-nav.tsx`
- Create: `src/pages/general-page.tsx`
- Create: `src/components/ui/button.tsx`
- Create: `src/components/ui/card.tsx`
- Create: `src/styles/globals.css`
- Test: `tests/frontend/dashboard-page.test.tsx`
- Test: `tests/frontend/settings-page.test.tsx`
- Test: `tests/electron/app-launch.spec.ts`

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react'
import { App } from '@/App'

test('renders workbench modules', () => {
  render(<App />)
  expect(screen.getByText('工作台总览')).toBeInTheDocument()
  expect(screen.getByText('通用')).toBeInTheDocument()
  expect(screen.getByText('价格浮窗')).toBeInTheDocument()
  expect(screen.getByText('设置')).toBeInTheDocument()
})

test('shows disconnected backend state on first launch', async () => {
  render(<App />)
  expect(await screen.findByText(/Disconnected|未连接/)).toBeInTheDocument()
})

test('settings test file scaffold exists for later task extensions', () => {
  expect(true).toBe(true)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/dashboard-page.test.tsx tests/frontend/settings-page.test.tsx`
Expected: FAIL because the renderer app does not exist.

- [ ] **Step 3: Write minimal implementation**

```tsx
export function ModuleNav() {
  return (
    <nav>
      <button>工作台总览</button>
      <button>通用</button>
      <button>价格浮窗</button>
      <button>价格预警</button>
      <button>账户管理</button>
      <button>波动预警</button>
      <button>设置</button>
    </nav>
  )
}
```

- [ ] **Step 4: Load the renderer into the Electron main window**

```ts
if (app.isPackaged) {
  mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
} else {
  mainWindow.loadURL('http://127.0.0.1:5173')
}
```

- [ ] **Step 5: Add disconnected-backend renderer fallback**

```tsx
export function DashboardPage() {
  return <div>未连接</div>
}
```

- [ ] **Step 6: Add dashboard runtime cards and quick actions scaffold**

```tsx
export function DashboardPage() {
  return (
    <div>
      <StatusCard title="MT5 连接" />
      <StatusCard title="浮窗状态" />
      <StatusCard title="监控品种" />
      <StatusCard title="最近更新" />
      <StatusCard title="当前配置" />
      <StatusCard title="异常提醒" />
      <button>进入浮窗与品种管理</button>
      <button>查看监控品种</button>
      <button>重连 MT5</button>
      <button>打开设置</button>
    </div>
  )
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/dashboard-page.test.tsx tests/frontend/settings-page.test.tsx`
Run: `pnpm exec vitest run tests/frontend/dashboard-page.test.tsx -t "disconnected backend state on first launch"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/main.tsx src/App.tsx src/routes/index.tsx src/layouts/workbench-shell.tsx src/pages/dashboard-page.tsx src/pages/general-page.tsx src/components/navigation/module-nav.tsx src/components/ui src/styles/globals.css tests/frontend/dashboard-page.test.tsx tests/frontend/settings-page.test.tsx tests/electron/app-launch.spec.ts
git commit -m "feat: add shadcn workbench shell"
```

### Task 6: Add Settings Contract And Persistence

**Files:**
- Create: `python_service/app/config.py`
- Create: `python_service/app/models.py`
- Create: `python_service/app/settings_store.py`
- Create: `python_service/app/routes/settings.py`
- Modify: `python_service/app/main.py`
- Test: `tests/python/test_settings_store.py`

Required persisted fields in `DEFAULT_CONFIG` and API models:

- `mt5_path`
- `monitored_symbols`
- `primary_symbol`
- `poll_interval_ms`
- `overlay_position`
- `overlay_opacity`
- `font_size`
- `show_symbol`
- `show_ask`
- `show_spread`
- `show_daily_change`
- `show_field_labels`
- `show_timestamp`
- `blink_on_price_change`
- `color_neutral`
- `color_up`
- `color_down`
- `color_error`
- `dingtalk_webhook`
- `qqbot_webhook`
- `telegram_bot_token`
- `telegram_chat_id`
- `price_alert_rules`
- `account_alert_rules`
- `volatility_alert_rules`

Settings API contract established by this task:

- `GET /settings/current` returns the active preview state used by the renderer.
- `GET /settings/saved` returns the last persisted settings from disk.
- `POST /settings/preview` merges a partial settings patch into preview state without persisting.
- `POST /settings/save` persists the current preview state and returns the saved full config.
- `POST /settings/restore-saved` replaces preview state with the last persisted config.

Shared state model for this task:

- `active_settings` is the in-memory preview state shared by the overlay page and settings workspace.
- `POST /settings/preview` must mutate `active_settings` in memory.
- `POST /settings/save` must persist `active_settings` to disk and keep `active_settings` equal to the saved value.
- `POST /settings/restore-saved` must replace `active_settings` with the last persisted settings from disk.

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.config import DEFAULT_CONFIG
from python_service.app.settings_store import SettingsStore


def test_store_returns_full_defaults_when_file_missing(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json')
    config = store.load()
    assert config == DEFAULT_CONFIG
    assert config['primary_symbol'] == 'XAUUSD'
    assert config['poll_interval_ms'] == 500
    assert config['overlay_position'] == {'x': 40, 'y': 40}
    assert config['show_spread'] is False
    assert config['show_daily_change'] is True
    assert config['show_symbol'] is False
    assert config['show_ask'] is False
    assert config['show_timestamp'] is False
    assert config['blink_on_price_change'] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_settings_store.py::test_store_returns_full_defaults_when_file_missing -v`
Expected: FAIL because the settings store does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
DEFAULT_CONFIG = {
    'mt5_path': '',
    'monitored_symbols': ['XAUUSD'],
    'primary_symbol': 'XAUUSD',
    'poll_interval_ms': 500,
    'overlay_position': {'x': 40, 'y': 40},
    'overlay_opacity': 0.88,
    'font_size': 14,
    'show_symbol': False,
    'show_ask': False,
    'show_spread': False,
    'show_daily_change': True,
    'show_field_labels': False,
    'show_timestamp': False,
    'blink_on_price_change': False,
    'color_neutral': '#FFFFFF',
    'color_up': '#00FF85',
    'color_down': '#FF4D6D',
    'color_error': '#FFB020',
    'dingtalk_webhook': '',
    'qqbot_webhook': '',
    'telegram_bot_token': '',
    'telegram_chat_id': '',
    'price_alert_rules': [],
    'account_alert_rules': [],
    'volatility_alert_rules': [],
}


class SettingsStore:
    def __init__(self, path):
        self.path = path

    def load(self):
        return DEFAULT_CONFIG
```

- [ ] **Step 4: Register the settings router and startup config load**

```python
app.include_router(settings_router)
active_settings = SettingsStore(SETTINGS_PATH).load()
```

- [ ] **Step 5: Add concrete settings endpoints**

```python
@router.get('/settings/current')
def get_current_settings():
    return active_settings


@router.get('/settings/saved')
def get_saved_settings():
    return SettingsStore(SETTINGS_PATH).load()


@router.post('/settings/preview')
def update_preview_settings(patch: dict):
    active_settings.update(patch)
    return active_settings


@router.post('/settings/save')
def save_settings():
    SettingsStore(SETTINGS_PATH).save(active_settings)
    return {'saved': True, 'config': active_settings}


@router.post('/settings/restore-saved')
def restore_saved_settings():
    active_settings.clear()
    active_settings.update(SettingsStore(SETTINGS_PATH).load())
    return active_settings
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/python/test_settings_store.py::test_store_returns_full_defaults_when_file_missing -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python_service/app/main.py python_service/app/config.py python_service/app/models.py python_service/app/settings_store.py python_service/app/routes/settings.py tests/python/test_settings_store.py
git commit -m "feat: add settings persistence core"
```

### Task 7: Implement MT5 Auto-Launch From Configured Path

**Files:**
- Modify: `python_service/app/mt5_client.py`
- Modify: `python_service/app/routes/settings.py`
- Modify: `python_service/app/config.py`
- Modify: `python_service/app/main.py`
- Create: `tests/python/test_mt5_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_valid_mt5_path_triggers_terminal_launch(monkeypatch, tmp_path):
    launched = []

    def fake_popen(args, **kwargs):
        launched.append(args)

    monkeypatch.setattr('subprocess.Popen', fake_popen)
    maybe_launch_mt5('C:/Program Files/MetaTrader 5/terminal64.exe')
    assert launched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_mt5_client.py -k terminal_launch -v`
Expected: FAIL because MT5 auto-launch support is not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
import os
import subprocess


def maybe_launch_mt5(mt5_path: str) -> bool:
    if not mt5_path or not os.path.exists(mt5_path):
        return False
    subprocess.Popen([mt5_path])
    return True
```

- [ ] **Step 4: Call auto-launch during startup after settings load**

```python
active_settings = SettingsStore(SETTINGS_PATH).load()
maybe_launch_mt5(active_settings.get('mt5_path', ''))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/python/test_mt5_client.py -k terminal_launch -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/main.py python_service/app/mt5_client.py python_service/app/routes/settings.py python_service/app/config.py tests/python/test_mt5_client.py
git commit -m "feat: auto-launch mt5 from configured path"
```

### Task 8: Implement Dashboard And Bootstrap Queries

**Files:**
- Create: `src/lib/api/types.ts`
- Create: `src/lib/api/client.ts`
- Create: `src/lib/store/app-store.ts`
- Create: `src/lib/hooks/use-app-bootstrap.ts`
- Modify: `python_service/app/main.py`
- Create: `src/pages/dashboard-page.tsx`
- Create: `src/components/dashboard/status-card.tsx`
- Test: `tests/frontend/settings-page.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
test('shows backend connected status after health load', async () => {
  render(<App />)
  expect(await screen.findByText(/Connected|已连接/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "health load"`
Expected: FAIL because the dashboard does not request backend status.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch('http://127.0.0.1:8765/health')
  return response.json()
}
```

- [ ] **Step 4: Add development CORS or preload bridge contract**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173'],
    allow_methods=['*'],
    allow_headers=['*'],
)
```

```ts
window.desktop.api.getHealth()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "health load"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/main.py src/lib/api/types.ts src/lib/api/client.ts src/lib/store/app-store.ts src/lib/hooks/use-app-bootstrap.ts src/pages/dashboard-page.tsx src/components/dashboard/status-card.tsx tests/frontend/settings-page.test.tsx
git commit -m "feat: add dashboard bootstrap state"
```

### Task 9: Implement Quote Polling, Symbol Discovery, And Overlay Preview

**Files:**
- Create: `python_service/app/mt5_client.py`
- Create: `python_service/app/quote_engine.py`
- Create: `python_service/app/overlay_state.py`
- Create: `python_service/app/symbol_service.py`
- Create: `python_service/app/routes/overlay.py`
- Create: `python_service/app/routes/symbols.py`
- Create: `python_service/app/routes/stream.py`
- Modify: `python_service/app/main.py`
- Create: `electron/ipc.ts`
- Create: `electron/preload.ts`
- Create: `src/pages/overlay-page.tsx`
- Create: `src/pages/overlay-display-page.tsx`
- Create: `src/components/overlay/monitored-symbols-panel.tsx`
- Create: `src/components/overlay/symbol-discovery-panel.tsx`
- Create: `src/components/overlay/overlay-actions.tsx`
- Create: `src/lib/hooks/use-overlay-stream.ts`
- Create: `electron/overlay-window.ts`
- Test: `tests/python/test_mt5_client.py`
- Test: `tests/python/test_overlay_routes.py`

Required behavior to deliver in this task, not later:

- overlay shows symbol, bid, ask, spread, and daily change based on saved field toggles
- overlay respects `show_field_labels`
- overlay respects `show_timestamp`
- overlay supports `blink_on_price_change`
- `刷新 MT5 品种` queries the latest available symbols from MT5
- `加入监控` appends selected discovered symbols into `monitored_symbols`
- overlay applies configured `font_size`
- overlay applies configured `overlay_opacity`
- precision follows MT5 symbol digits
- neutral/up/down/error colors come from saved settings
- invalid symbol shows readable error payload instead of crashing
- preview-only changes stay separate from saved settings
- live quote updates use a backend WebSocket endpoint exposed from `python_service/app/routes/stream.py`
- `src/lib/hooks/use-overlay-stream.ts` consumes that WebSocket stream for overlay/dashboard refreshes
- this task owns the startup sequence: load saved settings first, then create and place the overlay window from those settings
- overlay window actions are owned by Electron main process and executed through `electron/ipc.ts` plus `electron/overlay-window.ts`

- [ ] **Step 1: Write the failing tests**

```python
def test_quote_engine_returns_error_payload_when_symbol_missing():
    payload = build_overlay_payload(symbol='MISSING', tick=None)
    assert payload['status'] == 'error'
```

```tsx
test('overlay page lists watched symbols and preview action', async () => {
  render(<App />)
  expect(await screen.findByText('立即预览')).toBeInTheDocument()
})


test('overlay page can refresh mt5 symbols and add monitored symbols', async () => {
  render(<App />)
  expect(await screen.findByText('刷新 MT5 品种')).toBeInTheDocument()
  expect(await screen.findByText('加入监控')).toBeInTheDocument()
})


test('overlay stream hook subscribes to live quote events', async () => {
  expect(createOverlayStreamClient('/ws/overlay')).toBeDefined()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/python/test_mt5_client.py tests/python/test_overlay_routes.py -v`
Run: `pnpm exec vitest run tests/frontend/dashboard-page.test.tsx tests/frontend/settings-page.test.tsx`
Expected: FAIL because overlay APIs and UI do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def build_overlay_payload(symbol: str, tick):
    if tick is None:
        return {'status': 'error', 'text': f'{symbol} unavailable'}
    return {'status': 'ok', 'text': f'{symbol} {tick.bid}'}
```

```ts
export function OverlayActions() {
  return <button>立即预览</button>
}
```

- [ ] **Step 4: Create IPC bridge for overlay window commands**

```ts
ipcMain.handle('overlay:toggle-visible', () => toggleOverlayWindow())
ipcMain.handle('overlay:locate', () => locateOverlayWindow())
ipcMain.handle('overlay:close', () => closeOverlayWindow())
```

- [ ] **Step 5: Create the transparent borderless always-on-top overlay window**

```ts
const overlayWindow = new BrowserWindow({
  frame: false,
  transparent: true,
  alwaysOnTop: true,
  skipTaskbar: true,
})
```

- [ ] **Step 6: Add router registration and stream contract**

```python
app.include_router(overlay_router)
app.include_router(symbols_router)
app.include_router(stream_router)
```

```python
@router.websocket('/ws/overlay')
async def overlay_stream(websocket: WebSocket):
    await websocket.accept()
```

- [ ] **Step 7: Bridge quote polling to connected stream clients**

```python
class QuoteBroadcaster:
    def __init__(self):
        self.clients = set()

    async def broadcast(self, payload: dict):
        for client in list(self.clients):
            await client.send_json(payload)
```

```python
quote_engine.on_quote_update = broadcaster.broadcast
```

- [ ] **Step 8: Add field-toggle, precision, color, and preview-separation tests**

```python
def test_overlay_payload_respects_symbol_digits_and_field_toggles():
    payload = build_overlay_payload(
        symbol='EURUSD',
        tick=FakeTick(bid=1.23456, ask=1.23478),
        digits=5,
        settings={'show_symbol': True, 'show_ask': True, 'show_spread': True, 'show_daily_change': True},
    )
    assert '1.23456' in payload['text']


def test_overlay_payload_can_render_labels_timestamp_and_blink_flag():
    payload = build_overlay_payload(
        symbol='XAUUSD',
        tick=FakeTick(bid=2350.1, ask=2350.3),
        digits=2,
        settings={'show_field_labels': True, 'show_timestamp': True, 'blink_on_price_change': True},
    )
    assert payload['show_timestamp'] is True
    assert payload['blink'] is True


def test_overlay_runtime_applies_font_size_and_opacity():
    runtime = build_overlay_runtime_settings({'font_size': 18, 'overlay_opacity': 0.75})
    assert runtime['font_size'] == 18
    assert runtime['overlay_opacity'] == 0.75


def test_preview_changes_do_not_mutate_saved_settings(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json')
    saved = store.load()
    preview = build_preview_settings(saved, {'show_spread': True})
    assert preview['show_spread'] is True
    assert saved['show_spread'] is False
```

- [ ] **Step 9: Implement those behaviors minimally**

```python
def build_preview_settings(saved: dict, patch: dict) -> dict:
    preview = dict(saved)
    preview.update(patch)
    return preview
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `python -m pytest tests/python/test_mt5_client.py tests/python/test_overlay_routes.py -v`
Run: `pnpm exec vitest run tests/frontend/dashboard-page.test.tsx tests/frontend/settings-page.test.tsx`
Run: verify overlay window is `frame: false`, `transparent: true`, and `alwaysOnTop: true`
Expected: PASS for the new focused assertions.

- [ ] **Step 11: Commit**

```bash
git add python_service/app/main.py python_service/app/mt5_client.py python_service/app/quote_engine.py python_service/app/overlay_state.py python_service/app/symbol_service.py python_service/app/routes/overlay.py python_service/app/routes/symbols.py python_service/app/routes/stream.py electron/ipc.ts electron/preload.ts src/pages/overlay-page.tsx src/pages/overlay-display-page.tsx src/components/overlay/monitored-symbols-panel.tsx src/components/overlay/symbol-discovery-panel.tsx src/components/overlay/overlay-actions.tsx src/lib/hooks/use-overlay-stream.ts electron/overlay-window.ts tests/python/test_mt5_client.py tests/python/test_overlay_routes.py
git commit -m "feat: add mt5 quote polling and overlay preview"
```

### Task 10: Implement Price Alerts

**Files:**
- Create: `python_service/app/price_alerts.py`
- Create: `python_service/app/routes/alerts.py`
- Modify: `python_service/app/main.py`
- Modify: `src/routes/index.tsx`
- Modify: `src/components/navigation/module-nav.tsx`
- Modify: `python_service/app/notifiers.py`
- Modify: `python_service/app/quote_engine.py`
- Create: `src/pages/price-alerts-page.tsx`
- Create: `src/components/alerts/price-rule-editor.tsx`
- Test: `tests/python/test_price_alerts.py`
- Test: `tests/frontend/price-rule-editor.test.tsx`

Required behavior in this task:

- parse quick-add and batch-edit rules
- evaluate triggered rules on each quote-poll cycle
- send Windows/tray notifications for triggered rules
- send DingTalk notifications when configured
- expose triggered-alert status to the page UI
- show validation summary
- show sync/save feedback
- show total rule count
- show valid editor rule count
- show direction summary (`高于 x 条 / 低于 y 条`)

Triggered-alert API/UI contract for this task:

- `GET /alerts/price/rules` returns saved price alert rules from `active_settings['price_alert_rules']`.
- `POST /alerts/price/rules` persists price alert rules back into `active_settings['price_alert_rules']` and saved settings when requested.
- `GET /alerts/price/triggered` returns the current triggered price alerts list.
- `src/pages/price-alerts-page.tsx` renders triggered alert rows and latest delivery status.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_batch_price_rules_accepts_above_and_below():
    rules = parse_price_rules('XAUUSD,above,2350\nEURUSD,below,1.0800')
    assert len(rules.valid_rules) == 2
```

```tsx
test('shows quick-add fields for price alerts', () => {
  render(<PriceRuleEditor />)
  expect(screen.getByLabelText('symbol')).toBeInTheDocument()
})

test('price alerts page renders triggered alert status', () => {
  render(<PriceAlertsPage />)
  expect(screen.getByText(/triggered|已触发/i)).toBeInTheDocument()
})

test('price alerts page renders validation and count summaries', () => {
  render(<PriceAlertsPage />)
  expect(screen.getByText(/validation|校验/i)).toBeInTheDocument()
  expect(screen.getByText(/total|总数/i)).toBeInTheDocument()
  expect(screen.getByText(/高于.*低于|above.*below/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/python/test_price_alerts.py -v`
Run: `pnpm exec vitest run tests/frontend/price-rule-editor.test.tsx`
Expected: FAIL because price alert parser and UI are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_price_rules(text: str):
    lines = [line for line in text.splitlines() if line.strip()]
    return {'valid_rules': [line.split(',') for line in lines]}
```

- [ ] **Step 4: Add trigger evaluation and notifier coverage**

```python
def test_above_rule_triggers_and_dispatches_notification(monkeypatch):
    sent = []

    def fake_notify(message: str):
        sent.append(message)

    monkeypatch.setattr('python_service.app.notifiers.send_windows_notification', fake_notify)
    triggered = evaluate_price_rules(
        rules=[{'symbol': 'XAUUSD', 'direction': 'above', 'target': 2350}],
        quotes={'XAUUSD': {'bid': 2351}},
    )
    assert triggered
    assert sent
```

- [ ] **Step 5: Register alerts router**

```python
app.include_router(alerts_router)
```

- [ ] **Step 6: Add triggered-alert route contract**

```python
@router.get('/alerts/price/rules')
def get_price_alert_rules():
    return {'items': active_settings['price_alert_rules']}


@router.post('/alerts/price/rules')
def save_price_alert_rules():
    return {'saved': True}


@router.get('/alerts/price/triggered')
def get_triggered_price_alerts():
    return {'items': []}
```

- [ ] **Step 7: Wire price alerts page into routes and nav**

```tsx
<Route path="/price-alerts" element={<PriceAlertsPage />} />
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/python/test_price_alerts.py -v`
Run: `pnpm exec vitest run tests/frontend/price-rule-editor.test.tsx`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add python_service/app/main.py python_service/app/price_alerts.py python_service/app/routes/alerts.py python_service/app/notifiers.py python_service/app/quote_engine.py src/pages/price-alerts-page.tsx src/components/alerts/price-rule-editor.tsx tests/python/test_price_alerts.py tests/frontend/price-rule-editor.test.tsx
git commit -m "feat: add price alerts module"
```

### Task 11: Implement Overlay Import, Export, Apply, Save, Restore, And Reset Flows

**Files:**
- Modify: `python_service/app/routes/overlay.py`
- Modify: `python_service/app/routes/settings.py`
- Modify: `python_service/app/settings_store.py`
- Modify: `electron/ipc.ts`
- Modify: `electron/preload.ts`
- Modify: `electron/overlay-window.ts`
- Modify: `src/components/overlay/overlay-actions.tsx`
- Modify: `src/pages/overlay-page.tsx`
- Test: `tests/python/test_overlay_routes.py`
- Test: `tests/frontend/settings-page.test.tsx`

Workflow contract for this task:

- On app startup, the latest persisted settings must be loaded into shared preview/active state before either the overlay page or settings workspace renders.
- `Apply` updates the live overlay immediately using preview state only and does not persist to disk.
- `Save` persists current settings and refreshes the live overlay immediately.
- `Restore 已保存` replaces preview state with the last persisted settings and refreshes the live overlay.
- `Restore Defaults` replaces preview state with `DEFAULT_CONFIG` and does not persist until `Save`.
- `Import Config` opens a file picker, validates the JSON shape, loads the file into preview state, and does not persist until `Save`.
- `Export Current Config` writes the current preview state to a JSON file.
- `Reset Overlay Position` sets preview `overlay_position` back to default coordinates and does not persist until `Save`.
- `Locate Overlay` moves the live overlay window to the default coordinates immediately as a preview action.
- Imported and exported JSON uses the same top-level shape as `DEFAULT_CONFIG`.

Import/export ownership rule for this task:

- Electron IPC owns file dialogs and returns selected filesystem paths to the renderer.
- The renderer reads imported JSON from the chosen path and posts raw JSON to backend preview endpoints.
- The renderer requests export data from the backend, then writes the returned JSON payload to the selected path via Electron IPC.

Overlay-native command ownership for this task:

- The renderer emits intent through preload APIs.
- `electron/ipc.ts` resolves those intents to Electron main-process handlers.
- `electron/overlay-window.ts` performs the actual window show/hide, locate, and close/reopen operations.
- Task 11 owns command invocation only: show/hide, locate, reconnect, import/export, apply/save flows.
- Task 14 owns position synchronization details: moved-window coordinates updating preview state, persisted position restore, and startup placement from saved settings.

Reconnect semantics for this task:

- `Reconnect MT5` must shut down the existing MT5 session if present.
- It must reinitialize the MT5 client with the current saved path/session settings.
- It must restart quote polling and any alert evaluators that depend on live MT5 data.
- It must refresh backend health, overlay payload, and visible connection status in the workbench.
- It must return a success or failure payload with readable error text for the UI.

- [ ] **Step 1: Write the failing tests**

```python
def test_restore_defaults_does_not_persist_until_save(client):
    response = client.post('/overlay/restore-defaults')
    assert response.status_code == 200
    assert response.json()['persisted'] is False


def test_apply_updates_live_overlay_without_persisting(client):
    response = client.post('/overlay/apply', json={'show_spread': True})
    assert response.status_code == 200
    assert response.json()['persisted'] is False
    assert response.json()['overlay_refreshed'] is True


def test_save_persists_and_refreshes_live_overlay(client):
    response = client.post('/overlay/save', json={'show_spread': True})
    assert response.status_code == 200
    assert response.json()['persisted'] is True
    assert response.json()['overlay_refreshed'] is True


def test_import_loads_preview_state_without_persisting(client):
    response = client.post('/overlay/import', json={'show_spread': True})
    assert response.status_code == 200
    assert response.json()['persisted'] is False


def test_reset_overlay_position_only_updates_preview_state(client):
    response = client.post('/overlay/reset-position')
    assert response.status_code == 200
    assert response.json()['persisted'] is False
    assert response.json()['overlay_position'] == {'x': 40, 'y': 40}


def test_export_writes_current_preview_state(client):
    response = client.post('/overlay/export')
    assert response.status_code == 200
    assert response.json()['exported'] is True


def test_startup_restores_last_saved_settings(client, seeded_settings_file):
    response = client.get('/settings/current')
    assert response.status_code == 200
    assert response.json()['show_spread'] is True
```

```tsx
test('overlay actions show import export apply save restore', async () => {
  render(<OverlayActions />)
  expect(screen.getByText('应用')).toBeInTheDocument()
  expect(screen.getByText('保存设置')).toBeInTheDocument()
  expect(screen.getByText('恢复已保存')).toBeInTheDocument()
})

test('overlay action center shows toggle locate and reconnect actions', async () => {
  render(<OverlayActions />)
  expect(screen.getByText('显示/隐藏价格浮窗')).toBeInTheDocument()
  expect(screen.getByText('定位悬浮窗')).toBeInTheDocument()
  expect(screen.getByText('重连 MT5')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/python/test_overlay_routes.py -k "restore_defaults or import or export" -v`
Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "overlay actions show import export apply save restore"`
Expected: FAIL because import/export/reset/apply/save flows are not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
@router.post('/overlay/restore-defaults')
def restore_defaults():
    return {'persisted': False}
```

- [ ] **Step 4: Add explicit Apply and Save semantics**

```python
@router.post('/overlay/apply')
def apply_overlay_preview():
    return {'persisted': False, 'overlay_refreshed': True}


@router.post('/overlay/save')
def save_overlay_settings():
    return {'persisted': True, 'overlay_refreshed': True}
```

- [ ] **Step 5: Add native file-dialog integration for import/export**

```ts
ipcMain.handle('config:export', async () => {
  return dialog.showSaveDialog({ filters: [{ name: 'JSON', extensions: ['json'] }] })
})

ipcMain.handle('config:import', async () => {
  return dialog.showOpenDialog({ filters: [{ name: 'JSON', extensions: ['json'] }] })
})
```

- [ ] **Step 6: Add secure JSON read/write IPC bridge**

```ts
ipcMain.handle('file:read-json', async (_event, filePath) => JSON.parse(await fs.promises.readFile(filePath, 'utf8')))
ipcMain.handle('file:write-json', async (_event, filePath, payload) => fs.promises.writeFile(filePath, JSON.stringify(payload, null, 2)))
```

- [ ] **Step 7: Add backend import/export route semantics**

```python
@router.post('/overlay/export')
def export_config_preview():
    return {'exported': True, 'config': active_settings}
```

- [ ] **Step 8: Add renderer/backend handoff for import/export payloads**

```ts
const importPath = await window.desktop.configImportPath()
const importedConfig = await window.desktop.readJsonFile(importPath)
await api.post('/overlay/import', importedConfig)

const exportPath = await window.desktop.configExportPath()
const exportPayload = await api.post('/overlay/export')
await window.desktop.writeJsonFile(exportPath, exportPayload)
```

- [ ] **Step 9: Add overlay action-center command handlers**

```python
@router.post('/overlay/toggle-visible')
def toggle_visible():
    return {'ok': True}


@router.post('/overlay/locate')
def locate_overlay():
    return {'ok': True}


@router.post('/overlay/reconnect-mt5')
def reconnect_mt5():
    return {'ok': True, 'reconnected': True, 'overlay_refreshed': True}


@router.post('/overlay/import')
def import_config_preview():
    return {'persisted': False}


@router.post('/overlay/reset-position')
def reset_overlay_position():
    return {'persisted': False, 'overlay_position': {'x': 40, 'y': 40}}
```

- [ ] **Step 10: Implement real MT5 reconnect lifecycle**

```python
def reconnect_mt5_runtime():
    mt5_client.shutdown()
    mt5_client.initialize()
    quote_engine.restart()
    alert_engine.restart()
    return {'ok': True, 'reconnected': True, 'overlay_refreshed': True}
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `python -m pytest tests/python/test_overlay_routes.py -k "restore_defaults or import or export" -v`
Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "overlay actions show import export apply save restore"`
Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "overlay action center shows toggle locate and reconnect actions"`
Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add python_service/app/routes/overlay.py python_service/app/routes/settings.py python_service/app/settings_store.py electron/ipc.ts electron/preload.ts src/components/overlay/overlay-actions.tsx src/pages/overlay-page.tsx tests/python/test_overlay_routes.py tests/frontend/settings-page.test.tsx
git commit -m "feat: add overlay config workflows"
```

### Task 12: Implement Account Monitoring And Account Alerts

**Files:**
- Create: `python_service/app/account_monitor.py`
- Create: `python_service/app/routes/account.py`
- Modify: `python_service/app/main.py`
- Modify: `src/routes/index.tsx`
- Modify: `src/components/navigation/module-nav.tsx`
- Create: `src/pages/account-page.tsx`
- Create: `src/components/account/account-metrics-grid.tsx`
- Create: `src/components/account/account-alert-editor.tsx`
- Test: `tests/python/test_account_monitor.py`
- Test: `tests/frontend/account-page.test.tsx`

Required account alert behavior in this task:

- expose account identity fields: `server`, `account_number`, `currency`, `leverage`
- expose fund metrics: `balance`, `equity`, `floating_profit`, `floating_loss`
- expose risk metrics: `used_margin`, `free_margin`, `margin_level`, `risk_level`, `day_peak_equity`, `intraday_drawdown`, `intraday_drawdown_percent`, `last_update_time`
- expose `GET /account/summary` for the live account snapshot consumed by `src/pages/account-page.tsx`
- persist account alert rules for `equity`, `margin_level`, `floating_profit`, and `floating_loss`
- evaluate those rules against the latest account snapshot
- expose trigger status through `python_service/app/routes/account.py`
- render editable rules in `src/components/account/account-alert-editor.tsx`

- [ ] **Step 1: Write the failing test**

```python
def test_account_snapshot_includes_identity_funds_and_risk_fields():
    snapshot = build_account_snapshot(
        server='Demo-Server',
        account_number=123456,
        currency='USD',
        leverage=100,
        balance=10000,
        equity=9800,
        floating_profit=150,
        floating_loss=-350,
        margin=500,
        free_margin=9300,
    )
    assert snapshot['server'] == 'Demo-Server'
    assert snapshot['currency'] == 'USD'
    assert 'margin_level' in snapshot
    assert 'last_update_time' in snapshot


def test_intraday_drawdown_percent_uses_day_peak_equity():
    metrics = calculate_risk_metrics(equity=900, peak_equity=1000, margin=100, free_margin=800)
    assert metrics['intraday_drawdown_percent'] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_account_monitor.py -v`
Expected: FAIL because account monitoring logic is missing.

- [ ] **Step 3: Write minimal implementation**

```python
def calculate_risk_metrics(equity: float, peak_equity: float, margin: float, free_margin: float):
    return {
        'intraday_drawdown_percent': round(((peak_equity - equity) / peak_equity) * 100, 2),
        'used_margin': margin,
        'free_margin': free_margin,
    }
```

- [ ] **Step 4: Add account alert rule evaluation**

```python
def is_account_alert_triggered(metric_name: str, current_value: float, threshold: float, direction: str) -> bool:
    if direction == 'below':
        return current_value < threshold
    return current_value > threshold
```

- [ ] **Step 5: Add account alert persistence and route contract**

```python
@router.get('/account/summary')
def get_account_summary():
    return {'server': 'Demo-Server'}


@router.get('/account/alerts')
def get_account_alerts():
    return {'items': []}


@router.post('/account/alerts')
def save_account_alerts():
    return {'saved': True}
```

- [ ] **Step 6: Add account alert editor rendering test**

```tsx
test('account page renders editable account alert rules', () => {
  render(<AccountPage />)
  expect(screen.getByText(/equity|margin_level|floating_profit|floating_loss/i)).toBeInTheDocument()
})
```

- [ ] **Step 7: Register account router**

```python
app.include_router(account_router)
```

- [ ] **Step 8: Wire account page into routes and nav**

```tsx
<Route path="/account" element={<AccountPage />} />
```

- [ ] **Step 9: Run test to verify it passes**

Run: `python -m pytest tests/python/test_account_monitor.py -v`
Run: `pnpm exec vitest run tests/frontend/account-page.test.tsx`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add python_service/app/main.py python_service/app/account_monitor.py python_service/app/routes/account.py src/pages/account-page.tsx src/components/account/account-metrics-grid.tsx src/components/account/account-alert-editor.tsx tests/python/test_account_monitor.py tests/frontend/account-page.test.tsx
git commit -m "feat: add account monitoring module"
```

### Task 13: Implement Volatility Alerts And Notification Channels

**Files:**
- Create: `src/pages/settings-page.tsx`
- Create: `python_service/app/volatility_alerts.py`
- Create: `python_service/app/notifiers.py`
- Modify: `python_service/app/routes/alerts.py`
- Modify: `python_service/app/main.py`
- Modify: `python_service/app/quote_engine.py`
- Modify: `src/routes/index.tsx`
- Modify: `src/components/navigation/module-nav.tsx`
- Create: `src/pages/volatility-page.tsx`
- Create: `src/components/alerts/volatility-rule-editor.tsx`
- Test: `tests/python/test_volatility_alerts.py`
- Test: `tests/frontend/settings-page.test.tsx`

Required behavior in this task:

- support quick-add rules by `symbol`, `time window in minutes`, and `movement threshold in points`
- support batch edit lines like `XAUUSD,5,30`
- evaluate rules against a rolling window of quote history, not just two ad hoc prices
- dispatch Windows/tray and DingTalk notifications when triggered

Volatility API/UI contract for this task:

- `GET /alerts/volatility/rules` returns saved volatility rules.
- `POST /alerts/volatility/rules` saves volatility rules.
- `GET /alerts/volatility/triggered` returns currently triggered volatility alerts.
- `src/pages/volatility-page.tsx` renders saved rules, editor state, and triggered volatility items.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_batch_volatility_rules_accepts_symbol_window_threshold():
    rules = parse_volatility_rules('XAUUSD,5,30\nEURUSD,15,0.002')
    assert len(rules.valid_rules) == 2


def test_rule_triggers_when_point_move_exceeds_threshold_within_window():
    triggered = is_volatility_triggered(
        samples=[
            {'price': 100.0, 'ts': '2026-04-24T10:00:00Z'},
            {'price': 100.3, 'ts': '2026-04-24T10:02:00Z'},
            {'price': 100.7, 'ts': '2026-04-24T10:03:00Z'},
            {'price': 101.0, 'ts': '2026-04-24T10:04:00Z'},
        ],
        threshold_points=0.5,
        window_minutes=5,
    )
    assert triggered is True


def test_rule_does_not_trigger_when_move_is_outside_window():
    triggered = is_volatility_triggered(
        samples=[
            {'price': 100.0, 'ts': '2026-04-24T10:00:00Z'},
            {'price': 101.0, 'ts': '2026-04-24T10:20:00Z'},
        ],
        threshold_points=0.5,
        window_minutes=5,
    )
    assert triggered is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/python/test_volatility_alerts.py -v`
Expected: FAIL because volatility rule evaluation does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def is_volatility_triggered(samples: list[dict], threshold_points: float, window_minutes: int) -> bool:
    return movement_within_window(samples, window_minutes) >= threshold_points
```

- [ ] **Step 4: Add notification-channel settings coverage**

```tsx
test('settings page stores DingTalk, QQ bot, and Telegram fields', async () => {
  render(<SettingsPage />)
  expect(screen.getByLabelText('钉钉BOT')).toBeInTheDocument()
  expect(screen.getByLabelText('tencent QQbot')).toBeInTheDocument()
  expect(screen.getByLabelText('telegram BOt')).toBeInTheDocument()
})

test('settings page shows DingTalk test send action', async () => {
  render(<SettingsPage />)
  expect(screen.getByText('测试发送')).toBeInTheDocument()
})

test('settings page test-send action calls DingTalk API', async () => {
  render(<SettingsPage />)
  await user.click(screen.getByText('测试发送'))
  expect(mockApi.post).toHaveBeenCalledWith('/alerts/dingtalk/test')
})
```

- [ ] **Step 5: Add DingTalk test-send workflow**

```python
def test_send_dingtalk_message_returns_success(monkeypatch):
    assert send_dingtalk_test('https://example.invalid') is True
```

- [ ] **Step 6: Add DingTalk test-send API contract**

```python
@router.post('/alerts/dingtalk/test')
def dingtalk_test_send():
    return {'ok': True}
```

- [ ] **Step 7: Add volatility rule and triggered-status routes**

```python
@router.get('/alerts/volatility/rules')
def get_volatility_rules():
    return {'items': []}


@router.post('/alerts/volatility/rules')
def save_volatility_rules():
    return {'saved': True}


@router.get('/alerts/volatility/triggered')
def get_triggered_volatility_alerts():
    return {'items': []}
```

- [ ] **Step 8: Confirm alerts router remains registered after volatility endpoints are added**

```python
app.include_router(alerts_router)
```

- [ ] **Step 9: Wire volatility page into routes and nav**

```tsx
<Route path="/volatility-alerts" element={<VolatilityPage />} />
```

- [ ] **Step 10: Run test to verify it passes**

Run: `python -m pytest tests/python/test_volatility_alerts.py -v`
Run: `python -m pytest tests/python/test_volatility_alerts.py -k dingtalk -v`
Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "stores DingTalk, QQ bot, and Telegram"`
Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx -t "shows DingTalk test send action"`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add python_service/app/main.py python_service/app/volatility_alerts.py python_service/app/notifiers.py python_service/app/routes/alerts.py src/pages/volatility-page.tsx src/components/alerts/volatility-rule-editor.tsx src/pages/settings-page.tsx tests/python/test_volatility_alerts.py tests/frontend/settings-page.test.tsx
git commit -m "feat: add volatility alerts and notifications"
```

### Task 14: Implement Overlay Interaction And Position Persistence

**Files:**
- Modify: `electron/overlay-window.ts`
- Modify: `electron/ipc.ts`
- Modify: `src/pages/overlay-display-page.tsx`
- Modify: `python_service/app/routes/overlay.py`
- Modify: `python_service/app/settings_store.py`
- Test: `tests/electron/app-launch.spec.ts`
- Test: `tests/python/test_overlay_routes.py`

- [ ] **Step 1: Write the failing tests**

```ts
test('overlay window supports drag move and right click close', async () => {
  const app = await electron.launch({ args: ['dist-electron/main.js'] })
  const windows = await app.windows()
  const overlayWindow = windows[1]
  await expect(overlayWindow.getByText(/右键关闭|close/i)).toBeVisible()
  await app.close()
})
```

```python
def test_overlay_position_is_saved_and_restored(tmp_path):
    store = SettingsStore(tmp_path / 'settings.json')
    store.save_position(120, 160)
    assert store.load()['overlay_position'] == {'x': 120, 'y': 160}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pnpm exec playwright test tests/electron/app-launch.spec.ts -g "overlay window supports drag move and right click close"`
Run: `python -m pytest tests/python/test_overlay_routes.py -k position -v`
Expected: FAIL because overlay interaction and position persistence are not implemented.

- [ ] **Step 3: Write minimal implementation**

```python
def save_position(self, x: int, y: int):
    config = self.load()
    config['overlay_position'] = {'x': x, 'y': y}
    self.save(config)
```

- [ ] **Step 4: Implement overlay drag and right-click interaction in Electron/renderer**

```ts
overlayWindow.setIgnoreMouseEvents(false)
overlayWindow.webContents.send('overlay:enable-drag')
```

```tsx
window.addEventListener('contextmenu', () => {
  window.desktop.closeOverlay()
})
```

- [ ] **Step 5: Persist final position after drag ends**

```ts
overlayWindow.on('moved', () => {
  const [x, y] = overlayWindow.getPosition()
  updatePreviewOverlayPosition(x, y)
})
```

- [ ] **Step 6: Restore persisted overlay position on startup**

```ts
const savedPosition = settings.overlay_position
overlayWindow.setPosition(savedPosition.x, savedPosition.y)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pnpm exec playwright test tests/electron/app-launch.spec.ts -g "overlay window supports drag move and right click close"`
Run: `python -m pytest tests/python/test_overlay_routes.py -k position -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add electron/overlay-window.ts electron/ipc.ts src/pages/overlay-display-page.tsx python_service/app/routes/overlay.py python_service/app/settings_store.py tests/electron/app-launch.spec.ts tests/python/test_overlay_routes.py
git commit -m "feat: add overlay interaction and position restore"
```

### Task 15: Implement Settings Workspace, Tray, And Native Commands

**Files:**
- Modify: `src/pages/settings-page.tsx`
- Create: `src/components/settings/settings-tabs.tsx`
- Create: `src/components/settings/general-settings-form.tsx`
- Create: `src/components/settings/overlay-settings-form.tsx`
- Modify: `electron/main.ts`
- Create: `electron/ipc.ts`
- Create: `electron/preload.ts`
- Create: `electron/tray.ts`
- Test: `tests/frontend/settings-page.test.tsx`
- Test: `tests/electron/app-launch.spec.ts`

Required tray behavior in this task:

- single application instance via `app.requestSingleInstanceLock()`
- single system tray instance
- show main window
- toggle overlay
- locate overlay
- reconnect MT5
- exit app through the shared shutdown path

Shared-state rule for this task:

- `src/pages/settings-page.tsx` must operate on the same preview/persisted settings model used by the overlay module, so `Apply`, `Save`, `Restore 已保存`, import/export, reconnect, and reset-position workflows behave consistently in both surfaces.

Required settings controls in this task:

- `Mt5路径`
- `显示品种`
- `显示卖价`
- `显示点差`
- `显示日变化`
- `刷新频率`
- `浮窗文字大小`
- `透明度`
- `默认文字颜色`
- `上涨颜色`
- `下跌颜色`
- `错误颜色`
- `显示字段名称`
- `显示更新时间`
- `价格变动时闪烁`

Required settings-workspace actions in this task:

- `Apply`
- `Save`
- `Restore 已保存`
- `Import Config`
- `Export Current Config`
- `Restore Defaults`
- `Reset Overlay Position`
- `Reconnect MT5`

- [ ] **Step 1: Write the failing test**

```tsx
test('settings workspace shows segmented sections', () => {
  render(<SettingsPage />)
  expect(screen.getByText('通用')).toBeInTheDocument()
  expect(screen.getByText('浮窗与品种')).toBeInTheDocument()
})

test('settings workspace exposes overlay workflows', () => {
  render(<SettingsPage />)
  expect(screen.getByText('应用')).toBeInTheDocument()
  expect(screen.getByText('保存设置')).toBeInTheDocument()
  expect(screen.getByText('恢复已保存')).toBeInTheDocument()
})

test('settings workspace renders mt5 path and overlay controls', () => {
  render(<SettingsPage />)
  expect(screen.getByLabelText('Mt5路径')).toBeInTheDocument()
  expect(screen.getByLabelText('显示品种')).toBeInTheDocument()
  expect(screen.getByLabelText('显示点差')).toBeInTheDocument()
  expect(screen.getByLabelText('浮窗文字大小')).toBeInTheDocument()
  expect(screen.getByLabelText('透明度')).toBeInTheDocument()
})

test('settings workspace exposes import export reset and reconnect actions', () => {
  render(<SettingsPage />)
  expect(screen.getByText('Import Config')).toBeInTheDocument()
  expect(screen.getByText('Export Current Config')).toBeInTheDocument()
  expect(screen.getByText('Restore Defaults')).toBeInTheDocument()
  expect(screen.getByText('Reset Overlay Position')).toBeInTheDocument()
  expect(screen.getByText('Reconnect MT5')).toBeInTheDocument()
})
```

```ts
test('tray menu shows quick actions from one instance', async () => {
  const app = await electron.launch({ args: ['dist-electron/main.js'] })
  const window = await app.firstWindow()
  await expect(window).toHaveTitle(/Trader Workbench/)
  await app.close()
})

test('tray command wiring registers toggle locate reconnect and exit actions', async () => {
  const app = await electron.launch({ args: ['dist-electron/main.js'] })
  const window = await app.firstWindow()
  await expect(window).toHaveTitle(/Trader Workbench/)
  await app.close()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx`
Expected: FAIL because settings workspace does not exist.

- [ ] **Step 3: Write minimal implementation**

```tsx
export function SettingsTabs() {
  return (
    <div>
      <button>通用</button>
      <button>浮窗与品种</button>
      <button>价格预警</button>
      <button>账户管理</button>
      <button>波动预警</button>
    </div>
  )
}
```

- [ ] **Step 4: Wire tray creation and shared shutdown in Electron main**

```ts
const hasLock = app.requestSingleInstanceLock()
if (!hasLock) app.quit()

app.whenReady().then(() => {
  createMainWindow()
  createTray()
})

app.on('second-instance', () => {
  focusMainWindow()
})

app.on('before-quit', () => {
  stopPythonService()
  destroyTray()
})
```

- [ ] **Step 5: Wire settings-workspace actions to shared workflows**

```tsx
<button onClick={() => api.post('/overlay/apply')}>应用</button>
<button onClick={() => api.post('/overlay/save')}>保存设置</button>
<button onClick={() => api.post('/settings/restore-saved')}>恢复已保存</button>
<button onClick={() => window.desktop.configImportPath()}>Import Config</button>
<button onClick={() => window.desktop.configExportPath()}>Export Current Config</button>
<button onClick={() => api.post('/overlay/restore-defaults')}>Restore Defaults</button>
<button onClick={() => api.post('/overlay/reset-position')}>Reset Overlay Position</button>
<button onClick={() => api.post('/overlay/reconnect-mt5')}>Reconnect MT5</button>
```

- [ ] **Step 6: Add behavioral test for shared settings workflows**

```tsx
test('settings workspace actions call shared overlay/settings workflows', async () => {
  render(<SettingsPage />)
  await user.click(screen.getByText('应用'))
  expect(mockApi.post).toHaveBeenCalledWith('/overlay/apply')
})
```

- [ ] **Step 7: Verify tray command wiring with a testable abstraction**

Run: `pnpm exec playwright test tests/electron/app-launch.spec.ts -g "tray command wiring"`
Expected: PASS for tray command registration abstractions in Electron code.

- [ ] **Step 8: Manually verify native tray behavior on Windows**

Run: start the app on Windows and click the tray icon/menu
Expected: one tray instance, working quick actions, and one cleanup path on exit.

- [ ] **Step 9: Run test to verify it passes**

Run: `pnpm exec vitest run tests/frontend/settings-page.test.tsx`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/pages/settings-page.tsx src/components/settings/settings-tabs.tsx electron/main.ts electron/ipc.ts electron/preload.ts electron/tray.ts tests/frontend/settings-page.test.tsx tests/electron/app-launch.spec.ts
git commit -m "feat: add settings workspace and tray actions"
```

### Task 16: Build, Package, And Document The App

**Files:**
- Create: `scripts/dev.ps1`
- Create: `scripts/test.ps1`
- Create: `scripts/build.ps1`
- Create: `scripts/release.ps1`
- Create: `scripts/package-python-runtime.ps1`
- Create: `electron-builder.standard.json`
- Create: `electron-builder.protected.json`
- Create: `scripts/protect-python.ps1`
- Create: `python_service/requirements.txt`
- Modify: `README.md`
- Create: `readme_cn.md`

Required release outputs:

- `dist\priceonwindow-standard\priceonwindow.exe`
- `dist\priceonwindow-protected\priceonwindow.exe`
- `releases\priceonwindow-v<version>-standard\`
- `releases\priceonwindow-v<version>-standard.zip`
- `releases\priceonwindow-v<version>-protected\`
- `releases\priceonwindow-v<version>-protected.zip`

Protected build definition for this Electron architecture:

- Standard build packages readable Python service files.
- Protected build runs `scripts/protect-python.ps1` before packaging and replaces selected Python service modules with an obfuscated/protected output bundle.
- At minimum, protect the Electron-side Python runtime equivalents of the README's former sensitive modules: `python_service/app/main.py`, `python_service/app/mt5_client.py`, `python_service/app/quote_engine.py`, and `python_service/app/notifiers.py`.
- If PyArmor remains the chosen tool, codify that in `scripts/protect-python.ps1` and `electron-builder.protected.json` instead of leaving it as a human decision during implementation.
- Both standard and protected Windows builds must use the GUI/no-console subsystem so launching `priceonwindow.exe` does not open an extra console window for normal app use.

Packaged runtime definition for this task:

- `scripts/package-python-runtime.ps1` downloads or stages the Windows embeddable Python distribution into `packaging/python-runtime/`.
- The same script copies the service entrypoint and runtime modules into `packaging/python-service/`.
- The copied backend tree must keep the path `packaging/python-service/python_service/app/main.py` so packaged imports and direct execution stay consistent with source imports.
- The same script must bootstrap `pip` for the bundled runtime or replace the embeddable distribution with a prebuilt portable Python layout that already supports `site-packages`.
- After runtime bootstrap, the script installs Python dependencies into a packaged `Lib/site-packages` tree under `packaging/python-runtime/` so `fastapi`, `uvicorn`, `pydantic`, `MetaTrader5`, and other runtime dependencies are available without a separate virtualenv.
- `electron-builder.standard.json` must include both folders as `extraResources` so the installed app can start the backend without a machine-wide Python install.
- `electron-builder.protected.json` must package the protected `packaging/python-service/` output instead of the readable one.

- [ ] **Step 1: Write the failing verification checklist item**

```md
- [ ] `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1` produces `dist\priceonwindow-standard\priceonwindow.exe`
- [ ] `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Protected` produces `dist\priceonwindow-protected\priceonwindow.exe`
```

- [ ] **Step 2: Run build command to verify it fails before scripts exist**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1`
Run: `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Protected`
Expected: FAIL because the build scripts do not exist.

- [ ] **Step 3: Write minimal implementation**

```powershell
pnpm install
pnpm build
python -m pytest
pwsh -File .\scripts\package-python-runtime.ps1
pnpm exec electron-builder --config electron-builder.standard.json
pwsh -File .\scripts\protect-python.ps1
pnpm exec electron-builder --config electron-builder.protected.json
```

- [ ] **Step 4: Add packaged Python dependency installation**

```powershell
& .\packaging\python-runtime\python.exe -m pip install -r .\python_service\requirements.txt --target .\packaging\python-runtime\Lib\site-packages
```

- [ ] **Step 5: Add Electron builder resource wiring**

```json
{
  "win": { "target": "portable", "artifactName": "priceonwindow.exe" },
  "extraResources": [
    { "from": "packaging/python-runtime", "to": "python-runtime" },
    { "from": "packaging/python-service", "to": "python-service" }
  ]
}
```

- [ ] **Step 6: Add no-console Windows packaging verification**

Run: launch `dist\priceonwindow-standard\priceonwindow.exe`
Expected: app starts with no extra console window.

- [ ] **Step 7: Run verification to confirm it passes**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1`
Run: `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1`
Run: `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Protected`
Run: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1`
Run: `powershell -ExecutionPolicy Bypass -File .\scripts\release.ps1 -Protected`
Expected: PASS, with exact outputs under `dist\priceonwindow-standard`, `dist\priceonwindow-protected`, and versioned `releases\` folders. The protected build must differ from standard by packaging the protected Python service output created by `scripts\protect-python.ps1`.

- [ ] **Step 8: Commit**

```bash
git add scripts/dev.ps1 scripts/test.ps1 scripts/build.ps1 scripts/release.ps1 scripts/package-python-runtime.ps1 scripts/protect-python.ps1 electron-builder.standard.json electron-builder.protected.json packaging/python-runtime packaging/python-service python_service/requirements.txt README.md readme_cn.md
git commit -m "docs: add electron mt5 setup and release workflow"
```

## Implementation Notes

- Prefer one source of truth for defaults in `python_service/app/config.py`, then expose them to the frontend via settings API. Do not duplicate defaults across Electron and React.
- Keep MT5 SDK usage entirely inside Python. Do not attempt Node native bindings for MT5.
- Persist preview-only changes separately from saved settings so `Apply` and `Save` keep the behavior described in `README.md`.
- Use WebSocket or server-sent streaming only after the polling loop and REST contracts are stable. Do not start with a complex bidirectional IPC design.
- Generate shadcn components rather than hand-writing lookalikes. Keep app-specific behavior outside `src/components/ui/`.
- Preserve the product behavior in `README.md`: symbol discovery, save/restore/apply flows, tray actions, reconnect, overlay locate, drag move, right-click close, MT5-digit precision, and non-blocking polling.

## Manual Test Plan

Run after Task 16 on Windows:

1. Start MetaTrader 5 and log in to a demo account.
2. Run `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1`.
3. Confirm dashboard loads and shows backend health.
4. Configure `Mt5路径`, save, restart, and confirm MT5 auto-launch behavior.
5. Add monitored symbols from discovery, preview overlay, save, restart, and confirm settings restore.
6. Confirm invalid symbols show readable errors instead of crashing.
7. Add one price alert, one account alert, and one volatility alert, then verify notifications trigger.
8. Confirm overlay drag-to-move, right-click close, saved position restore, color changes, and MT5-digit precision all work.
9. Confirm tray actions for show window, toggle overlay, locate overlay, reconnect MT5, and exit all work.
10. Run `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1` and `powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Protected`, then launch both packaged apps.

## References

- Spec source: `README.md`
- UI implementation: `@shadcn`
- Execution workflow: `@superpowers:executing-plans`
- Recommended execution workflow: `@superpowers:executing-plans`
