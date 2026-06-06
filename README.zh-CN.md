# MT5 Trader Workbench

[English README](./README.md)

MT5 Trader Workbench 是一个面向 Windows 的桌面交易辅助工具，基于 Electron、React 与本地 FastAPI 服务构建。它连接 MetaTrader 5，将实时监控、预警、价格浮窗、订单统计和技术分析整合到同一工作台中。

## 功能概览

- 工作台总览，可查看 MT5 连接状态、余额、净值、盈亏和保证金比例
- 一键启动或重连 MT5，并可快速开启或关闭桌面价格浮窗
- 通过 WebSocket 推送实时行情的独立浮窗
- 支持自定义浮窗品种列表、字体大小、字体颜色、固定位置与显示状态
- 价格预警管理，支持新增、编辑、暂停、恢复、重置和删除
- 常用价格预警模板，可预填表单但不会自动创建规则
- 保存价格预警前，会结合 MT5 当前价格进行后端校验
- 波动检测，支持按交易品种、阈值和时间窗口配置规则
- 指标预警，支持技术条件监控，当前包含 RSI 规则
- 预警触发时支持桌面通知与提示音
- 订单中心，提供当日、本周、本月盈亏概览和日级复盘指标
- 历史订单日统计，并支持按日期区间查询
- 轻量事件日志，汇总当前可读取的本地跟单和订单同步事件
- 订单广播、订单同步、本地跟单页面带有高风险流程边界提示
- Python Quant 模块，用于绑定 MT5 账户的实时策略任务分配、运行状态查看、手动行情回填，以及共享策略发现
- Quant Backtest 模块，用于基于同一 MT5 账户池、共享策略注册表和本地缓存行情执行历史回测
- 技术分析入口，可生成报告并使用系统默认浏览器打开
- 设置模块，支持 MT5 路径、主题、界面语言、自动连接、刷新频率、浮窗选项、音效选项，以及钉钉、企业微信、飞书 Bot 凭据配置
- 配置迁移说明和敏感信息保护提示，覆盖本地设置、API Key、webhook/token 等信息
- 系统托盘集成，可快速显示主窗口、切换浮窗、退出应用
- 单实例桌面应用行为，并支持关闭主窗口后最小化到托盘
- 本地 FastAPI 后端提供健康检查、设置持久化、MT5 集成、预警、通知、历史数据、浮窗状态和数据流服务
- 前端使用 Vitest，Electron 端提供 Playwright 冒烟测试

## 模块

- `Dashboard`：工作台概览与快捷操作
- `Price Alerts`：价格阈值预警
- `Volatility`：剧烈波动监控
- `Indicator Alerts`：技术指标条件预警
- `Risk Control`：账户与阈值表单区域
- `Order Center`：绩效概览与日统计
- `Technical Analysis`：一键生成技术分析报告
- `Order Broadcast`：仅发送订单行为通知的广播规则
- `Order Sync`：MT5 到 TopStep 的同步配置与记录
- `Account List`：独立账户相关流程共用的 MT5 账户清单
- `Local Copy Trading`：主账户、跟单账户、关系映射和近期事件
- `Python Quant`：实时 Python 策略分配、运行控制、手动回填、本地 SQLite 行情缓存，以及用户策略目录
- `Quant Backtest`：复用同一账户池、策略列表和缓存行情的历史回测页面
- `Event Log`：来自同步相关模块的当前可用近期事件上下文
- `Settings`：连接、显示、通知和产品信息设置

## 技术栈

- Electron
- React
- TypeScript
- Vite
- Tailwind CSS
- Zustand
- FastAPI
- Uvicorn
- Pydantic
- MetaTrader5 Python SDK
- Vitest
- Playwright

## 项目结构

```text
.
|-- src/
|   |-- main/                # Electron 主进程
|   |-- preload/             # Electron 预加载桥接
|   `-- renderer/src/        # React 渲染层界面
|-- python_service/
|   `-- app/                 # FastAPI 路由、模型和服务
|-- resources/               # 图标与音频资源
|-- tests/                   # Electron 测试
`-- docs/                    # 内部计划与说明
```

## 开发

安装 Node.js 依赖：

```bash
npm install
```

安装 Python 后端依赖，Windows 打包所需的 `PyInstaller` 也包含在内：

```bash
python -m pip install -r python_service/requirements.txt
```

启动开发环境：

```bash
npm run dev
```

项目同时包含位于 `python_service/` 的 Python 后端。Electron 主进程会启动本地后端服务，并等待其在 `8765` 端口上通过健康检查。

## 常用脚本

- `npm run dev`：启动 Electron + Vite 开发流程
- `npm run build`：构建应用
- `npm run build:python`：通过 `python -m PyInstaller` 重新生成 `python_service/dist/mt5_service/mt5_service.exe`
- `npm run verify:packaging`：在 Windows 打包前校验后端目录、`mt5_service.exe`、`_internal` 运行时文件以及 Electron 资源路径
- `npm run package:win`：先重建 Electron，再重建 Python 后端，校验打包输入，自动递增本地 build 号，最后生成类似 `MT5 Trader Workbench Setup 1.0.0.1.exe` 的 Windows 安装包。打包脚本会使用仓库内的 `.cache/electron-builder` 作为本地缓存目录，并在可用时优先从 `C:\Users\Administrator\AppData\Local\electron-builder\Cache` 预热 `winCodeSign` 和 `nsis`，避免再次下载这些打包工具。
- `npm run test:frontend`：运行前端测试
- `npm run test:electron`：运行 Electron 冒烟测试
- `npm run test`：运行全部已配置测试

后端打包只使用 `python_service/mt5_service.spec`。不要再从已废弃的根目录 `mt5_service.spec` 发起构建。
本地打包计数保存在 `.build-version.json`，该文件已加入 git ignore。

## 后端能力

当前内置本地后端包含以下能力：

- 健康检查
- 设置读取与保存
- MT5 状态、启动、账户、持仓与路径验证
- 价格、波动、指标预警的增删改查
- 通知测试接口
- 历史概览与日统计
- 浮窗状态与导入导出
- 技术分析报告生成
- 基于 WebSocket 的浮窗行情推送
- 订单同步配置与运行记录
- 本地跟单配置与近期事件
- Python Quant 概览、实时任务生命周期控制与本地行情回填
- Quant Backtest 策略列表与回测执行

## Python Quant 与 Quant Backtest 说明

- `Account List` 是 `Python Quant` 实时分配和 `Quant Backtest` 回测共用的 MT5 账户来源。
- `Python Quant` 仅负责实时策略分配、运行状态、启动/停止控制和手动行情回填。
- `Quant Backtest` 仅负责历史回测，不会修改实时量化任务。
- 本地行情缓存位于 `storage/python_quant/market_data.sqlite3`。
- 量化任务持久化文件位于 `storage/python_quant/jobs.json`。
- 内置策略从 `python_service/app/quant/strategies/` 加载。
- 用户自定义策略在开发环境下从 `storage/python_quant/strategies/` 发现；打包后则从应用用户数据目录下的 `storage/python_quant/strategies/` 发现。
- `Python Quant` 与 `Quant Backtest` 共用由内置策略目录和用户策略目录合并得到的策略列表。
- 每个用户策略文件都需要定义 `STRATEGY_ID`、`STRATEGY_NAME`、`STRATEGY_DESCRIPTION`、`SUPPORTED_TIMEFRAMES` 和 `Strategy`。
- 当前内置示例策略为 `sma_cross`，打包后的后端包含该内置策略模块。
- 即使新增了量化模块，Python 测试仍然使用 `pytest tests/python`。

## 说明

- 该应用围绕本地 MT5 环境和 Windows 桌面使用场景设计。
- 交易相关自动化页面包含安全边界提示，因为通知和同步行为容易被误解为执行保证。
- `Event Log` 是基于当前可读取数据的轻量事件视图，不是完整持久化审计日志。
- 完整应用配置导入/导出尚未实现；设置页目前提供手动迁移路径说明，而不是暴露不可用行为。
