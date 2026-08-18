# Windows 安装体验与向导流程优化实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 Windows 安装包体验，将原本的一键静默安装升级为专业可交互的 NSIS 安装向导，支持自由选择安装目录、自定义创建桌面与开始菜单快捷方式、防多开进程冲突检测以及卸载时保护用户数据。

**Architecture:**
- **Electron-Builder NSIS Config (`package.json`)**: 显式声明 `win` 与 `nsis` 配置，开启多步向导模式 (`oneClick: false`)、允许自定义安装目录 (`allowToChangeInstallationDirectory: true`)、开启快捷方式配置与安装完成自启。
- **Custom NSIS Extension Script (`resources/installer.nsh`)**: 提供安装前与卸载前进程检测宏（`customInit` 与 `customUnInstall`），防止旧版本应用或后台 `mt5_service.exe` 进程占用导致的文件写入/删除失败。
- **Packaging Pipeline Verification (`scripts/verify-packaging.ps1`)**: 自动化校验 `package.json` 的 NSIS 配置项完整性与所需安装包资源文件存在性。
- **Automated Tests (`src/main/packaging-config.test.ts`)**: 自动化单元测试验证安装包配置规范。

---

## File Structure & Proposed Changes

| Action | Path | Description |
| :--- | :--- | :--- |
| **[NEW]** | `resources/installer.nsh` | Custom NSIS macro script for process watchdog and cleanup hooks |
| **[NEW]** | `src/main/packaging-config.test.ts` | Unit tests for NSIS installer configuration properties |
| **[MODIFY]** | `package.json` | Configure `win` target, explicit `nsis` options (custom directory, shortcuts, branding) |
| **[MODIFY]** | `scripts/verify-packaging.ps1` | Add verification checks for NSIS wizard configuration and icon assets |
| **[MODIFY]** | `README.md` & `README.zh-CN.md` | Document the new interactive installation wizard features |
| **[MODIFY]** | `GUIDE.md` | Synchronize architecture tree with new files |

---

## Bite-Sized Implementation Tasks

### Task 1: NSIS Configuration & Custom Installer Script

**Files:**
- Create: `resources/installer.nsh`
- Create: `src/main/packaging-config.test.ts`
- Modify: `package.json`

- [x] **Step 1: Write unit tests in `src/main/packaging-config.test.ts`**
- [x] **Step 2: Create `resources/installer.nsh`**
- [x] **Step 3: Update `package.json` build configuration**
- [x] **Step 4: Run Vitest to verify `packaging-config.test.ts` passes**

---

### Task 2: Packaging Verification Script & Dry-Run Testing

**Files:**
- Modify: `scripts/verify-packaging.ps1`

- [x] **Step 1: Update `scripts/verify-packaging.ps1`**
- [x] **Step 2: Run dry-run verification**

---

### Task 3: Documentation & Architecture Guide Sync

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `GUIDE.md`

- [x] **Step 1: Update `README.md` and `README.zh-CN.md`**
- [x] **Step 2: Run `check_guide_tree.py` and synchronize `GUIDE.md`**
- [x] **Step 3: Run full automated test suites**
