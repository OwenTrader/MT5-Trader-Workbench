# Python Quant Beta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Python Quant from an internal MVP into a safer beta workflow with paper/live execution separation, clearer backtest positioning, runtime observability, and a unified quant information architecture.

**Architecture:** Keep the existing FastAPI + React/Zustand structure. Add small, testable fields and endpoints first, then improve page flow without rewriting the current quant runtime.

**Tech Stack:** Electron, React, shadcn/ui, Zustand, FastAPI, Pydantic, Backtrader, SQLite, Vitest, pytest.

---

## File Map

- `python_service/app/quant/models.py`: Add job execution mode and future-safe status literals.
- `python_service/app/quant/routes.py`: Accept and validate execution mode in create/update payloads.
- `python_service/app/quant/runtime.py`: Persist execution mode, skip real MT5 execution for paper jobs, and preserve status transitions.
- `python_service/app/quant/mt5_execution.py`: Keep real execution isolated behind the runtime decision.
- `tests/python/test_quant_models.py`: Cover defaults and validation for execution mode.
- `tests/python/test_quant_routes.py`: Cover create/update/start behavior with paper/live jobs.
- `tests/python/test_quant_runtime.py`: Cover that paper jobs record signals but do not call MT5 execution.
- `src/renderer/src/lib/python-quant.ts`: Add frontend types/parsing for execution mode.
- `src/renderer/src/stores/python-quant-store.ts`: No structural change expected unless API payloads need mapping.
- `src/renderer/src/pages/PythonQuantPage.tsx`: Add execution mode selection and live-start confirmation.
- `src/renderer/src/pages/QuantBacktestPage.tsx`: Add signal-replay disclaimer and reduce overclaiming.
- `src/renderer/src/test/python-quant-page.test.tsx`: Cover execution mode UI and live confirmation.
- `src/renderer/src/test/quant-backtest-page.test.tsx`: Cover disclaimer copy.
- Later tasks may add `python_service/app/quant/event_log.py`, `tests/python/test_quant_event_log.py`, and frontend log/data tabs.

## Task 1: Execution Safety Baseline

**Outcome:** New jobs default to paper mode. Live jobs require an explicit frontend confirmation before starting. Paper jobs evaluate strategies and update status but never place MT5 orders.

**Files:**
- Modify: `python_service/app/quant/models.py`
- Modify: `python_service/app/quant/routes.py`
- Modify: `python_service/app/quant/runtime.py`
- Modify: `src/renderer/src/lib/python-quant.ts`
- Modify: `src/renderer/src/pages/PythonQuantPage.tsx`
- Test: `tests/python/test_quant_models.py`
- Test: `tests/python/test_quant_routes.py`
- Test: `tests/python/test_quant_runtime.py`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] Step 1: Add failing Python tests for execution mode default and paper-mode no-order behavior.
- [ ] Step 2: Add `execution_mode: 'paper' | 'live'` to `QuantJob`, defaulting to `paper`.
- [ ] Step 3: Extend create/update request models to accept `execution_mode`.
- [ ] Step 4: Update runtime to call `execute_signal` only when `job.execution_mode == 'live'`.
- [ ] Step 5: Add frontend type parsing and create/edit form field for execution mode.
- [ ] Step 6: Add live-start confirmation in `PythonQuantPage` before calling `/start`.
- [ ] Step 7: Run `pytest tests/python/test_quant_models.py tests/python/test_quant_routes.py tests/python/test_quant_runtime.py`.
- [ ] Step 8: Run `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx`.

## Task 2: Backtest Positioning And Trust Boundary

**Outcome:** Backtest page clearly communicates current limitations and avoids presenting signal replay as production-grade PnL analytics.

**Files:**
- Modify: `src/renderer/src/pages/QuantBacktestPage.tsx`
- Modify: `src/renderer/src/test/quant-backtest-page.test.tsx`
- Optionally modify: `README.zh-CN.md`, `README.md`

- [ ] Step 1: Add failing frontend test that expects a visible disclaimer about cached data, no fees/slippage/spread, and signal-replay limitations.
- [ ] Step 2: Add a visible shadcn-style callout or existing card copy near the run form.
- [ ] Step 3: Rename or annotate summary cards so `Total Return` is framed as simplified replay return.
- [ ] Step 4: Run `npm run test:frontend -- src/renderer/src/test/quant-backtest-page.test.tsx`.

## Task 3: Runtime Monitoring And Audit Log

**Outcome:** Users can answer whether a job ran recently, what signal was produced, and why execution failed.

**Files:**
- Create: `python_service/app/quant/event_log.py`
- Modify: `python_service/app/quant/models.py`
- Modify: `python_service/app/quant/runtime.py`
- Modify: `python_service/app/quant/routes.py`
- Modify: `src/renderer/src/lib/python-quant.ts`
- Modify: `src/renderer/src/pages/PythonQuantPage.tsx`
- Test: `tests/python/test_quant_event_log.py`
- Test: `tests/python/test_quant_routes.py`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] Step 1: Add failing tests for `signal_generated`, `order_skipped_paper`, `order_sent`, `order_failed`, and `strategy_error` log entries.
- [ ] Step 2: Add append-only JSON or SQLite event storage under `storage/python_quant`.
- [ ] Step 3: Record events during `run_job_once` and error handling.
- [ ] Step 4: Add `/python-quant/jobs/{job_id}/events` route.
- [ ] Step 5: Show recent events in the job table or an expandable job detail area.
- [ ] Step 6: Run `pytest tests/python` and targeted frontend tests.

## Task 4: Data Health Surface

**Outcome:** Users can see whether cached market data is current before running live or backtest workflows.

**Files:**
- Modify: `python_service/app/quant/market_data.py`
- Modify: `python_service/app/quant/routes.py`
- Modify: `src/renderer/src/lib/python-quant.ts`
- Modify: `src/renderer/src/pages/PythonQuantPage.tsx`
- Test: `tests/python/test_quant_market_data.py`
- Test: `tests/python/test_quant_routes.py`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] Step 1: Add backend function to return latest cached bar time and stale/fresh state for account/symbol/timeframe.
- [ ] Step 2: Add route to expose data health for current job inputs.
- [ ] Step 3: Show latest cached bar and freshness in create-job/backfill area and job rows.
- [ ] Step 4: Run Python and frontend targeted tests.

## Task 5: Quant Module Information Architecture

**Outcome:** Product navigation starts moving from two isolated menu items toward one Quant workflow.

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx`
- Modify: `src/renderer/src/App.tsx`
- Create or modify: `src/renderer/src/pages/QuantPage.tsx`
- Test: `src/renderer/src/test/python-quant-page.test.tsx`
- Test: `src/renderer/src/test/quant-backtest-page.test.tsx`

- [ ] Step 1: Add failing test for a unified Quant entry with Live Jobs and Backtest sections.
- [ ] Step 2: Add `QuantPage` wrapper with tabs or section navigation using existing shadcn components.
- [ ] Step 3: Preserve direct routes to `python-quant` and `quant-backtest` during transition if needed.
- [ ] Step 4: Run relevant frontend tests.

## Task 6: Strategy Management Foundation

**Outcome:** Users can understand strategy availability and loading failures instead of guessing from missing menu options.

**Files:**
- Modify: `python_service/app/quant/strategy_registry.py`
- Modify: `python_service/app/quant/routes.py`
- Modify: `src/renderer/src/lib/python-quant.ts`
- Create or modify: strategy section in `QuantPage` or `PythonQuantPage`
- Test: `tests/python/test_quant_strategy_registry.py`
- Test: frontend quant page tests

- [ ] Step 1: Add tests for invalid user strategy diagnostics.
- [ ] Step 2: Return skipped strategy errors in a safe diagnostics payload.
- [ ] Step 3: Display invalid strategy diagnostics in the strategy list area.
- [ ] Step 4: Run targeted tests.

## Verification Commands

- Python quant changes: `pytest tests/python`
- Renderer quant changes: `npm run test:frontend -- src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/quant-backtest-page.test.tsx`
- Full app build when navigation changes: `npm run build`

## Sequencing Rule

Implement Task 1 before any other work. Task 1 reduces live-trading risk and creates the safety vocabulary the later tasks depend on.
