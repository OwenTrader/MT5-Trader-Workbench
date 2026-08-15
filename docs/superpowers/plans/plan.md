# 打包体积缩减实施计划

> **面向代理执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划。所有步骤使用复选框语法（`- [ ]`）进行跟踪。

**目标：** 找出当前 Windows 安装包的主要体积来源，并按收益优先级逐步缩小 Electron 主包、Python 后端和最终安装包体积。

**架构：** 先建立可重复的体积基线，再给高风险瘦身点补行为回归测试，随后优先处理已确认的大头：Python 后端里的 `pandas/numpy` 运行时，以及 Electron 打包时被原样带入的 renderer 依赖。最后再做 renderer chunk 拆分和条件性的 Electron locale 裁剪，确保每一步都有可见的体积收益和验证证据。

**技术栈：** Electron, electron-builder, electron-vite, React, Vite, TypeScript, Python, FastAPI, PyInstaller, PowerShell, pytest, Vitest, npm

---

**当前基线**

- `dist/MT5 Trader Workbench Setup 1.0.0.3.exe`：`109.47 MB`
- `dist/win-unpacked/resources/app.asar`：`31.57 MB`
- `python_service/dist/mt5_service`：`82.61 MB`
- `python_service/dist/mt5_service/_internal`：`67.09 MB`
- 当前 Python 后端中最大的体积项：
  - `numpy.libs`：`20.02 MB`
  - `pandas`：`12.90 MB`
  - `python314.dll`：`6.45 MB`
  - `numpy`：`5.85 MB`
  - `pydantic_core`：`5.02 MB`
  - `libcrypto-3.dll`：`4.99 MB`
- 当前最大的 renderer 产物：
  - `out/renderer/assets/index-*.js`：约 `873.88 KB`
- 当前在 `package.json` 中声明的、体积最大的 npm 生产依赖：
  - `lucide-react`：`22.06 MB`
  - `react-dom`：`4.30 MB`
  - renderer-only 的依赖目前仍放在 `dependencies` 中，而 `src/main` / `src/preload` 实际只导入了 `@electron-toolkit/utils`

**优先顺序**

1. 去掉由 `pandas` / `numpy` 带来的 Python 运行时体积
2. 停止把 renderer-only 的 npm 包作为原始运行时依赖一起打进包里
3. 拆分 renderer bundle，避免低频页面抬高首屏 JS chunk 体积
4. 只有在前三步之后安装包仍然偏大时，才裁剪打包后的 Electron locales

**文件结构**

- Create: `scripts/package-size-report.ps1`
  - 统一输出安装包、`app.asar`、renderer chunk、Python 后端和主要目录体积分布
- Create: `scripts/audit-runtime-deps.mjs`
  - 当 `package.json.dependencies` 中存在未被 `src/main` 或 `src/preload` 导入的包时直接失败
- Create: `tests/python/test_indicator_math.py`
  - 为纯 Python RSI helper 提供回归测试
- Create: `python_service/app/services/indicator_math.py`
  - 纯 Python RSI 计算逻辑，用来替代 `pandas` / `numpy`
- Modify: `python_service/app/services/indicator_service.py`
  - 保留 MT5 数据获取逻辑，把计算委托给 `indicator_math.py`
- Create: `tests/python/test_history_math.py`
  - 为纯 Python 历史盈亏与日聚合 helper 提供回归测试
- Create: `python_service/app/services/history_math.py`
  - 纯 Python 的聚合和利润计算 helper，用来替代 `pandas`
- Modify: `python_service/app/services/history_service.py`
  - 保留 MT5 集成，把计算委托给 `history_math.py`
- Create: `python_service/requirements-dev.txt`
  - 开发环境专用 Python 依赖，例如 `pytest` 和 `pyinstaller`
- Modify: `python_service/requirements.txt`
  - 仅保留运行时 Python 依赖
- Modify: `python_service/pyproject.toml`
  - 与 runtime/dev 依赖拆分保持一致
- Modify: `python_service/mt5_service.spec`
  - 移除 `numpy` / `pandas` 的 hidden imports，并显式排除不再需要的打包负担
- Modify: `package.json`
  - 增加体积分析脚本、把 renderer 依赖迁移到 `devDependencies`、接入可选的 locale 裁剪钩子
- Modify: `package-lock.json`
  - 锁定依赖归类变更
- Modify: `electron.vite.config.ts`
  - 为 renderer 增加 manual chunk 策略
- Modify: `src/renderer/src/App.tsx`
  - 用 `React.lazy` 和 `Suspense` 改成路由/页面级懒加载
- Create: `scripts/prune-packaged-locales.cjs`
  - 条件性的 `afterPack` locale 删除钩子，只保留 `en-US.pak` 和 `zh-CN.pak`
- Modify: `scripts/verify-packaging.ps1`
  - 如果开启 locale 裁剪，则验证 locale 白名单
- Modify: `README.md`
  - 英文版打包体积工作流和验证命令
- Modify: `README.zh-CN.md`
  - 中文版打包体积工作流和验证命令

### Task 1: 建立可重复的体积基线脚本

**Files:**
- Create: `scripts/package-size-report.ps1`
- Modify: `package.json`

- [ ] **Step 1: 先运行一个不存在的分析脚本，证明当前还没有这层护栏**

运行：`npm run analyze:package-size`
预期：FAIL，并提示 `Missing script: "analyze:package-size"`

- [ ] **Step 2: 创建体积报告脚本**

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

- [ ] **Step 3: 在 npm 脚本中接入入口**

```json
{
  "scripts": {
    "analyze:package-size": "pwsh -File scripts/package-size-report.ps1"
  }
}
```

- [ ] **Step 4: 运行脚本并记录基线**

运行：`npm run analyze:package-size`
预期：PASS，并输出包含 `installer_mb`、`app_asar_mb`、`backend_dir_mb` 和 `top_backend_entries` 的 JSON

- [ ] **Step 5: 提交**

```bash
git add scripts/package-size-report.ps1 package.json
git commit -m "build: add package size baseline report"
```

### Task 2: 用纯 Python RSI helper 替换 `numpy` / `pandas`

**Files:**
- Create: `tests/python/test_indicator_math.py`
- Create: `python_service/app/services/indicator_math.py`
- Modify: `python_service/app/services/indicator_service.py`

- [ ] **Step 1: 先写失败测试**

```python
from python_service.app.services.indicator_math import calculate_latest_rsi


def test_calculate_latest_rsi_returns_none_when_bars_are_insufficient():
    assert calculate_latest_rsi([1.0, 2.0], period=3) is None


def test_calculate_latest_rsi_returns_100_for_all_gains():
    assert calculate_latest_rsi([1.0, 2.0, 3.0, 4.0], period=3) == 100.0


def test_calculate_latest_rsi_returns_0_for_all_losses():
    assert calculate_latest_rsi([4.0, 3.0, 2.0, 1.0], period=3) == 0.0
```

- [ ] **Step 2: 运行测试，确认它确实失败**

运行：`pytest tests/python/test_indicator_math.py -q`
预期：FAIL，并出现 `python_service.app.services.indicator_math` 的 `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现的 helper**

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

- [ ] **Step 4: 重构 MT5 侧 service，改为使用 helper 而不是 `DataFrame` 计算**

```python
from python_service.app.services.indicator_math import calculate_latest_rsi

closes = [float(rate['close']) for rate in rates]
return calculate_latest_rsi(closes, period)
```

- [ ] **Step 5: 运行测试，确认行为保持不变**

运行：`pytest tests/python/test_indicator_math.py tests/python/test_price_alerts.py -q`
预期：PASS

- [ ] **Step 6: 提交**

```bash
git add tests/python/test_indicator_math.py python_service/app/services/indicator_math.py python_service/app/services/indicator_service.py
git commit -m "refactor: remove dataframe usage from indicator math"
```

### Task 3: 用纯 Python 历史聚合 helper 替换 `pandas`

**Files:**
- Create: `tests/python/test_history_math.py`
- Create: `python_service/app/services/history_math.py`
- Modify: `python_service/app/services/history_service.py`

- [ ] **Step 1: 先写失败测试**

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

- [ ] **Step 2: 运行测试，确认它确实失败**

运行：`pytest tests/python/test_history_math.py -q`
预期：FAIL，并出现 `python_service.app.services.history_math` 的 `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现的 helper**

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

- [ ] **Step 4: 重构 `history_service.py`，把 MT5 namedtuple 转成 plain dict，并委托给 helper**

```python
from python_service.app.services.history_math import build_daily_aggregated_stats, calculate_closed_trade_profit

deals_dicts = [deal._asdict() for deal in deals]
return calculate_closed_trade_profit(deals_dicts)
```

- [ ] **Step 5: 仅在保证路由返回结构不变的前提下补全 helper，然后运行测试**

运行：`pytest tests/python/test_history_math.py tests/python/test_mt5_polling.py -q`
预期：PASS

- [ ] **Step 6: 提交**

```bash
git add tests/python/test_history_math.py python_service/app/services/history_math.py python_service/app/services/history_service.py
git commit -m "refactor: remove dataframe usage from history aggregation"
```

### Task 4: 收紧 Python 运行时依赖和 PyInstaller 产物

**Files:**
- Create: `python_service/requirements-dev.txt`
- Modify: `python_service/requirements.txt`
- Modify: `python_service/pyproject.toml`
- Modify: `python_service/mt5_service.spec`

- [ ] **Step 1: 先重建一次，确认当前后端仍然包含 `numpy` 和 `pandas`**

运行：`npm run build:python && npm run analyze:package-size`
预期：PASS，且 size report 中仍能看到 `numpy.libs`、`numpy` 和 `pandas` 位于最大后端条目里

- [ ] **Step 2: 拆分运行时依赖和开发依赖**

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

- [ ] **Step 3: 从 PyInstaller spec 中移除无用 hidden imports，并显式增加 excludes**

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

- [ ] **Step 4: 重新构建后端，并验证大块依赖已经消失**

运行：`npm run build:python && npm run analyze:package-size`
预期：PASS，且 top backend entries 中不再出现 `numpy.libs`、`numpy` 或 `pandas`

- [ ] **Step 5: 运行 Python 回归测试集**

运行：`pytest tests/python/test_indicator_math.py tests/python/test_history_math.py tests/python/test_settings.py tests/python/test_price_alerts.py -q`
预期：PASS

- [ ] **Step 6: 提交**

```bash
git add python_service/requirements.txt python_service/requirements-dev.txt python_service/pyproject.toml python_service/mt5_service.spec
git commit -m "build: trim python runtime dependencies"
```

### Task 5: 停止把 renderer-only npm 包原样塞进 `app.asar`

**Files:**
- Create: `scripts/audit-runtime-deps.mjs`
- Modify: `package.json`
- Modify: `package-lock.json`

- [ ] **Step 1: 运行一个不存在的运行时依赖审计脚本**

运行：`node scripts/audit-runtime-deps.mjs`
预期：FAIL，因为文件还不存在

- [ ] **Step 2: 创建审计脚本**

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

- [ ] **Step 3: 把 renderer-only 的包迁移到 `devDependencies`**

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

- [ ] **Step 4: 刷新 lockfile**

运行：`npm install`
预期：PASS，并更新 `package-lock.json`

- [ ] **Step 5: 运行依赖审计并重新打包**

运行：`node scripts/audit-runtime-deps.mjs && npm run build && npm run package:win && npm run analyze:package-size`
预期：PASS，且 `app.asar` 比当前 `31.57 MB` 基线明显更小

- [ ] **Step 6: 评审关卡**

运行：`@requesting-code-review`
预期：reviewer 聚焦依赖归类和打包回归风险

- [ ] **Step 7: 提交**

```bash
git add scripts/audit-runtime-deps.mjs package.json package-lock.json
git commit -m "build: stop shipping renderer-only runtime deps"
```

### Task 6: 对 renderer 做路由级 lazy loading 和 chunk 拆分

**Files:**
- Modify: `src/renderer/src/App.tsx`
- Modify: `electron.vite.config.ts`

- [ ] **Step 1: 记录当前 renderer 基线**

运行：`npm run build`
预期：PASS，且 `out/renderer/assets` 中仍然只有一个主导性的 JS 文件，大小约 `873.88 KB`

- [ ] **Step 2: 把 `App.tsx` 里的页面导入改成 lazy imports**

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

- [ ] **Step 3: 在 Vite 中增加 manual chunk 策略**

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

- [ ] **Step 4: 重建并验证最大 renderer chunk 已缩小**

运行：`npm run build`
预期：PASS，且 `out/renderer/assets` 出现多个 JS chunk；最大 chunk 小于原来的单文件基线

- [ ] **Step 5: 运行前端回归测试**

运行：`npm run test:frontend`
预期：PASS

- [ ] **Step 6: 评审关卡**

运行：`@requesting-code-review`
预期：reviewer 检查 lazy loading 的正确性和 chunk 配置的安全性

- [ ] **Step 7: 提交**

```bash
git add src/renderer/src/App.tsx electron.vite.config.ts
git commit -m "perf: split renderer pages and vendor chunks"
```

### Task 7: 如果前三步之后体积仍然偏大，再裁剪 Electron locales

**Files:**
- Create: `scripts/prune-packaged-locales.cjs`
- Modify: `package.json`
- Modify: `scripts/verify-packaging.ps1`

- [ ] **Step 1: 先判断这个任务是否还有必要**

运行：`npm run package:win && npm run analyze:package-size`
预期：如果安装包已经落到目标范围内，就跳过本任务剩余步骤；否则继续

- [ ] **Step 2: 创建 `afterPack` 钩子**

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

- [ ] **Step 3: 接入钩子并扩展打包验证**

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

- [ ] **Step 4: 重新打包并做冒烟测试**

运行：`npm run package:win && npm run verify:packaging && npm run test:electron`
预期：PASS，且安装包进一步缩小，同时不影响应用启动

- [ ] **Step 5: 提交**

```bash
git add scripts/prune-packaged-locales.cjs package.json scripts/verify-packaging.ps1
git commit -m "build: prune packaged electron locales"
```

### Task 8: 文档化体积预算和回归检查命令

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: 把新的打包体积工作流写进文档**

```md
1. Run `npm run build`
2. Run `npm run build:python`
3. Run `npm run package:win`
4. Run `npm run analyze:package-size`
```

- [ ] **Step 2: 记录预期热点和成功标准**

```md
- Python backend should no longer bundle `numpy` / `pandas`
- `package.json.dependencies` should only contain packages needed by `src/main` or `src/preload`
- Renderer output should not regress to a single dominant JS chunk
```

- [ ] **Step 3: 验证文档中的命令仍然和实际一致**

运行：`npm run analyze:package-size`
预期：PASS，且文档中写的命令名与实际脚本完全一致

- [ ] **Step 4: 提交**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: document package size workflow"
```

### 最终验证

- [ ] 运行：`pytest tests/python/test_indicator_math.py tests/python/test_history_math.py tests/python/test_price_alerts.py tests/python/test_settings.py -q`
  预期：PASS
- [ ] 运行：`npm run test:frontend`
  预期：PASS
- [ ] 运行：`npm run package:win && npm run verify:packaging && npm run analyze:package-size`
  预期：PASS，且报告显示安装包、更小的后端目录，以及更小的 `app.asar`
- [ ] 运行：`@requesting-code-review`
  预期：在合并前完成最终打包评审

### 预期结果

- Python 后端不再捆绑 `pandas` / `numpy`，优先移除当前已确认的最大体积来源
- `package.json.dependencies` 会收敛到真正被 Electron 运行时使用的依赖，而不是 renderer 的构建期库
- renderer 不再退化为单个主导性页面 chunk
- 最终安装包体积缩小有明确证据支撑，而不是凭猜测
- 未来体积回归可以通过 `npm run analyze:package-size` 和 `node scripts/audit-runtime-deps.mjs` 被及时发现
