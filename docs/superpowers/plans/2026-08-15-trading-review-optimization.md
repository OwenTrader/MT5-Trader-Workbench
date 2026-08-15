# Trading Review & Market Replay Simulator Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Trading Review (复盘) module into a professional-grade market replay simulator modeled after TradingView Bar Replay & Forex Tester 5, featuring automatic SL/TP execution, accurate multi-asset contract size calculations, keyboard hotkeys, chart indicator overlays (EMA / Volume), and live performance statistics (Win Rate, Profit Factor, Max Drawdown, Equity Curve).

**Architecture:** 
- Backend (`kline_db.py`, `trading_review.py`): Support Stop Loss (SL) & Take Profit (TP) fields, automated price-hit detection during candle stepping, and accurate asset-specific contract size math (Forex, Gold, Crypto, Indices).
- Store (`trading-review-store.ts`): Expanded state for SL/TP orders, performance metrics, and replay controls.
- Chart (`trading-chart.tsx`): Volume sub-series, EMA 20/50 overlays, and visual SL/TP price lines with entry markers.
- UI (`TradingReviewPage.tsx`): Keyboard shortcuts, professional order execution panel with Risk:Reward preview, dynamic analytics card with equity curve, and local cached data selector.

**Tech Stack:** React 18, Lightweight Charts, Zustand, TailwindCSS, FastAPI, SQLite, Vitest, Pytest.

---

## File Structure & Proposed Changes

| Action | Path | Description |
| :--- | :--- | :--- |
| **[MODIFY]** | `python_service/app/db/kline_db.py` | Add `sl`, `tp` columns to `review_trades`, update queries, support SL/TP auto-triggers |
| **[MODIFY]** | `python_service/app/routes/trading_review.py` | Multi-asset contract size profit formula, SL/TP trigger evaluation during candle advance |
| **[NEW]** | `tests/python/test_trading_review.py` | Pytest suite for review session creation, candle advance, and SL/TP auto-triggering |
| **[MODIFY]** | `src/renderer/src/stores/trading-review-store.ts` | SL/TP parameters, auto-close notifications, performance metrics calculations |
| **[NEW]** | `src/renderer/src/test/trading-review-store.test.ts` | Unit tests for review store state and trade operations |
| **[MODIFY]** | `src/renderer/src/components/trading-chart.tsx` | Volume histogram, EMA 20/50 indicators, SL/TP visual price lines |
| **[MODIFY]** | `src/renderer/src/pages/TradingReviewPage.tsx` | Order panel with SL/TP, hotkeys (`Space`, `ArrowRight`, `B`, `S`), performance analytics card |
| **[MODIFY]** | `src/renderer/src/i18n/messages.ts` | Dual language translation keys for review simulator enhancements |
| **[NEW]** | `src/renderer/src/test/trading-review-page.test.tsx` | Frontend component tests for review workspace and session list |
| **[MODIFY]** | `GUIDE.md` | Update repository architecture tree |

---

## Bite-Sized Implementation Tasks

### Task 1: Backend Contract Size, SL/TP Engine & Database Schema

**Files:**
- Modify: `python_service/app/db/kline_db.py`
- Modify: `python_service/app/routes/trading_review.py`
- Create: `tests/python/test_trading_review.py`

- [ ] **Step 1: Write backend tests for Trading Review session, trades, and SL/TP triggers**
  Create `tests/python/test_trading_review.py` testing session creation, order placement with SL/TP, stepping candles, and auto-execution when High/Low hits SL/TP.
- [ ] **Step 2: Run pytest to verify initial failure**
  Run: `pytest tests/python/test_trading_review.py -v`
  Expected: FAIL
- [ ] **Step 3: Update `kline_db.py` schema and trade helpers**
  Add `sl` and `tp` columns in `review_trades` table. Add `open_trade` with `sl` and `tp`.
- [ ] **Step 4: Update `trading_review.py` calculation and candle advance**
  Implement multi-asset contract size:
  - Gold (`XAUUSD`): 100
  - Forex (`EURUSD`, `GBPUSD`, etc.): 100,000
  - Crypto (`BTCUSD`, `ETHUSD`): 1
  - Indices (`US30`, `NAS100`): 1
  Check all open trades in `next_candle` for SL/TP hits against `high` and `low`.
- [ ] **Step 5: Run pytest to verify all tests pass**
  Run: `pytest tests/python/test_trading_review.py -v`
  Expected: PASS

---

### Task 2: Frontend Trading Review Store & Performance Analytics

**Files:**
- Modify: `src/renderer/src/stores/trading-review-store.ts`
- Create: `src/renderer/src/test/trading-review-store.test.ts`

- [ ] **Step 1: Write unit tests for `trading-review-store`**
  Test session state loading, open trade with SL/TP, floating PnL calculation, and performance metrics computation.
- [ ] **Step 2: Run vitest to verify test failure**
  Run: `npx vitest run src/renderer/src/test/trading-review-store.test.ts`
  Expected: FAIL
- [ ] **Step 3: Update `trading-review-store.ts`**
  Add `sl?: number`, `tp?: number` to `ReviewTrade` and `openTrade`.
  Add `calculatePerformanceMetrics(trades, initialBalance)` returning `{ winRate, profitFactor, maxDrawdown, maxDrawdownPercent, totalTrades, winTrades, lossTrades, netProfit }`.
- [ ] **Step 4: Run vitest to verify pass**
  Run: `npx vitest run src/renderer/src/test/trading-review-store.test.ts`
  Expected: PASS

---

### Task 3: Charting Upgrades (Volume, Moving Averages, SL/TP Lines)

**Files:**
- Modify: `src/renderer/src/components/trading-chart.tsx`

- [ ] **Step 1: Update `TradingChartProps` and indicator state**
  Add optional Volume histogram series and EMA 20 / EMA 50 line series.
- [ ] **Step 2: Add visual price lines for active trades' Entry, SL, and TP**
  Use Lightweight Charts `createPriceLine` for active positions:
  - Entry: Blue solid line
  - Stop Loss: Red dashed line
  - Take Profit: Green dashed line
- [ ] **Step 3: Support trade entry and exit visual markers**
  Display arrowUp/arrowDown and circles with PnL text.

---

### Task 4: Workspace UI, Replay Hotkeys & Performance Dashboard

**Files:**
- Modify: `src/renderer/src/pages/TradingReviewPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Create: `src/renderer/src/test/trading-review-page.test.tsx`

- [ ] **Step 1: Update i18n translation messages for review system**
  Add keys for SL/TP, Risk:Reward, Win Rate, Profit Factor, Max Drawdown, Hotkeys help, and Cached Data Selection.
- [ ] **Step 2: Enhance `TradingReviewPage.tsx`**
  - Add SL and TP input fields with dynamic Risk:Reward ratio calculation.
  - Add global hotkey listeners when workspace is active: `Space` (Play/Pause), `ArrowRight` (Step 1), `Shift+ArrowRight` (Step 10), `B` (Buy), `S` (Sell), `C` (Close All).
  - Add Live Performance Analytics Card displaying Win Rate, Profit Factor, Max Drawdown, and Equity curve preview.
  - Add "Quick Fill from Local Cached Data" dropdown on session creation card.
- [ ] **Step 3: Write component tests in `src/renderer/src/test/trading-review-page.test.tsx`**
- [ ] **Step 4: Run vitest to verify component tests pass**
  Run: `npx vitest run src/renderer/src/test/trading-review-page.test.tsx`
  Expected: PASS

---

### Task 5: Full Regression Testing & Architecture Synchronization

**Files:**
- Modify: `GUIDE.md`
- Verify: `npm run test:frontend`
- Verify: `pytest tests/python`
- Verify: `npm run build`

- [ ] **Step 1: Update `GUIDE.md` directory tree**
- [ ] **Step 2: Run `python .agents/skills/project-guide/scripts/check_guide_tree.py`**
  Expected: 0 stale, 0 missing, 0 conflicts
- [ ] **Step 3: Run full frontend test suite `npm run test:frontend`**
  Expected: All 31 test files pass
- [ ] **Step 4: Run full Python backend test suite `pytest tests/python`**
  Expected: All 29 test files pass
- [ ] **Step 5: Run production build `npm run build`**
  Expected: Build succeeds with 0 errors
