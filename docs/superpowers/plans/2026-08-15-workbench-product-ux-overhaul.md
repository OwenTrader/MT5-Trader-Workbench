# MT5 Trader Workbench 全面产品化与交互体验重构实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MT5 Trader Workbench 从“功能生硬堆砌、17 个碎片化菜单、操作路径繁琐”的初级原型，重构为“4 大业务工作区聚合、交易员心智优先、操作链路短、状态感知透明、具备专业级操作质感”的现代化 MT5 桌面交易终端。

**Architecture:** 采用“场景化工作区聚合 + 统一状态流 + 快捷操作层”架构。将现存 17 个扁平菜单合并收敛为 4 个一级工作区（【交易工作台】、【智能告警中心】、【自动化与跟单】、【量化与复盘实验室】）+ 1 个【系统管理】。主工作台集成实时自选行情、当前持仓监控与一键平仓；告警中心四合一（价格/波动/指标/播报）；自动化中心融合账户池、跟单、同步与风控；量化实验室打通数据下载、策略调试、回测与内嵌分析。全局增加实时底栏与快捷指令（Command Palette）。

**Tech Stack:** Electron 30, React 18, TypeScript, Tailwind CSS 3.4, Zustand 4.5, shadcn/ui (Radix UI), TradingView Lightweight Charts 5.2, FastAPI, MetaTrader5 SDK, Vitest, Playwright, Pytest.

---

## 现状问题与产品诊断

1. **信息架构与导航崩塌（17 个扁平菜单严重碎片化）**：
   - 告警分散在 4 个页面（价格、波动、指标、播报），用户配置提醒需反复横跳。
   - 量化与数据分散在 5 个页面（账户列表、K线数据、复盘、实盘、回测），流程割裂。
   - 顶级菜单充斥着“赞助”等非核心功能，噪音极大。
2. **核心交易体验（Trading Cockpit）缺失**：
   - Dashboard 仅有几个静态数值卡片，无持仓明细、无自选行情、无一键平仓，无法作为交易常驻看板。
   - 悬浮窗 (Overlay) 与主工作台脱节，无法在主界面一键 Pin 品种到桌面。
3. **自动化与高风险功能缺乏状态感知与信任度**：
   - 跟单和同步缺少实时执行延迟、心跳检测和失败熔断状态展示。
   - 事件日志 (Event Log) 功能原始，无法按模块与级别进行过滤搜索。
4. **交互细节与响应效率低下**：
   - 缺少全局状态感知底栏（MT5 延迟、后端连接、跟单引擎状态）。
   - 缺少键盘快捷流（快捷切换、快速平仓、指令面板）。

---

## 全新产品信息架构（4 + 1 核心工作区）

```text
MT5 Trader Workbench
├── 📊 交易工作台 (Cockpit / Dashboard)
│   ├── 账户资产指标 & 实时盈亏走势
│   ├── 实时持仓监控 & 快捷平仓/止损止盈
│   ├── 自选行情监控板 (Watchlist) & 一键 Pin 到桌面悬浮窗
│   └── 快速行情简图 (Lightweight Charts)
│
├── 🔔 智能告警中心 (Alerts Hub - 四合一)
│   ├── 统一告警规则管理 (价格阈值 / 剧烈波动 / RSI指标 / 订单播报)
│   ├── 极速规则创建向导 (一键抓取市价 / 常用模板)
│   └── 推送通道与通知测试 (钉钉 / 企微 / 飞书 / 声音 / Toast)
│
├── 🤖 自动化与多账户跟单 (Automation & Risk Center)
│   ├── 统一账户池管理 (Account Registry)
│   ├── 本地多账户跟单 (Local Copy Trading - 关系/乘数/延迟监控)
│   ├── TopStep 跨平台订单同步 (Order Sync)
│   └── 账户风控与熔断保护 (Risk Control)
│
├── 📈 量化与复盘实验室 (Quant Lab & Review)
│   ├── K线历史数据同步中心 (Data Management)
│   ├── 策略工坊与实盘监控 (Python Strategy Runner)
│   ├── Backtrader 回测引擎与评估报告 (Quant Backtest)
│   ├── 历史 K 线步进复盘与模拟训练 (Trading Review)
│   └── 嵌入式 AI 综合技术分析报告 (Embedded Analysis)
│
└── ⚙️ 系统与日志中心 (System & Diagnostics)
    ├── 基础与连接设置 (MT5 路径 / 主题 / 语言 / 悬浮窗外观)
    ├── 全景系统与交易事件日志 (Unified Event Log)
    └── 帮助文档与关于支持 (User Guide & About / Sponsor)
```

---

## File Structure & Module Responsibilities

```text
src/renderer/src/
├── components/
│   ├── module-nav.tsx                    # [MODIFY] 4+1 分组的全新侧边栏导航组件
│   ├── command-palette.tsx               # [NEW] 全局快捷指令面板 (Ctrl+K)
│   ├── status-bar.tsx                    # [NEW] 底部全局状态与连接感知栏
│   ├── dashboard/
│   │   ├── status-card.tsx               # [MODIFY] 资产与运行状态卡片
│   │   ├── position-table.tsx            # [NEW] 实时持仓监控与一键平仓组件
│   │   └── watchlist-card.tsx            # [NEW] 自选行情板与桌面 Pin 联动
│   └── trading-chart.tsx                 # [MODIFY] 轻量图表组件适配
├── layouts/
│   └── workbench-shell.tsx               # [MODIFY] 包含顶部搜索、主体工作区与底栏
├── pages/
│   ├── dashboard-page.tsx                # [MODIFY] 重构后的专业交易主工作台
│   ├── alerts/
│   │   └── AlertsCenterPage.tsx          # [NEW] 四合一智能告警中心 (Tab 分组)
│   ├── automation/
│   │   └── AutomationCenterPage.tsx      # [NEW] 自动化、跟单、同步与风控矩阵
│   ├── quant/
│   │   └── QuantLabPage.tsx              # [NEW] 数据、策略、回测、复盘与AI分析中心
│   ├── SettingsPage.tsx                  # [MODIFY] 优化后的系统设置与关于页
│   └── EventLogPage.tsx                  # [MODIFY] 支持多维度过滤的全景日志页
├── stores/
│   ├── alerts-store.ts                   # [MODIFY] 整合告警管理逻辑
│   ├── dashboard-store.ts                # [MODIFY] 引入持仓与自选行情状态
│   └── automation-store.ts               # [NEW] 整合账户池、跟单与同步状态
├── i18n/
│   └── messages.ts                       # [MODIFY] 全面更新中英文文案体系
└── App.tsx                               # [MODIFY] 适配全新 4+1 路由架构
```

---

## 实施任务分解 (Task Decomposition)

### Task 1: 重构信息架构与 4+1 现代化侧边栏导航

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx`
- Modify: `src/renderer/src/App.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/module-nav.test.tsx`

- [ ] **Step 1: 编写导航组件单测，覆盖 4+1 分组高亮与路由跳转**
- [ ] **Step 2: 运行测试确保失败**
  `npm run test:frontend -- src/renderer/src/test/module-nav.test.tsx`
- [ ] **Step 3: 更新 `messages.ts`，增加 4+1 工作区的语义化双语字典**
- [ ] **Step 4: 改造 `module-nav.tsx`，将 17 个碎片项合并为【交易工作台】、【告警中心】、【自动化与跟单】、【量化实验室】、【系统与日志】**
- [ ] **Step 5: 改造 `App.tsx` 路由匹配规则与重定向兼容机制**
- [ ] **Step 6: 运行单测验证通过**
  `npm run test:frontend -- src/renderer/src/test/module-nav.test.tsx`
- [ ] **Step 7: 提交代码**
  `git commit -m "feat(nav): overhaul information architecture to 4+1 core workspaces"`

---

### Task 2: 打造四合一智能告警中心 (`AlertsCenterPage`)

**Files:**
- Create: `src/renderer/src/pages/alerts/AlertsCenterPage.tsx`
- Modify: `src/renderer/src/stores/alerts-store.ts`
- Test: `src/renderer/src/test/alerts-center-page.test.tsx`

- [ ] **Step 1: 编写 `AlertsCenterPage` 单元测试（支持切换价格/波动/指标/播报 Tab，支持统一批量启停）**
- [ ] **Step 2: 运行测试确保失败**
  `npm run test:frontend -- src/renderer/src/test/alerts-center-page.test.tsx`
- [ ] **Step 3: 实现 `AlertsCenterPage.tsx`，在一个精美卡片式界面中提供：**
  - 顶部全局指标：活跃规则总数、今日触发次数、通知通道健康状态。
  - Tabs 分页：`[价格到达告警]`、`[突发波动监控]`、`[RSI等技术指标]`、`[成交订单播报]`。
  - 右侧统一极速新建侧滑抽屉（Sheet）：支持一键填入 MT5 当前市价，选择告警动作与推送目标。
- [ ] **Step 4: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/alerts-center-page.test.tsx`
- [ ] **Step 5: 提交代码**
  `git commit -m "feat(alerts): unify 4 alert modules into streamlined AlertsCenterPage"`

---

### Task 3: 升级主交易工作台 (Cockpit)——集成持仓、自选表与悬浮窗联动

**Files:**
- Create: `src/renderer/src/components/dashboard/position-table.tsx`
- Create: `src/renderer/src/components/dashboard/watchlist-card.tsx`
- Modify: `src/renderer/src/pages/dashboard-page.tsx`
- Modify: `src/renderer/src/stores/dashboard-store.ts`
- Test: `src/renderer/src/test/dashboard-page.test.tsx`

- [ ] **Step 1: 编写持仓与自选表格组件的单元测试**
- [ ] **Step 2: 运行测试确认失败**
  `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
- [ ] **Step 3: 实现 `position-table.tsx`：**
  - 展示当前订单号、品种、方向 (Buy/Sell)、开仓价、现价、止损/止盈、实时浮动盈亏。
  - 支持快捷一键平仓按钮与二次确认防误触，支持头部“一键平所有仓位”。
- [ ] **Step 4: 实现 `watchlist-card.tsx`：**
  - 显示重点品种的实时 Bid/Ask/Spread。
  - 支持一键将品种 Pin 入桌面悬浮窗 (`overlay_config.json` 同步)。
  - 点击品种可即时切换右侧小型 K 线图表。
- [ ] **Step 5: 重构 `dashboard-page.tsx` 布局**：采用上部核心指标看板 + 中部自选与图表联动 + 下部实时持仓与挂单列表的专业 Trader 工作台布局。
- [ ] **Step 6: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
- [ ] **Step 7: 提交代码**
  `git commit -m "feat(dashboard): transform dashboard into full-featured trading cockpit"`

---

### Task 4: 构建自动化与跟单中心 (`AutomationCenterPage`)

**Files:**
- Create: `src/renderer/src/pages/automation/AutomationCenterPage.tsx`
- Modify: `src/renderer/src/stores/local-copy-trading-store.ts`
- Modify: `src/renderer/src/stores/account-management-store.ts`
- Test: `src/renderer/src/test/automation-center-page.test.tsx`

- [ ] **Step 1: 编写自动化中心单测（验证多账户接入、跟单拓扑与风控联动的正确性）**
- [ ] **Step 2: 运行测试确认失败**
  `npm run test:frontend -- src/renderer/src/test/automation-center-page.test.tsx`
- [ ] **Step 3: 实现 `AutomationCenterPage.tsx`，整合：**
  - `Tab 1: 账户池总览 (Account Pool)`：统一查看所有主从 MT5 账号连接状态、资产净值与延时。
  - `Tab 2: 本地跟单矩阵 (Local Copy Trading)`：主从绑定关系卡片、手数换算倍率规则、实时执行日志流与紧急停止开关。
  - `Tab 3: TopStep 同步 (Order Sync)`：MT5 至远程平台的同步状态、映射合约与安全执行确认。
  - `Tab 4: 风险控制与熔断 (Risk Guard)`：最大日亏损保护、最大持仓手数、回撤报警与强平规则配置。
- [ ] **Step 4: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/automation-center-page.test.tsx`
- [ ] **Step 5: 提交代码**
  `git commit -m "feat(automation): integrate accounts, copy trading, order sync, and risk control"`

---

### Task 5: 打造量化与复盘实验室 (`QuantLabPage`) 并内嵌 AI 分析

**Files:**
- Create: `src/renderer/src/pages/quant/QuantLabPage.tsx`
- Modify: `src/renderer/src/pages/TechnicalAnalysisPage.tsx`
- Modify: `src/renderer/src/stores/python-quant-store.ts`
- Test: `src/renderer/src/test/quant-lab-page.test.tsx`

- [ ] **Step 1: 编写量化实验室单元测试（涵盖数据管理、策略配置、回测执行与报告内嵌）**
- [ ] **Step 2: 运行测试确认失败**
  `npm run test:frontend -- src/renderer/src/test/quant-lab-page.test.tsx`
- [ ] **Step 3: 实现 `QuantLabPage.tsx`，形成研发完整闭环：**
  - `Tab 1: 数据中心 (Data Sync)`：本地 SQLite K线下载、覆盖区间可视条与一键补全。
  - `Tab 2: 策略运行 (Live Strategies)`：内置策略与用户目录策略列表、运行状态切换、独立实盘参数。
  - `Tab 3: 历史回测 (Backtest Engine)`：Backtrader 参数寻优、收益走势曲线、夏普与最大回撤指标卡。
  - `Tab 4: 手工复盘演练 (Trading Review)`：历史 K 线步进播放器与模拟操盘控制。
  - `Tab 5: AI 技术分析 (Market Insight)`：直接在应用内嵌渲染多周期波浪与 SMC 分析报告（无需跳转外部浏览器）。
- [ ] **Step 4: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/quant-lab-page.test.tsx`
- [ ] **Step 5: 提交代码**
  `git commit -m "feat(quant): create unified QuantLabPage with embedded AI report renderer"`

---

### Task 6: 增加全局状态底栏 (StatusBar) 与快捷指令面板 (Command Palette)

**Files:**
- Create: `src/renderer/src/components/status-bar.tsx`
- Create: `src/renderer/src/components/command-palette.tsx`
- Modify: `src/renderer/src/layouts/workbench-shell.tsx`
- Test: `src/renderer/src/test/status-bar.test.tsx`

- [ ] **Step 1: 编写底栏与快捷指令面板的单元测试**
- [ ] **Step 2: 运行测试确认失败**
  `npm run test:frontend -- src/renderer/src/test/status-bar.test.tsx`
- [ ] **Step 3: 实现 `status-bar.tsx`**：常驻底部，实时展示 MT5 终端状态与心跳 Ping、WebSocket 推流状态、当前后台活跃跟单任务数、当前系统时间与快捷帮助入口。
- [ ] **Step 4: 实现 `command-palette.tsx`**：按 `Ctrl+K` 或点击顶部搜索框唤起，支持拼音与英文模糊搜索快速跳转任意工作区、一键切换语言、一键打开悬浮窗、一键重连 MT5 等快捷操作。
- [ ] **Step 5: 集成至 `workbench-shell.tsx`**。
- [ ] **Step 6: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/status-bar.test.tsx`
- [ ] **Step 7: 提交代码**
  `git commit -m "feat(shell): add global status bar and Ctrl+K command palette"`

---

### Task 7: 优化全景事件日志 (`EventLogPage`) 与系统设置页面

**Files:**
- Modify: `src/renderer/src/pages/EventLogPage.tsx`
- Modify: `src/renderer/src/pages/SettingsPage.tsx`
- Test: `src/renderer/src/test/event-log-page.test.tsx`

- [ ] **Step 1: 编写事件日志多维过滤测试**
- [ ] **Step 2: 运行测试确认失败**
  `npm run test:frontend -- src/renderer/src/test/event-log-page.test.tsx`
- [ ] **Step 3: 改造 `EventLogPage.tsx`**：增加模块筛选器（跟单/同步/告警/量化/系统）、级别筛选器（Info/Warn/Error）、搜索框、自动滚动锁定与一键导出功能。
- [ ] **Step 4: 精简 `SettingsPage.tsx`**：优化标签页分组，将开发者赞助与社区支持融入【关于与支持】标签，清理无用表单项，提升表单视觉层级。
- [ ] **Step 5: 运行测试验证通过**
  `npm run test:frontend -- src/renderer/src/test/event-log-page.test.tsx`
- [ ] **Step 6: 提交代码**
  `git commit -m "feat(system): polish unified event log filters and refined settings page"`

---

### Task 8: 全面回归测试、构建验证与 GUIDE.md 同步

**Files:**
- Modify: `GUIDE.md`
- Test: All tests

- [ ] **Step 1: 运行前端全量单元与组件测试**
  `npm run test:frontend`
- [ ] **Step 2: 运行 Python 后端全量测试**
  `pytest tests/python`
- [ ] **Step 3: 执行 Electron 打包构建验证**
  `npm run build`
- [ ] **Step 4: 运行 `check_guide_tree.py` 确保目录树与文档完全一致**
  `python .agents/skills/project-guide/scripts/check_guide_tree.py`
- [ ] **Step 5: 最终提交**
  `git commit -m "chore(release): complete comprehensive UX overhaul and update project guide"`

---

## 验证与验收指标 (Acceptance Criteria)

1. **导航项精简率**：一级菜单从 **17 个骤降至 5 个**，层级清晰无冗余。
2. **操作链路缩短**：
   - 告警创建：从原来在 4 个页面寻找对应告警，转变为在统一告警中心 1 次点击内完成模板选择与市价创建。
   - 交易监控：在 Dashboard 主页即可直接掌握账户资产、自选报价、当前持仓与一键平仓，无需跳转。
   - 跟单排查：在自动化中心一屏掌握多账户连通性、主从关系、跟单延迟与风控状态。
3. **测试覆盖**：所有新增与重构的页面与组件通过 `npm run test:frontend`，Python 测试全绿，`check_guide_tree.py` 验证 0 误差。
