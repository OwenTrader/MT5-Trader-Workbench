# MT5 Residual Wakeup Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the Python backend from continuing to connect to or launch MT5 after the Electron app is closed, and prevent passive backend polling from waking MT5 unless the user explicitly enables auto-connect or clicks reconnect.

**Architecture:** Keep the existing FastAPI lifespan and service modules, but make backend background tasks owned and cancellable. Centralize MT5 connection behavior behind an `allow_launch` flag so passive polling can read from already-running terminals without starting a new terminal process.

**Tech Stack:** Python 3, FastAPI lifespan, asyncio tasks, MetaTrader5 Python package, pytest, unittest.mock, Electron main process shutdown remains unchanged in this first pass.

---

## Scope

This plan fixes the Python backend MT5 lifecycle only. It intentionally does not change Electron shutdown or Windows process-tree cleanup in `src/main/python-service.ts`; that can be a separate hardening plan after backend behavior is safe and test-covered.

## Current Problem Summary

The backend starts `streaming_loop()` and `order_sync_loop()` unconditionally in `python_service/app/main.py`. `streaming_loop()` calls `get_mt5_client()` every second, and `get_mt5_client()` calls `init_mt5(get_settings_path())`. `init_mt5()` can call `mt5.initialize(path=actual_path)`, which can wake or launch MT5. If the backend process survives app close, it can keep waking MT5.

## File Structure

- Modify: `python_service/app/services/mt5_service.py`
- Responsibility: Provide explicit MT5 connection helpers that distinguish passive connection attempts from launch-capable attempts, and expose a shutdown helper.
- Modify: `python_service/app/services/streaming_service.py`
- Responsibility: Poll MT5 for overlay/account/alert data only when settings allow passive or launch-capable polling, and exit cleanly on task cancellation.
- Modify: `python_service/app/services/order_sync_service.py`
- Responsibility: Keep order sync polling cancellable. Order sync may still launch/connect MT5 only when sync is enabled because it is an explicit automation feature.
- Modify: `python_service/app/main.py`
- Responsibility: Own background task handles during FastAPI lifespan, cancel them during shutdown, and call MT5 shutdown.
- Create: `tests/python/test_mt5_service.py`
- Responsibility: Unit-test `allow_launch` behavior in MT5 initialization without real MT5.
- Create: `tests/python/test_backend_lifespan.py`
- Responsibility: Unit-test lifespan startup/shutdown cancellation and MT5 shutdown.
- Create: `tests/python/test_streaming_service.py`
- Responsibility: Unit-test that disabled auto-connect avoids MT5 initialization and that cancellation exits cleanly.
- Modify: `tests/python/test_order_sync_service.py`
- Responsibility: Add cancellation behavior coverage for `order_sync_loop()`.

## Relevant Commands

- Run focused Python tests after each task: `pytest tests/python/<file>.py -v`
- Run all Python tests after the plan: `pytest tests/python`
- Do not rely on `npm test` for Python changes. This repo does not wire Python tests into npm scripts.

## Task 1: Add Launch-Safe MT5 Initialization

**Files:**
- Modify: `python_service/app/services/mt5_service.py:1-93`
- Create: `tests/python/test_mt5_service.py`

- [ ] **Step 1: Write failing tests for passive initialization**

Create `tests/python/test_mt5_service.py`:

```python
from python_service.app.services import mt5_service


class FakeMT5:
    def __init__(self, initialize_results):
        self.initialize_results = list(initialize_results)
        self.calls = []
        self.shutdown_calls = 0

    def initialize(self, **kwargs):
        self.calls.append(kwargs)
        if self.initialize_results:
            return self.initialize_results.pop(0)
        return False

    def shutdown(self):
        self.shutdown_calls += 1

    def last_error(self):
        return (1, 'failed')


def test_init_mt5_without_launch_does_not_use_path(monkeypatch):
    fake_mt5 = FakeMT5([False])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)

    result = mt5_service.init_mt5('C:/MetaTrader 5/terminal64.exe', allow_launch=False)

    assert result is False
    assert fake_mt5.calls == [{}]


def test_init_mt5_with_launch_uses_existing_directory_terminal(monkeypatch):
    fake_mt5 = FakeMT5([False, True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: path == 'C:/MetaTrader 5')
    monkeypatch.setattr(mt5_service.time, 'sleep', lambda seconds: None)

    result = mt5_service.init_mt5('C:/MetaTrader 5', allow_launch=True)

    assert result is True
    assert fake_mt5.calls == [{}, {'path': 'C:/MetaTrader 5/terminal64.exe'}]


def test_shutdown_mt5_suppresses_mt5_errors(monkeypatch):
    class BrokenMT5:
        def shutdown(self):
            raise RuntimeError('ipc already closed')

    monkeypatch.setattr(mt5_service, 'mt5', BrokenMT5())

    mt5_service.shutdown_mt5()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_mt5_service.py -v`

Expected: FAIL because `init_mt5()` does not accept `allow_launch`, `mt5_service.time` is not module-level, and `shutdown_mt5()` does not exist.

- [ ] **Step 3: Implement minimal launch-safe helper**

Modify `python_service/app/services/mt5_service.py`:

```python
import MetaTrader5 as mt5
import subprocess
import os
import time


def is_mt5_running() -> bool:
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(['tasklist'], text=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=startupinfo)
        return 'terminal64.exe' in output
    except Exception:
        return False


def launch_mt5(path: str):
    if not path or not os.path.exists(path):
        return False

    try:
        subprocess.Popen([path])
        return True
    except Exception:
        return False


def _resolve_mt5_executable_path(path: str | None) -> str | None:
    if not path or not os.path.exists(path):
        return None

    if os.path.isdir(path):
        executable_path = os.path.join(path, 'terminal64.exe')
        if os.path.exists(executable_path):
            return executable_path

    return path


def init_mt5(path: str | None = None, *, allow_launch: bool = True) -> bool:
    try:
        if mt5.initialize():
            return True
    except Exception as e:
        print(f'Error checking for open MT5: {e}')

    if not allow_launch:
        return False

    actual_path = _resolve_mt5_executable_path(path)
    max_retries = 4

    for i in range(max_retries):
        if actual_path:
            print(f'Attempting to initialize MT5 at: {actual_path} (Attempt {i+1}/{max_retries})')
            try:
                if mt5.initialize(path=actual_path):
                    return True
                print(f'Attempt {i+1}/{max_retries} failed, error code = {mt5.last_error()}')
            except Exception as e:
                print(f'MT5 initialization crashed: {e}')

        if i < max_retries - 1:
            time.sleep(1)

    print(f'MT5 initialization failed after {max_retries} attempts.')
    return False


def shutdown_mt5() -> None:
    try:
        mt5.shutdown()
    except Exception:
        pass


def get_settings_path():
    try:
        from python_service.app.routes.settings import get_settings
        return get_settings().mt5_path
    except Exception:
        return None


def get_mt5_client(*, allow_launch: bool = True):
    if init_mt5(get_settings_path(), allow_launch=allow_launch):
        return mt5
    return None


def get_account_info(*, allow_launch: bool = True) -> dict:
    if not init_mt5(get_settings_path(), allow_launch=allow_launch):
        return {}

    info = mt5.account_info()
    if info is None:
        return {}

    return info._asdict()


def get_positions(*, allow_launch: bool = True) -> list[dict]:
    if not init_mt5(get_settings_path(), allow_launch=allow_launch):
        return []

    positions = mt5.positions_get()
    if positions is None:
        return []

    return [p._asdict() for p in positions]
```

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/python/test_mt5_service.py -v`

Expected: PASS.

- [ ] **Step 5: Run MT5 route smoke tests**

Run: `pytest tests/python/test_mt5.py tests/python/test_mt5_polling.py -v`

Expected: PASS, or existing environment-specific MT5 assumptions only. Do not broaden scope if unrelated tests depend on local MT5 state.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/services/mt5_service.py tests/python/test_mt5_service.py
git commit -m "fix: gate mt5 launch during initialization"
```

## Task 2: Prevent Passive Streaming From Waking MT5

**Files:**
- Modify: `python_service/app/services/streaming_service.py:1-163`
- Create: `tests/python/test_streaming_service.py`

- [ ] **Step 1: Write failing test for auto-connect disabled**

Create `tests/python/test_streaming_service.py`:

```python
import asyncio
from types import SimpleNamespace

import pytest

from python_service.app.services import streaming_service


def test_should_poll_mt5_returns_false_when_auto_connect_disabled(monkeypatch):
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=False),
        raising=False,
    )

    assert streaming_service.should_poll_mt5() is False


def test_should_poll_mt5_returns_true_when_auto_connect_enabled(monkeypatch):
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=True),
        raising=False,
    )

    assert streaming_service.should_poll_mt5() is True


@pytest.mark.asyncio
async def test_streaming_loop_does_not_initialize_mt5_when_auto_connect_disabled(monkeypatch):
    calls = {'get_mt5_client': 0}

    monkeypatch.setattr(streaming_service, 'should_poll_mt5', lambda: False)

    def fake_get_mt5_client(*, allow_launch=True):
        calls['get_mt5_client'] += 1
        return None

    async def fake_sleep(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(streaming_service, 'get_mt5_client', fake_get_mt5_client)
    monkeypatch.setattr(streaming_service.asyncio, 'sleep', fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await streaming_service.streaming_loop()

    assert calls['get_mt5_client'] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_streaming_service.py -v`

Expected: FAIL because `should_poll_mt5()` does not exist and `streaming_loop()` does not check it.

- [ ] **Step 3: Implement minimal streaming gate and cancellation path**

Modify `python_service/app/services/streaming_service.py`:

At top-level imports, add a stable settings import so tests can patch it:

```python
from python_service.app.routes.settings import get_settings
```

Add this helper near global state:

```python
def should_poll_mt5() -> bool:
    try:
        return bool(get_settings().auto_connect)
    except Exception:
        return False
```

Modify `streaming_loop()` so the first lines inside `while True` are:

```python
async def streaming_loop():
    """Background task to poll MT5 and broadcast quotes/alerts."""
    while True:
        try:
            if not should_poll_mt5():
                await asyncio.sleep(1.0)
                continue

            client = get_mt5_client(allow_launch=True)
            if client and mt5.terminal_info():
                settings = get_settings()
```

Remove duplicate local imports of `get_settings` inside the loop where practical. Keep the rest of the function behavior unchanged.

Add explicit cancellation handling before the broad `except Exception`:

```python
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Streaming loop error: {e}")
            await asyncio.sleep(5)
```

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/python/test_streaming_service.py -v`

Expected: PASS.

- [ ] **Step 5: Run existing alert and MT5 polling tests**

Run: `pytest tests/python/test_mt5_polling.py tests/python/test_mt5.py -v`

Expected: PASS, or only known unrelated local MT5 environment failures.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/services/streaming_service.py tests/python/test_streaming_service.py
git commit -m "fix: prevent passive streaming from waking mt5"
```

## Task 3: Make Order Sync Loop Cancellable

**Files:**
- Modify: `python_service/app/services/order_sync_service.py:250-257`
- Modify: `tests/python/test_order_sync_service.py`

- [ ] **Step 1: Write failing cancellation test**

Append to `tests/python/test_order_sync_service.py`:

```python
@pytest.mark.asyncio
async def test_order_sync_loop_propagates_cancellation(monkeypatch):
    calls = {'tick': 0}

    async def fake_process_order_sync_tick():
        calls['tick'] += 1

    async def fake_sleep(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(order_sync_service, 'process_order_sync_tick', fake_process_order_sync_tick)
    monkeypatch.setattr(order_sync_service.asyncio, 'sleep', fake_sleep)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    with pytest.raises(asyncio.CancelledError):
        await order_sync_service.order_sync_loop()

    assert calls['tick'] == 1
```

- [ ] **Step 2: Run test to verify behavior**

Run: `pytest tests/python/test_order_sync_service.py::test_order_sync_loop_propagates_cancellation -v`

Expected: PASS on modern Python if `CancelledError` is not caught by `except Exception`, or FAIL if cancellation is swallowed. Even if it passes, continue to Step 3 to make behavior explicit and future-proof.

- [ ] **Step 3: Add explicit cancellation handling**

Modify `order_sync_loop()`:

```python
async def order_sync_loop() -> None:
    while True:
        try:
            await process_order_sync_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _state.last_error = str(exc)
            _save()
        await asyncio.sleep(max(_state.poll_interval_seconds, 0.5))
```

- [ ] **Step 4: Run focused tests**

Run: `pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/services/order_sync_service.py tests/python/test_order_sync_service.py
git commit -m "fix: make order sync polling cancellable"
```

## Task 4: Own And Cancel Backend Lifespan Tasks

**Files:**
- Modify: `python_service/app/main.py:1-50`
- Create: `tests/python/test_backend_lifespan.py`

- [ ] **Step 1: Write failing lifespan shutdown test**

Create `tests/python/test_backend_lifespan.py`:

```python
import asyncio

import pytest

from python_service.app import main as backend_main


@pytest.mark.asyncio
async def test_lifespan_cancels_background_tasks_and_shutdowns_mt5(monkeypatch):
    task_started = asyncio.Event()
    task_cancelled = asyncio.Event()
    shutdown_calls = {'count': 0}

    async def fake_streaming_loop():
        task_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            task_cancelled.set()
            raise

    async def fake_order_sync_loop():
        await asyncio.Event().wait()

    def fake_shutdown_mt5():
        shutdown_calls['count'] += 1

    monkeypatch.setattr(backend_main, 'streaming_loop', fake_streaming_loop)
    monkeypatch.setattr(backend_main, 'order_sync_loop', fake_order_sync_loop)
    monkeypatch.setattr(backend_main, 'shutdown_mt5', fake_shutdown_mt5, raising=False)

    async with backend_main.lifespan(backend_main.app):
        await asyncio.wait_for(task_started.wait(), timeout=1)

    await asyncio.wait_for(task_cancelled.wait(), timeout=1)
    assert shutdown_calls['count'] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_backend_lifespan.py -v`

Expected: FAIL because `main.py` does not import `shutdown_mt5`, does not store task handles, and does not cancel tasks in shutdown.

- [ ] **Step 3: Implement lifespan task ownership**

Modify `python_service/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from contextlib import asynccontextmanager, suppress

from python_service.app.routes.health import router as health_router
from python_service.app.routes.settings import router as settings_router
from python_service.app.routes.mt5 import router as mt5_router
from python_service.app.routes.overlay import router as overlay_router
from python_service.app.routes.alerts import router as alerts_router
from python_service.app.routes.stream import router as stream_router
from python_service.app.routes.notifications import router as notifications_router
from python_service.app.routes.history import router as history_router
from python_service.app.routes.awakening import router as awakening_router
from python_service.app.routes.order_sync import router as order_sync_router
from python_service.app.services.mt5_service import shutdown_mt5
from python_service.app.services.order_sync_service import order_sync_loop
from python_service.app.services.streaming_service import streaming_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks = [
        asyncio.create_task(streaming_loop()),
        asyncio.create_task(order_sync_loop()),
    ]
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task
        shutdown_mt5()
```

Keep the rest of router registration unchanged.

- [ ] **Step 4: Run focused lifespan test**

Run: `pytest tests/python/test_backend_lifespan.py -v`

Expected: PASS.

- [ ] **Step 5: Run Python backend tests affected by app import**

Run: `pytest tests/python/test_mt5.py tests/python/test_mt5_polling.py tests/python/test_backend_lifespan.py -v`

Expected: PASS. If `TestClient(app)` now starts background loops and causes real MT5 access, patch tests to use mocked service functions or adjust the lifespan test strategy without weakening production shutdown behavior.

- [ ] **Step 6: Commit**

```bash
git add python_service/app/main.py tests/python/test_backend_lifespan.py
git commit -m "fix: cancel backend polling tasks on shutdown"
```

## Task 5: Make MT5 Account And Position Reads Launch-Safe By Default

**Files:**
- Modify: `python_service/app/routes/mt5.py:1-123`
- Modify: `tests/python/test_mt5.py`
- Modify: `tests/python/test_mt5_polling.py`

- [ ] **Step 1: Write failing route tests**

Append to `tests/python/test_mt5.py`:

```python
def test_account_endpoint_does_not_allow_launch_by_default(monkeypatch):
    seen = {}

    def fake_get_account_info(*, allow_launch=True):
        seen['allow_launch'] = allow_launch
        return {}

    monkeypatch.setattr('python_service.app.routes.mt5.get_account_info', fake_get_account_info)
    client = TestClient(app)

    response = client.get('/mt5/account')

    assert response.status_code == 200
    assert seen['allow_launch'] is False


def test_positions_endpoint_does_not_allow_launch_by_default(monkeypatch):
    seen = {}

    def fake_get_positions(*, allow_launch=True):
        seen['allow_launch'] = allow_launch
        return []

    monkeypatch.setattr('python_service.app.routes.mt5.get_positions', fake_get_positions)
    client = TestClient(app)

    response = client.get('/mt5/positions')

    assert response.status_code == 200
    assert seen['allow_launch'] is False
```

- [ ] **Step 2: Run route tests to verify they fail**

Run: `pytest tests/python/test_mt5.py::test_account_endpoint_does_not_allow_launch_by_default tests/python/test_mt5.py::test_positions_endpoint_does_not_allow_launch_by_default -v`

Expected: FAIL because routes call helpers without `allow_launch=False`.

- [ ] **Step 3: Update passive routes only**

Modify `python_service/app/routes/mt5.py`:

```python
@router.get('/mt5/account')
def get_mt5_account():
    return get_account_info(allow_launch=False)


@router.get('/mt5/positions')
def get_mt5_positions():
    return get_positions(allow_launch=False)
```

Do not change `/mt5/launch`; it should remain the explicit user action that allows launch:

```python
success = init_mt5(path=settings.mt5_path, allow_launch=True)
```

- [ ] **Step 4: Run route tests**

Run: `pytest tests/python/test_mt5.py tests/python/test_mt5_polling.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/routes/mt5.py tests/python/test_mt5.py tests/python/test_mt5_polling.py
git commit -m "fix: keep passive mt5 endpoints from launching terminal"
```

## Task 6: Final Verification

**Files:**
- No planned source changes unless tests reveal defects.

- [ ] **Step 1: Run all Python tests**

Run: `pytest tests/python`

Expected: PASS, except any already-known unrelated local MT5 environment assumptions. If failures appear in changed behavior, fix them before proceeding.

- [ ] **Step 2: Run frontend tests only if route contract changes affect renderer assumptions**

Run: `npm run test:frontend`

Expected: PASS. This is optional for this Python-only change unless renderer behavior was changed.

- [ ] **Step 3: Manual smoke test in development**

Run: `npm run dev`

Expected: App opens. With `storage/settings.local.json` `auto_connect` set to `false`, MT5 should not launch on app startup or dashboard load. Clicking Dashboard "启动/重连 MT5" should still attempt connection/launch. Quitting from tray should stop the backend.

- [ ] **Step 4: Manual residual-process check on Windows**

Run after quitting the app:

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
Get-Process python, mt5_service -ErrorAction SilentlyContinue
```

Expected: No listener on port `8765`. No repo-owned `python -m python_service.app.main` or packaged `mt5_service` process remains. Do not kill unrelated user Python processes.

- [ ] **Step 5: Commit final test adjustments if any**

```bash
git add python_service/app tests/python
git commit -m "test: verify mt5 backend shutdown behavior"
```

Only run this commit if Step 1-4 required extra changes not already committed.

## Follow-Up Plan Candidates

- Electron shutdown hardening: make `killBackendOnPort()` verify that port `8765` is no longer listening and log failures instead of swallowing them.
- Packaged app smoke test: add an e2e shutdown assertion around `npm run build` plus `npm run test:electron` to catch residual backend processes.
- UI behavior: clarify `auto_connect` copy so users understand it controls startup/background MT5 polling.
