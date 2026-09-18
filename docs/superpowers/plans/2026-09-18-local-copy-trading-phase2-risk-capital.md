# Local Copy Trading Phase 2 Risk And Capital Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local copy trading usable with real money by letting the follower choose its own position size, carry the source stop loss and take profit onto its own price scale, refuse orders that breach configured risk limits, and follow the source trader through partial closes and scale-ins.

**Architecture:** Three pure decision modules — `volume_planner` (how big), `price_mapping` (where the stops go) and `guards` (whether to trade at all) — sit beside the existing `follower_executor`, which is split into a plan phase that decides everything and a send phase that touches the broker. Everything that needs live account state (margin level, open positions, the follower's *actual* volume) runs inside `copy_service`, which already owns the MT5 session, so the engine stays a pure scheduler. The order map gains a recorded source size, which is what lets the engine tell a source partial close from a no-op and route it to a resize instead of short-circuiting.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, `sqlite3`, MetaTrader5 Python API, pytest.

---

## Scope Check

This plan continues `docs/superpowers/plans/2026-09-18-local-copy-trading-phase1-foundation.md` and **assumes Phase 1 is merged**. It cannot be executed before Phase 1, because:

- Task 4 rewrites `follower_executor.py`, which Phase 1 restructured to take a live client.
- Tasks 5 and 6 extend `copy_service.py` and keep its two-phase write, both introduced by Phase 1.
- Task 6 depends on the `copy_order_map` table and `init_db()`, both introduced by Phase 1.

The six tasks here do form one coherent release: volume modes, protective levels and guards are the three things a follower account needs before it can be pointed at a live source, and the drift sync is what keeps it in step afterwards. Task 4 is the hinge — it is where the plan/send split appears, and both Task 5 (guards need the planned volume) and Task 6 (resizing needs a request builder) depend on it.

**Credential encryption is explicitly out of scope.** The user excluded it by name, and it is not a task in this plan. Credentials continue to live in `storage/local_copy_trading.json` in plaintext, exactly as they do after Phase 1. The new `storage/copy-trading-risk.json` holds limits only and no secrets.

## Design Decisions

**1. Size, protective levels and guard verdicts are decided by pure functions, then applied.**

The pre-Phase-2 executor did everything in one pass: read the symbol, compute a volume inline, build a request, send it. Every Phase 2 feature needs to inspect or override something *before* the request is built, and two of them (guards, resizing) need the volume as an input. So the order is now built in two stages:

- `follower_executor.plan_copy_order(...) -> CopyPlan` decides and does not send.
- `follower_executor.send_copy_order(...)` sends a plan.

`copy_position_to_follower` remains as a thin wrapper over the two, so Phase 1's executor tests and any external caller keep working unchanged. This is the only reason the wrapper exists — do not delete it.

**2. Volume modes are a relationship property, and the follower's equity is read only when the mode needs it.**

`CopyRelationship.volume_mode` is one of `multiplier`, `fixed`, `equity_ratio`, `risk_percent`. The default stays `multiplier`, so every relationship stored by Phase 1 keeps its existing behaviour. `lot_multiplier` keeps its existing meaning in `multiplier` mode and doubles as the fixed size in `fixed` mode; `max_lot` (0 = no cap) and `risk_percent` are new fields.

`equity_ratio` is the only mode that needs a live account read, so `plan_copy_order` calls `client.account_info()` only when that mode is selected. `risk_percent` needs the source position to carry a stop loss, because the risk unit *is* the stop distance — a source position with no stop cannot be sized this way and is reported as a failed copy rather than guessed at.

**3. Protective levels are carried as a distance, and the side comes from the source level, not the direction.**

`price_mapping.translate_protective_levels` takes the source `sl`/`tp`, computes `abs(source_entry - level)`, and re-applies that distance from the *follower's* fill price. Which side of entry the follower level lands on is derived from `level < source_entry`, not from whether the position is a buy. Deriving it from the direction is the obvious implementation and it silently inverts take profit on any short — the source's take profit sits *below* entry for a short, and a direction-based implementation places it above.

`sync_sl_tp` defaults to `False`. Turning it on changes live order requests, so it is opt-in per relationship.

**4. A guard block is not a failure, and it gets its own status.**

A blocked order and a rejected order both mean "no position was opened", but they must be treated differently:

- A broker rejection is a fault. It should count towards the consecutive-failure breaker and it should be retried.
- A guard block is the risk system working. It must **not** count towards the breaker — otherwise a relationship that hits `max_positions_per_symbol` three times disables itself permanently. It should be retried once the limit that fired no longer applies.

The copy path therefore returns a `CopyResult` with an explicit `status` of `copied`, `failed` or `skipped`, and `process_tick` propagates it into the `SyncEvent` instead of collapsing everything to copied/failed. The order-map row is marked `skipped`, which is neither `pending` nor `confirmed`, so `list_open_records` ignores it and reconciliation will not mistake it for an orphan.

**5. Fixing the copy result contract is a Phase 1 amendment, and it is unavoidable.**

Phase 1's `execute_copy` returned a 4-tuple `(success, message, position_id, order_id)` and Phase 1's tests assert on it. There is no way to distinguish "skipped" from "failed" through that shape: encoding it in the message is exactly the message-parsing that decision 4 exists to avoid, and adding a fifth tuple element breaks every 4-way unpack.

Task 5 therefore changes the return type to `CopyResult` and updates the six Phase 1 tests in `tests/python/test_local_copy_trading_copy_service.py` to attribute access. `engine._copy_result_parts` accepts **both** `CopyResult` and the plain tuples, so an executor supplied as a lambda still works. This is a deliberate, documented contract change, not an accident.

**6. The follower is resized, not re-opened, and the engine needs a recorded size to know when.**

A source position keeps its ticket when the source trader partially closes or scales in, so the existing "already copied" short-circuit would leave the follower at its original size forever. `copy_order_map` gains `source_volume`, recording the source size the follower currently matches. On each tick the engine compares the live source volume against that value: equal means nothing to do, different means hand the position to the copy executor, which replans and sends either a partial close or an extra deal.

Two details make this settle instead of firing forever:

- The recorded size is updated after every adjustment, so the comparison converges.
- Without a reader the engine cannot prove drift, so it does nothing. A wrong resize on a live account is worse than a missed one.

`init_db` also gains `_ensure_column`, because `CREATE TABLE IF NOT EXISTS` leaves an existing table alone and an install upgrading in place would otherwise be missing the new column.

**7. Guards are disabled by default; 0 means "no limit".**

Every field of `CopyTradingRiskSettings` defaults to 0, which disables that rule, except `max_consecutive_failures` which defaults to 3. An install that has never written `storage/copy-trading-risk.json` therefore behaves exactly as it did after Phase 1, and the guard code path is only reached when `execute_copy` is called with settings. The tests rely on this: passing no settings is the "unconfigured" case.

## File Structure

### New files

| Path | Responsibility |
| :--- | :--- |
| `python_service/app/local_copy_trading/volume_planner.py` | Choose a follower volume from a relationship and a source position, in one of four modes; snap it to the symbol's limits; compute a resize delta. Pure. |
| `python_service/app/local_copy_trading/price_mapping.py` | Translate source stop loss and take profit onto the follower's price scale, and round to the symbol's digits. Pure. |
| `python_service/app/local_copy_trading/guards.py` | Evaluate the optional pre-trade limits and load/save the settings file. Pure. |
| `tests/python/test_local_copy_trading_volume_planner.py` | Volume modes, caps, step snapping, error cases. |
| `tests/python/test_local_copy_trading_price_mapping.py` | Long/short level placement, missing levels, ratio scaling, digit rounding. |
| `tests/python/test_local_copy_trading_guards.py` | Every rule, rule precedence, settings round-trip. |

### Existing files to modify

| Path | Change |
| :--- | :--- |
| `python_service/app/local_copy_trading/models.py` | `CopyRelationship` gains `volume_mode`, `max_lot`, `risk_percent`, `sync_sl_tp`. New `CopyTradingRiskSettings`. New `CopyResult`. |
| `python_service/app/local_copy_trading/follower_executor.py` | Split into `plan_copy_order` / `send_copy_order`; wire in volume modes and protective levels; add `adjust_copied_position_volume`; expose `as_dict` and `list_positions`. |
| `python_service/app/local_copy_trading/copy_service.py` | Return `CopyResult`; add the guard path; add the resize path for an already-confirmed position. |
| `python_service/app/local_copy_trading/copy_trading_db.py` | `source_volume` column plus in-place upgrade; `record_source_volume`, `get_recorded_volume`, `mark_skipped`. |
| `python_service/app/local_copy_trading/engine.py` | Propagate the executor's status; route an already-copied position to the executor when its source size moved. |
| `python_service/app/local_copy_trading/loop.py` | Pass `recorded_volume=copy_trading_db.get_recorded_volume` into `process_tick`. |
| `tests/python/test_local_copy_trading_follower_executor.py` | 15 new tests across planning, volume modes, protective levels and resizing. |
| `tests/python/test_local_copy_trading_copy_service.py` | 6 Phase 1 tests updated to `CopyResult`; 11 new tests for guards and resizing. |
| `tests/python/test_copy_trading_db.py` | 5 new tests for the recorded volume and the in-place upgrade (Task 5). |
| `tests/python/test_local_copy_trading_engine.py` | 1 new test for the skipped status (Task 5) and 4 for drift routing (Task 6). |

## Running the tests

All commands run from the repository root. The repo's `python_service/requirements.txt` includes `pytest`.

Use `python -m pytest` so the interpreter is explicit. Run only the file under test during TDD; run the whole copy-trading suite before the final commit of each task.

```bash
python -m pytest tests/python/test_local_copy_trading_volume_planner.py -v
python -m pytest tests/python -q -k "local_copy or copy_trading or mt5_session"
```

### Why the aggregate uses an explicit file list

The `-k "local_copy or copy_trading or mt5_session"` filter also sweeps in `test_local_copy_trading_lifespan.py`, `_models.py`, `_routes.py`, `_runtime.py` and `_storage.py`, which this plan neither creates nor modifies. Their test counts are not part of any figure below, so an aggregate run through that filter will report more than the numbers stated here. Use the explicit list instead whenever a count is asserted:

```bash
python -m pytest -q \
  tests/python/test_mt5_session.py \
  tests/python/test_copy_trading_db.py \
  tests/python/test_local_copy_trading_ownership.py \
  tests/python/test_local_copy_trading_reconcile.py \
  tests/python/test_local_copy_trading_snapshot.py \
  tests/python/test_local_copy_trading_source_adapter.py \
  tests/python/test_local_copy_trading_volume_planner.py \
  tests/python/test_local_copy_trading_price_mapping.py \
  tests/python/test_local_copy_trading_guards.py \
  tests/python/test_local_copy_trading_follower_executor.py \
  tests/python/test_local_copy_trading_copy_service.py \
  tests/python/test_local_copy_trading_engine.py
```

Those twelve files sum to the figures used throughout this plan: 142 after Task 5, 146 after Task 6.

### Test counts

Counts before this plan, after Phase 1:

| File | Before | After |
| :--- | ---: | ---: |
| `test_local_copy_trading_follower_executor.py` | 9 | 24 |
| `test_local_copy_trading_copy_service.py` | 8 | 19 |
| `test_copy_trading_db.py` | 7 | 12 |
| `test_local_copy_trading_engine.py` | 10 | 15 |

Task 5 lands most of this growth: after it the suite stands at 142 passed, and Task 6's four engine tests take it to 146.

The remaining Phase 1 files are untouched: `test_mt5_session.py` (7), `test_local_copy_trading_source_adapter.py` (3), `test_local_copy_trading_snapshot.py` (10), `test_local_copy_trading_ownership.py` (11), `test_local_copy_trading_reconcile.py` (7).

---

### Task 1: Follower volume modes

**Files:**
- Create: `python_service/app/local_copy_trading/volume_planner.py`
- Create: `tests/python/test_local_copy_trading_volume_planner.py`
- Modify: `python_service/app/local_copy_trading/models.py`

The four modes are decided here so that the executor never computes a size itself. `normalize_volume` is the same clamping Phase 1 had inline, moved somewhere both the copy path and the resize path can reach it.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_volume_planner.py`:

```python
from collections import namedtuple

import pytest

from python_service.app.local_copy_trading import volume_planner
from python_service.app.local_copy_trading.models import CopyRelationship


SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'volume_max', 'trade_contract_size'])


def _symbol(**overrides):
    fields = {
        'volume_min': 0.01,
        'volume_step': 0.01,
        'volume_max': 100.0,
        'trade_contract_size': 100.0,
    }
    fields.update(overrides)
    return SymbolInfo(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def test_multiplier_mode_scales_the_source_volume():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=2),
        {'volume': 0.1},
        symbol_info=_symbol(),
    )

    assert volume == 0.2


def test_fixed_mode_ignores_the_source_volume():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='fixed', lot_multiplier=0.5),
        {'volume': 3.0},
        symbol_info=_symbol(),
    )

    assert volume == 0.5


def test_equity_ratio_mode_scales_with_the_account_ratio():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='equity_ratio'),
        {'volume': 0.4},
        symbol_info=_symbol(),
        source_equity=10000.0,
        follower_equity=2500.0,
    )

    assert volume == 0.1


def test_equity_ratio_mode_requires_both_equities():
    with pytest.raises(ValueError, match='equity_ratio sizing requires both account equities'):
        volume_planner.plan_volume(
            _relationship(volume_mode='equity_ratio'),
            {'volume': 0.4},
            symbol_info=_symbol(),
            source_equity=10000.0,
        )


def test_risk_percent_mode_sizes_from_the_stop_distance():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='risk_percent', risk_percent=1),
        {'volume': 0.1, 'price_open': 2300.0, 'sl': 2280.0},
        symbol_info=_symbol(),
        source_equity=10000.0,
    )

    assert volume == 0.05


def test_risk_percent_mode_requires_a_stop_loss():
    with pytest.raises(ValueError, match='requires a source position with a stop loss'):
        volume_planner.plan_volume(
            _relationship(volume_mode='risk_percent'),
            {'volume': 0.1, 'price_open': 2300.0, 'sl': 0.0},
            symbol_info=_symbol(),
            source_equity=10000.0,
        )


def test_risk_percent_mode_requires_a_contract_size():
    with pytest.raises(ValueError, match='requires a known contract size'):
        volume_planner.plan_volume(
            _relationship(volume_mode='risk_percent'),
            {'volume': 0.1, 'price_open': 2300.0, 'sl': 2280.0},
            symbol_info=_symbol(trade_contract_size=0.0),
            source_equity=10000.0,
        )


def test_max_lot_caps_the_result():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=100, max_lot=0.5),
        {'volume': 1.0},
        symbol_info=_symbol(),
    )

    assert volume == 0.5


def test_a_zero_max_lot_means_no_cap():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=3, max_lot=0),
        {'volume': 1.0},
        symbol_info=_symbol(),
    )

    assert volume == 3.0


def test_result_is_snapped_to_the_volume_step():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=1),
        {'volume': 0.107},
        symbol_info=_symbol(),
    )

    assert volume == 0.1


def test_result_is_lifted_to_the_symbol_minimum():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=1),
        {'volume': 0.001},
        symbol_info=_symbol(),
    )

    assert volume == 0.01


def test_result_is_capped_by_the_symbol_maximum():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='fixed', lot_multiplier=50.0),
        {'volume': 0.1},
        symbol_info=_symbol(volume_max=10.0),
    )

    assert volume == 10.0


def test_multiplier_mode_rejects_a_zero_source_volume():
    with pytest.raises(ValueError, match='copy volume must be greater than 0'):
        volume_planner.plan_volume(
            _relationship(),
            {'volume': 0.0},
            symbol_info=_symbol(),
        )


def test_unknown_volume_mode_is_rejected():
    relationship = _relationship()
    object.__setattr__(relationship, 'volume_mode', 'martingale')

    with pytest.raises(ValueError, match='Unsupported volume mode'):
        volume_planner.plan_volume(relationship, {'volume': 0.1}, symbol_info=_symbol())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_volume_planner.py -v`

Expected: FAIL at collection with `ImportError: cannot import name 'volume_planner'`.

- [ ] **Step 3: Add the relationship fields**

In `python_service/app/local_copy_trading/models.py`, insert these four lines into `CopyRelationship` **between** the existing `lot_multiplier` field and the existing `is_active` field. Both of those already exist — do not repeat them, or Pydantic will reject the model with a duplicate-field error.

```python
    volume_mode: Literal['multiplier', 'fixed', 'equity_ratio', 'risk_percent'] = 'multiplier'
    max_lot: float = 0
    risk_percent: float = 1
    sync_sl_tp: bool = False
```

After the edit the field block reads:

```python
    symbol: str = ''
    source_symbol: str = ''
    follower_symbol: str = ''
    lot_multiplier: float = 1
    volume_mode: Literal['multiplier', 'fixed', 'equity_ratio', 'risk_percent'] = 'multiplier'
    max_lot: float = 0
    risk_percent: float = 1
    sync_sl_tp: bool = False
    is_active: bool = True
```

`sync_sl_tp` belongs to Task 2 but is declared here so the model is edited once. Then add these two validators next to the existing `validate_lot_multiplier`:

```python
    @field_validator('max_lot')
    @classmethod
    def validate_max_lot(cls, value: float) -> float:
        if value < 0:
            raise ValueError('max_lot must not be negative')
        return value

    @field_validator('risk_percent')
    @classmethod
    def validate_risk_percent(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('risk_percent must be greater than 0')
        return value
```

- [ ] **Step 4: Create the volume planner**

Create `python_service/app/local_copy_trading/volume_planner.py`:

```python
"""Decide the follower volume for one copied position.

Four sizing modes are supported. All of them end in the same place: a volume
that has been clamped to the follower symbol's contract limits and to the
relationship's own ceiling, so the caller never has to think about broker
granularity.

The module is pure: it takes account figures and symbol metadata as arguments
instead of reading them, which keeps it testable and keeps the MT5 connection
out of the sizing decision.
"""

from __future__ import annotations

import math

from python_service.app.local_copy_trading.models import CopyRelationship


VOLUME_MODES = ('multiplier', 'fixed', 'equity_ratio', 'risk_percent')


def normalize_volume(raw_volume: float, symbol_info) -> float:
    """Snap a volume to the symbol's minimum, maximum and step."""
    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')

    volume_min = float(getattr(symbol_info, 'volume_min', 0.01) or 0.01)
    volume_max = float(getattr(symbol_info, 'volume_max', 0) or 0)
    volume_step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)

    volume = max(raw_volume, volume_min)
    if volume_max > 0:
        volume = min(volume, volume_max)

    steps = math.floor((volume - volume_min) / volume_step + 0.000001)
    normalized = volume_min + steps * volume_step
    if volume_max > 0:
        normalized = min(normalized, volume_max)
    return round(max(normalized, volume_min), 8)


def plan_volume(
    relationship: CopyRelationship,
    source_position: dict,
    *,
    symbol_info,
    source_equity: float | None = None,
    follower_equity: float | None = None,
) -> float:
    """Return the follower volume for this relationship and source position.

    Raises:
        ValueError: when the inputs cannot produce a positive volume.
    """
    source_volume = float(source_position.get('volume') or 0)
    mode = relationship.volume_mode

    if mode == 'multiplier':
        raw_volume = source_volume * relationship.lot_multiplier
    elif mode == 'fixed':
        raw_volume = relationship.lot_multiplier
    elif mode == 'equity_ratio':
        if source_equity is None or follower_equity is None:
            raise ValueError('equity_ratio sizing requires both account equities')
        if float(source_equity) <= 0:
            raise ValueError('source equity must be greater than 0')
        raw_volume = source_volume * (float(follower_equity) / float(source_equity)) * relationship.lot_multiplier
    elif mode == 'risk_percent':
        raw_volume = _volume_from_risk(relationship, source_position, source_equity, symbol_info)
    else:
        raise ValueError(f'Unsupported volume mode: {mode}')

    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')

    if relationship.max_lot > 0:
        raw_volume = min(raw_volume, relationship.max_lot)

    return normalize_volume(raw_volume, symbol_info)


def plan_volume_delta(
    expected_volume: float,
    actual_volume: float,
    *,
    symbol_info,
    tolerance: float = 0.0,
) -> float:
    """Return the volume to add or remove on an already-open follower position.

    Positive means scale in, negative means partially close, 0 means the
    position already matches. Differences smaller than one tradeable step are
    ignored so the engine does not send orders the broker would reject as
    zero-volume.
    """
    delta = round(float(expected_volume) - float(actual_volume), 8)
    step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)
    if step > 0 and abs(delta) < step:
        return 0.0
    if tolerance > 0 and abs(delta) <= tolerance:
        return 0.0
    return delta


def _volume_from_risk(
    relationship: CopyRelationship,
    source_position: dict,
    source_equity: float | None,
    symbol_info,
) -> float:
    """Size so that the follower risks a fixed fraction of the source equity.

    Uses the source position's stop distance as the risk unit, converted to
    money through the follower symbol's contract size. This assumes the account
    currency and the instrument's quote currency match, which holds for the
    USD-quoted symbols this tool targets; a cross-currency instrument would need
    a conversion rate here.
    """
    if source_equity is None:
        raise ValueError('risk_percent sizing requires the source equity')

    entry = float(source_position.get('price_open') or 0)
    stop = float(source_position.get('sl') or 0)
    if entry <= 0 or stop <= 0:
        raise ValueError('risk_percent sizing requires a source position with a stop loss')

    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        raise ValueError('risk_percent sizing requires a non-zero stop distance')

    contract_size = float(getattr(symbol_info, 'trade_contract_size', 0) or 0)
    if contract_size <= 0:
        raise ValueError('risk_percent sizing requires a known contract size')

    risk_amount = float(source_equity) * (relationship.risk_percent / 100.0)
    return risk_amount / (stop_distance * contract_size)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_volume_planner.py -v`

Expected: `14 passed`

- [ ] **Step 6: Confirm the model change did not break Phase 1**

Run: `python -m pytest tests/python -q -k "local_copy or copy_trading"`

Expected: no failures. The new fields all have defaults, so existing relationship payloads in `storage/local_copy_trading.json` still load.

- [ ] **Step 7: Commit**

```bash
git add python_service/app/local_copy_trading/models.py python_service/app/local_copy_trading/volume_planner.py tests/python/test_local_copy_trading_volume_planner.py
git commit -m "feat(copy-trading): add follower volume modes"
```

---

### Task 2: Protective level translation

**Files:**
- Create: `python_service/app/local_copy_trading/price_mapping.py`
- Create: `tests/python/test_local_copy_trading_price_mapping.py`

Stop loss and take profit cannot be copied as raw prices, because the follower fills at its own price on its own broker. Only the distance from entry survives, plus the side of entry the level sits on.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_price_mapping.py`:

```python
from collections import namedtuple

from python_service.app.local_copy_trading import price_mapping


SymbolInfo = namedtuple('SymbolInfo', ['digits'])


def test_a_long_position_keeps_stop_below_and_target_above():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2301.5)

    assert stop_loss == 2281.5
    assert take_profit == 2341.5


def test_a_short_position_keeps_stop_above_and_target_below():
    source = {'price_open': 2300.0, 'sl': 2320.0, 'tp': 2260.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2299.5)

    assert stop_loss == 2319.5
    assert take_profit == 2259.5


def test_a_missing_source_stop_stays_missing():
    source = {'price_open': 2300.0, 'sl': 0.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2300.0)

    assert stop_loss == 0.0
    assert take_profit == 2340.0


def test_a_missing_source_entry_yields_no_levels():
    source = {'price_open': 0.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2300.0)

    assert (stop_loss, take_profit) == (0.0, 0.0)


def test_the_ratio_scales_the_distance_for_a_differently_quoted_symbol():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 0.0}

    stop_loss, _ = price_mapping.translate_protective_levels(
        source, follower_entry=2300.0, ratio=10.0
    )

    assert stop_loss == 2100.0


def test_the_levels_follow_a_follower_entry_that_differs_from_the_source():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2295.0)

    assert stop_loss == 2275.0
    assert take_profit == 2335.0


def test_normalize_price_rounds_to_the_symbol_digits():
    assert price_mapping.normalize_price(2301.5678, SymbolInfo(digits=2)) == 2301.57
    assert price_mapping.normalize_price(1.23456789, SymbolInfo(digits=5)) == 1.23457


def test_normalize_price_keeps_zero_as_zero():
    assert price_mapping.normalize_price(0.0, SymbolInfo(digits=2)) == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_price_mapping.py -v`

Expected: FAIL at collection with `ImportError: cannot import name 'price_mapping'`.

- [ ] **Step 3: Create the price mapping module**

Create `python_service/app/local_copy_trading/price_mapping.py`:

```python
"""Translate source protective levels onto the follower's price scale.

Stop loss and take profit cannot be copied as raw prices. The follower opens at
its own price on its own broker, so the only meaningful thing to carry across is
the *distance* from entry, together with which side of entry the level sits on.

Deriving the side from the source level itself (rather than from the trade
direction) is what keeps a take profit above entry for a long position and below
entry for a short one.
"""

from __future__ import annotations


def translate_protective_levels(
    source_position: dict,
    *,
    follower_entry: float,
    ratio: float = 1.0,
) -> tuple[float, float]:
    """Return ``(stop_loss, take_profit)`` on the follower's price scale.

    A source level of 0 (not set) stays 0, so the follower simply has no stop on
    that side. ``ratio`` scales the distance for instruments quoted on a
    different scale between the two brokers; it is 1.0 for identical symbols.

    Returns ``(0.0, 0.0)`` when the source entry price is unknown, because a
    distance cannot be derived from nothing.
    """
    source_entry = float(source_position.get('price_open') or 0)
    if source_entry <= 0 or follower_entry <= 0:
        return 0.0, 0.0

    def translate(level_key: str) -> float:
        level = float(source_position.get(level_key) or 0)
        if level <= 0:
            return 0.0
        distance = abs(source_entry - level) * ratio
        return follower_entry - distance if level < source_entry else follower_entry + distance

    return translate('sl'), translate('tp')


def normalize_price(price: float, symbol_info) -> float:
    """Round a price to the symbol's digits so MT5 accepts the request."""
    if price <= 0:
        return 0.0
    digits = int(getattr(symbol_info, 'digits', 0) or 0)
    return round(price, digits)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_price_mapping.py -v`

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/price_mapping.py tests/python/test_local_copy_trading_price_mapping.py
git commit -m "feat(copy-trading): translate source stop loss and take profit"
```

---

### Task 3: Pre-trade guard module

**Files:**
- Create: `python_service/app/local_copy_trading/guards.py`
- Create: `tests/python/test_local_copy_trading_guards.py`
- Modify: `python_service/app/local_copy_trading/models.py`

The rules are written and tested before anything calls them, so Task 5 is a pure wiring change. `GuardDecision.rule` is a stable identifier rather than a message, so callers and tests can assert on the specific rule that fired.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_guards.py`:

```python
from python_service.app.local_copy_trading import guards
from python_service.app.local_copy_trading.models import CopyRelationship, CopyTradingRiskSettings


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def _evaluate(**overrides):
    fields = {
        'planned_volume': 0.1,
        'follower_account_info': None,
        'follower_positions': [],
        'settings': CopyTradingRiskSettings(),
    }
    fields.update(overrides)
    relationship = fields.pop('relationship', _relationship())
    return guards.evaluate_open_guard(relationship, **fields)


def test_default_settings_allow_everything():
    decision = _evaluate()

    assert decision.allowed is True
    assert decision.rule == ''


def test_position_count_limit_blocks_a_new_position():
    settings = CopyTradingRiskSettings(max_positions_per_symbol=2)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.1}, {'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held)

    assert decision.allowed is False
    assert decision.rule == 'max_positions_per_symbol'


def test_position_count_ignores_other_symbols():
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    held = [{'symbol': 'EURUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held)

    assert decision.allowed is True


def test_volume_limit_counts_what_is_already_held():
    settings = CopyTradingRiskSettings(max_volume_per_symbol=0.5)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.3}, {'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held, planned_volume=0.2)

    assert decision.allowed is False
    assert decision.rule == 'max_volume_per_symbol'


def test_volume_limit_allows_an_order_that_fits():
    settings = CopyTradingRiskSettings(max_volume_per_symbol=0.5)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held, planned_volume=0.2)

    assert decision.allowed is True


def test_daily_open_count_limit_blocks_further_orders():
    settings = CopyTradingRiskSettings(max_daily_open_count=5)

    decision = _evaluate(settings=settings, daily_open_count=5)

    assert decision.allowed is False
    assert decision.rule == 'daily_open_count'


def test_daily_loss_limit_blocks_further_orders():
    settings = CopyTradingRiskSettings(max_daily_loss=200)

    decision = _evaluate(settings=settings, daily_realized_profit=-200.0)

    assert decision.allowed is False
    assert decision.rule == 'daily_loss'


def test_daily_loss_limit_allows_a_profitable_day():
    settings = CopyTradingRiskSettings(max_daily_loss=200)

    decision = _evaluate(settings=settings, daily_realized_profit=150.0)

    assert decision.allowed is True


def test_margin_level_limit_blocks_a_stretched_account():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': 120.0})

    assert decision.allowed is False
    assert decision.rule == 'margin_level'


def test_margin_level_limit_allows_a_healthy_account():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': 480.0})

    assert decision.allowed is True


def test_margin_level_rule_is_skipped_when_the_terminal_reports_none():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': None})

    assert decision.allowed is True


def test_consecutive_failure_limit_blocks_a_stuck_relationship():
    settings = CopyTradingRiskSettings(max_consecutive_failures=3)

    decision = _evaluate(settings=settings, consecutive_failures=3)

    assert decision.allowed is False
    assert decision.rule == 'consecutive_failures'


def test_consecutive_failure_limit_allows_a_recovering_relationship():
    settings = CopyTradingRiskSettings(max_consecutive_failures=3)

    decision = _evaluate(settings=settings, consecutive_failures=2)

    assert decision.allowed is True


def test_the_account_level_rule_wins_over_the_order_level_rule():
    settings = CopyTradingRiskSettings(min_margin_level=150, max_positions_per_symbol=1)

    decision = _evaluate(
        settings=settings,
        follower_account_info={'margin_level': 100.0},
        follower_positions=[{'symbol': 'XAUUSD.m', 'volume': 0.1}],
    )

    assert decision.rule == 'margin_level'


def test_settings_round_trip_through_disk(tmp_path):
    path = tmp_path / 'copy-trading-risk.json'
    settings = CopyTradingRiskSettings(max_volume_per_symbol=1.5, max_daily_loss=300)

    guards.save_risk_settings(settings, path)
    loaded = guards.load_risk_settings(path)

    assert loaded.max_volume_per_symbol == 1.5
    assert loaded.max_daily_loss == 300


def test_missing_settings_file_yields_defaults(tmp_path):
    loaded = guards.load_risk_settings(tmp_path / 'absent.json')

    assert loaded == CopyTradingRiskSettings()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_guards.py -v`

Expected: FAIL at collection with `ImportError: cannot import name 'guards'`.

- [ ] **Step 3: Add the risk settings model**

In `python_service/app/local_copy_trading/models.py`, append after `LocalCopyTradingRuntimeUpdate`:

```python
class CopyTradingRiskSettings(BaseModel):
    """Optional pre-trade limits.

    A value of 0 disables the corresponding rule, so the default settings impose
    no restrictions and an existing install keeps behaving as before.
    """

    max_volume_per_symbol: float = 0
    max_positions_per_symbol: int = 0
    max_daily_open_count: int = 0
    max_daily_loss: float = 0
    min_margin_level: float = 0
    max_consecutive_failures: int = 3
```

- [ ] **Step 4: Create the guards module**

Create `python_service/app/local_copy_trading/guards.py`:

```python
"""Pre-trade guards for copy actions.

A guard answers one question: should this copy be allowed to reach the broker?
Every rule is optional and disabled by default (a limit of 0 means "no limit"),
so an unconfigured install behaves exactly as it did before this module existed.

Guards run *before* the order is sent and *after* the volume has been planned,
because several rules need to know the size of the order being placed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from python_service.app.local_copy_trading.models import CopyRelationship, CopyTradingRiskSettings


RISK_SETTINGS_PATH = Path('storage/copy-trading-risk.json')


@dataclass(frozen=True)
class GuardDecision:
    """Outcome of a guard evaluation.

    ``rule`` is a stable identifier so the UI and tests can assert on the
    specific rule that fired instead of parsing a message.
    """

    allowed: bool
    rule: str = ''
    message: str = ''


def load_risk_settings(path: Path | str = RISK_SETTINGS_PATH) -> CopyTradingRiskSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return CopyTradingRiskSettings()
    raw = settings_path.read_text(encoding='utf-8').strip('\ufeff\x00 \t\r\n')
    if not raw:
        return CopyTradingRiskSettings()
    return CopyTradingRiskSettings(**json.loads(raw))


def save_risk_settings(settings: CopyTradingRiskSettings, path: Path | str = RISK_SETTINGS_PATH) -> None:
    settings_path = Path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings.model_dump(), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _symbol_positions(follower_positions: list[dict], symbol: str) -> list[dict]:
    target = str(symbol or '').strip().casefold()
    return [
        position
        for position in follower_positions
        if str(position.get('symbol') or '').strip().casefold() == target
    ]


def evaluate_open_guard(
    relationship: CopyRelationship,
    *,
    planned_volume: float,
    follower_account_info: dict | None,
    follower_positions: list[dict],
    settings: CopyTradingRiskSettings,
    daily_open_count: int = 0,
    daily_realized_profit: float = 0.0,
    consecutive_failures: int = 0,
) -> GuardDecision:
    """Decide whether this copy may proceed.

    Returns an allowed decision unless a configured limit is breached. The first
    breach wins; rules are ordered from "the account is already in trouble" to
    "this specific order is too big".
    """
    if settings.max_consecutive_failures > 0 and consecutive_failures >= settings.max_consecutive_failures:
        return GuardDecision(
            False,
            'consecutive_failures',
            f'Relationship has failed {consecutive_failures} times in a row (limit {settings.max_consecutive_failures})',
        )

    if settings.max_daily_open_count > 0 and daily_open_count >= settings.max_daily_open_count:
        return GuardDecision(
            False,
            'daily_open_count',
            f'Daily open count {daily_open_count} reached the limit of {settings.max_daily_open_count}',
        )

    if settings.max_daily_loss > 0 and daily_realized_profit <= -abs(settings.max_daily_loss):
        return GuardDecision(
            False,
            'daily_loss',
            f'Daily realised result {daily_realized_profit:.2f} reached the loss limit of {settings.max_daily_loss}',
        )

    if follower_account_info and settings.min_margin_level > 0:
        margin_level = follower_account_info.get('margin_level')
        if margin_level is not None and float(margin_level) < settings.min_margin_level:
            return GuardDecision(
                False,
                'margin_level',
                f'Follower margin level {margin_level} is below the required {settings.min_margin_level}',
            )

    symbol = relationship.follower_symbol
    existing = _symbol_positions(follower_positions, symbol)

    if settings.max_positions_per_symbol > 0 and len(existing) >= settings.max_positions_per_symbol:
        return GuardDecision(
            False,
            'max_positions_per_symbol',
            f'{symbol} already holds {len(existing)} positions (limit {settings.max_positions_per_symbol})',
        )

    if settings.max_volume_per_symbol > 0:
        held_volume = sum(float(position.get('volume') or 0) for position in existing)
        if held_volume + planned_volume > settings.max_volume_per_symbol:
            return GuardDecision(
                False,
                'max_volume_per_symbol',
                f'{symbol} would hold {held_volume + planned_volume:.2f} lots (limit {settings.max_volume_per_symbol})',
            )

    return GuardDecision(True)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_guards.py -v`

Expected: `16 passed`

- [ ] **Step 6: Commit**

```bash
git add python_service/app/local_copy_trading/models.py python_service/app/local_copy_trading/guards.py tests/python/test_local_copy_trading_guards.py
git commit -m "feat(copy-trading): add optional pre-trade risk guards"
```

---

### Task 4: Split order placement and wire sizing into the executor

**Files:**
- Modify: `python_service/app/local_copy_trading/follower_executor.py`
- Test: `tests/python/test_local_copy_trading_follower_executor.py`

This is the hinge task. The executor gains a plan phase that decides size and protective levels, a send phase that transmits, a resize function, and two new read helpers (`as_dict`, `list_positions`) that the guard path needs in Task 5.

`copy_position_to_follower` is kept as a wrapper over plan-then-send, so all nine Phase 1 tests continue to pass untouched.

- [ ] **Step 1: Make sure the test fixture can describe a symbol**

In `tests/python/test_local_copy_trading_follower_executor.py`, confirm the module-level `SymbolInfo` namedtuple has a `digits` field, because `normalize_price` reads it:

```python
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'digits'])
```

and that `FakeClient.symbol_info` returns it:

```python
    def symbol_info(self, symbol):
        return SymbolInfo(volume_min=0.01, volume_step=0.01, digits=2)
```

- [ ] **Step 2: Append the new failing tests**

Append to the end of `tests/python/test_local_copy_trading_follower_executor.py`:

```python
def test_copy_position_leaves_protective_levels_unset_by_default():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 2280.0,
            'tp': 2340.0,
        },
    )

    request = client.sent_requests[0]
    assert request['sl'] == 0.0
    assert request['tp'] == 0.0


def test_copy_position_translates_protective_levels_when_enabled():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(sync_sl_tp=True),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 2280.0,
            'tp': 2340.0,
        },
    )

    request = client.sent_requests[0]
    # The buy fills at the ask (2301.5), so the source distances of 20 and 40 carry over.
    assert request['sl'] == 2281.5
    assert request['tp'] == 2341.5


def test_copy_position_uses_the_fixed_volume_mode():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='fixed', lot_multiplier=0.3),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.9, 'type': 0},
    )

    assert client.sent_requests[0]['volume'] == 0.3


def test_copy_position_reports_a_sizing_failure_as_a_failed_copy():
    client = FakeClient()

    success, message, _, _ = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='risk_percent'),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 0.0,
            'source_equity': 10000.0,
        },
    )

    assert success is False
    assert 'requires a source position with a stop loss' in message
    assert client.sent_requests == []


def test_copy_position_scales_by_equity_when_the_follower_reports_equity():
    class EquityClient(FakeClient):
        def account_info(self):
            return namedtuple('AccountInfo', ['equity'])(equity=2500.0)

    client = EquityClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='equity_ratio'),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.4, 'type': 0, 'source_equity': 10000.0},
    )

    assert client.sent_requests[0]['volume'] == 0.1


def _source(**overrides):
    fields = {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.2, 'type': 0}
    fields.update(overrides)
    return fields


def test_adjust_partially_closes_when_the_follower_is_too_large():
    client = FakeClient(positions=[_owned_position(volume=0.3)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is True
    request = client.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL
    assert 'Partially closed' in message


def test_adjust_scales_in_when_the_follower_is_too_small():
    client = FakeClient(positions=[_owned_position(volume=0.1)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.3
    )

    assert success is True
    request = client.sent_requests[0]
    assert 'position' not in request
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert 'Scaled in' in message


def test_adjust_reverses_the_direction_for_a_short_position():
    client = FakeClient(positions=[_owned_position(type=1, volume=0.3)])

    follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(type=1), expected_volume=0.1
    )

    request = client.sent_requests[0]
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert request['volume'] == 0.2


def test_adjust_sends_nothing_when_the_volume_already_matches():
    client = FakeClient(positions=[_owned_position(volume=0.2)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.2
    )

    assert success is True
    assert client.sent_requests == []
    assert 'already matches' in message


def test_adjust_ignores_a_difference_smaller_than_one_step():
    client = FakeClient(positions=[_owned_position(volume=0.2)])

    success, _ = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.205
    )

    assert success is True
    assert client.sent_requests == []


def test_adjust_fails_when_no_position_is_owned():
    client = FakeClient(positions=[Position(222, 222, 'XAUUSD.m', 0, 0.5, 0, '')])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is False
    assert 'No owned follower position' in message
    assert client.sent_requests == []


def test_adjust_reports_a_broker_rejection():
    class RejectingClient(FakeClient):
        def order_send(self, request):
            self.sent_requests.append(request)
            return OrderResult(retcode=10006, order=0, deal=0, comment='rejected')

    client = RejectingClient(positions=[_owned_position(volume=0.3)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is False
    assert 'Retcode: 10006' in message


def test_adjust_is_a_no_op_for_simulated_followers():
    success, message = follower_executor.adjust_copied_position_volume(
        None, _follower(connection_type='simulated'), _relationship(), _source(), expected_volume=0.1
    )

    assert success is True
    assert 'Simulated volume sync' in message


def test_plan_copy_order_exposes_the_size_before_anything_is_sent():
    client = FakeClient()

    plan = follower_executor.plan_copy_order(
        client, _follower(), _relationship(lot_multiplier=3), _source(volume=0.1)
    )

    assert plan.ok is True
    assert plan.volume == 0.3
    assert plan.request['volume'] == 0.3
    assert client.sent_requests == []


def test_plan_copy_order_reports_a_missing_symbol_without_sending():
    class NoSelectClient(FakeClient):
        def symbol_select(self, symbol, enabled):
            return False

    plan = follower_executor.plan_copy_order(
        NoSelectClient(), _follower(), _relationship(), _source()
    )

    assert plan.ok is False
    assert plan.request is None
    assert 'Failed to select follower symbol' in plan.message
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: FAIL — `AttributeError: module ... has no attribute 'adjust_copied_position_volume'`, and the sizing tests fail because the executor still multiplies `lot_multiplier` for every mode.

- [ ] **Step 4: Rewrite the executor**

Replace the whole of `python_service/app/local_copy_trading/follower_executor.py` with the content below. The parts carried over unchanged from Phase 1 are `as_dict` (formerly `_as_dict`), `list_positions` (formerly inline logic), `_position_is_buy`, `_done_codes`, `find_owned_position`, and `close_copied_position_on_follower`.

```python
"""Execute follower-side MT5 orders against an already-open session.

The caller owns the connection (see ``services.mt5_session``). This module only
builds and validates order requests, so it can be tested without a terminal.

Follower positions are identified by the ownership token written into the order
comment (see ``position_ownership``). There is deliberately no symbol-based
fallback: matching the wrong position on a live account is worse than reporting
that nothing was found.

Order placement is split in two: ``plan_copy_order`` decides size and protective
levels without touching the broker, and ``send_copy_order`` transmits the
request. The split exists so that pre-trade guards can inspect a fully planned
order (they need the volume) before anything reaches the broker.
"""

from dataclasses import dataclass

from python_service.app.local_copy_trading import position_ownership, price_mapping, volume_planner
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent


@dataclass(frozen=True)
class CopyPlan:
    """A follower order that has been sized and priced but not yet sent.

    ``short_circuit`` carries a finished result for the cases that never produce
    a request at all (simulated followers, unsupported connection types). When it
    is set the caller must return it unchanged.
    """

    ok: bool
    message: str = ''
    request: dict | None = None
    volume: float = 0.0
    short_circuit: tuple | None = None


def as_dict(value) -> dict:
    """Normalise an MT5 namedtuple-like result into a plain dict."""
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


def list_positions(client, symbol: str | None = None) -> list[dict]:
    """Read open positions as plain dicts, tolerating brokers that ignore filters."""
    try:
        positions = client.positions_get(symbol=symbol) if symbol else client.positions_get()
    except TypeError:
        positions = client.positions_get()
    except Exception:
        return []
    return [as_dict(position) for position in (positions or [])]


def _position_is_buy(position: dict, client) -> bool:
    value = position.get('type')
    if isinstance(value, str):
        return value.strip().casefold() in {'buy', 'long', '0'}
    return int(value or 0) == getattr(client, 'POSITION_TYPE_BUY', 0)


def _done_codes(client) -> set:
    return {
        getattr(client, 'TRADE_RETCODE_DONE', 10009),
        getattr(client, 'TRADE_RETCODE_PLACED', 10008),
    }


def find_owned_position(
    client,
    symbol: str,
    *,
    relationship_id: str,
    position_id: str,
) -> dict | None:
    """Locate the follower position owned by this relationship/source pair.

    Returns None when the position is absent. Callers must treat None as
    "nothing to act on" rather than falling back to another position.
    """
    try:
        positions = client.positions_get(symbol=symbol)
    except TypeError:
        positions = client.positions_get()
    except Exception:
        return None

    return position_ownership.select_owned_position(
        [as_dict(position) for position in (positions or [])],
        relationship_id=relationship_id,
        position_id=position_id,
    )


def plan_copy_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> CopyPlan:
    """Size and price a follower order without sending it.

    Returns a plan whose ``short_circuit`` is set when no order will ever be
    built, and whose ``ok`` is False when the inputs cannot produce a request.
    """
    if follower.connection_type == 'simulated':
        message = f'Simulated copy {relationship.source_symbol} to {relationship.follower_symbol}'
        return CopyPlan(
            ok=True,
            message=message,
            short_circuit=(True, message, source_position.get('position_id', ''), ''),
        )
    if follower.connection_type != 'mt5_terminal':
        return CopyPlan(ok=False, message=f'Unsupported follower connection type: {follower.connection_type}')

    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not position_id:
        return CopyPlan(ok=False, message='Source position has no identifier')

    symbol = relationship.follower_symbol
    if not client.symbol_select(symbol, True):
        return CopyPlan(ok=False, message=f'Failed to select follower symbol {symbol}. Error: {client.last_error()}')

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return CopyPlan(
            ok=False,
            message=f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}',
        )

    is_buy = _position_is_buy(source_position, client)
    order_type = getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1)
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return CopyPlan(ok=False, message=f'Missing executable price for follower symbol {symbol}')

    follower_equity = None
    if relationship.volume_mode == 'equity_ratio':
        account_info = client.account_info()
        if account_info is not None:
            follower_equity = float(getattr(account_info, 'equity', 0) or 0)

    try:
        volume = volume_planner.plan_volume(
            relationship,
            source_position,
            symbol_info=symbol_info,
            source_equity=source_position.get('source_equity'),
            follower_equity=follower_equity,
        )
    except ValueError as error:
        return CopyPlan(ok=False, message=str(error))

    stop_loss = 0.0
    take_profit = 0.0
    if relationship.sync_sl_tp:
        raw_stop, raw_target = price_mapping.translate_protective_levels(
            source_position,
            follower_entry=price,
        )
        stop_loss = price_mapping.normalize_price(raw_stop, symbol_info)
        take_profit = price_mapping.normalize_price(raw_target, symbol_info)

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'price': price,
        'sl': stop_loss,
        'tp': take_profit,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    return CopyPlan(ok=True, request=request, volume=volume)


def send_copy_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    plan: CopyPlan,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Transmit a plan produced by :func:`plan_copy_order`."""
    if plan.short_circuit is not None:
        return plan.short_circuit
    if not plan.ok or plan.request is None:
        return False, plan.message, '', ''

    symbol = plan.request['symbol']
    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    result = client.order_send(plan.request)
    if result is None:
        return False, f'MT5 order_send returned no result. Error: {client.last_error()}', '', ''

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 order_send failed. Retcode: {result_code}. {comment}', '', ''

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    owned = find_owned_position(
        client,
        symbol,
        relationship_id=relationship.id,
        position_id=position_id,
    )
    follower_position_id = str(owned.get('ticket') or '') if owned else ''
    return (
        True,
        f'Copied {relationship.source_symbol} to {symbol}, volume {plan.volume}, order {order_id}',
        follower_position_id,
        str(order_id or ''),
    )


def copy_position_to_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Open a follower position mirroring ``source_position``.

    Returns ``(success, message, follower_position_id, follower_order_id)``.
    """
    plan = plan_copy_order(client, follower, relationship, source_position)
    if plan.short_circuit is not None:
        return plan.short_circuit
    if not plan.ok:
        return False, plan.message, '', ''
    return send_copy_order(client, follower, relationship, plan, source_position)


def adjust_copied_position_volume(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    expected_volume: float,
) -> tuple[bool, str]:
    """Bring an already-open follower position to ``expected_volume``.

    A source position can shrink (the source trader takes partial profit) or grow
    (the source trader scales in) while keeping the same ticket. Mirroring that
    means sending either a partial close or an additional deal, never a new
    independent position.

    Returns ``(success, message)``. A position that already matches is reported
    as success so the caller can settle the record without further action.
    """
    if follower.connection_type == 'simulated':
        return True, f'Simulated volume sync to {expected_volume}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    symbol = relationship.follower_symbol
    owned = find_owned_position(
        client,
        symbol,
        relationship_id=relationship.id,
        position_id=position_id,
    )
    if owned is None:
        return False, f'No owned follower position for source position {position_id}'

    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return False, f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}'

    actual_volume = float(owned.get('volume') or 0)
    delta = volume_planner.plan_volume_delta(expected_volume, actual_volume, symbol_info=symbol_info)
    if delta == 0:
        return True, f'Follower position already matches {actual_volume} lots'

    position_ticket = int(owned.get('ticket') or 0)
    is_buy = _position_is_buy(owned, client)
    scaling_in = delta > 0
    order_type = (
        (getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1))
        if scaling_in
        else (getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0))
    )
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return False, f'Missing adjustment price for follower symbol {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume_planner.normalize_volume(abs(delta), symbol_info),
        'type': order_type,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    if not scaling_in:
        request['position'] = position_ticket

    result = client.order_send(request)
    if result is None:
        return False, f'MT5 volume adjustment returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 volume adjustment failed. Retcode: {result_code}. {comment}'

    action = 'Scaled in' if scaling_in else 'Partially closed'
    return True, f'{action} follower position {position_ticket} by {abs(delta):.2f} lots to {expected_volume}'


def close_copied_position_on_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
) -> tuple[bool, str]:
    """Close the follower position owned by ``copied_event``."""
    if follower.connection_type == 'simulated':
        return True, f'Simulated close {copied_event.follower_position_id or copied_event.position_id}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    target_position = find_owned_position(
        client,
        copied_event.symbol,
        relationship_id=relationship.id,
        position_id=copied_event.position_id,
    )
    if target_position is None:
        return True, f'No owned follower position for source position {copied_event.position_id}; nothing to close'

    symbol = str(target_position.get('symbol') or copied_event.symbol or relationship.follower_symbol)
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    tick = client.symbol_info_tick(symbol)
    if tick is None:
        return False, f'Missing tick for follower symbol {symbol}. Error: {client.last_error()}'

    is_buy = _position_is_buy(target_position, client)
    order_type = getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0)
    price = float(getattr(tick, 'bid', 0) if is_buy else getattr(tick, 'ask', 0))
    if price <= 0:
        return False, f'Missing close price for follower symbol {symbol}'

    position_ticket = int(target_position.get('ticket') or 0)
    volume = float(target_position.get('volume') or 0)
    if position_ticket <= 0 or volume <= 0:
        return False, f'Invalid follower position data for {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'position': position_ticket,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, copied_event.position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 close order_send returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 close order_send failed. Retcode: {result_code}. {comment}'

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    return True, f'Closed follower position {position_ticket}, order {order_id}'
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: `24 passed`

- [ ] **Step 6: Confirm the copy-trading suite is still green**

Run: `python -m pytest tests/python -q -k "local_copy or copy_trading"`

Expected: no failures. In particular `test_local_copy_trading_copy_service.py` must still pass — `copy_service` still calls `copy_position_to_follower`, which now routes through the plan phase.

- [ ] **Step 7: Commit**

```bash
git add python_service/app/local_copy_trading/follower_executor.py tests/python/test_local_copy_trading_follower_executor.py
git commit -m "feat(copy-trading): plan orders before sending and add follower resizing"
```

---

### Task 5: Structured copy outcome, guards and drift bookkeeping

**Files:**
- Modify: `python_service/app/local_copy_trading/models.py`
- Modify: `python_service/app/local_copy_trading/copy_trading_db.py`
- Modify: `python_service/app/local_copy_trading/copy_service.py`
- Modify: `python_service/app/local_copy_trading/engine.py`
- Test: `tests/python/test_local_copy_trading_copy_service.py`
- Test: `tests/python/test_copy_trading_db.py`
- Test: `tests/python/test_local_copy_trading_engine.py`

This task does two things that belong together: it introduces `CopyResult` so a guard block is distinguishable from a failure, and it gives the order map a recorded source size so an already-copied position can be recognised as unchanged without opening a connection.

The recorded size has to land here rather than later, because the "already copied" early return depends on it. Without it, every already-confirmed position would look drifted on every tick and would open a follower connection just to check. Task 6 then teaches the engine to compare the live source size against that recorded value; until then the early return is inert, because nothing writes a value other than 0.

- [ ] **Step 1: Write the failing db tests**

Append to `tests/python/test_copy_trading_db.py`:

```python
def test_a_new_record_starts_with_no_recorded_source_volume(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.0


def test_record_source_volume_round_trips(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.35, updated_at='2026-09-18T00:00:05+00:00', db_path=db
    )

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.35


def test_recorded_volume_is_unknown_for_an_absent_pair(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    assert copy_trading_db.get_recorded_volume('rel-9', 'pos-9', db_path=db) is None


def test_a_marked_skip_is_not_an_open_record(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)
    copy_trading_db.mark_skipped(
        'rel-1:pos-1', message='limit reached', updated_at='2026-09-18T00:00:06+00:00', db_path=db
    )

    assert copy_trading_db.list_open_records(db_path=db) == []
    assert copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)['status'] == 'skipped'


def test_init_db_upgrades_a_database_written_before_source_volume_existed(tmp_path):
    """An install upgrading in place must not lose its existing order map."""
    import sqlite3

    db = tmp_path / 'legacy.db'
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE copy_order_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_key TEXT NOT NULL UNIQUE,
            relationship_id TEXT NOT NULL,
            source_account_id TEXT NOT NULL,
            follower_account_id TEXT NOT NULL,
            source_position_id TEXT NOT NULL,
            status TEXT NOT NULL,
            follower_position_ticket TEXT NOT NULL DEFAULT '',
            follower_order_id TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO copy_order_map (
            client_key, relationship_id, source_account_id, follower_account_id,
            source_position_id, status, created_at, updated_at
        ) VALUES ('rel-1:pos-1', 'rel-1', 'src-1', 'fol-1', 'pos-1', 'confirmed',
                  '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    copy_trading_db.init_db(db)

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['source_volume'] == 0
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.2, updated_at='2026-09-18T00:00:07+00:00', db_path=db
    )
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.2
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/python/test_copy_trading_db.py -v`

Expected: FAIL with `AttributeError: module ... has no attribute 'get_recorded_volume'`.

- [ ] **Step 3: Add the recorded volume and the skipped status to the order map**

In `python_service/app/local_copy_trading/copy_trading_db.py`, add the column to `_SCHEMA` between `follower_order_id` and `message`:

```
    follower_order_id TEXT NOT NULL DEFAULT '',
    source_volume REAL NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
```

Replace `init_db` and add `_ensure_column` directly beneath it:

```python
def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    connection = connect(db_path)
    try:
        connection.executescript(_SCHEMA)
        _ensure_column(connection, 'copy_order_map', 'source_volume', 'REAL NOT NULL DEFAULT 0')
        connection.commit()
    finally:
        connection.close()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing table when it predates the current schema.

    ``CREATE TABLE IF NOT EXISTS`` silently leaves an old table alone, so a
    database written by an earlier version would be missing newly added columns.
    This keeps an in-place upgrade working without a separate migration step.
    """
    existing = {row[1] for row in connection.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in existing:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
```

Then insert these two functions immediately before `def mark_failed(`:

```python
def record_source_volume(
    client_key: str,
    *,
    source_volume: float,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    """Remember the source size this copy last matched.

    The next tick compares the live source volume against this value to decide
    whether the follower needs a partial close or a scale in. Recording it after
    every action is what makes the comparison settle instead of firing forever.
    """
    connection = connect(db_path)
    try:
        connection.execute(
            """
            UPDATE copy_order_map
               SET source_volume = ?, updated_at = ?
             WHERE client_key = ?
            """,
            (float(source_volume), updated_at, client_key),
        )
        connection.commit()
    finally:
        connection.close()


def get_recorded_volume(
    relationship_id: str,
    source_position_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> float | None:
    """Return the source volume last matched for this pair, or None if unknown."""
    connection = connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT source_volume FROM copy_order_map
             WHERE relationship_id = ? AND source_position_id = ?
             ORDER BY id DESC
             LIMIT 1
            """,
            (relationship_id, source_position_id),
        ).fetchone()
        if row is None:
            return None
        return float(row['source_volume'] or 0)
    finally:
        connection.close()
```

Then append after `mark_drifted`:

```python
def mark_skipped(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    """Settle a record whose order a pre-trade guard refused to send."""
    _set_status(client_key, 'skipped', message=message, updated_at=updated_at, db_path=db_path)
```

- [ ] **Step 4: Run the db tests**

Run: `python -m pytest tests/python/test_copy_trading_db.py -v`

Expected: `12 passed`

- [ ] **Step 5: Add `CopyResult`**

In `python_service/app/local_copy_trading/models.py`, change the import line at the top to:

```python
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
```

and insert this immediately before `class SyncEvent(BaseModel):`:

```python
@dataclass(frozen=True)
class CopyResult:
    """Outcome of one copy action.

    ``status`` separates the three things that can happen to a copy, because
    they must be handled differently downstream:

    ``copied``
        An order was accepted (or the position already matched).
    ``failed``
        The broker or the session refused. Retried on the next tick.
    ``skipped``
        A pre-trade guard refused. Not a failure, so it must not count towards
        the consecutive-failure breaker, and the copy is retried on a later tick
        once the limit that fired no longer applies.
    """

    success: bool
    status: Literal['copied', 'failed', 'skipped'] = 'copied'
    message: str = ''
    follower_position_id: str = ''
    follower_order_id: str = ''
```

- [ ] **Step 6: Update the six Phase 1 service tests to the new contract**

In `tests/python/test_local_copy_trading_copy_service.py`, replace the whole section from `def test_execute_copy_records_a_confirmed_order` through the end of `test_execute_copy_rejects_a_position_without_an_identifier` with:

```python
def test_execute_copy_records_a_confirmed_order(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda client, follower, relationship, position: (True, 'Copied', '789', '456'),
    )

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is True
    assert result.status == 'copied'
    assert result.follower_position_id == '789'
    assert result.follower_order_id == '456'
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'


def test_execute_copy_does_not_send_a_second_order_for_the_same_position(db, session, monkeypatch):
    sent = []

    def fake_copy(client, follower, relationship, position):
        sent.append(position['position_id'])
        return True, 'Copied', '789', '456'

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', fake_copy)

    copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)
    second = copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)

    assert sent == ['pos-1']
    assert second.success is True
    assert 'Already copied' in second.message


def test_execute_copy_skips_a_position_confirmed_before_a_crash(db, session, monkeypatch):
    """A row written before the crash must suppress the order, not repeat it."""
    _seed_confirmed(db)

    def exploding_copy(*args, **kwargs):
        raise AssertionError('a second order must not be sent')

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', exploding_copy)

    result = copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)

    assert result.success is True
    assert result.follower_position_id == '789'
    assert 'Already copied' in result.message


def test_execute_copy_marks_the_row_failed_when_the_order_is_rejected(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda *args: (False, 'Retcode: 10004', '', ''),
    )

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is False
    assert result.status == 'failed'
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['message'] == 'Retcode: 10004'


def test_execute_copy_marks_the_row_failed_when_the_session_fails(db, monkeypatch):
    def failing_use_account(*args, **kwargs):
        raise Mt5SessionError('login failed')

    monkeypatch.setattr(copy_service, 'use_account', failing_use_account)

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is False
    assert 'login failed' in result.message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'


def test_execute_copy_rejects_a_position_without_an_identifier(db, session):
    result = copy_service.execute_copy(_follower(), _relationship(), {}, db_path=db)

    assert result.success is False
    assert 'no identifier' in result.message
```

Two of these are worth understanding before you move on, because their passing is the whole reason the recorded size is in this task. `test_execute_copy_does_not_send_a_second_order_for_the_same_position` and `test_execute_copy_skips_a_position_confirmed_before_a_crash` both seed no source volume, and their payloads carry no `volume` either, so the recorded size and the current size are both 0 and the early return fires without opening a connection. "Size unknown" must mean "do nothing", not "resize to zero".

- [ ] **Step 7: Replace the test fixture client with one that can answer guard questions**

In the same file, replace the header — everything from the first `import` down to and including the body of `class FakeClient` — and, separately, the `session` fixture. Leave the `db` fixture and the `_seed_confirmed` helper untouched: they sit between `_copied_event` and `session`, and outside both replaced regions. Confirm all three still exist before running Step 11.

```python
import contextlib
from collections import namedtuple

import pytest

from python_service.app.local_copy_trading import copy_service, copy_trading_db, position_ownership
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyTradingRiskSettings,
    FollowerAccount,
    SyncEvent,
)
from python_service.app.services.mt5_session import Mt5SessionError


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'volume_max', 'digits', 'trade_contract_size'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
AccountInfo = namedtuple('AccountInfo', ['equity', 'margin_level'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume', 'magic', 'comment'])


class FakeClient:
    """Minimal MetaTrader5 stand-in covering what the copy path touches."""

    POSITION_TYPE_BUY = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, positions=None, margin_level=None):
        self.sent_requests = []
        self.positions = list(positions or [])
        self.margin_level = margin_level

    def symbol_select(self, symbol, enabled):
        return enabled is True

    def symbol_info(self, symbol):
        return SymbolInfo(
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
            digits=2,
            trade_contract_size=100.0,
        )

    def symbol_info_tick(self, symbol):
        return Tick(ask=2301.5, bid=2301.3)

    def account_info(self):
        return AccountInfo(equity=10000.0, margin_level=self.margin_level)

    def order_send(self, request):
        self.sent_requests.append(request)
        return OrderResult(retcode=10009, order=456, deal=0, comment='done')

    def positions_get(self, symbol=None):
        return self.positions

    def last_error(self):
        return (0, 'ok')
```

and the fixture:

```python
@pytest.fixture
def session(monkeypatch):
    client = FakeClient()

    @contextlib.contextmanager
    def fake_use_account(*args, **kwargs):
        yield client

    monkeypatch.setattr(copy_service, 'use_account', fake_use_account)
    return client
```

- [ ] **Step 8: Append the guard and resize tests**

Append to the end of `tests/python/test_local_copy_trading_copy_service.py`:

```python
# --- pre-trade guards -------------------------------------------------------


def _owned(ticket=789, position_id='pos-1', volume=0.2, relationship_id='rel-1'):
    return Position(
        ticket=ticket,
        identifier=ticket,
        symbol='XAUUSD.m',
        type=0,
        volume=volume,
        magic=position_ownership.COPY_TRADING_MAGIC,
        comment=position_ownership.build_comment(relationship_id, position_id),
    )


def test_execute_copy_skips_the_order_when_a_guard_blocks_it(db, session):
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'skipped'
    assert result.success is False
    assert session.sent_requests == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'skipped'


def test_execute_copy_places_the_order_when_the_guard_allows_it(db, session):
    settings = CopyTradingRiskSettings(max_positions_per_symbol=2)
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'copied'
    assert result.follower_position_id == '789'
    assert len(session.sent_requests) == 1


def test_execute_copy_reports_the_guard_that_fired_in_the_event_message(db, session):
    settings = CopyTradingRiskSettings(min_margin_level=150)
    session.margin_level = 120.0

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'skipped'
    assert 'margin level' in result.message
    assert session.sent_requests == []


def test_a_guarded_copy_does_not_count_as_a_failure(db, session):
    """A blocked copy must not feed the consecutive-failure breaker."""
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))

    copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'skipped'
    assert record['status'] != 'failed'


def test_a_guarded_copy_is_retried_once_the_limit_no_longer_applies(db, session):
    """The skipped row must not permanently suppress the position."""
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))
    payload = {'position_id': 'pos-1', 'volume': 0.1}

    first = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db, risk_settings=settings)
    session.positions.clear()
    second = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db, risk_settings=settings)

    assert first.status == 'skipped'
    assert second.status == 'copied'


# --- volume reconciliation --------------------------------------------------


def test_execute_copy_partially_closes_when_the_source_shrinks(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.3, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.3))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.status == 'copied'
    assert len(session.sent_requests) == 1
    request = session.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL
    assert 'Partially closed' in result.message


def test_execute_copy_scales_in_when_the_source_grows(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.1, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.2}, db_path=db
    )

    assert result.status == 'copied'
    request = session.sent_requests[0]
    assert 'position' not in request
    assert request['volume'] == 0.1
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert 'Scaled in' in result.message


def test_execute_copy_sends_nothing_when_the_source_size_is_unchanged(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.1, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is True
    assert session.sent_requests == []


def test_execute_copy_remembers_the_source_size_it_acted_on(db, session):
    copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.4}, db_path=db
    )

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.4


def test_execute_copy_reports_a_sizing_failure_on_an_existing_position(db, session):
    """A drift that cannot be sized is reported, and the open position stays recorded.

    The follower position is still open and still ours, so invalidating the row
    would only make reconciliation mistake it for an orphan.
    """
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.3, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.3))

    result = copy_service.execute_copy(
        _follower(),
        _relationship(volume_mode='risk_percent'),
        {'position_id': 'pos-1', 'volume': 0.1, 'price_open': 2300.0, 'sl': 0.0, 'source_equity': 10000.0},
        db_path=db,
    )

    assert result.status == 'failed'
    assert 'requires a source position with a stop loss' in result.message
    assert session.sent_requests == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'


def test_execute_copy_does_nothing_when_the_owned_position_is_gone(db, session):
    """Ownership resolving to nothing must not fall back to another position."""
    _seed_confirmed(db)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.9, 0, ''))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.5}, db_path=db
    )

    assert result.status == 'failed'
    assert session.sent_requests == []
    assert 'No owned follower position' in result.message
```

One precondition these tests rely on without stating it: `_follower()` from Phase 1 defaults to `connection_type='mt5_terminal'`. That is what routes `execute_copy` through the patched `use_account`, and therefore through the fake client's positions and account info. If that default is ever changed to `simulated`, the guard and resize tests in this step will stop exercising anything real and will report `status='copied'` from the simulated short-circuit instead. Leave the default alone.

- [ ] **Step 9: Run the service tests to verify they fail**

Run: `python -m pytest tests/python/test_local_copy_trading_copy_service.py -v`

Expected: FAIL on the guard and resize tests — `copy_service.execute_copy()` does not accept `risk_settings` yet, and `_sync_existing_position` does not exist.

- [ ] **Step 10: Rewrite the copy service**

Replace the whole of `python_service/app/local_copy_trading/copy_service.py` with the content below. `build_client_key`, `execute_close` and the two-phase write are carried over from Phase 1; the guard path and the resize path are new.

```python
"""Idempotent copy and close actions.

This is the layer that makes a copy action safe to retry. Before an order is
sent, the intent is written to SQLite keyed by ``<relationship>:<source
position>``. The key is unique, so a retry after a crash finds the existing row
instead of opening a second position.

``engine.process_tick`` talks to these functions and knows nothing about
persistence or connections.

Two things happen here that deliberately do not happen in the pure engine:

* Pre-trade guards read live follower state (margin level, open positions), so
  they need the connection that is about to place the order.
* Volume reconciliation needs the follower's *actual* position size, which is
  only knowable from the terminal.
"""

from __future__ import annotations

from pathlib import Path

from python_service.app.local_copy_trading import copy_trading_db, follower_executor, guards, volume_planner
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyResult,
    CopyTradingRiskSettings,
    FollowerAccount,
    SyncEvent,
)
from python_service.app.local_copy_trading.runtime import utc_now_iso
from python_service.app.services.mt5_session import Mt5SessionError, use_account


def build_client_key(relationship_id: str, source_position_id: str) -> str:
    """Identity of one source position copied through one relationship."""
    return f'{relationship_id}:{source_position_id}'


def _source_volume(source_position: dict) -> float:
    return float(source_position.get('volume') or 0)


def _guard_decision(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    *,
    planned_volume: float,
    settings: CopyTradingRiskSettings | None,
    daily_open_count: int,
    daily_realized_profit: float,
    consecutive_failures: int,
):
    """Evaluate the configured limits against live follower state."""
    if settings is None:
        return guards.GuardDecision(True)

    account_info = None
    positions: list[dict] = []
    if client is not None:
        raw_account_info = client.account_info()
        if raw_account_info is not None:
            account_info = follower_executor.as_dict(raw_account_info)
        positions = follower_executor.list_positions(client)

    return guards.evaluate_open_guard(
        relationship,
        planned_volume=planned_volume,
        follower_account_info=account_info,
        follower_positions=positions,
        settings=settings,
        daily_open_count=daily_open_count,
        daily_realized_profit=daily_realized_profit,
        consecutive_failures=consecutive_failures,
    )


def _sync_existing_position(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    client_key: str,
    existing: dict,
    db_path: Path | str,
) -> CopyResult:
    """Bring an already-copied follower position in line with the source size.

    The source ticket survives a partial close and a scale in, so reaching this
    branch means the position is still open but may no longer be the right size.

    The size is re-planned rather than taken from the source volume directly,
    because the relationship's own mode and cap still apply: a source that
    doubles must not bypass ``max_lot``.

    A sizing failure leaves the row ``confirmed``. The follower position is still
    open and still ours, so invalidating the row would only make reconciliation
    mistake it for an orphan.
    """
    follower_position_id = existing['follower_position_ticket'] or ''
    follower_order_id = existing['follower_order_id'] or ''
    if client is None:
        return CopyResult(
            True,
            'copied',
            f"Already copied as follower position {follower_position_id or follower_order_id}",
            follower_position_id,
            follower_order_id,
        )

    symbol = relationship.follower_symbol
    try:
        if not client.symbol_select(symbol, True):
            return CopyResult(
                False,
                'failed',
                f'Failed to select follower symbol {symbol}. Error: {client.last_error()}',
                follower_position_id,
                follower_order_id,
            )
        symbol_info = client.symbol_info(symbol)
        if symbol_info is None:
            return CopyResult(
                False,
                'failed',
                f'Missing symbol info for follower symbol {symbol}. Error: {client.last_error()}',
                follower_position_id,
                follower_order_id,
            )

        follower_equity = None
        if relationship.volume_mode == 'equity_ratio':
            account_info = client.account_info()
            if account_info is not None:
                follower_equity = float(getattr(account_info, 'equity', 0) or 0)

        expected_volume = volume_planner.plan_volume(
            relationship,
            source_position,
            symbol_info=symbol_info,
            source_equity=source_position.get('source_equity'),
            follower_equity=follower_equity,
        )
    except ValueError as error:
        return CopyResult(False, 'failed', str(error), follower_position_id, follower_order_id)

    success, message = follower_executor.adjust_copied_position_volume(
        client,
        follower,
        relationship,
        source_position,
        expected_volume=expected_volume,
    )

    copy_trading_db.record_source_volume(
        client_key,
        source_volume=_source_volume(source_position),
        updated_at=utc_now_iso(),
        db_path=db_path,
    )
    if success:
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket=follower_position_id,
            follower_order_id=follower_order_id,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        return CopyResult(True, 'copied', message, follower_position_id, follower_order_id)

    copy_trading_db.mark_failed(
        client_key,
        message=message,
        updated_at=utc_now_iso(),
        db_path=db_path,
    )
    return CopyResult(False, 'failed', message, follower_position_id, follower_order_id)


def execute_copy(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    db_path: Path | str = copy_trading_db.DEFAULT_DB_PATH,
    risk_settings: CopyTradingRiskSettings | None = None,
    daily_open_count: int = 0,
    daily_realized_profit: float = 0.0,
    consecutive_failures: int = 0,
) -> CopyResult:
    """Copy one source position, at most once, ever.

    Passing ``risk_settings`` enables the pre-trade guards; leaving it as None
    keeps the previous behaviour of sending the order unconditionally.
    """
    source_position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not source_position_id:
        return CopyResult(False, 'failed', 'Source position has no identifier')

    client_key = build_client_key(relationship.id, source_position_id)
    existing = copy_trading_db.find_by_client_key(client_key, db_path=db_path)
    open_existing = existing is not None and existing['status'] == 'confirmed'

    # A confirmed row that still matches the source size is already done, and
    # this check sits before any database write or connection, so an unchanged
    # position costs nothing. A confirmed row whose source size moved needs the
    # follower adjusted, and that only makes sense with a live connection.
    if open_existing and float(existing['source_volume'] or 0) == _source_volume(source_position):
        return CopyResult(
            True,
            'copied',
            f"Already copied as follower position {existing['follower_position_ticket'] or existing['follower_order_id']}",
            existing['follower_position_ticket'] or '',
            existing['follower_order_id'] or '',
        )

    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id=relationship.id,
        source_account_id=relationship.source_account_id,
        follower_account_id=relationship.follower_account_id,
        source_position_id=source_position_id,
        created_at=utc_now_iso(),
        db_path=db_path,
    )

    if follower.connection_type != 'mt5_terminal':
        if open_existing:
            return _sync_existing_position(
                None,
                follower,
                relationship,
                source_position,
                client_key=client_key,
                existing=existing,
                db_path=db_path,
            )
        result = follower_executor.copy_position_to_follower(None, follower, relationship, source_position)
        return _settle(client_key, result, source_position, db_path)

    try:
        with use_account(
            follower.terminal_path,
            follower.login,
            follower.password,
            follower.server,
        ) as client:
            if open_existing:
                return _sync_existing_position(
                    client,
                    follower,
                    relationship,
                    source_position,
                    client_key=client_key,
                    existing=existing,
                    db_path=db_path,
                )

            return _place_order(
                client,
                follower,
                relationship,
                source_position,
                client_key=client_key,
                db_path=db_path,
                risk_settings=risk_settings,
                daily_open_count=daily_open_count,
                daily_realized_profit=daily_realized_profit,
                consecutive_failures=consecutive_failures,
            )
    except Mt5SessionError as error:
        copy_trading_db.mark_failed(
            client_key,
            message=str(error),
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        return CopyResult(False, 'failed', str(error))


def _place_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    client_key: str,
    db_path: Path | str,
    risk_settings: CopyTradingRiskSettings | None,
    daily_open_count: int,
    daily_realized_profit: float,
    consecutive_failures: int,
) -> CopyResult:
    """Place a new follower order, guarding it when limits are configured.

    Without settings there is nothing to decide, so the executor's combined call
    is used directly and nothing reaches the broker later than before. With
    settings the order is planned first, because every limit is expressed in
    terms of the size being placed.
    """
    if risk_settings is None:
        result = follower_executor.copy_position_to_follower(client, follower, relationship, source_position)
        return _settle(client_key, result, source_position, db_path)

    plan = follower_executor.plan_copy_order(client, follower, relationship, source_position)
    if plan.short_circuit is None and plan.ok:
        decision = _guard_decision(
            client,
            follower,
            relationship,
            planned_volume=plan.volume,
            settings=risk_settings,
            daily_open_count=daily_open_count,
            daily_realized_profit=daily_realized_profit,
            consecutive_failures=consecutive_failures,
        )
        if not decision.allowed:
            copy_trading_db.mark_skipped(
                client_key,
                message=decision.message,
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            return CopyResult(False, 'skipped', decision.message)

    result = follower_executor.send_copy_order(client, follower, relationship, plan, source_position)
    return _settle(client_key, result, source_position, db_path)


def _settle(
    client_key: str,
    result: tuple,
    source_position: dict,
    db_path: Path | str,
) -> CopyResult:
    """Write the order-map row to match an executor result."""
    success, message, follower_position_id, follower_order_id = result

    if success:
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket=follower_position_id,
            follower_order_id=follower_order_id,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        copy_trading_db.record_source_volume(
            client_key,
            source_volume=_source_volume(source_position),
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
    else:
        copy_trading_db.mark_failed(
            client_key,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )

    return CopyResult(
        bool(success),
        'copied' if success else 'failed',
        message,
        follower_position_id,
        follower_order_id,
    )


def execute_close(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
    *,
    db_path: Path | str = copy_trading_db.DEFAULT_DB_PATH,
) -> tuple[bool, str]:
    """Close a copied follower position and settle its order-map row."""
    if follower.connection_type == 'mt5_terminal':
        try:
            with use_account(
                follower.terminal_path,
                follower.login,
                follower.password,
                follower.server,
            ) as client:
                success, message = follower_executor.close_copied_position_on_follower(
                    client, follower, relationship, copied_event
                )
        except Mt5SessionError as error:
            success, message = False, str(error)
    else:
        success, message = follower_executor.close_copied_position_on_follower(
            None, follower, relationship, copied_event
        )

    if success:
        copy_trading_db.mark_closed(
            build_client_key(relationship.id, copied_event.position_id),
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
    return success, message
```

- [ ] **Step 11: Run the service tests**

Run: `python -m pytest tests/python/test_local_copy_trading_copy_service.py -v`

Expected: `19 passed`

- [ ] **Step 12: Propagate the status through the engine**

In `python_service/app/local_copy_trading/engine.py`, change the import block to:

```python
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyResult,
    FollowerAccount,
    LocalCopyTradingState,
    SyncEvent,
)
```

and replace `_copy_result_parts` with:

```python
def _copy_result_parts(result: CopyResult | tuple) -> tuple[bool, str, str, str, str]:
    """Normalise an executor result into ``(success, message, position, order, status)``.

    Both the structured ``CopyResult`` and the legacy plain tuples are accepted
    so a custom executor can stay a two-line lambda.
    """
    if isinstance(result, CopyResult):
        return result.success, result.message, result.follower_position_id, result.follower_order_id, result.status

    is_success = bool(result[0])
    message = str(result[1] if len(result) > 1 else '')
    follower_position_id = str(result[2] if len(result) > 2 else '')
    follower_order_id = str(result[3] if len(result) > 3 else '')
    status = str(result[4]) if len(result) > 4 else ('copied' if is_success else 'failed')
    return is_success, message, follower_position_id, follower_order_id, status
```

Then, in the copy loop, replace the unpacking and the event construction with:

```python
        is_copied, message, follower_position_id, follower_order_id, status = _copy_result_parts(
            copy_executor(follower, relationship, position)
        )
        event = SyncEvent(
            relationship_id=relationship.id,
            source_account_id=relationship.source_account_id,
            follower_account_id=relationship.follower_account_id,
            position_id=position_id,
            follower_position_id=follower_position_id,
            follower_order_id=follower_order_id,
            symbol=relationship.follower_symbol,
            status=status if status in {'copied', 'failed', 'skipped'} else ('copied' if is_copied else 'failed'),
            message=message,
            created_at=utc_now_iso(),
        )
```

- [ ] **Step 13: Add the engine test for the skipped status**

Append to `tests/python/test_local_copy_trading_engine.py`:

```python
def test_engine_records_a_guard_skip_as_its_own_status():
    from python_service.app.local_copy_trading.models import CopyResult

    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')
        ],
    )

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
        execute_copy=lambda follower, relationship, position: CopyResult(False, 'skipped', 'limit reached'),
    )

    assert len(events) == 1
    assert events[0].status == 'skipped'
    assert events[0].message == 'limit reached'
```

- [ ] **Step 14: Run the engine tests**

Run: `python -m pytest tests/python/test_local_copy_trading_engine.py -v`

Expected: `11 passed`

- [ ] **Step 15: Run the whole copy-trading suite**

Run the twelve-file command from "Why the aggregate uses an explicit file list".

Expected: `142 passed`. Task 6 adds the remaining four.

- [ ] **Step 16: Commit**

```bash
git add python_service/app/local_copy_trading/models.py python_service/app/local_copy_trading/copy_trading_db.py python_service/app/local_copy_trading/copy_service.py python_service/app/local_copy_trading/engine.py tests/python/test_copy_trading_db.py tests/python/test_local_copy_trading_copy_service.py tests/python/test_local_copy_trading_engine.py
git commit -m "feat(copy-trading): guard copy orders and track the source size"
```

---

### Task 6: Route drifted positions to the resize path

**Files:**
- Modify: `python_service/app/local_copy_trading/engine.py`
- Modify: `python_service/app/local_copy_trading/loop.py`
- Test: `tests/python/test_local_copy_trading_engine.py`

Task 5 built the resize capability and the recorded size but left the engine short-circuiting every already-copied position. This task connects the two: the engine compares the live source size against the recorded one and hands drifted positions to the copy executor, which replans and resizes.

- [ ] **Step 1: Append the failing engine tests**

Append to the end of `tests/python/test_local_copy_trading_engine.py`:

```python
def _copied_state() -> LocalCopyTradingState:
    """A state that has already copied pos-1 once."""
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')
        ],
    )
    process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
    )
    return state


def test_engine_leaves_a_copied_position_alone_without_a_volume_reader():
    """Without a reader the engine cannot prove drift, so it must not guess."""
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.5}],
    )

    assert events == []


def test_engine_leaves_a_copied_position_alone_when_the_source_size_is_unchanged():
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
        recorded_volume=lambda relationship_id, position_id: 0.1,
    )

    assert events == []


def test_engine_resends_a_copied_position_when_the_source_size_moves():
    state = _copied_state()
    seen = []

    def fake_copy(follower, relationship, position):
        seen.append(position['volume'])
        return True, 'Resized', '789', '456'

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.4}],
        execute_copy=fake_copy,
        recorded_volume=lambda relationship_id, position_id: 0.1,
    )

    assert seen == [0.4]
    assert len(events) == 1


def test_engine_ignores_a_copied_position_with_no_recorded_volume():
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.4}],
        recorded_volume=lambda relationship_id, position_id: None,
    )

    assert events == []
```

The first of these passes before this task's implementation too, because the old short-circuit also produces no events. It is written anyway so that removing the reader later cannot silently reintroduce a resize-on-a-guess.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/python/test_local_copy_trading_engine.py -v`

Expected: 3 FAIL — `TypeError: process_tick() got an unexpected keyword argument 'recorded_volume'` — and `test_engine_resends_a_copied_position_when_the_source_size_moves` fails on `assert seen == [0.4]`. `test_engine_leaves_a_copied_position_alone_without_a_volume_reader` passes.

- [ ] **Step 3: Compare the source size in the engine**

In `python_service/app/local_copy_trading/engine.py`, add below the `CloseExecutor` alias:

```python
VolumeReader = Callable[[str, str], float | None]

# Source sizes reported by a broker are exact lot values, so only a genuine
# change should trigger an adjustment rather than float noise.
VOLUME_EPSILON = 1e-9
```

Then add this function immediately before `def process_tick`:

```python
def _needs_volume_sync(
    state: LocalCopyTradingState,
    relationship: CopyRelationship,
    position: dict,
    *,
    position_id: str,
    recorded_volume: VolumeReader | None,
) -> bool:
    """Decide whether a source position should be handed to the copy executor.

    A position that has never been copied always is. A position that already has
    a follower counterpart is only re-sent when its source size moved, and only
    when a reader can tell us what size we last matched. Without a reader the
    engine cannot tell, and the safe default is to leave the existing position
    alone rather than resize it on a guess.
    """
    already_copied = has_copied_position(
        state,
        relationship_id=relationship.id,
        source_account_id=relationship.source_account_id,
        follower_account_id=relationship.follower_account_id,
        position_id=position_id,
    )
    if not already_copied:
        return True

    if recorded_volume is None:
        return False

    recorded = recorded_volume(relationship.id, position_id)
    if recorded is None or recorded <= 0:
        return False

    current = float(position.get('volume') or 0)
    return abs(float(recorded) - current) > VOLUME_EPSILON
```

Change the `process_tick` signature to accept the reader:

```python
def process_tick(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    execute_copy: CopyExecutor | None = None,
    execute_close: CloseExecutor | None = None,
    recorded_volume: VolumeReader | None = None,
) -> list[SyncEvent]:
```

and replace the dedupe gate inside the relationship loop:

```python
            position_id = str(position.get('position_id') or position.get('ticket') or '')
            if not position_id:
                continue
            if not _needs_volume_sync(
                state,
                relationship,
                position,
                position_id=position_id,
                recorded_volume=recorded_volume,
            ):
                continue
            pending_copies.append((follower.id, relationship, position))
```

- [ ] **Step 4: Run the engine tests**

Run: `python -m pytest tests/python/test_local_copy_trading_engine.py -v`

Expected: `15 passed`

- [ ] **Step 5: Wire the loop**

In `python_service/app/local_copy_trading/loop.py`, pass the reader into the tick:

```python
                    process_tick(
                        state,
                        source_positions,
                        execute_copy=copy_service.execute_copy,
                        execute_close=copy_service.execute_close,
                        recorded_volume=copy_trading_db.get_recorded_volume,
                    )
```

- [ ] **Step 6: Run the whole copy-trading suite**

Run the twelve-file command from "Why the aggregate uses an explicit file list".

Expected: `146 passed` — the complete count for this plan. If a count is off, use the per-file table under "Test counts" to find the drift.

- [ ] **Step 7: Run the full Python suite**

Run: `python -m pytest tests/python -q`

Expected: no failures. Any failure in `test_mt5.py`, `test_mt5_polling.py` or `test_order_sync_service.py` means the session or settings change leaked into another feature — investigate before committing.

- [ ] **Step 8: Confirm nothing sends an order before a guard when guards are on**

Run:

```bash
python -m pytest tests/python/test_local_copy_trading_copy_service.py -q -k "guard or skip"
```

Expected: `6 passed`. These are the tests that would fail if `_place_order` sent before consulting the guard.

- [ ] **Step 9: Commit**

```bash
git add python_service/app/local_copy_trading/engine.py python_service/app/local_copy_trading/loop.py tests/python/test_local_copy_trading_engine.py
git commit -m "feat(copy-trading): follow source partial closes and scale-ins"
```

---

## Definition of done

Phase 2 is complete when all of the following hold:

1. A relationship set to `fixed` copies the configured size regardless of the source volume, and `max_lot` caps it.
2. A relationship set to `equity_ratio` sizes by the ratio of the two accounts' equity, and is reported as a failed copy — not a guessed one — when the follower's equity cannot be read.
3. A relationship set to `risk_percent` sizes from the source stop distance, and a source position with no stop loss is reported as failed rather than sized.
4. With `sync_sl_tp` on, a short position's take profit lands **below** the follower's entry, and a long position's lands above it.
5. With risk settings configured, a copy that breaches a limit sends no order, produces a `skipped` event, and does **not** increment the consecutive-failure count; it is retried once the limit no longer applies.
6. With risk settings configured, a copy that breaches nothing sends exactly one order.
7. A source partial close reduces the follower's position by the difference and sends no new position.
8. A source scale-in increases the follower's position by the difference.
9. A tick whose source size is unchanged sends no order for an already-copied position.
10. A database created before this change is upgraded in place on `init_db` without losing its rows.
11. `python -m pytest tests/python` passes.

## Notes for the implementer

- **Do not delete `copy_position_to_follower`.** It is the compatibility wrapper over plan-then-send, and both Phase 1's tests and the no-settings branch of `_place_order` depend on it. The same goes for `_copy_result_parts`' tolerance of plain tuples.
- **Do not derive the protective level side from the trade direction.** `translate_protective_levels` decides from `level < source_entry` on purpose. A direction-based implementation looks right in a long-only test and silently inverts take profit on every short.
- **Do not treat a guard block as a failure.** Marking it `failed` would feed `max_consecutive_failures` and permanently disable a relationship that merely hit a position cap, and it would make reconciliation report the position as an orphan candidate.
- **Do not resend an already-copied position without a recorded volume.** A resize is a real order on a real account; "I could not tell" must mean "do nothing".
- **A sizing failure on an already-open position leaves the row `confirmed`.** The position is still open and still ours. Marking the row `failed` would make reconciliation mistake it for an orphan.
- **`storage/copy-trading-risk.json` is new optional app state.** Like `storage/alerts.json`, it is runtime config and not source. Do not add it to the packaging `extraResources` list; `load_risk_settings` returns defaults when it is absent, which is the intended unconfigured state.
- **`storage/local_copy_trading.db` gains a column, not a new file.** The in-place upgrade in `init_db` is what protects an existing install. Do not replace it with a version-stamped migration framework for one column.
- **`max_lot` of 0 means "no cap", not "no volume".** Same convention as every guard field: 0 disables the rule. A relationship that must never trade a lot size should use `fixed` mode with an explicit `lot_multiplier` and `max_lot`.
- **Task 5's resize branch is intentionally naive and Task 6 replaces it.** If you stop after Task 5, an already-copied position resizes to the source's raw volume, which is only correct for `multiplier` mode. Do not ship Task 5 without Task 6.
- **`daily_open_count`, `daily_realized_profit` and `consecutive_failures` are parameters, not state.** This plan threads them through `execute_copy` but does not compute them, because the daily aggregates live outside the copy-trading package and the caller (`loop.py`) has not been taught to gather them. They default to 0, which combined with the default settings means those three rules never fire today. Wiring them to real counters is follow-up work, not a Phase 2 deliverable.
