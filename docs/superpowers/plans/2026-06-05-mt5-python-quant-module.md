# MT5 Python Quant Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `Python Quant` module that lets the user pick an existing MT5 account, pick a Python strategy, start/stop strategy jobs, and source local market data from MT5 into a reusable local cache.

**Architecture:** Implement a new backend subsystem under `python_service/app/quant` that owns strategy discovery, MT5-backed market-data caching, persisted quant jobs, and a background runtime loop. Use `backtrader` as the first quant kernel behind our own registry/runtime boundary so the renderer and API talk only to our models, not directly to the external library. Reuse existing local-copy-trading accounts as the source of MT5 credentials, and store historical bars in a local SQLite database populated from MT5 on demand and refreshed by the runtime loop.

**Tech Stack:** FastAPI, Pydantic, MetaTrader5 Python SDK, `backtrader`, SQLite (`sqlite3`), Electron, React, Zustand, Vitest, PyInstaller

---

## Scope Check

This request is still one shippable subsystem if kept to live strategy orchestration + local market-data cache.

Do **not** expand this plan into these separate projects:

- browser-based backtest reporting UI
- cloud or paid market-data connectors
- multi-broker quant abstraction
- user-authenticated remote strategy distribution

If those are required later, create follow-up plans.

## Open-Source Module Choice

Use `backtrader` as the initial embedded quant engine **only behind a local adapter layer**.

Why this choice for this repo:

- it is mature and widely used
- it works with pandas/CSV/custom feeds instead of requiring a second platform UI
- it is much easier to package into the current FastAPI service than a full external trading platform
- it lets us keep MT5 account execution and market-data retrieval inside our existing backend

Important implementation note:

- because this application is packaged and distributed, validate `backtrader` license suitability before merging release builds
- if legal/product blocks that choice, keep the same file boundaries below and swap only the engine adapter in `python_service/app/quant/strategy_registry.py` and `python_service/app/quant/runtime.py`

## File Structure

### Create

- `python_service/app/quant/__init__.py`
  Responsibility: package marker and shared exports.
- `python_service/app/quant/models.py`
  Responsibility: quant job, strategy metadata, runtime status, and market-data request/response models.
- `python_service/app/quant/storage.py`
  Responsibility: persist quant jobs to `storage/python_quant/jobs.json` and ensure storage directories exist.
- `python_service/app/quant/market_data.py`
  Responsibility: create/query/update local SQLite OHLCV cache and fetch missing bars from MT5.
- `python_service/app/quant/strategy_registry.py`
  Responsibility: discover built-in and user strategy modules and normalize them into API-safe metadata.
- `python_service/app/quant/mt5_execution.py`
  Responsibility: connect to a specific MT5 account and place/close orders for one quant job.
- `python_service/app/quant/runtime.py`
  Responsibility: in-memory runtime state, job lifecycle, signal evaluation, dedupe, and last-run status updates.
- `python_service/app/quant/loop.py`
  Responsibility: background polling loop that runs enabled jobs.
- `python_service/app/quant/routes.py`
  Responsibility: FastAPI endpoints for quant overview, jobs, controls, and data backfill.
- `python_service/app/quant/strategies/__init__.py`
  Responsibility: built-in strategy package export.
- `python_service/app/quant/strategies/sma_cross.py`
  Responsibility: first built-in sample strategy proving discovery and live execution.
- `tests/python/test_quant_models.py`
  Responsibility: model validation/default coverage.
- `tests/python/test_quant_storage.py`
  Responsibility: JSON persistence tests for jobs.
- `tests/python/test_quant_market_data.py`
  Responsibility: SQLite cache + MT5 backfill tests.
- `tests/python/test_quant_routes.py`
  Responsibility: API contract tests for overview/job lifecycle.
- `tests/python/test_quant_runtime.py`
  Responsibility: signal evaluation, dedupe, and account execution decision tests.
- `tests/python/test_quant_lifespan.py`
  Responsibility: verify backend lifespan starts and cancels the quant loop.
- `src/renderer/src/lib/python-quant.ts`
  Responsibility: API types, parsers, and constants for the new renderer module.
- `src/renderer/src/stores/python-quant-store.ts`
  Responsibility: Zustand store for overview loading, create/start/stop/delete actions.
- `src/renderer/src/pages/PythonQuantPage.tsx`
  Responsibility: page UI for selecting an MT5 account, strategy, symbol/timeframe, and controlling jobs.
- `src/renderer/src/test/python-quant-store.test.ts`
  Responsibility: store endpoint and error handling tests.
- `src/renderer/src/test/python-quant-page.test.tsx`
  Responsibility: page render and user-flow tests.

### Modify

- `python_service/app/main.py:9-130`
  Responsibility: register the quant router and quant background loop in the backend lifespan.
- `python_service/app/services/mt5_service.py:180-361`
  Responsibility: add account-scoped MT5 helpers for login plus historical bar/tick retrieval.
- `python_service/requirements.txt:1-9`
  Responsibility: add `backtrader` dependency.
- `python_service/pyproject.toml:1-15`
  Responsibility: keep Python dependency metadata aligned.
- `python_service/mt5_service.spec:10-34`
  Responsibility: add `backtrader` hidden import(s) and ship built-in strategy files.
- `src/renderer/src/App.tsx:22-76`
  Responsibility: register the `python-quant` route.
- `src/renderer/src/components/module-nav.tsx:1-98`
  Responsibility: add the new menu item.
- `src/renderer/src/i18n/messages.ts:16-37, 39-136, 638-720`
  Responsibility: add `nav.pythonQuant` and the new module copy in both languages.
- `README.md:7-139`
  Responsibility: document the new module, local data cache, and Python dependency.
- `README.zh-CN.md:7-133`
  Responsibility: same documentation updates in Chinese.

### Runtime Data Created On First Run

- `storage/python_quant/jobs.json`
  Responsibility: persisted quant jobs.
- `storage/python_quant/market_data.sqlite3`
  Responsibility: local OHLCV cache.
- `storage/python_quant/strategies/*.py`
  Responsibility: optional user-provided custom strategies loaded in addition to built-ins.

## Data Model Decisions

- A quant job references an existing local-copy-trading `account_id`; do not create a second account store.
- Market data is keyed by `(account_id, symbol, timeframe)` so the cache stays tied to the same MT5 environment the strategy trades against.
- V1 forbids more than one enabled job for the same `(account_id, symbol)` pair. Enforce this in create, update, and start validation so the first release does not need MT5 magic-number isolation.
- V1 strategy execution supports one open directional position per enabled `(account_id, symbol)` pair and market orders only.
- V1 strategies produce one of four actions: `buy`, `sell`, `close`, `hold`.
- V1 renderer supports built-in strategies plus drop-in user strategy files discovered from the writable local strategy directory.

## API Shape

Use these endpoints.

- `GET /python-quant/overview`
- `POST /python-quant/jobs`
- `PUT /python-quant/jobs/{job_id}`
- `DELETE /python-quant/jobs/{job_id}`
- `POST /python-quant/jobs/{job_id}/start`
- `POST /python-quant/jobs/{job_id}/stop`
- `POST /python-quant/data/backfill`

Recommended overview payload:

```json
{
  "accounts": [{"id": "acc-1", "name": "Main A", "login": "10001"}],
  "strategies": [{"id": "sma_cross", "name": "SMA Cross", "timeframes": ["M1", "M5", "M15"]}],
  "jobs": [
    {
      "id": "job-1",
      "name": "Gold M5 Trend",
      "account_id": "acc-1",
      "strategy_id": "sma_cross",
      "symbol": "XAUUSD",
      "timeframe": "M5",
      "lot": 0.01,
      "enabled": true,
      "status": "running",
      "last_signal": "buy",
      "last_error": null,
      "last_bar_time": "2026-06-05T08:35:00+00:00",
      "updated_at": "2026-06-05T08:35:04+00:00"
    }
  ]
}
```

## Test Isolation Rules

All new quant backend tests must avoid writing real app-state files.

- Route, runtime, and storage tests must monkeypatch `python_service.app.quant.storage.DEFAULT_JOBS_PATH` to `tmp_path / 'jobs.json'`.
- Market-data tests must pass `tmp_path / 'market_data.sqlite3'` explicitly.
- Route tests that need local-copy-trading accounts should seed runtime state in memory instead of relying on `storage/local_copy_trading.json`.

## Task 1: Quant Domain Models And Persistence Skeleton

**Files:**
- Create: `python_service/app/quant/__init__.py`
- Create: `python_service/app/quant/models.py`
- Create: `python_service/app/quant/storage.py`
- Test: `tests/python/test_quant_models.py`
- Test: `tests/python/test_quant_storage.py`

- [ ] **Step 1: Write the failing model test**

```python
from python_service.app.quant.models import QuantJob


def test_quant_job_defaults_to_stopped_state():
    job = QuantJob(
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
    )

    assert job.enabled is False
    assert job.status == 'stopped'
    assert job.last_signal is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_models.py::test_quant_job_defaults_to_stopped_state -v`
Expected: FAIL with `ModuleNotFoundError` for `python_service.app.quant`

- [ ] **Step 3: Write the minimal model implementation**

```python
from pydantic import BaseModel, Field
from typing import Literal
from uuid import uuid4
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuantJob(BaseModel):
    id: str = Field(default_factory=lambda: f'job-{uuid4().hex[:12]}')
    name: str
    account_id: str
    strategy_id: str
    symbol: str
    timeframe: Literal['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    lot: float
    enabled: bool = False
    status: Literal['stopped', 'running', 'error'] = 'stopped'
    last_signal: Literal['buy', 'sell', 'close', 'hold'] | None = None
    last_error: str | None = None
    last_bar_time: str | None = None
    updated_at: str = Field(default_factory=utc_now_iso)
```

- [ ] **Step 4: Add the failing persistence test**

```python
from python_service.app.quant.models import QuantJob
from python_service.app.quant.storage import load_jobs, save_jobs


def test_save_jobs_round_trips_json(tmp_path):
    storage_path = tmp_path / 'jobs.json'
    jobs = [
        QuantJob(
            id='job-1',
            name='Gold M5 Trend',
            account_id='acc-1',
            strategy_id='sma_cross',
            symbol='XAUUSD',
            timeframe='M5',
            lot=0.01,
        )
    ]

    save_jobs(jobs, storage_path)
    loaded = load_jobs(storage_path)

    assert [job.id for job in loaded] == ['job-1']
    assert loaded[0].symbol == 'XAUUSD'
```

- [ ] **Step 5: Implement minimal JSON storage**

```python
import json
from pathlib import Path

from python_service.app.quant.models import QuantJob


DEFAULT_JOBS_PATH = Path('storage/python_quant/jobs.json')


def load_jobs(storage_path: Path | str = DEFAULT_JOBS_PATH) -> list[QuantJob]:
    path = Path(storage_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding='utf-8'))
    return [QuantJob(**item) for item in payload]


def save_jobs(jobs: list[QuantJob], storage_path: Path | str = DEFAULT_JOBS_PATH) -> None:
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([job.model_dump() for job in jobs], indent=2), encoding='utf-8')
```

- [ ] **Step 6: Run the focused tests**

Run: `pytest tests/python/test_quant_models.py tests/python/test_quant_storage.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python_service/app/quant/__init__.py python_service/app/quant/models.py python_service/app/quant/storage.py tests/python/test_quant_models.py tests/python/test_quant_storage.py
git commit -m "feat: add quant job models"
```

## Task 2: Strategy Discovery And Built-In SMA Cross Strategy

**Files:**
- Create: `python_service/app/quant/strategy_registry.py`
- Create: `python_service/app/quant/strategies/__init__.py`
- Create: `python_service/app/quant/strategies/sma_cross.py`
- Modify: `python_service/requirements.txt:1-9`
- Modify: `python_service/pyproject.toml:1-15`
- Test: `tests/python/test_quant_models.py`

- [ ] **Step 1: Write the failing discovery test**

```python
from python_service.app.quant.strategy_registry import list_strategies


def test_list_strategies_includes_builtin_sma_cross():
    strategies = list_strategies()

    assert any(item.id == 'sma_cross' for item in strategies)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_models.py::test_list_strategies_includes_builtin_sma_cross -v`
Expected: FAIL with `ImportError` for `strategy_registry` or missing `list_strategies`

- [ ] **Step 3: Add the dependency and discovery scaffolding**

`python_service/requirements.txt`

```text
fastapi
uvicorn
pydantic
MetaTrader5
pytest
httpx
pandas
numpy
pyinstaller
backtrader
```

`python_service/app/quant/strategy_registry.py`

```python
from dataclasses import dataclass
import importlib
import pkgutil
from types import ModuleType

from python_service.app.quant import strategies as builtin_strategies


@dataclass
class StrategyDescriptor:
    id: str
    name: str
    description: str
    timeframes: list[str]
    module_path: str


def list_strategies() -> list[StrategyDescriptor]:
    items: list[StrategyDescriptor] = []
    for module in pkgutil.iter_modules(builtin_strategies.__path__):
        imported = importlib.import_module(f'{builtin_strategies.__name__}.{module.name}')
        items.append(StrategyDescriptor(
            id=imported.STRATEGY_ID,
            name=imported.STRATEGY_NAME,
            description=imported.STRATEGY_DESCRIPTION,
            timeframes=imported.SUPPORTED_TIMEFRAMES,
            module_path=imported.__name__,
        ))
    return items


def get_strategy_module(strategy_id: str) -> ModuleType:
    for descriptor in list_strategies():
        if descriptor.id == strategy_id:
            return importlib.import_module(descriptor.module_path)
    raise ValueError(f'Unknown strategy: {strategy_id}')
```

- [ ] **Step 4: Add the minimal built-in strategy module**

```python
import backtrader as bt

STRATEGY_ID = 'sma_cross'
STRATEGY_NAME = 'SMA Cross'
STRATEGY_DESCRIPTION = 'Fast/slow SMA crossover with one-position directional bias.'
SUPPORTED_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1']


class Strategy(bt.Strategy):
    params = (('fast', 10), ('slow', 30))

    def __init__(self):
        self.fast_sma = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.slow_sma = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.cross = bt.ind.CrossOver(self.fast_sma, self.slow_sma)

    def next(self):
        if self.cross[0] > 0:
            self.signal_output = 'buy'
        elif self.cross[0] < 0:
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
```

- [ ] **Step 5: Run tests and import smoke check**

Run: `pytest tests/python/test_quant_models.py::test_list_strategies_includes_builtin_sma_cross -v`
Expected: PASS

Run: `python -c "import backtrader; print(backtrader.__name__)"`
Expected: prints `backtrader`

- [ ] **Step 6: Commit**

```bash
git add python_service/app/quant/strategy_registry.py python_service/app/quant/strategies/__init__.py python_service/app/quant/strategies/sma_cross.py python_service/requirements.txt python_service/pyproject.toml tests/python/test_quant_models.py
git commit -m "feat: add quant strategy registry"
```

## Task 3: Local MT5 Market-Data Cache

**Files:**
- Create: `python_service/app/quant/market_data.py`
- Modify: `python_service/app/services/mt5_service.py:227-361`
- Test: `tests/python/test_quant_market_data.py`

- [ ] **Step 1: Write the failing cache test**

```python
from python_service.app.quant.market_data import upsert_bars, load_recent_bars


def test_upsert_bars_round_trips_sqlite_rows(tmp_path):
    db_path = tmp_path / 'market_data.sqlite3'
    bars = [
        {
            'time': '2026-06-05T08:30:00+00:00',
            'open': 3300.0,
            'high': 3302.0,
            'low': 3299.0,
            'close': 3301.0,
            'tick_volume': 100,
        }
    ]

    upsert_bars(db_path, 'acc-1', 'XAUUSD', 'M5', bars)
    loaded = load_recent_bars(db_path, 'acc-1', 'XAUUSD', 'M5', limit=1)

    assert loaded[0]['close'] == 3301.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_market_data.py::test_upsert_bars_round_trips_sqlite_rows -v`
Expected: FAIL because `market_data.py` does not exist

- [ ] **Step 3: Implement minimal SQLite cache**

```python
import sqlite3
from pathlib import Path


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        '''
        create table if not exists bars (
            account_id text not null,
            symbol text not null,
            timeframe text not null,
            time text not null,
            open real not null,
            high real not null,
            low real not null,
            close real not null,
            tick_volume integer not null,
            primary key (account_id, symbol, timeframe, time)
        )
        '''
    )
    return conn


def upsert_bars(db_path: Path | str, account_id: str, symbol: str, timeframe: str, bars: list[dict]) -> int:
    with connect(db_path) as conn:
        conn.executemany(
            '''
            insert into bars (account_id, symbol, timeframe, time, open, high, low, close, tick_volume)
            values (:account_id, :symbol, :timeframe, :time, :open, :high, :low, :close, :tick_volume)
            on conflict(account_id, symbol, timeframe, time) do update set
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                tick_volume=excluded.tick_volume
            ''',
            [{**bar, 'account_id': account_id, 'symbol': symbol, 'timeframe': timeframe} for bar in bars],
        )
        return len(bars)


def load_recent_bars(db_path: Path | str, account_id: str, symbol: str, timeframe: str, limit: int) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            '''
            select time, open, high, low, close, tick_volume
            from bars
            where account_id = ? and symbol = ? and timeframe = ?
            order by time desc
            limit ?
            ''',
            (account_id, symbol, timeframe, limit),
        ).fetchall()
    return [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'tick_volume': row[5],
        }
        for row in reversed(rows)
    ]
```

- [ ] **Step 4: Write the failing MT5 backfill test**

```python
from python_service.app.quant.market_data import backfill_from_mt5


def test_backfill_from_mt5_persists_missing_bars(tmp_path, monkeypatch):
    monkeypatch.setattr(
        'python_service.app.quant.market_data.fetch_account_bars',
        lambda **kwargs: [
            {
                'time': '2026-06-05T08:35:00+00:00',
                'open': 1.0,
                'high': 2.0,
                'low': 0.5,
                'close': 1.5,
                'tick_volume': 10,
            }
        ],
    )

    rows = backfill_from_mt5(
        db_path=tmp_path / 'market_data.sqlite3',
        account={'terminal_path': 'C:/MT5/terminal64.exe', 'login': '1001', 'password': 'secret', 'server': 'demo'},
        account_id='acc-1',
        symbol='XAUUSD',
        timeframe='M5',
        bars=1,
    )

    assert rows == 1
```

- [ ] **Step 5: Add the MT5 helper and backfill function**

`python_service/app/services/mt5_service.py`

```python
def fetch_account_bars(path: str, login: str, password: str, server: str, symbol: str, timeframe: int, count: int) -> list[dict]:
    with _mt5_lock:
        ok, detail = _init_mt5_account_unlocked(path, login, password, server)
        if not ok:
            raise RuntimeError(detail or 'Failed to connect account')
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            return []
        return [
            {
                'time': datetime.fromtimestamp(int(rate['time']), timezone.utc).isoformat(),
                'open': float(rate['open']),
                'high': float(rate['high']),
                'low': float(rate['low']),
                'close': float(rate['close']),
                'tick_volume': int(rate['tick_volume']),
            }
            for rate in rates
        ]
```

`python_service/app/quant/market_data.py`

```python
TIMEFRAME_SECONDS = {
    'M1': 60,
    'M5': 300,
    'M15': 900,
    'M30': 1800,
    'H1': 3600,
    'H4': 14400,
    'D1': 86400,
}


def backfill_from_mt5(db_path: Path | str, account: dict, account_id: str, symbol: str, timeframe: str, bars: int) -> int:
    fetched = fetch_account_bars(
        path=account['terminal_path'],
        login=account['login'],
        password=account['password'],
        server=account['server'],
        symbol=symbol,
        timeframe=timeframe,
        count=bars,
    )
    return upsert_bars(db_path, account_id, symbol, timeframe, fetched)


def latest_cached_bar_time(db_path: Path | str, account_id: str, symbol: str, timeframe: str) -> str | None:
    rows = load_recent_bars(db_path, account_id, symbol, timeframe, limit=1)
    return rows[0]['time'] if rows else None
```

- [ ] **Step 6: Run the focused tests**

Run: `pytest tests/python/test_quant_market_data.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python_service/app/quant/market_data.py python_service/app/services/mt5_service.py tests/python/test_quant_market_data.py
git commit -m "feat: add quant market data cache"
```

## Task 4: Quant Runtime And API

**Files:**
- Create: `python_service/app/quant/mt5_execution.py`
- Create: `python_service/app/quant/runtime.py`
- Create: `python_service/app/quant/routes.py`
- Test: `tests/python/test_quant_routes.py`
- Test: `tests/python/test_quant_runtime.py`

- [ ] **Step 1: Write the failing overview route test**

```python
from fastapi.testclient import TestClient
from python_service.app.main import app


def test_python_quant_overview_returns_accounts_strategies_and_jobs(monkeypatch):
    client = TestClient(app)

    response = client.get('/python-quant/overview')

    assert response.status_code == 200
    payload = response.json()
    assert 'accounts' in payload
    assert 'strategies' in payload
    assert 'jobs' in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_routes.py::test_python_quant_overview_returns_accounts_strategies_and_jobs -v`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Implement route skeleton and reuse existing accounts**

```python
from fastapi import APIRouter

from python_service.app.local_copy_trading.runtime import get_state as get_local_copy_trading_state
from python_service.app.quant.storage import load_jobs
from python_service.app.quant.strategy_registry import list_strategies

router = APIRouter(prefix='/python-quant')


@router.get('/overview')
def get_overview():
    state = get_local_copy_trading_state()
    return {
        'accounts': [
            {
                'id': account.id,
                'name': account.name,
                'login': account.login,
                'server': account.server,
                'terminal_path': account.terminal_path,
            }
            for account in state.accounts
            if account.is_active
        ],
        'strategies': [item.__dict__ for item in list_strategies()],
        'jobs': [job.model_dump() for job in load_jobs()],
    }
```

- [ ] **Step 4: Write the failing runtime decision test**

```python
from python_service.app.quant.models import QuantJob
from python_service.app.quant.runtime import resolve_signal_action


def test_resolve_signal_action_ignores_duplicate_bar_signal():
    job = QuantJob(
        id='job-1',
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
        enabled=True,
        status='running',
        last_bar_time='2026-06-05T08:35:00+00:00',
        last_signal='buy',
    )

    action = resolve_signal_action(job, signal='buy', bar_time='2026-06-05T08:35:00+00:00')

    assert action == 'hold'
```

- [ ] **Step 5: Add the failing route coverage for update, delete, and backfill**

```python
def test_update_job_route_persists_mutations(monkeypatch):
    client = TestClient(app)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()

    response = client.put(f"/python-quant/jobs/{created['id']}", json={
        'name': 'Gold M15 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'lot': 0.02,
    })

    assert response.status_code == 200
    assert response.json()['timeframe'] == 'M15'


def test_delete_job_route_removes_job():
    client = TestClient(app)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()

    response = client.delete(f"/python-quant/jobs/{created['id']}")

    assert response.status_code == 200
    assert response.json()['id'] == created['id']


def test_backfill_route_returns_inserted_row_count(monkeypatch):
    monkeypatch.setattr('python_service.app.quant.routes.request_backfill', lambda **kwargs: 120)
    client = TestClient(app)

    response = client.post('/python-quant/data/backfill', json={
        'account_id': 'acc-1',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'bars': 120,
    })

    assert response.status_code == 200
    assert response.json() == {'inserted_rows': 120}
```

- [ ] **Step 6: Implement minimal runtime logic and full API mutations**

```python
class QuantJobCreateRequest(BaseModel):
    name: str
    account_id: str
    strategy_id: str
    symbol: str
    timeframe: Literal['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    lot: float


class QuantJobUpdateRequest(QuantJobCreateRequest):
    enabled: bool | None = None


class QuantBackfillRequest(BaseModel):
    account_id: str
    symbol: str
    timeframe: Literal['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    bars: int = 500


def validate_unique_account_symbol(jobs: list[QuantJob], account_id: str, symbol: str, ignore_job_id: str | None = None) -> None:
    normalized_symbol = symbol.strip().upper()
    for job in jobs:
        if ignore_job_id and job.id == ignore_job_id:
            continue
        if job.account_id == account_id and job.symbol.strip().upper() == normalized_symbol and job.enabled:
            raise HTTPException(status_code=400, detail='Only one enabled quant job per account and symbol is allowed in V1')


def replace_job(job_id: str, payload: QuantJobUpdateRequest) -> QuantJob:
    jobs = load_jobs()
    updated_jobs = []
    updated_job = None
    for job in jobs:
        if job.id != job_id:
            updated_jobs.append(job)
            continue
        updated_job = job.model_copy(update={**payload.model_dump(exclude_none=True), 'updated_at': utc_now_iso()})
        updated_jobs.append(updated_job)
    if updated_job is None:
        raise HTTPException(status_code=404, detail=f'Unknown quant job: {job_id}')
    save_jobs(updated_jobs)
    return updated_job


def remove_job(job_id: str) -> QuantJob:
    jobs = load_jobs()
    remaining_jobs = []
    deleted_job = None
    for job in jobs:
        if job.id == job_id:
            deleted_job = job
            continue
        remaining_jobs.append(job)
    if deleted_job is None:
        raise HTTPException(status_code=404, detail=f'Unknown quant job: {job_id}')
    save_jobs(remaining_jobs)
    return deleted_job


def request_backfill(account_id: str, symbol: str, timeframe: str, bars: int) -> int:
    account = get_account_by_id(account_id)
    return backfill_from_mt5(DEFAULT_MARKET_DATA_PATH, account, account_id, symbol, timeframe, bars)


def resolve_signal_action(job: QuantJob, signal: str, bar_time: str) -> str:
    if job.last_bar_time == bar_time and job.last_signal == signal:
        return 'hold'
    return signal


@router.post('/jobs')
def create_job(job: QuantJobCreateRequest):
    jobs = load_jobs()
    validate_unique_account_symbol(jobs, job.account_id, job.symbol)
    new_job = QuantJob(**job.model_dump())
    jobs.append(new_job)
    save_jobs(jobs)
    return new_job.model_dump()


@router.put('/jobs/{job_id}')
def update_job(job_id: str, payload: QuantJobUpdateRequest):
    jobs = load_jobs()
    if payload.enabled:
        validate_unique_account_symbol(jobs, payload.account_id, payload.symbol, ignore_job_id=job_id)
    updated = replace_job(job_id, payload)
    return updated.model_dump()


@router.delete('/jobs/{job_id}')
def delete_job(job_id: str):
    deleted = remove_job(job_id)
    return deleted.model_dump()


@router.post('/jobs/{job_id}/start')
def start_job(job_id: str):
    job = get_job(job_id)
    validate_unique_account_symbol(load_jobs(), job.account_id, job.symbol, ignore_job_id=job_id)
    updated = set_job_enabled(job_id, True)
    return updated.model_dump()


@router.post('/jobs/{job_id}/stop')
def stop_job(job_id: str):
    updated = set_job_enabled(job_id, False)
    return updated.model_dump()


@router.post('/data/backfill')
def backfill_data(payload: QuantBackfillRequest):
    inserted_rows = request_backfill(
        account_id=payload.account_id,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        bars=payload.bars,
    )
    return {'inserted_rows': inserted_rows}
```

- [ ] **Step 7: Run the focused tests**

Run: `pytest tests/python/test_quant_routes.py tests/python/test_quant_runtime.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add python_service/app/quant/mt5_execution.py python_service/app/quant/runtime.py python_service/app/quant/routes.py tests/python/test_quant_routes.py tests/python/test_quant_runtime.py
git commit -m "feat: add quant runtime api"
```

## Task 5: End-To-End Strategy Execution Pipeline

**Files:**
- Create: `python_service/app/quant/mt5_execution.py`
- Modify: `python_service/app/quant/runtime.py`
- Modify: `python_service/app/quant/market_data.py`
- Test: `tests/python/test_quant_runtime.py`

- [ ] **Step 1: Write the failing strategy execution test**

```python
from python_service.app.quant.models import QuantJob
from python_service.app.quant.runtime import run_job_once


def test_run_job_once_backfills_executes_and_records_signal(monkeypatch):
    job = QuantJob(
        id='job-1',
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
        enabled=True,
        status='running',
    )

    monkeypatch.setattr('python_service.app.quant.runtime.get_account_for_job', lambda job: {
        'id': 'acc-1',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'password': 'secret',
        'server': 'demo',
    })
    monkeypatch.setattr('python_service.app.quant.runtime.ensure_recent_bars', lambda **kwargs: [
        {'time': '2026-06-05T08:30:00+00:00', 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.0, 'tick_volume': 10},
        {'time': '2026-06-05T08:35:00+00:00', 'open': 1.0, 'high': 2.1, 'low': 0.9, 'close': 2.0, 'tick_volume': 12},
    ])
    monkeypatch.setattr('python_service.app.quant.runtime.evaluate_strategy_signal', lambda **kwargs: ('buy', '2026-06-05T08:35:00+00:00'))
    executed = {}
    monkeypatch.setattr('python_service.app.quant.runtime.execute_signal', lambda **kwargs: executed.setdefault('signal', kwargs['signal']))

    updated = run_job_once(job)

    assert updated.last_signal == 'buy'
    assert updated.last_bar_time == '2026-06-05T08:35:00+00:00'
    assert updated.status == 'running'
    assert executed['signal'] == 'buy'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_runtime.py::test_run_job_once_backfills_executes_and_records_signal -v`
Expected: FAIL because `run_job_once` does not exist

- [ ] **Step 3: Implement cache freshness and strategy evaluation helpers**

`python_service/app/quant/market_data.py`

```python
def ensure_recent_bars(db_path: Path | str, account: dict, account_id: str, symbol: str, timeframe: str, min_bars: int) -> list[dict]:
    rows = load_recent_bars(db_path, account_id, symbol, timeframe, limit=min_bars)
    latest_time = latest_cached_bar_time(db_path, account_id, symbol, timeframe)
    is_stale = latest_time is None or bar_is_stale(latest_time, timeframe)
    if len(rows) >= min_bars and not is_stale:
        return rows
    backfill_from_mt5(
        db_path=db_path,
        account=account,
        account_id=account_id,
        symbol=symbol,
        timeframe=timeframe,
        bars=min_bars,
    )
    return load_recent_bars(db_path, account_id, symbol, timeframe, limit=min_bars)
```

`python_service/app/quant/runtime.py`

```python
import backtrader as bt
import pandas as pd
from datetime import datetime, timezone

from python_service.app.quant.strategy_registry import get_strategy_module


def bar_is_stale(latest_time: str, timeframe: str) -> bool:
    latest = datetime.fromisoformat(latest_time)
    age_seconds = (datetime.now(timezone.utc) - latest).total_seconds()
    return age_seconds >= TIMEFRAME_SECONDS[timeframe]


def evaluate_strategy_signal(strategy_id: str, bars: list[dict]) -> tuple[str, str | None]:
    if len(bars) < 30:
        return 'hold', None

    strategy_module = get_strategy_module(strategy_id)
    frame = pd.DataFrame(bars)
    frame['datetime'] = pd.to_datetime(frame['time'])
    frame = frame.set_index('datetime').rename(columns={'tick_volume': 'volume'})

    data = bt.feeds.PandasData(dataname=frame[['open', 'high', 'low', 'close', 'volume']])
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(strategy_module.Strategy)
    cerebro.adddata(data)
    strategies = cerebro.run()

    latest_bar_time = bars[-1]['time']
    signal = getattr(strategies[0], 'signal_output', 'hold')
    return signal, latest_bar_time
```

- [ ] **Step 4: Implement MT5 order helpers and execution adapter**

`python_service/app/services/mt5_service.py`

```python
def place_market_order(path: str, login: str, password: str, server: str, symbol: str, lot: float, side: str) -> dict:
    with _mt5_lock:
        ok, detail = _init_mt5_account_unlocked(path, login, password, server)
        if not ok:
            raise RuntimeError(detail or 'Failed to connect MT5 account')

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f'Failed to select symbol: {symbol}')

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f'Failed to fetch latest tick for {symbol}')

        order_type = mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == 'buy' else tick.bid
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': lot,
            'type': order_type,
            'price': price,
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f'MT5 order_send failed: {getattr(result, "retcode", None)}')
        return result._asdict()


def close_open_positions(path: str, login: str, password: str, server: str, symbol: str) -> None:
    with _mt5_lock:
        ok, detail = _init_mt5_account_unlocked(path, login, password, server)
        if not ok:
            raise RuntimeError(detail or 'Failed to connect MT5 account')
        positions = mt5.positions_get(symbol=symbol) or []
        for position in positions:
            side = 'sell' if position.type == mt5.POSITION_TYPE_BUY else 'buy'
            place_market_order(path, login, password, server, symbol, float(position.volume), side)
```

`python_service/app/quant/mt5_execution.py`

```python
from python_service.app.services.mt5_service import close_open_positions, place_market_order


def execute_signal(account: dict, symbol: str, lot: float, signal: str) -> None:
    if signal == 'hold':
        return
    if signal == 'close':
        close_open_positions(
            path=account['terminal_path'],
            login=account['login'],
            password=account['password'],
            server=account['server'],
            symbol=symbol,
        )
        return

    place_market_order(
        path=account['terminal_path'],
        login=account['login'],
        password=account['password'],
        server=account['server'],
        symbol=symbol,
        lot=lot,
        side=signal,
    )
```

- [ ] **Step 5: Implement `run_job_once` and batch runner**

```python
def run_job_once(job: QuantJob) -> QuantJob:
    account = get_account_for_job(job)
    bars = ensure_recent_bars(
        db_path=DEFAULT_MARKET_DATA_PATH,
        account=account,
        account_id=job.account_id,
        symbol=job.symbol,
        timeframe=job.timeframe,
        min_bars=100,
    )
    signal, bar_time = evaluate_strategy_signal(job.strategy_id, bars)
    action = resolve_signal_action(job, signal=signal, bar_time=bar_time or '')
    if action != 'hold' and bar_time:
        execute_signal(account=account, symbol=job.symbol, lot=job.lot, signal=action)
    return job.model_copy(update={
        'status': 'running',
        'last_signal': signal,
        'last_bar_time': bar_time,
        'last_error': None,
        'updated_at': utc_now_iso(),
    })


async def run_enabled_jobs_once() -> None:
    jobs = load_jobs()
    updated_jobs = []
    for job in jobs:
        if not job.enabled:
            updated_jobs.append(job)
            continue
        try:
            updated_jobs.append(run_job_once(job))
        except Exception as error:
            updated_jobs.append(job.model_copy(update={
                'status': 'error',
                'last_error': str(error),
                'updated_at': utc_now_iso(),
            }))
    save_jobs(updated_jobs)
```

- [ ] **Step 6: Run the focused runtime tests**

Run: `pytest tests/python/test_quant_runtime.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add python_service/app/quant/mt5_execution.py python_service/app/quant/runtime.py python_service/app/quant/market_data.py tests/python/test_quant_runtime.py
git commit -m "feat: execute quant jobs against mt5"
```

## Task 6: Background Loop And Backend Lifespan Integration

**Files:**
- Create: `python_service/app/quant/loop.py`
- Modify: `python_service/app/main.py:9-130`
- Test: `tests/python/test_quant_lifespan.py`
- Test: `tests/python/test_backend_lifespan.py`

- [ ] **Step 1: Write the failing lifespan test**

```python
import asyncio

from python_service.app import main as backend_main


def test_lifespan_registers_independent_quant_loop(monkeypatch):
    async def run_test():
        started = {'quant': False}
        cancelled = {'quant': False}

        async def fake_quant_loop():
            started['quant'] = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled['quant'] = True
                raise

        monkeypatch.setattr(backend_main, 'quant_loop', fake_quant_loop)

        async with backend_main.lifespan(backend_main.app):
            await asyncio.sleep(0)

        assert started['quant'] is True
        assert cancelled['quant'] is True

    asyncio.run(run_test())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/python/test_quant_lifespan.py::test_lifespan_registers_independent_quant_loop -v`
Expected: FAIL because `quant_loop` is not wired into `main.py`

- [ ] **Step 3: Implement the loop and wire it into lifespan**

`python_service/app/quant/loop.py`

```python
import asyncio

from python_service.app.quant.runtime import run_enabled_jobs_once


async def quant_loop() -> None:
    while True:
        await run_enabled_jobs_once()
        await asyncio.sleep(2)
```

`python_service/app/main.py`

```python
from python_service.app.quant.routes import router as python_quant_router
from python_service.app.quant.loop import quant_loop

background_tasks = [
    asyncio.create_task(streaming_loop()),
    asyncio.create_task(order_sync_loop()),
    asyncio.create_task(local_copy_trading_loop()),
    asyncio.create_task(quant_loop()),
]

app.include_router(python_quant_router)
```

- [ ] **Step 4: Run the lifespan-focused tests**

Run: `pytest tests/python/test_quant_lifespan.py tests/python/test_backend_lifespan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python_service/app/quant/loop.py python_service/app/main.py tests/python/test_quant_lifespan.py tests/python/test_backend_lifespan.py
git commit -m "feat: run quant loop in backend lifespan"
```

## Task 7: Renderer Store, Route, Navigation, And I18n

**Files:**
- Create: `src/renderer/src/lib/python-quant.ts`
- Create: `src/renderer/src/stores/python-quant-store.ts`
- Modify: `src/renderer/src/App.tsx:22-76`
- Modify: `src/renderer/src/components/module-nav.tsx:23-44, 67-97`
- Modify: `src/renderer/src/i18n/messages.ts:16-37, 39-136, 638-720`
- Test: `src/renderer/src/test/python-quant-store.test.ts`

- [ ] **Step 1: Write the failing store test**

```ts
import { act, renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { usePythonQuantStore } from '@/stores/python-quant-store'


it('loads quant overview from the backend', async () => {
  global.fetch = vi.fn(async () => ({
    ok: true,
    json: async () => ({ accounts: [], strategies: [], jobs: [] }),
  })) as typeof fetch

  const { result } = renderHook(() => usePythonQuantStore())
  await act(async () => {
    await result.current.fetchOverview()
  })

  expect(result.current.overview.jobs).toHaveLength(0)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-store.test.ts`
Expected: FAIL because the store module does not exist

- [ ] **Step 3: Implement the API lib and Zustand store**

```ts
export const PYTHON_QUANT_API_BASE = 'http://127.0.0.1:8765/python-quant'

export type PythonQuantOverview = {
  accounts: Array<{ id: string; name: string; login: string }>
  strategies: Array<{ id: string; name: string; description: string; timeframes: string[] }>
  jobs: Array<{ id: string; name: string; account_id: string; strategy_id: string; symbol: string; timeframe: string; lot: number; enabled: boolean; status: string; last_signal: string | null; last_error: string | null }>
}
```

```ts
export const usePythonQuantStore = create<PythonQuantStore>((set) => ({
  overview: { accounts: [], strategies: [], jobs: [] },
  isLoading: false,
  error: null,
  fetchOverview: async () => {
    set({ isLoading: true, error: null })
    const response = await fetch(`${PYTHON_QUANT_API_BASE}/overview`)
    const overview = await response.json()
    set({ overview, isLoading: false })
  },
  createJob: async (payload) => { /* POST /jobs then refresh overview */ },
  updateJob: async (jobId, payload) => { /* PUT /jobs/{jobId} then refresh overview */ },
  startJob: async (jobId) => { /* POST /jobs/{jobId}/start then refresh overview */ },
  stopJob: async (jobId) => { /* POST /jobs/{jobId}/stop then refresh overview */ },
  deleteJob: async (jobId) => { /* DELETE /jobs/{jobId} then refresh overview */ },
  backfillData: async (payload) => { /* POST /data/backfill and return inserted_rows */ },
}))
```

- [ ] **Step 4: Add route and navigation wiring**

`src/renderer/src/App.tsx`

```tsx
const VALID_MODULES = new Set([
  'dashboard',
  'python-quant',
  'order-broadcast',
  'order-sync',
  'account-list',
])
```

`src/renderer/src/components/module-nav.tsx`

```tsx
const primaryNavItems = [
  { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
  { id: 'python-quant', label: t('nav.pythonQuant'), icon: LineChart },
  { id: 'price-alerts', label: t('nav.priceAlerts'), icon: Bell },
]
```

- [ ] **Step 5: Add i18n strings**

```ts
nav: {
  pythonQuant: 'Python Quant',
}

pythonQuant: {
  title: 'Python Quant',
  description: 'Run Python strategies against a selected MT5 account using locally cached market data.',
  createJob: 'Create Job',
  start: 'Start',
  stop: 'Stop',
}
```

- [ ] **Step 6: Run the focused frontend test**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-store.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/lib/python-quant.ts src/renderer/src/stores/python-quant-store.ts src/renderer/src/App.tsx src/renderer/src/components/module-nav.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/python-quant-store.test.ts
git commit -m "feat: add quant renderer store"
```

## Task 8: Python Quant Page UI

**Files:**
- Create: `src/renderer/src/pages/PythonQuantPage.tsx`
- Modify: `src/renderer/src/App.tsx:48-64`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] **Step 1: Write the failing page render test**

```tsx
import { render, screen } from '@testing-library/react'

import { I18nProvider } from '@/i18n'
import { PythonQuantPage } from '@/pages/PythonQuantPage'


it('renders the python quant page heading', async () => {
  render(
    <I18nProvider language="en">
      <PythonQuantPage />
    </I18nProvider>,
  )

  expect(await screen.findByRole('heading', { name: 'Python Quant' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx`
Expected: FAIL because the page file does not exist

- [ ] **Step 3: Implement the minimal page**

```tsx
export function PythonQuantPage() {
  const { t } = useI18n()
  const { overview, fetchOverview } = usePythonQuantStore()

  useEffect(() => {
    void fetchOverview()
  }, [fetchOverview])

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('pythonQuant.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('pythonQuant.description')}</p>
        </CardHeader>
      </Card>
    </div>
  )
}
```

- [ ] **Step 4: Add the create/start/stop form flow**

Implement these controls on the page:

- account `<Select>` populated from `overview.accounts`
- strategy `<Select>` populated from `overview.strategies`
- symbol `<Input>` default `XAUUSD`
- timeframe `<Select>`
- lot `<Input>` default `0.01`
- `Create Job` button
- jobs table with `Edit`, `Start`, `Stop`, `Delete`, `Last Signal`, `Last Error`, `Last Bar Time`
- edit dialog that reuses the create-job form and submits `PUT /python-quant/jobs/{job_id}`

Minimal create payload shape:

```ts
{
  name: 'Gold M5 Trend',
  account_id: 'acc-1',
  strategy_id: 'sma_cross',
  symbol: 'XAUUSD',
  timeframe: 'M5',
  lot: 0.01,
}
```

- [ ] **Step 5: Add interaction tests**

Add tests for:

- creating a job posts to `/python-quant/jobs`
- updating a job posts to `/python-quant/jobs/{job_id}`
- starting a job posts to `/python-quant/jobs/{job_id}/start`
- stopping a job posts to `/python-quant/jobs/{job_id}/stop`
- deleting a job calls `DELETE /python-quant/jobs/{job_id}`
- manual backfill posts to `/python-quant/data/backfill`
- inline backend error text is shown when create/start fails

- [ ] **Step 6: Add manual data-backfill controls**

Implement these page controls so the user can manage local market data explicitly:

- `Backfill Data` button near the create-job form
- numeric bars input default `500`
- success message showing `Inserted {count} rows`
- inline error when `/python-quant/data/backfill` fails

- [ ] **Step 7: Implement the edit-job dialog**

Use the same form fields as create, but prefill from the selected row and submit through `updateJob(job.id, payload)`.

- [ ] **Step 8: Run the focused frontend tests**

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/python-quant-store.test.ts`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/renderer/src/pages/PythonQuantPage.tsx src/renderer/src/App.tsx src/renderer/src/test/python-quant-page.test.tsx
git commit -m "feat: add python quant page"
```

## Task 9: Packaging, Docs, And End-To-End Verification

**Files:**
- Modify: `python_service/mt5_service.spec:10-34`
- Modify: `README.md:7-139`
- Modify: `README.zh-CN.md:7-133`
- Test: `tests/python/test_quant_routes.py`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] **Step 1: Update PyInstaller inputs**

Add `backtrader` and strategy package imports.

```python
hiddenimports=[
    'numpy',
    'pandas',
    'MetaTrader5',
    'backtrader',
    'python_service.app.quant.strategies.sma_cross',
]
```

- [ ] **Step 2: Update docs**

Add these README points in both languages:

- new `Python Quant` module in the feature list
- local SQLite cache path for market data
- built-in strategy plus drop-in user strategy directory
- reminder that Python tests are still `pytest tests/python`

- [ ] **Step 3: Run targeted backend and frontend suites**

Run: `pytest tests/python/test_quant_models.py tests/python/test_quant_storage.py tests/python/test_quant_market_data.py tests/python/test_quant_routes.py tests/python/test_quant_runtime.py tests/python/test_quant_lifespan.py -v`
Expected: PASS

Run: `npm run test:frontend -- src/renderer/src/test/python-quant-store.test.ts src/renderer/src/test/python-quant-page.test.tsx`
Expected: PASS

- [ ] **Step 4: Run full required suites for touched areas**

Run: `pytest tests/python -v`
Expected: PASS

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 5: Run packaging verification**

Run: `npm run build`
Expected: PASS and updated `out/main`, `out/preload`, `out/renderer`

Run: `npm run build:python`
Expected: PASS and rebuilt `python_service/dist/mt5_service`

Run: `npm run verify:packaging`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python_service/mt5_service.spec README.md README.zh-CN.md
git commit -m "docs: document python quant module"
```

## Final Verification Checklist

- `GET /python-quant/overview` returns active MT5 accounts from local-copy-trading state
- creating a job persists to `storage/python_quant/jobs.json`
- starting a job changes status to `running`
- the quant loop backfills missing bars into `storage/python_quant/market_data.sqlite3`
- a built-in SMA Cross strategy appears in the renderer
- the renderer can start and stop a job without leaving the page
- `pytest tests/python` passes
- `npm run test:frontend` passes
- `npm run build`, `npm run build:python`, and `npm run verify:packaging` pass

## Risks And Guardrails

- Reusing local-copy-trading accounts means quant execution is impossible until the user has created at least one verified MT5 account; keep that dependency explicit in the page copy.
- Do not allow arbitrary Python import paths from the renderer. The API should accept a strategy ID only, and the backend should map IDs to discovered modules.
- Keep V1 to market orders and one position per symbol/job. Do not add stop-limit/bracket orders in this plan.
- Keep market data local-first. Fetch from MT5 only when bars are missing or stale; do not refetch the full history every loop.
- If `backtrader` is rejected for licensing reasons, preserve all API/storage/UI contracts and replace only the engine adapter layer.

## Execution Notes

- Use `@superpowers:subagent-driven-development` for task-by-task implementation if you want the safest execution flow.
- Use `@superpowers:executing-plans` only if you intentionally want batched inline execution.
