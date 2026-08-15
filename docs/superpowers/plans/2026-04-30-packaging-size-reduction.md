# Packaging Size Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 找出当前 Windows 安装包的主要体积来源，并按收益优先级逐步缩小 Electron 主包、Python 后端和最终安装包体积。

**Architecture:** 先建立可重复的体积基线，再给高风险瘦身点补行为回归测试，随后优先处理已确认的大头：Python 后端里的 `pandas/numpy` 运行时，以及 Electron 打包时被原样带入的 renderer 依赖。最后再做 renderer chunk 拆分和条件性的 Electron locale 裁剪，确保每一步都有可见的体积收益和验证证据。

**Tech Stack:** Electron, electron-builder, electron-vite, React, Vite, TypeScript, Python, FastAPI, PyInstaller, PowerShell, pytest, Vitest, npm

---

**Current Baseline**

- `dist/MT5 Trader Workbench Setup 1.0.0.3.exe`: `109.47 MB`
- `dist/win-unpacked/resources/app.asar`: `31.57 MB`
- `python_service/dist/mt5_service`: `82.61 MB`
- `python_service/dist/mt5_service/_internal`: `67.09 MB`
- Largest Python backend payloads:
  - `numpy.libs`: `20.02 MB`
  - `pandas`: `12.90 MB`
  - `python314.dll`: `6.45 MB`
  - `numpy`: `5.85 MB`
  - `pydantic_core`: `5.02 MB`
  - `libcrypto-3.dll`: `4.99 MB`
- Largest renderer asset:
  - `out/renderer/assets/index-*.js`: about `873.88 KB`
- Largest npm production dependencies currently declared in `package.json`:
  - `lucide-react`: `22.06 MB`
  - `react-dom`: `4.30 MB`
  - Renderer-only packages are still in `dependencies`, while `src/main` / `src/preload` only import `@electron-toolkit/utils`

**Priority Order**

1. Remove Python runtime weight caused by `pandas` / `numpy`
2. Stop shipping renderer-only npm packages as raw runtime dependencies
3. Split renderer bundle so low-traffic pages do not inflate the first JS chunk
4. Prune packaged Electron locales only if the first three steps still leave the installer above target

**File Structure**

- Create: `scripts/package-size-report.ps1`
  - Single source of truth for installer, `app.asar`, renderer chunk, Python backend, and top-directory size reporting
- Create: `scripts/audit-runtime-deps.mjs`
  - Fails when `package.json.dependencies` contains packages not imported by `src/main` or `src/preload`
- Create: `tests/python/test_indicator_math.py`
  - Regression tests for a pure-Python RSI helper
- Create: `python_service/app/services/indicator_math.py`
  - Pure-Python RSI calculation, replacing `pandas` / `numpy` usage
- Modify: `python_service/app/services/indicator_service.py`
  - Keep MT5 data fetch logic, delegate math to `indicator_math.py`
- Create: `tests/python/test_history_math.py`
  - Regression tests for pure-Python history profit and daily aggregation helpers
- Create: `python_service/app/services/history_math.py`
  - Pure-Python aggregation and profit calculation helpers, replacing `pandas`
- Modify: `python_service/app/services/history_service.py`
  - Keep MT5 integration, delegate calculations to `history_math.py`
- Create: `python_service/requirements-dev.txt`
  - Developer-only Python dependencies such as `pytest` and `pyinstaller`
- Modify: `python_service/requirements.txt`
  - Runtime-only Python dependencies
- Modify: `python_service/pyproject.toml`
  - Match runtime/dev dependency split
- Modify: `python_service/mt5_service.spec`
  - Remove `numpy` / `pandas` hidden imports and add explicit excludes for dead packaging weight
- Modify: `package.json`
  - Add package size scripts, reclassify renderer libraries into `devDependencies`, wire conditional locale pruning hook
- Modify: `package-lock.json`
  - Lock the dependency classification changes
- Modify: `electron.vite.config.ts`
  - Add renderer manual chunk strategy
- Modify: `src/renderer/src/App.tsx`
  - Route/page lazy loading with `React.lazy` and `Suspense`
- Create: `scripts/prune-packaged-locales.cjs`
  - Conditional `afterPack` locale deletion hook that keeps only `en-US.pak` and `zh-CN.pak`
- Modify: `scripts/verify-packaging.ps1`
  - Verify locale allowlist only if locale pruning is enabled
- Modify: `README.md`
  - English packaging size workflow and verification commands
- Modify: `README.zh-CN.md`
  - Chinese packaging size workflow and verification commands

### Task 1: 建立可重复的体积基线脚本

**Files:**
- Create: `scripts/package-size-report.ps1`
- Modify: `package.json`

- [ ] **Step 1: Run the missing analysis script to prove the guardrail does not exist yet**

Run: `npm run analyze:package-size`
Expected: FAIL with `Missing script: "analyze:package-size"`

- [ ] **Step 2: Create the reporting script**

```powershell
function Get-DirSizeBytes {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return 0 }
  return (Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object Length -Sum).Sum
}

function Get-FileSizeMB {
  param([string]$Path)
  if (-not (Test-Path $Path)) { return $null }
  return [math]::Round((Get-Item $Path).Length / 1MB, 2)
}

$report = [ordered]@{
  installer_mb        = Get-FileSizeMB 'dist/MT5 Trader Workbench Setup 1.0.0.3.exe'
  app_asar_mb         = Get-FileSizeMB 'dist/win-unpacked/resources/app.asar'
  backend_dir_mb      = [math]::Round((Get-DirSizeBytes 'python_service/dist/mt5_service') / 1MB, 2)
  backend_internal_mb = [math]::Round((Get-DirSizeBytes 'python_service/dist/mt5_service/_internal') / 1MB, 2)
  renderer_dir_mb     = [math]::Round((Get-DirSizeBytes 'out/renderer') / 1MB, 2)
}

$topBackend = Get-ChildItem 'python_service/dist/mt5_service/_internal' | ForEach-Object {
  $size = if ($_.PSIsContainer) {
    Get-DirSizeBytes $_.FullName
  } else {
    $_.Length
  }
  [pscustomobject]@{
    name = $_.Name
    size_mb = [math]::Round($size / 1MB, 2)
  }
} | Sort-Object size_mb -Descending | Select-Object -First 15

[pscustomobject]@{
  summary = [pscustomobject]$report
  top_backend_entries = $topBackend
} | ConvertTo-Json -Depth 4
```

- [ ] **Step 3: Add the npm entry point**

```json
{
  "scripts": {
    "analyze:package-size": "pwsh -File scripts/package-size-report.ps1"
  }
}
```

- [ ] **Step 4: Run the script and capture the baseline**

Run: `npm run analyze:package-size`
Expected: PASS and prints JSON containing `installer_mb`, `app_asar_mb`, `backend_dir_mb`, and `top_backend_entries`

- [ ] **Step 5: Commit**

```bash
git add scripts/package-size-report.ps1 package.json
git commit -m "build: add package size baseline report"
```

### Task 2: 用纯 Python RSI helper 替换 `numpy` / `pandas`

**Files:**
- Create: `tests/python/test_indicator_math.py`
- Create: `python_service/app/services/indicator_math.py`
- Modify: `python_service/app/services/indicator_service.py`

- [ ] **Step 1: Write the failing test**

```python
from python_service.app.services.indicator_math import calculate_latest_rsi


def test_calculate_latest_rsi_returns_none_when_bars_are_insufficient():
    assert calculate_latest_rsi([1.0, 2.0], period=3) is None


def test_calculate_latest_rsi_returns_100_for_all_gains():
    assert calculate_latest_rsi([1.0, 2.0, 3.0, 4.0], period=3) == 100.0


def test_calculate_latest_rsi_returns_0_for_all_losses():
    assert calculate_latest_rsi([4.0, 3.0, 2.0, 1.0], period=3) == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/python/test_indicator_math.py -q`
Expected: FAIL with `ModuleNotFoundError` for `python_service.app.services.indicator_math`

- [ ] **Step 3: Write the minimal helper**

```python
def calculate_latest_rsi(closes: list[float], period: int) -> float | None:
    if len(closes) < period + 1:
        return None

    deltas = [curr - prev for prev, curr in zip(closes, closes[1:])]
    window = deltas[-period:]
    gains = [delta for delta in window if delta > 0]
    losses = [-delta for delta in window if delta < 0]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
      return 100.0
    if avg_gain == 0:
      return 0.0

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 10)
```

- [ ] **Step 4: Refactor the MT5-facing service to use the helper instead of `DataFrame` math**

```python
from python_service.app.services.indicator_math import calculate_latest_rsi

closes = [float(rate['close']) for rate in rates]
return calculate_latest_rsi(closes, period)
```

- [ ] **Step 5: Run tests to verify the behavior is preserved**

Run: `pytest tests/python/test_indicator_math.py tests/python/test_price_alerts.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/python/test_indicator_math.py python_service/app/services/indicator_math.py python_service/app/services/indicator_service.py
git commit -m "refactor: remove dataframe usage from indicator math"
```

### Task 3: 用纯 Python 历史聚合 helper 替换 `pandas`

**Files:**
- Create: `tests/python/test_history_math.py`
- Create: `python_service/app/services/history_math.py`
- Modify: `python_service/app/services/history_service.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime

from python_service.app.services.history_math import (
    build_daily_aggregated_stats,
    calculate_closed_trade_profit,
)


def test_calculate_closed_trade_profit_counts_only_exit_buy_sell_deals():
    deals = [
        {"entry": 1, "type": 0, "profit": 10.0, "commission": -1.0, "swap": 0.0},
        {"entry": 2, "type": 1, "profit": 5.0, "commission": -0.5, "swap": 0.0},
        {"entry": 0, "type": 0, "profit": 999.0, "commission": 0.0, "swap": 0.0},
    ]
    assert calculate_closed_trade_profit(deals) == 13.5


def test_build_daily_aggregated_stats_returns_descending_rows():
    deals = [
        {"time": 1714521600, "entry": 1, "type": 0, "profit": 10.0, "commission": -1.0, "swap": 0.0, "volume": 0.10},
        {"time": 1714525200, "entry": 0, "type": 0, "profit": 0.0, "commission": 0.0, "swap": 0.0, "volume": 0.10},
    ]
    result = build_daily_aggregated_stats(
        all_deals=deals,
        current_balance=1010.0,
        from_date=datetime(2024, 5, 1),
        to_date=datetime(2024, 5, 1, 23, 59, 59),
    )
    assert result[0]["date"] == "2024-05-01"
    assert result[0]["profit"] == 9.0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/python/test_history_math.py -q`
Expected: FAIL with `ModuleNotFoundError` for `python_service.app.services.history_math`

- [ ] **Step 3: Write the minimal helper**

```python
from collections import defaultdict
from datetime import datetime


def calculate_closed_trade_profit(deals: list[dict]) -> float:
    total = 0.0
    for deal in deals:
        if deal.get("entry") in (1, 2) and deal.get("type") in (0, 1):
            total += float(deal.get("profit", 0.0))
            total += float(deal.get("commission", 0.0))
            total += float(deal.get("swap", 0.0))
    return round(total, 2)


def build_daily_aggregated_stats(all_deals: list[dict], current_balance: float, from_date: datetime, to_date: datetime) -> list[dict]:
    daily_changes = defaultdict(float)
    for deal in all_deals:
        deal_dt = datetime.fromtimestamp(deal["time"])
        date_key = deal_dt.strftime("%Y-%m-%d")
        daily_changes[date_key] += float(deal.get("profit", 0.0)) + float(deal.get("commission", 0.0)) + float(deal.get("swap", 0.0))

    rows = []
    for date_key, net_change in daily_changes.items():
        if from_date.strftime("%Y-%m-%d") <= date_key <= to_date.strftime("%Y-%m-%d"):
            rows.append({
                "date": date_key,
                "total_lots": 0.0,
                "min_lot": 0.0,
                "max_lot": 0.0,
                "trades_count": 0,
                "profit": round(net_change, 2),
                "profit_pct": 0.0,
                "balance": round(current_balance, 2),
            })
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows
```

- [ ] **Step 4: Refactor `history_service.py` to convert MT5 namedtuples to plain dicts and delegate the math**

```python
from python_service.app.services.history_math import build_daily_aggregated_stats, calculate_closed_trade_profit

deals_dicts = [deal._asdict() for deal in deals]
return calculate_closed_trade_profit(deals_dicts)
```

- [ ] **Step 5: Expand the helper just enough to match existing route shape, then run tests**

Run: `pytest tests/python/test_history_math.py tests/python/test_mt5_polling.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/python/test_history_math.py python_service/app/services/history_math.py python_service/app/services/history_service.py
git commit -m "refactor: remove dataframe usage from history aggregation"
```

### Task 4: 收紧 Python 运行时依赖和 PyInstaller payload

**Files:**
- Create: `python_service/requirements-dev.txt`
- Modify: `python_service/requirements.txt`
- Modify: `python_service/pyproject.toml`
- Modify: `python_service/mt5_service.spec`

- [ ] **Step 1: Rebuild once to confirm the current backend still contains `numpy` and `pandas`**

Run: `npm run build:python && npm run analyze:package-size`
Expected: PASS and the size report still shows `numpy.libs`, `numpy`, and `pandas` among the largest backend entries

- [ ] **Step 2: Split runtime and developer dependencies**

```text
# python_service/requirements.txt
fastapi
uvicorn
pydantic
MetaTrader5
httpx
```

```text
# python_service/requirements-dev.txt
-r requirements.txt
pytest
pyinstaller
```

```toml
[project]
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "MetaTrader5",
    "httpx",
]

[project.optional-dependencies]
dev = ["pytest", "pyinstaller"]
```

- [ ] **Step 3: Remove dead hidden imports and add explicit excludes to the PyInstaller spec**

```python
hiddenimports=[
    'pydantic',
    'MetaTrader5',
    'gold_analysis',
    'wave_analysis',
    'elliott_wave',
    'pa_wave_fusion',
    'smc_snapshot',
    'scenario_playbook',
    'institutional_render',
    'economic_calendar',
],
excludes=['numpy', 'pandas', 'pytest', 'pyinstaller', 'setuptools', 'pip'],
```

- [ ] **Step 4: Rebuild the backend and verify the fat packages disappear**

Run: `npm run build:python && npm run analyze:package-size`
Expected: PASS and the top backend entries no longer contain `numpy.libs`, `numpy`, or `pandas`

- [ ] **Step 5: Run the Python regression suite**

Run: `pytest tests/python/test_indicator_math.py tests/python/test_history_math.py tests/python/test_settings.py tests/python/test_price_alerts.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add python_service/requirements.txt python_service/requirements-dev.txt python_service/pyproject.toml python_service/mt5_service.spec
git commit -m "build: trim python runtime dependencies"
```

### Task 5: 停止把 renderer-only npm 包原样塞进 `app.asar`

**Files:**
- Create: `scripts/audit-runtime-deps.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`

- [ ] **Step 1: Run the missing runtime dependency audit**

Run: `node scripts/audit-runtime-deps.mjs`
Expected: FAIL because the file does not exist yet

- [ ] **Step 2: Create the audit script**

```js
import fs from 'node:fs'
import path from 'node:path'

const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'))
const runtimeRoots = ['src/main', 'src/preload']
const imported = new Set()

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (/\.(ts|tsx|js|mjs|cjs)$/.test(entry.name)) {
      const text = fs.readFileSync(full, 'utf8')
      for (const match of text.matchAll(/from ['"]([^./][^'"]*)['"]/g)) imported.add(match[1])
      for (const match of text.matchAll(/require\(['"]([^./][^'"]*)['"]\)/g)) imported.add(match[1])
    }
  }
}

runtimeRoots.forEach(walk)

const deps = Object.keys(pkg.dependencies || {})
const extra = deps.filter((name) => !imported.has(name))

if (extra.length) {
  console.error(`Move these packages to devDependencies: ${extra.join(', ')}`)
  process.exit(1)
}
```

- [ ] **Step 3: Move renderer-only packages into `devDependencies`**

```json
{
  "dependencies": {
    "@electron-toolkit/utils": "^4.0.0"
  },
  "devDependencies": {
    "@radix-ui/react-checkbox": "...",
    "@radix-ui/react-label": "...",
    "@radix-ui/react-scroll-area": "...",
    "@radix-ui/react-select": "...",
    "@radix-ui/react-slot": "...",
    "@radix-ui/react-switch": "...",
    "@radix-ui/react-tabs": "...",
    "class-variance-authority": "...",
    "clsx": "...",
    "lucide-react": "...",
    "next-themes": "...",
    "react": "...",
    "react-dom": "...",
    "react-router-dom": "...",
    "sonner": "...",
    "tailwind-merge": "...",
    "zustand": "..."
  }
}
```

- [ ] **Step 4: Refresh the lockfile**

Run: `npm install`
Expected: PASS and updates `package-lock.json`

- [ ] **Step 5: Run the dependency audit and package again**

Run: `node scripts/audit-runtime-deps.mjs && npm run build && npm run package:win && npm run analyze:package-size`
Expected: PASS and `app.asar` is materially smaller than the current `31.57 MB` baseline

- [ ] **Step 6: Review gate**

Run: `@requesting-code-review`
Expected: reviewer focuses on dependency classification and packaging regressions before continuing

- [ ] **Step 7: Commit**

```bash
git add scripts/audit-runtime-deps.mjs package.json package-lock.json
git commit -m "build: stop shipping renderer-only runtime deps"
```

### Task 6: 对 renderer 做路由级 lazy loading 和 chunk 拆分

**Files:**
- Modify: `src/renderer/src/App.tsx`
- Modify: `electron.vite.config.ts`

- [ ] **Step 1: Capture the current renderer baseline**

Run: `npm run build`
Expected: PASS and `out/renderer/assets` still contains one dominant JS file around `873.88 KB`

- [ ] **Step 2: Convert page imports in `App.tsx` to lazy imports**

```tsx
import React, { Suspense, useState } from 'react'

const DashboardPage = React.lazy(() => import('@/pages/dashboard-page').then((m) => ({ default: m.DashboardPage })))
const OrderBroadcastPage = React.lazy(() => import('@/pages/OrderBroadcastPage').then((m) => ({ default: m.OrderBroadcastPage })))
const SettingsPage = React.lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
```

```tsx
<Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading module...</div>}>
  {activeModule === 'dashboard' && <DashboardPage />}
</Suspense>
```

- [ ] **Step 3: Add a manual chunk strategy in Vite**

```ts
build: {
  outDir: resolve(__dirname, 'out/renderer'),
  rollupOptions: {
    output: {
      manualChunks: {
        react: ['react', 'react-dom', 'react-router-dom'],
        ui: [
          '@radix-ui/react-checkbox',
          '@radix-ui/react-label',
          '@radix-ui/react-scroll-area',
          '@radix-ui/react-select',
          '@radix-ui/react-slot',
          '@radix-ui/react-switch',
          '@radix-ui/react-tabs'
        ],
        icons: ['lucide-react'],
        state: ['zustand', 'sonner', 'next-themes']
      }
    }
  }
}
```

- [ ] **Step 4: Rebuild and verify the largest renderer chunk shrinks**

Run: `npm run build`
Expected: PASS and `out/renderer/assets` contains multiple JS chunks; the largest chunk is smaller than the original single-file baseline

- [ ] **Step 5: Run frontend regression tests**

Run: `npm run test:frontend`
Expected: PASS

- [ ] **Step 6: Review gate**

Run: `@requesting-code-review`
Expected: reviewer checks lazy loading correctness and chunk configuration safety

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/App.tsx electron.vite.config.ts
git commit -m "perf: split renderer pages and vendor chunks"
```

### Task 7: 如果前三步后体积仍然偏大，再裁剪 Electron locales

**Files:**
- Create: `scripts/prune-packaged-locales.cjs`
- Modify: `package.json`
- Modify: `scripts/verify-packaging.ps1`

- [ ] **Step 1: Check whether this task is still necessary**

Run: `npm run package:win && npm run analyze:package-size`
Expected: If the installer is already within target, skip the rest of this task; otherwise continue

- [ ] **Step 2: Create the `afterPack` hook**

```js
const fs = require('node:fs')
const path = require('node:path')

module.exports = async function prunePackagedLocales(context) {
  const localesDir = path.join(context.appOutDir, 'locales')
  const keep = new Set(['en-US.pak', 'zh-CN.pak'])

  for (const name of fs.readdirSync(localesDir)) {
    if (name.endsWith('.pak') && !keep.has(name)) {
      fs.unlinkSync(path.join(localesDir, name))
    }
  }
}
```

- [ ] **Step 3: Wire the hook and extend packaging verification**

```json
{
  "build": {
    "afterPack": "scripts/prune-packaged-locales.cjs"
  }
}
```

```powershell
$expectedLocales = @('en-US.pak', 'zh-CN.pak')
$localeDir = 'dist/win-unpacked/locales'
Get-ChildItem $localeDir -Filter *.pak | ForEach-Object {
  if ($_.Name -notin $expectedLocales) {
    throw "Unexpected packaged locale: $($_.Name)"
  }
}
```

- [ ] **Step 4: Repackage and smoke test**

Run: `npm run package:win && npm run verify:packaging && npm run test:electron`
Expected: PASS and the installer shrinks further without breaking app launch

- [ ] **Step 5: Commit**

```bash
git add scripts/prune-packaged-locales.cjs package.json scripts/verify-packaging.ps1
git commit -m "build: prune packaged electron locales"
```

### Task 8: 文档化体积预算和回归检查命令

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Add the new packaging size workflow to the docs**

```md
1. Run `npm run build`
2. Run `npm run build:python`
3. Run `npm run package:win`
4. Run `npm run analyze:package-size`
```

- [ ] **Step 2: Document the expected hotspots and success criteria**

```md
- Python backend should no longer bundle `numpy` / `pandas`
- `package.json.dependencies` should only contain packages needed by `src/main` or `src/preload`
- Renderer output should not regress to a single dominant JS chunk
```

- [ ] **Step 3: Verify the docs commands still match reality**

Run: `npm run analyze:package-size`
Expected: PASS and the documented command exists exactly as written

- [ ] **Step 4: Commit**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: document package size workflow"
```

### Final Verification

- [ ] Run: `pytest tests/python/test_indicator_math.py tests/python/test_history_math.py tests/python/test_price_alerts.py tests/python/test_settings.py -q`
  Expected: PASS
- [ ] Run: `npm run test:frontend`
  Expected: PASS
- [ ] Run: `npm run package:win && npm run verify:packaging && npm run analyze:package-size`
  Expected: PASS and the report shows a smaller installer, a smaller backend directory, and a smaller `app.asar`
- [ ] Run: `@requesting-code-review`
  Expected: final packaging review before merge

### Expected Outcome

- Python backend stops bundling `pandas` / `numpy`, removing the biggest confirmed payloads first
- `package.json.dependencies` is reduced to actual Electron runtime packages instead of renderer build-time libraries
- Renderer no longer ships as one dominant page chunk
- Final installer size is reduced with evidence, not guesses
- Future regressions are caught by `npm run analyze:package-size` and `node scripts/audit-runtime-deps.mjs`
