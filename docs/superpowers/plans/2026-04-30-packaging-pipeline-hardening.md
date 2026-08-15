# Packaging Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Windows 打包链路，确保 Electron 安装包始终包含本次构建的 `mt5_service.exe`，并移除重复、易错的 Python 打包配置。

**Architecture:** 方案收敛为单一 Python spec、单一 Python 输出目录、单一 Electron 打包入口。先把后端产物路径解析独立成可测试 helper，再把 `package.json` 脚本和校验脚本接入打包流程，最后补齐 Python 依赖声明与文档，并用哈希校验确认安装包内的 `mt5_service.exe` 确实来自本次构建。

**Tech Stack:** Electron, electron-builder, electron-vite, PyInstaller, TypeScript, Vitest, PowerShell, npm

---

**File Structure**

- Modify: `package.json`
  - 增加 `build:python`、`verify:packaging`，并让 `package:win` 串联完整流程
- Modify: `src/main/python-service.ts`
  - 改为调用独立的打包路径 helper
- Modify: `src/main/python-service.test.ts`
  - 补打包后端路径解析测试
- Create: `src/main/packaging-paths.ts`
  - 统一封装打包后端目录与 exe 路径
- Create: `src/main/packaging-paths.test.ts`
  - 覆盖打包路径 helper
- Modify: `python_service/mt5_service.spec`
  - 作为唯一 PyInstaller spec，补齐 datas、hiddenimports、无控制台配置
- Delete: `mt5_service.spec`
  - 删除重复 spec，消除双入口
- Modify: `python_service/pyproject.toml`
  - 与实际运行依赖对齐
- Modify: `python_service/requirements.txt`
  - 与 `pyproject.toml` 对齐
- Create: `scripts/check-python-deps.ps1`
  - 结构化检查 Python 依赖声明是否对齐
- Create: `scripts/verify-packaging.ps1`
  - 检查 Python 产物存在且 Electron 配置引用正确目录
- Modify: `README.md`
  - 更新英文打包说明
- Modify: `README.zh-CN.md`
  - 更新中文打包说明

### Task 1: 提取统一的后端打包路径 helper

**Files:**
- Create: `src/main/packaging-paths.ts`
- Create: `src/main/packaging-paths.test.ts`
- Modify: `src/main/python-service.ts`
- Modify: `src/main/python-service.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest'
import { getPackagedBackendExecutablePath, getPackagedBackendWorkingDirectory } from './packaging-paths'

describe('packaging paths', () => {
  it('builds packaged backend paths from resources path', () => {
    expect(getPackagedBackendWorkingDirectory('C:/app/resources')).toBe('C:/app/resources/mt5_service')
    expect(getPackagedBackendExecutablePath('C:/app/resources')).toBe('C:/app/resources/mt5_service/mt5_service.exe')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/main/packaging-paths.test.ts`
Expected: FAIL with module not found

- [ ] **Step 3: Write minimal implementation**

```ts
import path from 'node:path'

export function getPackagedBackendWorkingDirectory(resourcesPath: string): string {
  return path.join(resourcesPath, 'mt5_service')
}

export function getPackagedBackendExecutablePath(resourcesPath: string): string {
  return path.join(getPackagedBackendWorkingDirectory(resourcesPath), 'mt5_service.exe')
}
```

- [ ] **Step 4: Refactor `python-service.ts` to use the helper**

```ts
const backendWorkingDirectory = app.isPackaged
  ? getPackagedBackendWorkingDirectory(process.resourcesPath)
  : app.getAppPath()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm run test:frontend -- src/main/packaging-paths.test.ts src/main/python-service.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/main/packaging-paths.ts src/main/packaging-paths.test.ts src/main/python-service.ts src/main/python-service.test.ts
git commit -m "refactor: centralize packaged backend paths"
```

### Task 2: 统一 Python 打包 spec 为单一入口

**Files:**
- Modify: `python_service/mt5_service.spec`
- Delete: `mt5_service.spec`

- [ ] **Step 1: Inspect the current duplicate specs**

Run: `git diff --no-index -- "mt5_service.spec" "python_service/mt5_service.spec"`
Expected: shows meaningful differences in `datas`, `hiddenimports`, and `console`

- [ ] **Step 2: Update the surviving spec minimally**

```python
a = Analysis(
    ['app\\main.py'],
    pathex=['.'],
    datas=[('app', 'app')],
    hiddenimports=['numpy', 'numpy._core', 'numpy._core.multiarray', 'numpy.core', 'pandas', 'pydantic', 'MetaTrader5'],
)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mt5_service',
    console=False,
)
```

- [ ] **Step 3: Delete the duplicate root spec**

Delete: `mt5_service.spec`

- [ ] **Step 4: Rebuild to verify the canonical spec works**

Run from `python_service/`: `pyinstaller --noconfirm "mt5_service.spec" --distpath "dist" --workpath "build"`
Expected: PASS and writes `python_service/dist/mt5_service/mt5_service.exe`

- [ ] **Step 5: Commit**

```bash
git add python_service/mt5_service.spec mt5_service.spec
git commit -m "build: consolidate python service spec"
```

### Task 3: 把 Python 构建接入 npm 打包链路

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Inspect current npm scripts**

Run: `npm pkg get scripts`
Expected: output does not include `build:python`

- [ ] **Step 2: Add the minimal scripts**

```json
{
  "scripts": {
    "build:python": "pyinstaller --noconfirm \"python_service/mt5_service.spec\" --distpath \"python_service/dist\" --workpath \"python_service/build\"",
    "package:win": "npm run build && npm run build:python && electron-builder --win"
  }
}
```

- [ ] **Step 3: Run the new build command**

Run: `npm run build:python`
Expected: PASS and updates `python_service/dist/mt5_service/mt5_service.exe`

- [ ] **Step 4: Commit**

```bash
git add package.json
git commit -m "build: add python packaging script"
```

### Task 4: 增加 Python 依赖一致性检查

**Files:**
- Create: `scripts/check-python-deps.ps1`
- Modify: `python_service/pyproject.toml`
- Modify: `python_service/requirements.txt`

- [ ] **Step 1: Verify the scripts directory exists**

Run: `ls scripts`
Expected: FAIL because the directory does not exist yet

- [ ] **Step 2: Create the scripts directory**

Run: `mkdir scripts`
Expected: PASS

- [ ] **Step 3: Write the failing dependency check script**

```powershell
$pyproject = Get-Content "python_service/pyproject.toml" -Raw
$requirements = Get-Content "python_service/requirements.txt" | Where-Object { $_ -and -not $_.StartsWith('#') }

$dependencyBlock = [regex]::Match($pyproject, 'dependencies\s*=\s*\[(?<items>.*?)\]', 'Singleline').Groups['items'].Value
if (-not $dependencyBlock) { throw 'pyproject.toml missing dependencies block' }

$normalize = {
  param([string]$name)
  return (($name -split '[<>=!~;\[]')[0]).Trim().ToLowerInvariant()
}

$pyprojectDeps = [regex]::Matches($dependencyBlock, '"([^"]+)"') | ForEach-Object { & $normalize $_.Groups[1].Value }
$requirementsDeps = $requirements | ForEach-Object { & $normalize $_ }
$missingFromPyproject = $requirementsDeps | Where-Object { $_ -notin $pyprojectDeps }
$missingFromRequirements = $pyprojectDeps | Where-Object { $_ -notin $requirementsDeps }

if ($missingFromPyproject.Count -gt 0) { throw "pyproject.toml missing: $($missingFromPyproject -join ', ')" }
if ($missingFromRequirements.Count -gt 0) { throw "requirements.txt missing: $($missingFromRequirements -join ', ')" }
```

- [ ] **Step 4: Run check to verify it fails**

Run: `pwsh -File scripts/check-python-deps.ps1`
Expected: FAIL with missing dependency error

- [ ] **Step 5: Add the missing runtime dependencies without dropping existing ones**

```toml
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "MetaTrader5",
    "pytest",
    "httpx",
    "pandas",
    "numpy",
]
```

```txt
fastapi
uvicorn
pydantic
MetaTrader5
pytest
httpx
pandas
numpy
```

- [ ] **Step 6: Run check to verify it passes**

Run: `pwsh -File scripts/check-python-deps.ps1`
Expected: PASS with no output

- [ ] **Step 7: Commit**

```bash
git add scripts/check-python-deps.ps1 python_service/pyproject.toml python_service/requirements.txt
git commit -m "build: align python dependency manifests"
```

### Task 5: 增加打包前校验脚本

**Files:**
- Create: `scripts/verify-packaging.ps1`
- Modify: `package.json`

- [ ] **Step 1: Inspect the current packaging configuration**

Run: `npm pkg get build.extraResources`
Expected: output includes the `mt5_service` resource entry, but there is no dedicated verification script yet

- [ ] **Step 2: Write the minimal verification script**

```powershell
$exe = "python_service/dist/mt5_service/mt5_service.exe"
if (-not (Test-Path $exe)) { throw "Missing Python backend artifact: $exe" }

$packageJson = Get-Content "package.json" -Raw | ConvertFrom-Json
$resourceEntry = $packageJson.build.extraResources | Where-Object { $_.to -eq 'mt5_service' }
if (-not $resourceEntry) { throw 'Missing extraResources entry for mt5_service' }
if ($resourceEntry.from -ne 'python_service/dist/mt5_service') { throw 'Electron extraResources path is not aligned with python output path' }

Get-Item $exe | Select-Object FullName, Length, LastWriteTime
```

- [ ] **Step 3: Chain it into npm scripts**

```json
{
  "scripts": {
    "verify:packaging": "pwsh -File scripts/verify-packaging.ps1",
    "package:win": "npm run build && npm run build:python && npm run verify:packaging && electron-builder --win"
  }
}
```

- [ ] **Step 4: Run verification**

Run: `npm run verify:packaging`
Expected: PASS and prints the Python artifact metadata

- [ ] **Step 5: Commit**

```bash
git add scripts/verify-packaging.ps1 package.json
git commit -m "build: verify packaging inputs before installer build"
```

### Task 6: 更新打包文档

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Add explicit packaging commands**

```md
- `npm run build:python`: rebuilds `python_service/dist/mt5_service/mt5_service.exe`
- `npm run verify:packaging`: verifies the Python backend artifact and Electron resource path before Windows packaging
- `npm run package:win`: rebuilds Electron, rebuilds Python backend, verifies packaging inputs, then creates the Windows installer
```

- [ ] **Step 2: Add the single-spec rule**

```md
Use only `python_service/mt5_service.spec` for backend packaging. Do not build from the deprecated root `mt5_service.spec`.
```

- [ ] **Step 3: Review docs for stale references**

Run: `rg "mt5_service.spec|python_service/dist/mt5_service|package:win" README.md README.zh-CN.md`
Expected: only current instructions remain

- [ ] **Step 4: Commit**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: document canonical packaging workflow"
```

### Task 7: 运行单元测试验收

**Files:**
- Test: `src/main/packaging-paths.test.ts`
- Test: `src/main/python-service.test.ts`

- [ ] **Step 1: Run targeted tests**

Run: `npm run test:frontend -- src/main/packaging-paths.test.ts src/main/python-service.test.ts`
Expected: PASS

- [ ] **Step 2: Commit if any test-only fix was needed**

```bash
git add src/main/packaging-paths.test.ts src/main/python-service.test.ts
git commit -m "test: finalize packaging pipeline coverage"
```

### Task 8: 运行构建验收

**Files:**
- Modify only if verification finds a real defect during packaging

- [ ] **Step 1: Rebuild Python backend**

Run: `npm run build:python`
Expected: PASS

- [ ] **Step 2: Build Windows installer**

Run: `npm run package:win`
Expected: PASS

- [ ] **Step 3: Verify unpacked installer resources**

Run: `$source = Get-FileHash "python_service/dist/mt5_service/mt5_service.exe"; $packaged = Get-FileHash "dist/win-unpacked/resources/mt5_service/mt5_service.exe"; if ($source.Hash -ne $packaged.Hash) { throw 'Packaged backend exe does not match the freshly built artifact' }`
Expected: PASS with no output

- [ ] **Step 4: Commit only if packaging verification required a code fix**

```bash
git add package.json python_service/mt5_service.spec scripts/verify-packaging.ps1 src/main/packaging-paths.ts src/main/python-service.ts README.md README.zh-CN.md
git commit -m "build: finalize packaging pipeline hardening"
```

---

**Notes**
- DRY: 一套 spec、一套输出路径、一套 npm 打包入口。
- YAGNI: 不引入安装器自定义脚本或额外 release 基础设施。
- TDD: 只对真正适合测试驱动的路径解析和依赖校验做红绿循环。
- Frequent commits: 每个任务单独提交；如果某个验收任务没有代码变更，就不创建空提交。
