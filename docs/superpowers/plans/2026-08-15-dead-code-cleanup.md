# Dead Code & Redundancy Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up unreferenced dead code, redundant legacy wrappers, and unused static assets across Electron Main, React Renderer, and resources without impacting any existing functionality or test suites.

**Architecture:** Systematic audit and removal of dead code identified across four areas: (1) Electron Main unreferenced IPC handlers and static markdown string data (`awakening-data.ts`), (2) React Renderer unreferenced UI components (`status-card.tsx`), (3) Redundant legacy page wrapper (`QuantPage.tsx` merged into `QuantLabPage.tsx`), and (4) Leftover legacy icon/backup assets.

**Tech Stack:** TypeScript, React, Electron, Vite, Vitest, Pytest.

---

## File Structure & Proposed Changes

| Action | Path | Description |
| :--- | :--- | :--- |
| **[DELETE]** | `src/main/awakening-data.ts` | 14KB unreferenced static markdown string registry |
| **[MODIFY]** | `src/main/index.ts` | Remove unused `awakening:list-files` & `awakening:read-file` IPC handlers |
| **[DELETE]** | `src/renderer/src/components/dashboard/status-card.tsx` | Unreferenced component with 0 usages |
| **[DELETE]** | `src/renderer/src/components/navigation/` | Empty directory |
| **[MODIFY]** | `src/renderer/src/pages/quant/QuantLabPage.tsx` | Support `useSearchParams` (`tab=backtest`, `tab=python-quant`) for URL tab syncing |
| **[DELETE]** | `src/renderer/src/pages/QuantPage.tsx` | Redundant 2-tab wrapper superseded by `QuantLabPage.tsx` |
| **[MODIFY]** | `src/renderer/src/App.tsx` | Direct `/quant` and `/quant-lab` to unified `QuantLabPage` |
| **[DELETE]** | `resources/png.ico` | 370KB unreferenced legacy icon file |
| **[DELETE]** | `resources/app-icon.original.ico` | Unreferenced backup icon |
| **[DELETE]** | `resources/app-icon.pre-icon-png-test.ico` | Unreferenced backup icon |
| **[DELETE]** | `resources/fav.ico` | Unreferenced backup icon |
| **[MODIFY]** | `GUIDE.md` | Update repository tree to maintain 100% sync |

---

## Bite-Sized Implementation Tasks

### Task 1: Clean Up Electron Main Unreferenced IPC & Static Data

**Files:**
- Delete: `src/main/awakening-data.ts`
- Modify: `src/main/index.ts:15-20,325-350`
- Test: `npm run test:frontend` (verifies all main and renderer tests pass)

- [ ] **Step 1: Remove unreferenced awakening IPC handlers from `src/main/index.ts`**
  Remove `import { AWAKENING_DOCS } from './awakening-data'` and the `awakening:list-files` and `awakening:read-file` handlers.
- [ ] **Step 2: Delete `src/main/awakening-data.ts`**
- [ ] **Step 3: Run tests to verify zero regressions**
  Run: `npm run test:frontend`
  Expected: PASS

---

### Task 2: Remove Dead Component & Empty Directories in Renderer

**Files:**
- Delete: `src/renderer/src/components/dashboard/status-card.tsx`
- Delete: `src/renderer/src/components/navigation/`
- Test: `npm run test:frontend`

- [ ] **Step 1: Delete `src/renderer/src/components/dashboard/status-card.tsx`**
- [ ] **Step 2: Remove empty directory `src/renderer/src/components/navigation/`**
- [ ] **Step 3: Run tests to verify zero regressions**
  Run: `npx vitest run src/renderer/src/test/dashboard-page.test.tsx`
  Expected: PASS

---

### Task 3: Unify Quant Lab & Remove Redundant `QuantPage.tsx`

**Files:**
- Modify: `src/renderer/src/pages/quant/QuantLabPage.tsx` (add URL search parameter synchronization for tab selection)
- Delete: `src/renderer/src/pages/QuantPage.tsx`
- Modify: `src/renderer/src/App.tsx`
- Test: `src/renderer/src/test/quant-lab-page.test.tsx`, `src/renderer/src/test/python-quant-page.test.tsx`

- [ ] **Step 1: Enhance `QuantLabPage.tsx` with `useSearchParams` support**
  Allow URL query parameter `?tab=backtest` or `?tab=python-quant` to control the initial/active tab seamlessly.
- [ ] **Step 2: Update `App.tsx` to render `QuantLabPage` for `activeModule === 'quant'`**
- [ ] **Step 3: Delete redundant `src/renderer/src/pages/QuantPage.tsx`**
- [ ] **Step 4: Run tests to verify**
  Run: `npx vitest run src/renderer/src/test/python-quant-page.test.tsx src/renderer/src/test/quant-lab-page.test.tsx`
  Expected: PASS

---

### Task 4: Remove Unreferenced Legacy Icon Assets in `resources/`

**Files:**
- Delete: `resources/png.ico`
- Delete: `resources/app-icon.original.ico`
- Delete: `resources/app-icon.pre-icon-png-test.ico`
- Delete: `resources/fav.ico`
- Test: `npm run build`

- [ ] **Step 1: Delete unreferenced icon files in `resources/`**
- [ ] **Step 2: Verify `package.json` build resources and icons remain intact (`resources/app-icon.ico`, `resources/icon.png`, `resources/tray-icon.png`)**

---

### Task 5: Sync `GUIDE.md` & Full Verification

**Files:**
- Modify: `GUIDE.md`
- Verify: `python .agents/skills/project-guide/scripts/check_guide_tree.py`
- Verify: `npm run test:frontend`
- Verify: `pytest tests/python`
- Verify: `npm run build`

- [ ] **Step 1: Update `GUIDE.md` directory tree to reflect deleted files**
- [ ] **Step 2: Run `python .agents/skills/project-guide/scripts/check_guide_tree.py`**
  Expected: `Result: GUIDE.md tree matches repository structure.` (0 stale, 0 missing, 0 conflicts)
- [ ] **Step 3: Run full frontend test suite `npm run test:frontend`**
  Expected: 29 files, 105 tests PASS
- [ ] **Step 4: Run backend Python test suite `pytest tests/python`**
  Expected: 28 files, 163 tests PASS
- [ ] **Step 5: Run production build `npm run build`**
  Expected: Main, preload, renderer built successfully with zero errors
