# Tray Quit Shutdown Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make tray-triggered app shutdown observable and reliably tear down the local backend process tree without leaving residual processes.

**Architecture:** Add structured shutdown diagnostics in the Electron main process so the tray quit path, window close interception, quit lifecycle hooks, and backend cleanup can be traced in logs. Refactor backend shutdown into an async, waitable path that attempts owned-child termination, waits for exit, then forcibly terminates the backend process tree on Windows before falling back to port cleanup. Coordinate Electron shutdown through a single guarded cleanup promise in `before-quit` so repeated quit hooks reuse the same teardown work.

**Tech Stack:** Electron main process, Node child_process, PowerShell task management, Vitest

---

### Task 1: Add shutdown diagnostics in the Electron main process

**Files:**
- Modify: `src/main/index.ts`
- Modify: `src/main/python-service.ts`
- Test: `src/main/python-service.test.ts`

- [ ] **Step 1: Add a shared shutdown logging helper**

Create a small helper in the main-process shutdown path that logs the shutdown stage, whether quit was tray-triggered, and whether backend cleanup is being awaited.

- [ ] **Step 2: Wire diagnostics into tray quit, window close interception, and app lifecycle hooks**

Instrument the tray quit click handler, `mainWindow.on('close')`, `window-all-closed`, `before-quit`, and `will-quit` to emit ordered logs that can reconstruct whether the app hid to tray or proceeded through full shutdown.

- [ ] **Step 3: Add backend cleanup logs around graceful and forced termination**

Emit logs when the backend child receives a graceful kill, when the code waits for exit, when the process tree is force-killed, and when port cleanup fallback is invoked.

- [ ] **Step 4: Keep logs concise and deterministic**

Use a consistent prefix so users can filter logs easily and tests can assert meaningful behavior without depending on timestamps.

### Task 2: Make backend shutdown waitable and more reliable on Windows

**Files:**
- Modify: `src/main/python-service.ts`
- Modify: `src/main/index.ts`
- Test: `src/main/python-service.test.ts`

- [ ] **Step 1: Convert backend stop logic into an async function**

Change `stopPythonService` so callers can await backend teardown rather than fire-and-forget the shutdown request.

- [ ] **Step 2: Attempt owned-child termination and wait with timeout**

If Electron owns a backend child process, request termination, wait for its `close` event up to a short timeout, and only then escalate to stronger cleanup.

- [ ] **Step 3: Add Windows process-tree force kill fallback**

When the child does not exit in time, use `taskkill /PID <pid> /T /F` to terminate the child and any descendants it spawned.

- [ ] **Step 4: Preserve port-based cleanup as the last fallback**

Retain the existing port cleanup behavior behind `killPort`, but run it after child/process-tree cleanup so it serves as a safety net rather than the primary mechanism.

- [ ] **Step 5: Gate Electron quit through one shared async shutdown promise**

Use `before-quit` as the async coordination point with `event.preventDefault()` on the first pass, start one shared shutdown promise, and let repeated tray/lifecycle quit events reuse that in-flight cleanup instead of racing duplicate teardown.

### Task 3: Cover the shutdown behavior with targeted tests

**Files:**
- Modify: `src/main/python-service.test.ts`
- Create or Modify: focused main-process shutdown test covering the shared quit coordinator if extraction is needed

- [ ] **Step 1: Mock child-process spawning and process control primitives**

Extend the existing mocks so tests can simulate child `kill`, `close`, `error`, and Windows force-kill behavior.

- [ ] **Step 2: Add a test for graceful child shutdown**

Verify that `stopPythonService()` resolves after the backend child exits and does not force-kill the process tree when graceful shutdown succeeds.

- [ ] **Step 3: Add a test for Windows process-tree fallback**

Verify that a stuck backend child triggers the `taskkill` fallback and still performs port cleanup when requested.

- [ ] **Step 4: Add coverage for once-only shutdown coordination**

Verify that repeated quit hooks share one in-flight cleanup operation and do not trigger duplicate backend teardown.

- [ ] **Step 5: Keep the existing port-cleanup coverage passing**

Adjust existing assertions to account for the new stop behavior while retaining the guarantee that port cleanup can still be requested explicitly.

### Task 4: Validate the implementation

**Files:**
- Modify: `src/main/index.ts`
- Modify: `src/main/python-service.ts`
- Modify: `src/main/python-service.test.ts`

- [ ] **Step 1: Run the focused main-process tests**

Run: `npm run test:frontend -- src/main/python-service.test.ts`

Expected: PASS

- [ ] **Step 2: Review the final shutdown path for duplicate cleanup races**

Confirm the tray quit path and lifecycle hooks share one in-flight shutdown promise instead of racing independent cleanup calls.
