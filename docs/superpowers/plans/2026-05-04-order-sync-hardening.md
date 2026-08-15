# Order Sync Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MT5 → TopStep order sync safer and more robust by adding API retry, optional high-frequency duplicate blocking, and explicit MT5 lots to TopStep contracts mapping.

**Architecture:** Keep the existing polling architecture. Add deterministic backend helpers for retry, duplicate throttling, and quantity conversion so behavior can be unit-tested without real MT5 or TopStep calls. Extend the existing order sync config model and page instead of adding a new subsystem.

**Tech Stack:** Python FastAPI/Pydantic backend, `urllib` TopStep REST client, React + Zustand renderer, Vitest, pytest.

---

## File Structure

- Modify: `python_service/app/models/order_sync.py`
  - Add `block_high_frequency_orders`, `high_frequency_window_seconds`, and explicit mapping fields for lot conversion.
  - Preserve old `quantity_multiplier` as an internal/backward compatible field only if needed for existing saved config.
- Modify: `python_service/app/services/topstep_service.py`
  - Keep raw API calls here.
  - Do not put retry policy here unless every TopStep API call should use the same retry behavior.
- Modify: `python_service/app/services/order_sync_service.py`
  - Add retry wrapper around TopStep open/close operations.
  - Add high-frequency duplicate gate before placing a new TopStep order.
  - Add explicit lot-to-contract conversion helper.
- Modify: `python_service/app/routes/order_sync.py`
  - No API path change expected; ensure model updates serialize through existing GET/POST endpoints.
- Modify: `src/renderer/src/stores/order-sync-store.ts`
  - Add new config fields and mapping form fields to TypeScript types/defaults.
- Modify: `src/renderer/src/pages/OrderSyncPage.tsx`
  - Add runtime switch: “阻止高频订单”.
  - Add mapping form inputs for MT5 lots and TopStep contracts.
  - Display the explicit ratio in the mapping list.
- Modify: `src/renderer/src/i18n/messages.ts`
  - Add zh-CN/en labels and validation messages.
- Create: `tests/python/test_order_sync_service.py`
  - Unit tests for retry, high-frequency gate, quantity conversion, and close retry.
- Optional Test: add renderer test only if existing test setup can cover this page cheaply; otherwise rely on `npm run build` and store/page smoke through existing App tests.

---

### Task 1: Backend Config Model Extensions

**Files:**
- Modify: `python_service/app/models/order_sync.py`
- Test: `tests/python/test_order_sync_service.py`

- [ ] **Step 1: Write failing tests for new defaults**

Create `tests/python/test_order_sync_service.py` if it does not exist.

```python
from python_service.app.models.order_sync import OrderSyncState, OrderSymbolMapping


def test_order_sync_state_defaults_disable_high_frequency_blocking():
    state = OrderSyncState()

    assert state.block_high_frequency_orders is False
    assert state.high_frequency_window_seconds == 5


def test_symbol_mapping_defaults_to_one_mt5_lot_equals_one_topstep_contract():
    mapping = OrderSymbolMapping(mt5_symbol='xauusd', topstep_contract_id='CON.F.US.GC.TEST')

    assert mapping.mt5_symbol == 'XAUUSD'
    assert mapping.mt5_lots == 1
    assert mapping.topstep_contracts == 1
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: FAIL because fields do not exist.

- [ ] **Step 3: Add model fields**

In `OrderSymbolMapping`, add:

```python
mt5_lots: float = 1
topstep_contracts: int = 1
```

In `OrderSyncState`, add:

```python
block_high_frequency_orders: bool = False
high_frequency_window_seconds: float = 5
```

In `OrderSyncConfigUpdate`, add:

```python
block_high_frequency_orders: bool = False
high_frequency_window_seconds: float = 5
```

- [ ] **Step 4: Run targeted tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add python_service/app/models/order_sync.py tests/python/test_order_sync_service.py
git commit -m "test: cover order sync config defaults"
```

---

### Task 2: Explicit MT5 Lot To TopStep Contract Conversion

**Files:**
- Modify: `python_service/app/services/order_sync_service.py`
- Test: `tests/python/test_order_sync_service.py`

- [ ] **Step 1: Write failing conversion tests**

Add:

```python
from python_service.app.models.order_sync import OrderSymbolMapping
from python_service.app.services.order_sync_service import calculate_topstep_contract_size


def test_calculates_topstep_contract_size_from_mapping_ratio():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        mt5_lots=0.1,
        topstep_contracts=1,
    )

    assert calculate_topstep_contract_size({'volume': 0.3}, mapping) == 3


def test_contract_size_is_at_least_one():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        mt5_lots=10,
        topstep_contracts=1,
    )

    assert calculate_topstep_contract_size({'volume': 0.01}, mapping) == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Implement helper**

In `order_sync_service.py`, replace `_position_size(position, multiplier)` with:

```python
def calculate_topstep_contract_size(position: dict, mapping: OrderSymbolMapping) -> int:
    volume = float(position.get('volume') or 0)
    mt5_lots = max(float(mapping.mt5_lots or 1), 0.000001)
    topstep_contracts = max(int(mapping.topstep_contracts or 1), 1)
    return max(1, math.floor((volume / mt5_lots) * topstep_contracts))
```

Update the open-order path from:

```python
size = _position_size(position, mapping.quantity_multiplier)
```

to:

```python
size = calculate_topstep_contract_size(position, mapping)
```

- [ ] **Step 4: Run targeted tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add python_service/app/services/order_sync_service.py tests/python/test_order_sync_service.py
git commit -m "feat: support explicit order sync lot mapping"
```

---

### Task 3: TopStep Retry Policy For Open And Close

**Files:**
- Modify: `python_service/app/services/order_sync_service.py`
- Test: `tests/python/test_order_sync_service.py`

- [ ] **Step 1: Write failing retry tests**

Add:

```python
import pytest
from python_service.app.services.order_sync_service import run_topstep_with_retries
from python_service.app.services.topstep_service import TopStepApiError


@pytest.mark.asyncio
async def test_topstep_operation_retries_three_times_then_succeeds():
    calls = {'count': 0}

    def flaky_operation():
        calls['count'] += 1
        if calls['count'] < 3:
            raise TopStepApiError('temporary')
        return 9056

    result = await run_topstep_with_retries(flaky_operation, retry_delay_seconds=0)

    assert result == 9056
    assert calls['count'] == 3


@pytest.mark.asyncio
async def test_topstep_operation_fails_after_three_attempts():
    calls = {'count': 0}

    def failing_operation():
        calls['count'] += 1
        raise TopStepApiError('still down')

    with pytest.raises(TopStepApiError):
        await run_topstep_with_retries(failing_operation, retry_delay_seconds=0)

    assert calls['count'] == 3
```

- [ ] **Step 2: Run tests and verify failure**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: FAIL because helper does not exist.

- [ ] **Step 3: Implement retry helper**

In `order_sync_service.py`, add:

```python
async def run_topstep_with_retries(operation, attempts: int = 3, retry_delay_seconds: float = 0.5):
    last_error = None
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(operation)
        except TopStepApiError as exc:
            last_error = exc
            if attempt < attempts - 1 and retry_delay_seconds > 0:
                await asyncio.sleep(retry_delay_seconds)
    raise last_error
```

Use it in open-order sync:

```python
order_id = await run_topstep_with_retries(
    lambda: client.place_market_order(mapping.topstep_contract_id, side, size, f'mt5-{ticket}')
)
```

Use it in close sync:

```python
await run_topstep_with_retries(lambda: client.close_contract_position(order.topstep_contract_id))
```

- [ ] **Step 4: Run targeted tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add python_service/app/services/order_sync_service.py tests/python/test_order_sync_service.py
git commit -m "feat: retry topstep order sync operations"
```

---

### Task 4: High-Frequency Duplicate Blocking

**Files:**
- Modify: `python_service/app/models/order_sync.py`
- Modify: `python_service/app/services/order_sync_service.py`
- Test: `tests/python/test_order_sync_service.py`

- [ ] **Step 1: Extend synced order model for duplicate gate metadata**

In tests, assert model can store original MT5 volume:

```python
from python_service.app.models.order_sync import SyncedOrder


def test_synced_order_stores_mt5_volume_for_frequency_gate():
    order = SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )

    assert order.mt5_volume == 0.1
```

- [ ] **Step 2: Add duplicate gate tests**

Add:

```python
from python_service.app.models.order_sync import OrderSyncState, SyncedOrder
from python_service.app.services.order_sync_service import should_block_high_frequency_order


def test_blocks_same_symbol_side_and_volume_inside_window():
    state = OrderSyncState(block_high_frequency_orders=True, high_frequency_window_seconds=5)
    state.synced_orders = [SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )]

    assert should_block_high_frequency_order(
        state,
        symbol='XAUUSD',
        side='buy',
        mt5_volume=0.1,
        now_iso='2026-05-04T00:00:04+00:00',
    ) is True


def test_allows_same_order_after_window():
    state = OrderSyncState(block_high_frequency_orders=True, high_frequency_window_seconds=5)
    state.synced_orders = [SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )]

    assert should_block_high_frequency_order(
        state,
        symbol='XAUUSD',
        side='buy',
        mt5_volume=0.1,
        now_iso='2026-05-04T00:00:06+00:00',
    ) is False
```

- [ ] **Step 3: Run tests and verify failure**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: FAIL because `mt5_volume` and gate helper do not exist.

- [ ] **Step 4: Implement metadata and gate helper**

In `SyncedOrder`, add:

```python
mt5_volume: float = 0
blocked_reason: str | None = None
```

In `order_sync_service.py`, add:

```python
def should_block_high_frequency_order(state: OrderSyncState, symbol: str, side: str, mt5_volume: float, now_iso: str) -> bool:
    if not state.block_high_frequency_orders:
        return False

    now = datetime.fromisoformat(now_iso)
    for order in state.synced_orders:
        if order.status not in {'open', 'closed'}:
            continue
        if order.mt5_symbol != symbol or order.side != side:
            continue
        if abs(float(order.mt5_volume or 0) - mt5_volume) > 0.000001:
            continue
        opened_at = datetime.fromisoformat(order.opened_at)
        if (now - opened_at).total_seconds() <= state.high_frequency_window_seconds:
            return True
    return False
```

- [ ] **Step 5: Apply gate in open-order path**

Before creating TopStep order, calculate:

```python
now_iso = _utc_now()
mt5_volume = float(position.get('volume') or 0)
if should_block_high_frequency_order(_state, symbol, side, mt5_volume, now_iso):
    _state.synced_orders.append(SyncedOrder(
        mt5_ticket=ticket,
        mt5_symbol=symbol,
        mt5_volume=mt5_volume,
        topstep_account_id=credential.account_id,
        topstep_contract_id=mapping.topstep_contract_id,
        side=side,
        size=0,
        status='blocked',
        opened_at=now_iso,
        blocked_reason='high_frequency_duplicate',
    ))
    continue
```

Update TypeScript union later to include `blocked`.

- [ ] **Step 6: Run targeted tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add python_service/app/models/order_sync.py python_service/app/services/order_sync_service.py tests/python/test_order_sync_service.py
git commit -m "feat: block high frequency order sync duplicates"
```

---

### Task 5: Frontend Store Types And Config Payload

**Files:**
- Modify: `src/renderer/src/stores/order-sync-store.ts`

- [ ] **Step 1: Update TypeScript interfaces**

In `OrderSymbolMapping`, replace/augment multiplier fields:

```ts
mt5_lots: number
topstep_contracts: number
```

In `SyncedOrder`, add:

```ts
mt5_volume: number
status: 'open' | 'closed' | 'error' | 'blocked'
blocked_reason: string | null
```

In `OrderSyncStateData`, add:

```ts
block_high_frequency_orders: boolean
high_frequency_window_seconds: number
```

In `DEFAULT_CONFIG`, add matching defaults:

```ts
block_high_frequency_orders: false,
high_frequency_window_seconds: 5,
```

- [ ] **Step 2: Update `saveConfig` accepted payload**

Change the `Pick<>` to include:

```ts
'block_high_frequency_orders' | 'high_frequency_window_seconds'
```

- [ ] **Step 3: Run frontend tests**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx src/renderer/src/test/settings-page-language.test.tsx`

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add src/renderer/src/stores/order-sync-store.ts
git commit -m "feat: extend order sync frontend state"
```

---

### Task 6: Frontend Runtime Switch And Mapping Ratio Form

**Files:**
- Modify: `src/renderer/src/pages/OrderSyncPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`

- [ ] **Step 1: Add i18n labels**

Under `orderSync` zh-CN, add:

```ts
blockHighFrequency: '阻止高频订单',
blockHighFrequencyHint: '开启后，相同品种、方向、手数的 MT5 订单在 5 秒内最多同步一次',
highFrequencyWindow: '防高频窗口 (秒)',
mt5Lots: 'MT5 手数',
topstepContracts: 'TopStep 合约数',
mappingRatioHint: '例如 0.1 手 MT5 = 1 张 TopStep 合约',
blocked: '已阻止',
```

Under English, add equivalent labels.

- [ ] **Step 2: Update mapping form default**

Change `DEFAULT_MAPPING` to include:

```ts
mt5_lots: 0.1,
topstep_contracts: 1,
```

Keep `quantity_multiplier` only if needed for compatibility; do not display it after this task.

- [ ] **Step 3: Add runtime switch UI**

In the runtime card below the existing enabled switch, add:

```tsx
<div className="flex items-center justify-between rounded-lg border p-3">
  <div>
    <Label>{t('orderSync.blockHighFrequency')}</Label>
    <div className="text-xs text-muted-foreground">{t('orderSync.blockHighFrequencyHint')}</div>
  </div>
  <Switch
    checked={config.block_high_frequency_orders}
    onCheckedChange={(block_high_frequency_orders) => persist({ block_high_frequency_orders })}
  />
</div>
```

Add a numeric input for `high_frequency_window_seconds`, default 5.

- [ ] **Step 4: Replace multiplier input with explicit ratio inputs**

Replace the old `quantity_multiplier` input with two fields:

```tsx
<Input
  type="number"
  min="0.01"
  step="0.01"
  value={mappingForm.mt5_lots}
  onChange={(event) => setMappingForm({ ...mappingForm, mt5_lots: Number(event.target.value) })}
/>
<Input
  type="number"
  min="1"
  step="1"
  value={mappingForm.topstep_contracts}
  onChange={(event) => setMappingForm({ ...mappingForm, topstep_contracts: Number(event.target.value) })}
/>
```

- [ ] **Step 5: Update submit mapping payload**

Set:

```ts
mt5_lots: Number(mappingForm.mt5_lots) || 1,
topstep_contracts: Math.max(1, Math.floor(Number(mappingForm.topstep_contracts) || 1)),
```

- [ ] **Step 6: Update mapping list display**

Show:

```tsx
{t('orderSync.mappingRatioHint')}: {mapping.mt5_lots} → {mapping.topstep_contracts}
```

- [ ] **Step 7: Update synced record status display**

If `status === 'blocked'`, render a visible badge and blocked reason; do not show it as a successful TopStep order.

- [ ] **Step 8: Run frontend tests and build**

Run: `npm run test:frontend`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/renderer/src/pages/OrderSyncPage.tsx src/renderer/src/i18n/messages.ts
git commit -m "feat: add order sync safety controls"
```

---

### Task 7: End-To-End Backend Behavior Tests Without Real APIs

**Files:**
- Modify: `tests/python/test_order_sync_service.py`
- Modify if needed: `python_service/app/services/order_sync_service.py`

- [ ] **Step 1: Add test seams if needed**

If module globals make tests hard, add focused helpers only:

```python
def reset_order_sync_state_for_tests(state: OrderSyncState | None = None) -> None:
    global _state, _loaded, _clients
    _state = state or OrderSyncState()
    _loaded = True
    _clients = {}
```

This helper should be clearly named for tests and not used by production code.

- [ ] **Step 2: Test open retry through `process_order_sync_tick`**

Mock:
- `get_positions` to return one MT5 position.
- `_get_client` to return an object whose `place_market_order` fails twice then succeeds.
- `_save` to no-op.

Assert:
- One synced order is created.
- `topstep_order_id` is set.
- client method called 3 times.

- [ ] **Step 3: Test close retry through `process_order_sync_tick`**

Seed state with one open synced order.

Mock:
- `get_positions` to return no positions.
- `_get_client` to return an object whose `close_contract_position` fails twice then succeeds.
- `_save` to no-op.

Assert:
- order status becomes `closed`.
- `closed_at` is set.
- client method called 3 times.

- [ ] **Step 4: Test high-frequency block through `process_order_sync_tick`**

Seed state with `block_high_frequency_orders=True` and a recent synced order.

Mock `get_positions` to return another same-symbol/same-side/same-volume ticket.

Assert:
- new record status is `blocked`.
- no TopStep client order placement occurs.

- [ ] **Step 5: Run targeted tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add python_service/app/services/order_sync_service.py tests/python/test_order_sync_service.py
git commit -m "test: cover order sync retry and throttling"
```

---

### Task 8: Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run frontend tests**

Run: `npm run test:frontend`

Expected: PASS.

- [ ] **Step 2: Run Python order sync tests**

Run: `$env:PYTHONPATH='E:\ai\workbench-gemini'; pytest tests/python/test_order_sync_service.py -v`

Expected: PASS.

- [ ] **Step 3: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 4: Note known unrelated Python suite failures**

Do not claim full `pytest tests/python` passes unless existing unrelated failures are fixed. Current known unrelated issues include MT5 launch environment assumptions and older alert model field names.

- [ ] **Step 5: Commit verification-only changes if any**

If no files changed, do not commit.

---

## Implementation Notes

- Retry should apply to TopStep order placement and TopStep close calls only. Do not retry MT5 polling itself in this change.
- High-frequency blocking should happen before TopStep order placement and should produce an audit record with `status='blocked'` so the user can see why no TopStep order was sent.
- “Same order” for blocking means same MT5 symbol, same side, and same MT5 volume within the configured 5-second default window.
- Explicit mapping ratio should supersede the old `quantity_multiplier` UI. If old saved configs exist with only `quantity_multiplier`, either keep a compatibility fallback in backend conversion or document one-time re-entry of mappings. Prefer a backend fallback if it is a small localized change.
- Keep credentials behavior unchanged in this plan; secure credential storage is a separate feature.
