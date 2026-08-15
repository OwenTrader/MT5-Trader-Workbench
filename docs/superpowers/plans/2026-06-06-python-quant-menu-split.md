# Python Quant Menu Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current `Python Quant` area into a live account-strategy assignment module and a separate `Quant Backtest` module, while making strategy discovery and user-added strategies explicit.

**Architecture:** Keep the existing `python-quant` live runtime flow for job assignment, status, and manual market-data backfill, but narrow the page so it is only about live task management. Add a separate backtest backend and renderer flow that reuses the existing strategy registry and local SQLite market-data cache. Expand strategy discovery so the backend scans both built-in strategy modules and a user-writable local strategy directory.

**Tech Stack:** FastAPI, Pydantic, Backtrader, SQLite (`sqlite3`), Electron, React, Zustand, Vitest, Pytest, shadcn/ui

---

## Scope Check

This request touches two user-facing areas that are tightly related enough to plan together:

- live strategy assignment/runtime management
- historical backtesting

Keep the first backtest release minimal and testable. If you later want optimization, chart-heavy analytics, or strategy editing, write a separate follow-up plan.

## File Structure

### Create

- `python_service/app/quant/paths.py`
  Responsibility: resolve user-writable quant directories for development and packaged builds.
- `python_service/app/quant/backtest_models.py`
  Responsibility: request/response models for backtest runs and results.
- `python_service/app/quant/backtest_service.py`
  Responsibility: run historical backtests from local cached bars and normalize metrics/trades/equity curve.
- `python_service/app/quant/backtest_routes.py`
  Responsibility: FastAPI endpoints for backtest strategy listing and backtest execution.
- `tests/python/test_quant_strategy_registry.py`
  Responsibility: verify built-in and user strategy discovery.
- `tests/python/test_quant_backtest_service.py`
  Responsibility: verify backtest metrics, equity curve, and error handling.
- `tests/python/test_quant_backtest_routes.py`
  Responsibility: verify HTTP contract for running a backtest.
- `src/renderer/src/lib/quant-backtest.ts`
  Responsibility: typed frontend parser and payload helpers for backtest responses.
- `src/renderer/src/stores/quant-backtest-store.ts`
  Responsibility: Zustand state for backtest execution and result display.
- `src/renderer/src/pages/QuantBacktestPage.tsx`
  Responsibility: dedicated UI for choosing strategy/data range and showing backtest results.
- `src/renderer/src/test/quant-backtest-store.test.ts`
  Responsibility: store request/error/result handling tests.
- `src/renderer/src/test/quant-backtest-page.test.tsx`
  Responsibility: page interaction tests for the new backtest module.

### Modify

- `python_service/app/quant/strategy_registry.py:1-41`
  Responsibility: explain and extend strategy discovery to built-in package + local user strategy directory.
- `python_service/app/quant/storage.py:1-23`
  Responsibility: move quant job persistence path resolution onto the same dev/packaged path contract as the rest of the quant runtime.
- `src/main/python-service.ts:54-235`
  Responsibility: pass quant runtime directory environment variables to the backend in both dev and packaged modes.
- `python_service/app/quant/runtime.py:29-95`
  Responsibility: keep live overview focused on live assignment/runtime state while preserving account-list integration.
- `python_service/app/quant/routes.py:1-172`
  Responsibility: keep live module routes limited to assignment/runtime/backfill; do not add backtest logic here.
- `python_service/app/quant/market_data.py:1-174`
  Responsibility: support historical bar queries by explicit date range for backtests.
- `python_service/app/services/mt5_service.py:344-498`
  Responsibility: add account-scoped MT5 historical bar fetch by explicit date range for backfill and backtest support.
- `python_service/app/main.py:18-135`
  Responsibility: register the new backtest router.
- `src/renderer/src/App.tsx:23-67`
  Responsibility: add `quant-backtest` route and keep `python-quant` for live task management only.
- `src/renderer/src/components/module-nav.tsx:23-91`
  Responsibility: place both `Python Quant` and `Quant Backtest` under the `独立账户模块` / `Independent Accounts` group.
- `src/renderer/src/pages/PythonQuantPage.tsx:1-612`
  Responsibility: narrow the page to live assignment, runtime status, and manual data backfill only.
- `src/renderer/src/stores/python-quant-store.ts:15-132`
  Responsibility: keep only live-job mutations and overview refresh.
- `src/renderer/src/lib/python-quant.ts:1-219`
  Responsibility: keep types focused on live jobs/overview.
- `src/renderer/src/i18n/messages.ts:16-120, 638-768`
  Responsibility: add `nav.quantBacktest`, split copy between live quant and backtest, and make account-list dependency explicit.
- `src/renderer/src/test/python-quant-page.test.tsx:1-335`
  Responsibility: verify the live page no longer implies backtest behavior.
- `README.md:7-139`
  Responsibility: document strategy discovery, user strategy directory, and the new two-menu structure.
- `README.zh-CN.md:7-133`
  Responsibility: same documentation in Chinese.
- `.gitignore:1-26`
  Responsibility: ensure local strategy/user-cache runtime paths stay ignored if new local strategy directory is introduced.

### Runtime Directories

- `storage/python_quant/strategies/`
  Responsibility: user drop-in strategy directory scanned in addition to built-in strategies.

### Path Rule

- In development, quant runtime paths may stay under repo `storage/python_quant/`.
- In packaged builds, user-added strategies and generated backtest/runtime data must resolve to a user-writable app-data location, not the packaged resources directory.
- Pass those paths from Electron main to the backend through environment variables, following the same pattern already used for settings paths.

## Strategy Discovery Design

After this change, the strategy list should be computed from two sources:

1. Built-in strategies in `python_service/app/quant/strategies/`
2. User strategies in `storage/python_quant/strategies/`

Each strategy file must expose:

- `STRATEGY_ID`
- `STRATEGY_NAME`
- `STRATEGY_DESCRIPTION`
- `SUPPORTED_TIMEFRAMES`
- `Strategy`

The live and backtest menus must use the same unified strategy list.

## Menu Split Design

### `Python Quant`

This menu should only handle:

- account selection from `Account List`
- strategy selection
- symbol/timeframe/lot assignment
- job create/update/delete
- job start/stop
- status, last signal, last error, last bar time
- manual data backfill

### `Quant Backtest`

This menu should only handle:

- strategy selection
- account/data-source selection from the same account pool
- symbol/timeframe/date range selection
- run backtest
- show summary metrics
- show a compact trade list and equity curve summary

## Backtest API Shape

Use these endpoints.

- `GET /python-quant/backtests/strategies`
- `POST /python-quant/backtests/run`

Suggested response shape:

```json
{
  "strategy": {"id": "sma_cross", "name": "SMA Cross"},
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "range": {"start_at": "2026-05-01T00:00:00Z", "end_at": "2026-05-31T23:59:59Z"},
  "summary": {
    "total_return_pct": 4.52,
    "trade_count": 18,
    "win_rate_pct": 55.56,
    "max_drawdown_pct": -2.14
  },
  "equity_curve": [
    {"time": "2026-05-01T00:00:00Z", "equity": 10000.0},
    {"time": "2026-05-02T00:00:00Z", "equity": 10031.2}
  ],
  "trades": [
    {"entry_time": "2026-05-02T08:00:00Z", "exit_time": "2026-05-02T10:30:00Z", "side": "buy", "pnl": 31.2}
  ]
}
```

## Task 1: Strategy Discovery And User Strategy Directory

**Files:**
- Create: `python_service/app/quant/paths.py`
- Modify: `python_service/app/quant/strategy_registry.py`
- Modify: `python_service/app/quant/storage.py`
- Modify: `src/main/python-service.ts`
- Create: `tests/python/test_quant_strategy_registry.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Write the failing strategy-registry test**

```python
from python_service.app.quant.strategy_registry import list_strategies


def test_list_strategies_reads_user_strategy_directory(tmp_path, monkeypatch):
    strategies_dir = tmp_path / 'strategies'
    strategies_dir.mkdir()
    (strategies_dir / 'custom_breakout.py').write_text(
        """
STRATEGY_ID = 'custom_breakout'
STRATEGY_NAME = 'Custom Breakout'
STRATEGY_DESCRIPTION = 'User strategy.'
SUPPORTED_TIMEFRAMES = ['M5']
class Strategy: pass
""",
        encoding='utf-8',
    )
    monkeypatch.setenv('PYTHON_QUANT_STRATEGIES_DIR', str(strategies_dir))

    strategies = list_strategies()

    assert any(item.id == 'custom_breakout' for item in strategies)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_strategy_registry.py::test_list_strategies_reads_user_strategy_directory -v`
Expected: FAIL because user strategy directory scanning is not implemented

- [ ] **Step 3: Implement built-in + user strategy discovery**

```python
def list_strategies() -> list[StrategyDescriptor]:
    return [
        *load_builtin_strategies(),
        *load_user_strategies(get_user_strategies_dir()),
    ]
```

- [ ] **Step 4: Resolve user strategy directory for dev and packaged builds**

Use a helper like:

```python
def get_user_strategies_dir() -> Path:
    return Path(os.environ.get('PYTHON_QUANT_STRATEGIES_DIR', 'storage/python_quant/strategies'))


def get_jobs_path() -> Path:
    return Path(os.environ.get('PYTHON_QUANT_JOBS_PATH', 'storage/python_quant/jobs.json'))
```

And pass those environment variables from `src/main/python-service.ts` for both development and packaged app-data locations.

- [ ] **Step 5: Add docs for user-added strategies**

Document that users can add strategies by dropping Python files into:

```text
storage/python_quant/strategies/
```

- [ ] **Step 6: Run the focused test**

Run: `pytest tests/python/test_quant_strategy_registry.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python_service/app/quant/paths.py python_service/app/quant/strategy_registry.py python_service/app/quant/storage.py src/main/python-service.ts tests/python/test_quant_strategy_registry.py README.md README.zh-CN.md
git commit -m "feat: support user quant strategy discovery"
```

## Task 2: Split Navigation And Route Skeleton

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx`
- Modify: `src/renderer/src/App.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Create: `src/renderer/src/pages/QuantBacktestPage.tsx`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] **Step 1: Write the failing nav test**

```tsx
it('renders both Python Quant and Quant Backtest inside the account module group', async () => {
  render(<TestApp />)

  expect(await screen.findByText('Python Quant')).toBeInTheDocument()
  expect(screen.getByText('Quant Backtest')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx`
Expected: FAIL because `Quant Backtest` route/menu does not exist

- [ ] **Step 3: Add the new nav entry and route**

Add `quant-backtest` under the `localCopyTrading` group in `module-nav.tsx`, and add the route in `App.tsx`.

- [ ] **Step 4: Add a minimal `QuantBacktestPage` skeleton so the app still compiles**

```tsx
export function QuantBacktestPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Quant Backtest" icon={LineChart} />
      <Card>
        <CardHeader>
          <CardTitle>Quant Backtest</CardTitle>
          <p className="text-sm text-muted-foreground">Run historical backtests with local cached MT5 market data.</p>
        </CardHeader>
      </Card>
    </div>
  )
}
```

- [ ] **Step 5: Add i18n keys**

Add:

```ts
nav: {
  quantBacktest: 'Quant Backtest',
}

quantBacktest: {
  title: 'Quant Backtest',
  description: 'Run historical backtests with local cached MT5 market data.',
  run: 'Run Backtest',
}
```

- [ ] **Step 6: Run the focused test**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/components/module-nav.tsx src/renderer/src/App.tsx src/renderer/src/i18n/messages.ts src/renderer/src/pages/QuantBacktestPage.tsx src/renderer/src/test/python-quant-page.test.tsx
git commit -m "feat: split quant navigation"
```

## Task 3: Refocus The Existing Python Quant Page On Live Assignment

**Files:**
- Modify: `src/renderer/src/pages/PythonQuantPage.tsx`
- Modify: `src/renderer/src/stores/python-quant-store.ts`
- Modify: `src/renderer/src/lib/python-quant.ts`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`
- Test: `src/renderer/src/test/python-quant-store.test.ts`

- [ ] **Step 1: Write the failing page test**

```tsx
it('shows that Python Quant reuses Account List accounts for live assignments', async () => {
  renderPage()

  expect(await screen.findByText(/already configured in Account List/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Run Backtest' })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx`
Expected: FAIL until live page copy and responsibilities are narrowed

- [ ] **Step 3: Keep the page focused on live job management**

Retain only:

- job create/edit/delete
- job start/stop
- runtime status table
- manual data backfill

Remove any copy that implies backtest belongs on this page.

- [ ] **Step 4: Make Account List dependency explicit**

Add helper copy like:

```tsx
Python Quant uses MT5 accounts already configured in Account List.
```

- [ ] **Step 5: Run focused live-page tests**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/python-quant-store.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/renderer/src/pages/PythonQuantPage.tsx src/renderer/src/stores/python-quant-store.ts src/renderer/src/lib/python-quant.ts src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/python-quant-store.test.ts
git commit -m "refactor: focus python quant on live assignments"
```

## Task 4: Add Backend Backtest Service

**Files:**
- Create: `python_service/app/quant/backtest_models.py`
- Create: `python_service/app/quant/backtest_service.py`
- Modify: `python_service/app/quant/market_data.py`
- Modify: `python_service/app/services/mt5_service.py`
- Create: `tests/python/test_quant_backtest_service.py`

- [ ] **Step 1: Write the failing backtest-service test**

```python
from python_service.app.quant.backtest_service import run_backtest


def test_run_backtest_returns_summary_and_trades(monkeypatch):
    monkeypatch.setattr(
        'python_service.app.quant.backtest_service.load_bars_for_range',
        lambda **kwargs: [
            {'time': '2026-05-01T00:00:00Z', 'open': 1, 'high': 2, 'low': 1, 'close': 2, 'tick_volume': 10},
        ],
    )

    result = run_backtest(account_id='acc-1', strategy_id='sma_cross', symbol='XAUUSD', timeframe='M15', start_at='2026-05-01T00:00:00Z', end_at='2026-05-31T23:59:59Z')

    assert 'summary' in result
    assert 'trades' in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_backtest_service.py::test_run_backtest_returns_summary_and_trades -v`
Expected: FAIL because backtest service does not exist

- [ ] **Step 3: Implement the minimal backtest service**

Use the existing strategy registry and local bar cache. Compute summary metrics, trades, and a compact equity curve from cached historical data.

Use one explicit service signature throughout the implementation:

```python
def run_backtest(*, account_id: str, strategy_id: str, symbol: str, timeframe: Timeframe, start_at: str, end_at: str) -> dict:
    ...
```

- [ ] **Step 4: Add date-range bar loading to the market-data layer**

Implement a helper in `python_service/app/quant/market_data.py` like:

```python
def load_bars_for_range(db_path: Path | str, account_id: str, symbol: str, timeframe: Timeframe, start_at: str, end_at: str) -> list[dict]:
    ...
```

If the local cache does not fully cover the requested range, backfill from MT5 first and then query the SQLite rows for that range.

- [ ] **Step 5: Add explicit MT5 range-fetch support**

Modify `python_service/app/services/mt5_service.py` with a helper like:

```python
def fetch_account_bars_range(path: str, login: str, password: str, server: str, symbol: str, timeframe: Timeframe, start_at: str, end_at: str) -> list[dict]:
    ...
```

Use MT5’s time-range history APIs so backtest range backfill does not have to guess candle counts.

- [ ] **Step 6: Run focused backtest-service tests**

Run: `pytest tests/python/test_quant_backtest_service.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python_service/app/quant/backtest_models.py python_service/app/quant/backtest_service.py python_service/app/quant/market_data.py python_service/app/services/mt5_service.py tests/python/test_quant_backtest_service.py
git commit -m "feat: add quant backtest service"
```

## Task 5: Add Backend Backtest Routes

**Files:**
- Create: `python_service/app/quant/backtest_routes.py`
- Modify: `python_service/app/main.py`
- Create: `tests/python/test_quant_backtest_routes.py`

- [ ] **Step 1: Write the failing backtest-route test**

```python
from fastapi.testclient import TestClient
from fastapi import FastAPI
from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount
from python_service.app.local_copy_trading.runtime import reset_state
from python_service.app.quant.backtest_routes import router as quant_backtest_router


def test_backtest_run_route_returns_summary_payload(monkeypatch):
    reset_state(LocalCopyTradingState(accounts=[
        SourceAccount(id='acc-1', name='Main A', connection_type='mt5_terminal', terminal_path='C:/MT5/terminal64.exe', login='1001', server='demo', password='secret', is_active=True)
    ]))
    app = FastAPI()
    app.include_router(quant_backtest_router)
    client = TestClient(app)
    monkeypatch.setattr('python_service.app.quant.backtest_routes.run_backtest', lambda **kwargs: {'summary': {'trade_count': 1}, 'trades': [], 'equity_curve': []})

    response = client.post('/python-quant/backtests/run', json={
        'strategy_id': 'sma_cross',
        'account_id': 'acc-1',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'start_at': '2026-05-01T00:00:00Z',
        'end_at': '2026-05-31T23:59:59Z',
    })

    assert response.status_code == 200
    assert response.json()['summary']['trade_count'] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_backtest_routes.py::test_backtest_run_route_returns_summary_payload -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Implement backtest routes and register them**

Expose:

- `GET /python-quant/backtests/strategies`
- `POST /python-quant/backtests/run`

Also add a route test for:

- `GET /python-quant/backtests/strategies`

to verify the same unified strategy list used by the live module is returned end-to-end.

- [ ] **Step 4: Run focused route tests**

Run: `pytest tests/python/test_quant_backtest_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/quant/backtest_routes.py python_service/app/main.py tests/python/test_quant_backtest_routes.py
git commit -m "feat: add quant backtest routes"
```

## Task 6: Add Frontend Backtest Store And Page

**Files:**
- Create: `src/renderer/src/lib/quant-backtest.ts`
- Create: `src/renderer/src/stores/quant-backtest-store.ts`
- Create: `src/renderer/src/pages/QuantBacktestPage.tsx`
- Create: `src/renderer/src/test/quant-backtest-store.test.ts`
- Create: `src/renderer/src/test/quant-backtest-page.test.tsx`
- Modify: `src/renderer/src/App.tsx`

- [ ] **Step 1: Write the failing backtest-store test**

```ts
import { act, renderHook } from '@testing-library/react'
import { useQuantBacktestStore } from '@/stores/quant-backtest-store'


it('posts backtest requests and stores results', async () => {
  const { result } = renderHook(() => useQuantBacktestStore())

  await act(async () => {
    await result.current.runBacktest({
      strategy_id: 'sma_cross',
      account_id: 'acc-1',
      symbol: 'XAUUSD',
      timeframe: 'M15',
      start_at: '2026-05-01T00:00:00Z',
      end_at: '2026-05-31T23:59:59Z',
    })
  })

  expect(result.current.result?.summary.trade_count).toBeDefined()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/quant-backtest-store.test.ts`
Expected: FAIL because the store does not exist

- [ ] **Step 3: Implement store and page**

The page should include:

- strategy selector
- account selector using the same account pool as `Python Quant`, sourced from the same `/python-quant/overview` account list derived from `Account List`
- symbol/timeframe selector
- start/end date inputs
- `Run Backtest` button
- summary card
- compact equity-curve summary section
- trades table

- [ ] **Step 4: Run focused frontend tests**

Run: `npm run test:frontend -- src/renderer/src/test/quant-backtest-store.test.ts src/renderer/src/test/quant-backtest-page.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/renderer/src/lib/quant-backtest.ts src/renderer/src/stores/quant-backtest-store.ts src/renderer/src/pages/QuantBacktestPage.tsx src/renderer/src/test/quant-backtest-store.test.ts src/renderer/src/test/quant-backtest-page.test.tsx src/renderer/src/App.tsx
git commit -m "feat: add quant backtest page"
```

## Task 7: Docs, Ignore Rules, And Full Verification

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `src/main/python-service.test.ts`
- Test: `tests/python/test_quant_strategy_registry.py`
- Test: `tests/python/test_quant_backtest_service.py`
- Test: `tests/python/test_quant_backtest_routes.py`
- Test: `src/renderer/src/test/quant-backtest-store.test.ts`
- Test: `src/renderer/src/test/quant-backtest-page.test.tsx`

- [ ] **Step 1: Ignore the local user strategy directory**

Add:

```text
storage/python_quant/strategies/
```

- [ ] **Step 2: Update both READMEs**

Document:

- `Python Quant` is for live assignment/runtime status
- `Quant Backtest` is for historical backtesting
- strategy list comes from built-in strategies + `storage/python_quant/strategies/`
- `Account List` is the shared source of MT5 accounts for both menus

- [ ] **Step 3: Add packaged-path coverage in Electron main tests**

Add a focused test in `src/main/python-service.test.ts` that verifies the spawned backend environment includes the quant path variables needed for packaged and development modes, for example:

```ts
expect(spawnEnv.PYTHON_QUANT_STRATEGIES_DIR).toContain('storage')
expect(spawnEnv.PYTHON_QUANT_DATA_DIR).toContain('storage')
expect(spawnEnv.PYTHON_QUANT_JOBS_PATH).toContain('storage')
```

- [ ] **Step 4: Run targeted Python suites**

Run: `pytest tests/python/test_quant_strategy_registry.py tests/python/test_quant_backtest_service.py tests/python/test_quant_backtest_routes.py -v`
Expected: PASS

- [ ] **Step 5: Run targeted frontend suites**

Run: `npm run test:frontend -- src/renderer/src/test/quant-backtest-store.test.ts src/renderer/src/test/quant-backtest-page.test.tsx src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/python-quant-store.test.ts`
Expected: PASS

- [ ] **Step 6: Run full touched-area suites**

Run: `pytest tests/python -v`
Expected: PASS

Run: `npm run test:frontend`
Expected: PASS

Run: `npm run build`
Expected: PASS

Run: `npm run build:python`
Expected: PASS

Run: `npm run verify:packaging`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .gitignore README.md README.zh-CN.md src/main/python-service.test.ts
git commit -m "docs: document quant menu split"
```

## Final Verification Checklist

- `Python Quant` appears under the `独立账户模块` group and is clearly live-task focused
- `Quant Backtest` appears as a separate menu under the same group
- both menus use the same account pool maintained by `Account List`
- strategy list includes built-in strategies and user drop-in strategies
- live runtime APIs still work
- backtest API returns summary, trades, and equity curve
- `pytest tests/python` passes
- `npm run test:frontend` passes

## Risks And Guardrails

- Do not move live-task execution into the backtest route/service.
- Do not make the backtest page mutate live jobs.
- Do not add a strategy editor UI in this plan.
- Keep user strategy discovery file-based only for this release.
- Keep the backtest result set minimal and serializable; avoid introducing heavyweight charting dependencies in the backend.

## Execution Notes

- Use `@superpowers:subagent-driven-development` for safest task-by-task execution.
- If the team later wants optimization, parameter sweep, or Monte Carlo analytics, create a separate follow-up plan rather than expanding this one in place.
