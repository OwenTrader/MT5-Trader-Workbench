# MT5 Trader Workbench

[English README](./README.md)

MT5 Trader Workbench 是一个面向 Windows 的桌面交易辅助工具，基于 Electron、React 与本地 FastAPI 服务构建。它连接 MetaTrader 5，将实时监控、预警、价格浮窗、订单统计和技术分析整合到同一工作台中。

## 功能概览

- 工作台总览，可查看 MT5 连接状态、余额、净值、盈亏和保证金比例
- 一键启动或重连 MT5，并可快速开启或关闭桌面价格浮窗
- 通过 WebSocket 推送实时行情的独立浮窗
- 支持自定义浮窗品种列表、字体大小、字体颜色、固定位置与显示状态
- 价格预警管理，支持新增、编辑、暂停、恢复、重置和删除
- 保存价格预警前，会结合 MT5 当前价格进行后端校验
- 波动检测，支持按交易品种、阈值和时间窗口配置规则
- 指标预警，支持技术条件监控，当前包含 RSI 规则
- 预警触发时支持桌面通知与提示音
- 订单中心，提供当日、本周、本月盈亏概览
- 历史订单日统计，并支持按日期区间查询
- 技术分析入口，可生成报告并使用系统默认浏览器打开
- 设置模块，支持 MT5 路径、主题、界面语言、自动连接、刷新频率、浮窗选项、音效选项和钉钉 Bot 凭据配置
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
- `Settings`：应用、浮窗、音效与 Bot 配置
- `Order Broadcast`：界面中已预留，当前仍在开发中

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

## 说明

- 该应用围绕本地 MT5 环境和 Windows 桌面使用场景设计。
- 当前部分模块仍保持轻量实现，例如 `Risk Control`。
- `Order Broadcast` 已出现在导航中，但尚未完成。
