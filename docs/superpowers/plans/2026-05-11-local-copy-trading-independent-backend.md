# Local Copy Trading Independent Backend In-App Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `本地跟单` in-app module backed by a brand-new `python_service.app.local_copy_trading` backend package that is fully separate from the legacy MT5 and order-sync backend modules.

**Architecture:** Add a new renderer route and page for `#/local-copy-trading`, then back it with a dedicated FastAPI router, models, storage, runtime helpers, engine, and loop under `python_service.app.local_copy_trading`. Keep legacy `mt5` and `order_sync` code untouched except for `python_service/app/main.py` registering the new router and loop, so the new module stays isolated and can evolve independently.

**Tech Stack:** Electron, React, TypeScript, FastAPI, Pydantic, pytest, Vitest, `shadcn/ui`

---

## Scope Check

This is one user-facing feature, but it spans three coupled areas that should ship together:

1. New backend package and storage for local copy trading.
2. In-app module UI and store.
3. Sidebar and route wiring.

Do not split these unless the user explicitly asks for backend-only scaffolding first.

## File Structure

### Existing files to modify

- `python_service/app/main.py`
  Responsibility: register the new local copy trading router and background loop only.

- `src/renderer/src/App.tsx`
  Responsibility: add the `local-copy-trading` module route using the existing `HashRouter` pattern so the in-app route resolves to `#/local-copy-trading`.

- `src/renderer/src/components/module-nav.tsx`
  Responsibility: add the `本地跟单` navigation item.

- `src/renderer/src/i18n/messages.ts`
  Responsibility: add localized strings for the new module label and page copy.

- `src/renderer/src/test/dashboard-page.test.tsx`
  Responsibility: verify the sidebar exposes the new item, updates the route, and renders the in-app page through `App.tsx`.

### New files to create

- `python_service/app/local_copy_trading/__init__.py`
  Responsibility: mark the new backend package boundary.

- `python_service/app/local_copy_trading/models.py`
  Responsibility: define source accounts, follower accounts, relationships, sync events, runtime state, and request payload models.

- `python_service/app/local_copy_trading/storage.py`
  Responsibility: load and save local copy trading state from `storage/local_copy_trading.json`.

- `python_service/app/local_copy_trading/runtime.py`
  Responsibility: own in-memory runtime state, state mutation helpers, and overview/read-model assembly.

- `python_service/app/local_copy_trading/engine.py`
  Responsibility: execute sync fan-out logic without delegating to any legacy backend module.

- `python_service/app/local_copy_trading/source_adapter.py`
  Responsibility: own source-position acquisition for the new package so position fetching stays inside the new package boundary and does not drift back to legacy `mt5` or `order_sync` code.

- `python_service/app/local_copy_trading/loop.py`
  Responsibility: own the independent async background loop for the new package.

- `python_service/app/local_copy_trading/routes.py`
  Responsibility: expose overview and write-flow APIs for the new module.

- `tests/python/test_local_copy_trading_models.py`
  Responsibility: verify model defaults and multi-source/multi-follower shape.

- `tests/python/test_local_copy_trading_storage.py`
  Responsibility: verify dedicated storage load/save behavior.

- `tests/python/test_local_copy_trading_runtime.py`
  Responsibility: verify state mutations and overview assembly.

- `tests/python/test_local_copy_trading_engine.py`
  Responsibility: verify relationship filtering, multi-follower fan-out, and event recording.

- `tests/python/test_local_copy_trading_routes.py`
  Responsibility: verify isolated API endpoints and write flows using a router-only FastAPI app plus temporary storage.

- `tests/python/test_local_copy_trading_lifespan.py`
  Responsibility: verify `python_service/app/main.py` registers `local_copy_trading_loop` as a distinct new lifespan task.

- `src/renderer/src/stores/local-copy-trading-store.ts`
  Responsibility: fetch overview data and submit source/follower/relationship mutations to the new backend routes.

- `src/renderer/src/pages/LocalCopyTradingPage.tsx`
  Responsibility: render the new module page using existing `shadcn/ui` components only.

- `src/renderer/src/test/local-copy-trading-store.test.ts`
  Responsibility: verify the store hits only the new backend endpoints and handles success and failure states.

- `src/renderer/src/test/local-copy-trading-page.test.tsx`
  Responsibility: verify page rendering, multi-account management, relationship management, event display, and dialog flows.

## Design Rules

1. All new backend business logic for this feature must live under one dedicated package: `python_service.app.local_copy_trading`.
2. That package must not import, call, subclass, or otherwise reuse anything from the legacy `python_service.app.routes.mt5`, `python_service.app.services.mt5*`, `python_service.app.routes.order_sync`, `python_service.app.services.order_sync*`, or `python_service.app.models.order_sync*` namespaces.
3. The new renderer module must not reuse `OrderSyncPage` or `order-sync-store`.
4. Use existing `shadcn/ui` primitives already present under `src/renderer/src/components/ui` first.
5. Do not create custom base UI components unless a required `shadcn/ui` primitive is missing and there is no compositional alternative.
6. Do not create non-essential custom styles. Prefer `Card`, `Tabs`, `Table`, `Badge`, `Switch`, `Select`, `Dialog`, `ScrollArea`, `Separator`, `Button`, `Input`, and `Label` with existing variants.
7. Follow TDD strictly for both backend and frontend work.
8. Do not use `git add .` in this repo. Stage only files touched by the task.

## Suggested Backend Shape

```python
class SourceAccount(BaseModel):
    id: str = ''
    name: str
    connection_type: Literal['mt5_terminal', 'mt5_api', 'simulated'] = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True


class FollowerAccount(BaseModel):
    id: str = ''
    name: str
    connection_type: Literal['mt5_terminal', 'mt5_api', 'simulated'] = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True


class CopyRelationship(BaseModel):
    id: str = ''
    source_account_id: str
    follower_account_id: str
    symbol: str
    lot_multiplier: float = 1
    is_active: bool = True


class SyncEvent(BaseModel):
    id: str = ''
    relationship_id: str
    source_account_id: str
    follower_account_id: str
    symbol: str
    status: Literal['queued', 'copied', 'closed', 'failed', 'skipped'] = 'queued'
    message: str = ''
    created_at: str


class LocalCopyTradingState(BaseModel):
    enabled: bool = False
    poll_interval_seconds: float = 1
    source_accounts: list[SourceAccount] = []
    follower_accounts: list[FollowerAccount] = []
    relationships: list[CopyRelationship] = []
    events: list[SyncEvent] = []
    last_error: str | None = None
    last_checked_at: str | None = None
```

### Task 1: Scaffold the Independent Backend Package and Models

**Files:**
- Create: `python_service/app/local_copy_trading/__init__.py`
- Create: `python_service/app/local_copy_trading/models.py`
- Create: `tests/python/test_local_copy_trading_models.py`
- Test: `tests/python/test_local_copy_trading_models.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.local_copy_trading.models import SourceAccount, FollowerAccount, CopyRelationship, LocalCopyTradingState


def test_local_copy_trading_state_supports_multiple_sources_and_followers():
    state = LocalCopyTradingState(
        source_accounts=[
            SourceAccount(id='src-1', name='Main A'),
            SourceAccount(id='src-2', name='Main B'),
        ],
        follower_accounts=[
            FollowerAccount(id='fol-1', name='Follower A'),
            FollowerAccount(id='fol-2', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-2', follower_account_id='fol-2', symbol='NAS100'),
        ],
    )

    assert len(state.source_accounts) == 2
    assert len(state.follower_accounts) == 2
    assert state.relationships[0].symbol == 'XAUUSD'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_local_copy_trading_models.py::test_local_copy_trading_state_supports_multiple_sources_and_followers -v`
Expected: FAIL with missing package or model definitions.

- [ ] **Step 3: Write minimal implementation**

```python
class SourceAccount(BaseModel):
    id: str = ''
    name: str
    connection_type: str = 'simulated'
    terminal_path: str = ''
    login: str = ''
    server: str = ''
    password: str = ''
    is_active: bool = True
```

Repeat for `FollowerAccount`, `CopyRelationship`, `SyncEvent`, and `LocalCopyTradingState`.

- [ ] **Step 4: Run model tests**

Run: `pytest tests/python/test_local_copy_trading_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/__init__.py python_service/app/local_copy_trading/models.py tests/python/test_local_copy_trading_models.py
git commit -m "feat: scaffold local copy trading package models"
```

### Task 2: Add Dedicated Storage Module

**Files:**
- Create: `python_service/app/local_copy_trading/storage.py`
- Create: `tests/python/test_local_copy_trading_storage.py`
- Test: `tests/python/test_local_copy_trading_storage.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from python_service.app.local_copy_trading.storage import load_state


def test_storage_loads_default_state_when_file_missing(tmp_path: Path):
    state = load_state(tmp_path / 'local_copy_trading.json')

    assert state.enabled is False
    assert state.source_accounts == []
    assert state.follower_accounts == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_local_copy_trading_storage.py::test_storage_loads_default_state_when_file_missing -v`
Expected: FAIL with missing storage module.

- [ ] **Step 3: Write minimal implementation**

```python
def load_state(storage_path: Path | str = DEFAULT_STORAGE_PATH) -> LocalCopyTradingState:
    path = Path(storage_path)
    if not path.exists():
        return LocalCopyTradingState()
    return LocalCopyTradingState(**json.loads(path.read_text(encoding='utf-8')))
```

- [ ] **Step 4: Run storage tests**

Run: `pytest tests/python/test_local_copy_trading_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/storage.py tests/python/test_local_copy_trading_storage.py
git commit -m "feat: add local copy trading storage module"
```

### Task 3: Add Runtime State Module

**Files:**
- Create: `python_service/app/local_copy_trading/runtime.py`
- Create: `tests/python/test_local_copy_trading_runtime.py`
- Test: `tests/python/test_local_copy_trading_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.local_copy_trading.models import CopyRelationship, LocalCopyTradingState
from python_service.app.local_copy_trading.runtime import add_relationship


def test_runtime_adds_relationship():
    state = LocalCopyTradingState()
    updated = add_relationship(state, CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'))

    assert len(updated.relationships) == 1
    assert updated.relationships[0].id == 'rel-1'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_local_copy_trading_runtime.py::test_runtime_adds_relationship -v`
Expected: FAIL with missing runtime helper.

- [ ] **Step 3: Write minimal implementation**

```python
def add_relationship(state: LocalCopyTradingState, relationship: CopyRelationship) -> LocalCopyTradingState:
    state.relationships.append(relationship)
    return state
```

- [ ] **Step 4: Run runtime tests**

Run: `pytest tests/python/test_local_copy_trading_runtime.py -v`
Expected: PASS with add/update/remove coverage for source accounts, follower accounts, and relationships.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/runtime.py tests/python/test_local_copy_trading_runtime.py
git commit -m "feat: add local copy trading runtime module"
```

### Task 4: Add Independent Engine and Loop Modules

**Files:**
- Create: `python_service/app/local_copy_trading/engine.py`
- Create: `python_service/app/local_copy_trading/source_adapter.py`
- Create: `python_service/app/local_copy_trading/loop.py`
- Create: `tests/python/test_local_copy_trading_engine.py`
- Test: `tests/python/test_local_copy_trading_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.local_copy_trading.engine import process_tick
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, LocalCopyTradingState, SourceAccount


def test_engine_fans_out_one_source_position_to_multiple_followers():
    state = LocalCopyTradingState(
        enabled=True,
        source_accounts=[SourceAccount(id='src-1', name='Main A')],
        follower_accounts=[
            FollowerAccount(id='fol-1', name='Follower A'),
            FollowerAccount(id='fol-2', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-1', follower_account_id='fol-2', symbol='XAUUSD'),
        ],
    )

    events = process_tick(state, source_positions=[{'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(events) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_local_copy_trading_engine.py::test_engine_fans_out_one_source_position_to_multiple_followers -v`
Expected: FAIL with missing engine function.

- [ ] **Step 3: Write minimal implementation**

```python
def process_tick(state: LocalCopyTradingState, source_positions: list[dict]) -> list[SyncEvent]:
    events: list[SyncEvent] = []
    for relationship in state.relationships:
        for position in source_positions:
            if relationship.source_account_id == position.get('source_account_id') and relationship.symbol == position.get('symbol'):
                events.append(SyncEvent(
                    relationship_id=relationship.id,
                    source_account_id=relationship.source_account_id,
                    follower_account_id=relationship.follower_account_id,
                    symbol=relationship.symbol,
                    status='copied',
                    created_at='2026-05-11T00:00:00+00:00',
                ))
    return events
```

- [ ] **Step 4: Run engine tests**

Run: `pytest tests/python/test_local_copy_trading_engine.py -v`
Expected: PASS with explicit coverage for multi-source filtering, inactive relationships, inactive followers, and event recording.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/engine.py python_service/app/local_copy_trading/source_adapter.py python_service/app/local_copy_trading/loop.py tests/python/test_local_copy_trading_engine.py
git commit -m "feat: add local copy trading engine and loop modules"
```

### Task 5: Add Isolated Routes and Main Registration

**Files:**
- Create: `python_service/app/local_copy_trading/routes.py`
- Modify: `python_service/app/main.py`
- Create: `tests/python/test_local_copy_trading_routes.py`
- Create: `tests/python/test_local_copy_trading_lifespan.py`

- [ ] **Step 1: Write the failing route tests**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from python_service.app.local_copy_trading.routes import router as local_copy_trading_router


def test_get_overview_returns_local_copy_payload(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(local_copy_trading_router)
    client = TestClient(app)

    response = client.get('/local-copy-trading')

    assert response.status_code == 200
    assert 'source_accounts' in response.json()
    assert 'follower_accounts' in response.json()
    assert 'relationships' in response.json()
    assert 'events' in response.json()
```

Add three more failing route tests:
1. `POST /local-copy-trading/source-accounts`
2. `POST /local-copy-trading/follower-accounts`
3. `POST /local-copy-trading/relationships`

Each test must:
1. build a tiny isolated `FastAPI()` app with only `local_copy_trading_router`
2. monkeypatch the new storage module to `tmp_path / 'local_copy_trading.json'`
3. reset in-memory local-copy runtime state before the request

Add one failing lifespan test in `tests/python/test_local_copy_trading_lifespan.py` that monkeypatches `python_service.app.main.streaming_loop`, `python_service.app.main.order_sync_loop`, and `python_service.app.main.local_copy_trading_loop`, enters the real app lifespan, and asserts the local-copy loop starts as a distinct third task.

Add one more failing integration test in `tests/python/test_local_copy_trading_lifespan.py` that creates `TestClient(python_service.app.main.app)` and asserts `GET /local-copy-trading` returns `200`, proving the real `main.app` serves the new router.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python/test_local_copy_trading_routes.py tests/python/test_local_copy_trading_lifespan.py -v`
Expected: FAIL with missing routes or missing loop registration.

- [ ] **Step 3: Write minimal implementation**

```python
router = APIRouter(prefix='/local-copy-trading')


@router.get('')
def get_overview():
    return get_overview_payload()
```

Then add:
1. `POST /local-copy-trading/source-accounts`
2. `POST /local-copy-trading/follower-accounts`
3. `POST /local-copy-trading/relationships`

And register:
1. `app.include_router(local_copy_trading_router)`
2. `asyncio.create_task(local_copy_trading_loop())`

in `python_service/app/main.py`.

- [ ] **Step 4: Run route and lifespan tests**

Run: `pytest tests/python/test_local_copy_trading_routes.py tests/python/test_local_copy_trading_lifespan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/routes.py python_service/app/main.py tests/python/test_local_copy_trading_routes.py tests/python/test_local_copy_trading_lifespan.py
git commit -m "feat: expose local copy trading routes and register loop"
```

### Task 6: Add Independent Frontend Store

**Files:**
- Create: `src/renderer/src/stores/local-copy-trading-store.ts`
- Create: `src/renderer/src/test/local-copy-trading-store.test.ts`
- Test: `src/renderer/src/test/local-copy-trading-store.test.ts`

- [ ] **Step 1: Write the failing tests**

```tsx
it('loads overview data from the local copy trading endpoint only', async () => {
  global.fetch = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading')
    return {
      ok: true,
      json: async () => ({
        runtime: { enabled: true, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
        source_accounts: [{ id: 'src-1', name: 'Main A' }],
        follower_accounts: [{ id: 'fol-1', name: 'Follower A' }],
        relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD' }],
        events: [{ id: 'evt-1', relationship_id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', status: 'copied', created_at: '2026-05-11T00:00:00+00:00' }],
      }),
    } as Response
  }) as any
```

Add one failing error-path test that expects store error state when `fetch` returns `ok: false`.

Add three failing POST tests in `src/renderer/src/test/local-copy-trading-store.test.ts` that assert the store uses:
1. `POST http://127.0.0.1:8765/local-copy-trading/source-accounts`
2. `POST http://127.0.0.1:8765/local-copy-trading/follower-accounts`
3. `POST http://127.0.0.1:8765/local-copy-trading/relationships`

Each test must assert method, JSON body, and successful state refresh.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-store.test.ts`
Expected: FAIL with missing store module.

- [ ] **Step 3: Write minimal implementation**

```ts
const API_BASE = 'http://127.0.0.1:8765/local-copy-trading'
```

- [ ] **Step 4: Run store tests**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-store.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/stores/local-copy-trading-store.ts src/renderer/src/test/local-copy-trading-store.test.ts
git commit -m "feat: add local copy trading store"
```

### Task 7: Add In-App Page With shadcn/ui Only

**Files:**
- Create: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Create: `src/renderer/src/test/local-copy-trading-page.test.tsx`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it('renders the local copy trading heading and tabs', async () => {
  render(<LocalCopyTradingPage />)

  expect(await screen.findByRole('heading', { name: 'Local Copy Trading' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Source Accounts' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Follower Accounts' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Relationships' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Events' })).toBeInTheDocument()
})
```

Add one failing test that expects multiple source rows, multiple follower rows, and at least one relationship row.

Add one failing test that expects a runtime/config section to render values such as enabled state and poll interval from store data.

Render these page tests through the existing i18n provider test harness pattern used elsewhere in `src/renderer/src/test`, or explicitly force the language to `en`, so string assertions remain stable.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-page.test.tsx`
Expected: FAIL with missing page.

- [ ] **Step 3: Write minimal implementation**

```tsx
<Tabs defaultValue="sources">
  <TabsList>
    <TabsTrigger value="sources">Source Accounts</TabsTrigger>
    <TabsTrigger value="followers">Follower Accounts</TabsTrigger>
    <TabsTrigger value="relationships">Relationships</TabsTrigger>
    <TabsTrigger value="events">Events</TabsTrigger>
  </TabsList>
</Tabs>
```

- [ ] **Step 4: Run page tests**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-page.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/pages/LocalCopyTradingPage.tsx src/renderer/src/test/local-copy-trading-page.test.tsx
git commit -m "feat: add local copy trading page"
```

### Task 8: Add Source/Follower/Relationship Write Flows

**Files:**
- Modify: `python_service/app/local_copy_trading/routes.py`
- Modify: `python_service/app/local_copy_trading/runtime.py`
- Modify: `src/renderer/src/stores/local-copy-trading-store.ts`
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Modify: `src/renderer/src/test/local-copy-trading-page.test.tsx`
- Modify: `tests/python/test_local_copy_trading_routes.py`

- [ ] **Step 1: Write the failing tests**

```tsx
it('submits source-account, follower-account, and relationship dialogs and refreshes the page', async () => {
  render(<LocalCopyTradingPage />)

  await user.click(await screen.findByRole('button', { name: 'Add Source Account' }))
  await user.type(screen.getByLabelText('Source Account Name'), 'Main A')
  await user.click(screen.getByRole('button', { name: 'Save Source Account' }))

  await user.click(screen.getByRole('button', { name: 'Add Follower Account' }))
  await user.type(screen.getByLabelText('Follower Account Name'), 'Follower A')
  await user.click(screen.getByRole('button', { name: 'Save Follower Account' }))

  await user.click(screen.getByRole('button', { name: 'Add Relationship' }))
  await user.click(screen.getByRole('button', { name: 'Save Relationship' }))

  expect(await screen.findByText('Main A')).toBeInTheDocument()
  expect(await screen.findByText('Follower A')).toBeInTheDocument()
})
```

Add one failing frontend assertion that a failed POST shows an error state and does not leave the dialog in a fake success state.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-page.test.tsx`
Expected: FAIL because write flows do not exist.

- [ ] **Step 3: Write minimal implementation**

```tsx
<Dialog>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Add Source Account</DialogTitle>
    </DialogHeader>
    <Input />
    <Button>Save</Button>
  </DialogContent>
</Dialog>
```

Repeat the same pattern for follower accounts and relationships.

- [ ] **Step 4: Run page and route tests**

Run: `npm run test:frontend -- src/renderer/src/test/local-copy-trading-page.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/stores/local-copy-trading-store.ts src/renderer/src/pages/LocalCopyTradingPage.tsx src/renderer/src/test/local-copy-trading-page.test.tsx
git commit -m "feat: add local copy trading management flows"
```

### Task 9: Wire Sidebar and Route

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx`
- Modify: `src/renderer/src/App.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it('navigates to and renders the local copy trading page from the sidebar', async () => {
  const user = userEvent.setup()
  render(<TestRoot />)

  const trigger = await getSidebarTrigger()
  await user.click(trigger)
  const nav = getSidebarNav()
  if (!nav) throw new Error('Sidebar navigation not found')

  await user.click(await within(nav).findByRole('button', { name: 'Local Copy Trading' }))

  expect(window.location.hash).toContain('/local-copy-trading')
  expect(await screen.findByRole('heading', { name: 'Local Copy Trading' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: FAIL because the item and route do not exist.

- [ ] **Step 3: Write minimal implementation**

```tsx
const VALID_MODULES = new Set([
  'dashboard',
  'local-copy-trading',
])
```

Also render the new page branch in `App.tsx`:

```tsx
{activeModule === 'local-copy-trading' && <LocalCopyTradingPage />}
```

Important: append the new module to the existing `VALID_MODULES` set and keep all existing page branches unchanged.

- [ ] **Step 4: Run renderer tests**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/components/module-nav.tsx src/renderer/src/App.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/dashboard-page.test.tsx
git commit -m "feat: add local copy trading navigation"
```

### Task 10: Run Full Verification

**Files:**
- Modify: none unless fixes are required
- Test: `src/renderer/src/test/dashboard-page.test.tsx`
- Test: `src/renderer/src/test/local-copy-trading-store.test.ts`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`
- Test: `tests/python/test_local_copy_trading_models.py`
- Test: `tests/python/test_local_copy_trading_storage.py`
- Test: `tests/python/test_local_copy_trading_runtime.py`
- Test: `tests/python/test_local_copy_trading_engine.py`
- Test: `tests/python/test_local_copy_trading_routes.py`
- Test: `tests/python/test_local_copy_trading_lifespan.py`

- [ ] **Step 1: Run frontend tests**

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 2: Run Python tests**

Run: `pytest tests/python/test_local_copy_trading_models.py tests/python/test_local_copy_trading_storage.py tests/python/test_local_copy_trading_runtime.py tests/python/test_local_copy_trading_engine.py tests/python/test_local_copy_trading_routes.py tests/python/test_local_copy_trading_lifespan.py -v`
Expected: PASS

- [ ] **Step 3: Verify backend independence and UI composition constraints**

Run: `rg "python_service\.app\.(routes\.mt5|services\.mt5|routes\.order_sync|services\.order_sync|models\.order_sync)" python_service/app/local_copy_trading`
Expected: no matches

Run: `rg "from python_service\.app\.(routes|services|models) import (mt5|mt5_service|order_sync|order_sync_service)" python_service/app/local_copy_trading`
Expected: no matches

Run: `rg "@/components/ui/" src/renderer/src/pages/LocalCopyTradingPage.tsx`
Expected: matches for page primitives imported from existing `@/components/ui/*`

Run: `rg -P "@/components/(?!ui/|page-header$)" src/renderer/src/pages/LocalCopyTradingPage.tsx`
Expected: no matches for non-approved component imports

- [ ] **Step 4: Build the app**

Run: `npm run build`
Expected: PASS and produce `out/main`, `out/preload`, and `out/renderer`.

- [ ] **Step 5: Smoke-test manually**

Run: `npm run dev`
Expected:
1. Electron app opens normally.
2. Clicking `本地跟单` navigates to the in-app page.
3. The page shows source accounts, follower accounts, relationships, runtime status, and sync events.

- [ ] **Step 6: Commit any final fixes**

```bash
git add python_service/app/main.py python_service/app/local_copy_trading/__init__.py python_service/app/local_copy_trading/models.py python_service/app/local_copy_trading/storage.py python_service/app/local_copy_trading/runtime.py python_service/app/local_copy_trading/engine.py python_service/app/local_copy_trading/source_adapter.py python_service/app/local_copy_trading/loop.py python_service/app/local_copy_trading/routes.py src/renderer/src/App.tsx src/renderer/src/components/module-nav.tsx src/renderer/src/i18n/messages.ts src/renderer/src/stores/local-copy-trading-store.ts src/renderer/src/pages/LocalCopyTradingPage.tsx src/renderer/src/test/dashboard-page.test.tsx src/renderer/src/test/local-copy-trading-store.test.ts src/renderer/src/test/local-copy-trading-page.test.tsx tests/python/test_local_copy_trading_models.py tests/python/test_local_copy_trading_storage.py tests/python/test_local_copy_trading_runtime.py tests/python/test_local_copy_trading_engine.py tests/python/test_local_copy_trading_routes.py tests/python/test_local_copy_trading_lifespan.py
git commit -m "test: verify local copy trading module end to end"
```

## Notes For The Implementer

1. Keep all new backend business logic inside `python_service.app.local_copy_trading`.
2. Do not import any legacy `mt5` or `order_sync` backend namespace into the new package.
3. Keep the new module’s persistence isolated in its own storage file.
4. Keep the new UI inside the existing renderer route structure.
5. Prefer `Table` plus `Dialog` over custom layout systems for account management tables.
