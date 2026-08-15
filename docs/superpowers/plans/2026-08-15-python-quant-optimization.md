# Python Quant Strategy Engine & Workflow Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Python Quant module into a powerful, multi-strategy quantitative trading and automation engine featuring 5 new classic institutional-grade quantitative strategies (RSI Reversal, MACD Trend, Bollinger Breakout, Dual Thrust, Turtle Donchian), custom Python strategy code viewing/creation, on-demand signal diagnostics, and batch job management cockpit.

**Architecture:**
- **Quant Strategies (`python_service/app/quant/strategies/`)**: 5 new standardized Backtrader strategies with full multi-timeframe parameter support.
- **REST Endpoints (`routes.py`)**: Strategy source code reading (`GET /strategies/{id}/code`), custom user strategy creation (`POST /strategies/custom`), and instant signal evaluation (`POST /jobs/{id}/evaluate`).
- **Store (`python-quant-store.ts`)**: Expanded state for strategy code inspection, custom strategy creation, and job evaluation actions.
- **UI (`PythonQuantPage.tsx`)**: Real-time quant metric cockpit, strategy source code viewer modal with boilerplate templates, job filters, and one-click backtest jump.

**Tech Stack:** React 18, Zustand, Backtrader, Pandas, FastAPI, Vitest, Pytest.

---

## File Structure & Proposed Changes

| Action | Path | Description |
| :--- | :--- | :--- |
| **[NEW]** | `python_service/app/quant/strategies/rsi_reversal.py` | Built-in RSI(14) dynamic mean reversion strategy |
| **[NEW]** | `python_service/app/quant/strategies/macd_trend.py` | Built-in MACD(12, 26, 9) trend following & signal cross strategy |
| **[NEW]** | `python_service/app/quant/strategies/bollinger_breakout.py` | Built-in Bollinger Bands(20, 2) volatility channel breakout strategy |
| **[NEW]** | `python_service/app/quant/strategies/dual_thrust.py` | Built-in Dual Thrust classic intraday range breakout strategy |
| **[NEW]** | `python_service/app/quant/strategies/turtle_donchian.py` | Built-in Turtle Donchian(20) channel trend breakout strategy |
| **[NEW]** | `tests/python/test_quant_strategies_execution.py` | Pytest suite validating signal generation for all built-in strategies |
| **[MODIFY]** | `python_service/app/quant/routes.py` | Endpoints for strategy source code, custom strategy saving, and job manual evaluation |
| **[MODIFY]** | `tests/python/test_quant_routes.py` | Pytest tests for strategy code inspection and manual evaluation routes |
| **[MODIFY]** | `src/renderer/src/lib/python-quant.ts` | Types and API clients for strategy code, custom strategy, and evaluate actions |
| **[MODIFY]** | `src/renderer/src/stores/python-quant-store.ts` | Store actions for strategy code inspection and custom strategy creation |
| **[MODIFY]** | `src/renderer/src/test/python-quant-store.test.ts` | Unit tests for python quant store actions |
| **[MODIFY]** | `src/renderer/src/pages/PythonQuantPage.tsx` | Cockpit metrics, strategy code viewer dialog, custom strategy creator, evaluate button |
| **[MODIFY]** | `src/renderer/src/i18n/messages.ts` | Dual-language translations for quant strategies and cockpit features |
| **[MODIFY]** | `src/renderer/src/test/python-quant-page.test.tsx` | Component tests for quant page enhancements |
| **[MODIFY]** | `GUIDE.md` | Update repository tree with new strategy and test files |

---

## Bite-Sized Implementation Tasks

### Task 1: Built-in Professional Quant Strategy Arsenal

**Files:**
- Create: `python_service/app/quant/strategies/rsi_reversal.py`
- Create: `python_service/app/quant/strategies/macd_trend.py`
- Create: `python_service/app/quant/strategies/bollinger_breakout.py`
- Create: `python_service/app/quant/strategies/dual_thrust.py`
- Create: `python_service/app/quant/strategies/turtle_donchian.py`
- Create: `tests/python/test_quant_strategies_execution.py`

- [x] **Step 1: Write pytest test file `test_quant_strategies_execution.py`**
- [x] **Step 2: Run pytest to observe failures**
- [x] **Step 3: Implement the 5 built-in quantitative strategies**
- [x] **Step 4: Run pytest to verify all strategies pass**

---

### Task 2: Strategy Source Code Inspection & Custom Strategy Backend Routes

**Files:**
- Modify: `python_service/app/quant/routes.py`
- Modify: `tests/python/test_quant_routes.py`

- [x] **Step 1: Write route tests in `tests/python/test_quant_routes.py`**
- [x] **Step 2: Implement route handlers in `python_service/app/quant/routes.py`**
- [x] **Step 3: Run pytest to verify routes pass**

---

### Task 3: Frontend Python Quant Store & Types

**Files:**
- Modify: `src/renderer/src/lib/python-quant.ts`
- Modify: `src/renderer/src/stores/python-quant-store.ts`
- Modify: `src/renderer/src/test/python-quant-store.test.ts`

- [x] **Step 1: Write store unit tests in `python-quant-store.test.ts`**
- [x] **Step 2: Update `python-quant.ts` and `python-quant-store.ts`**
- [x] **Step 3: Run vitest to verify store tests pass**

---

### Task 4: UI Cockpit & Code Viewer in `PythonQuantPage.tsx`

**Files:**
- Modify: `src/renderer/src/i18n/messages.ts`
- Modify: `src/renderer/src/pages/PythonQuantPage.tsx`
- Modify: `src/renderer/src/test/python-quant-page.test.tsx`

- [x] **Step 1: Add i18n translation keys**
- [x] **Step 2: Overhaul `PythonQuantPage.tsx`**
- [x] **Step 3: Run vitest for `python-quant-page.test.tsx`**

---

### Task 5: Full Regression Testing & Architecture Sync

**Files:**
- Modify: `GUIDE.md`
- Verify: `npm run test:frontend`
- Verify: `pytest tests/python`
- Verify: `npm run build`

- [x] **Step 1: Update `GUIDE.md` directory tree**
- [x] **Step 2: Run `python .agents/skills/project-guide/scripts/check_guide_tree.py`**
- [x] **Step 3: Run full frontend test suite `npm run test:frontend`**
- [x] **Step 4: Run full Python backend test suite `pytest tests/python`**
- [x] **Step 5: Run production build `npm run build`**
