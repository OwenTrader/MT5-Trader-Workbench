# TODOs — 遗留项与待做项

> 来源：2026-10 全项目审计（81 条发现，见 `docs/superpowers/plans/2026-10-01-project-review-and-roadmap.md`）及后续六轮修复会话。
> 状态基线：Python 360/360、前端 131/131、typecheck/lint 零问题、push/PR CI 已生效。

## 一、遗留项（需要外部资源或产品决策）

- [ ] **安装包代码签名**：需购买证书。当前 `CSC_IDENTITY_AUTO_DISCOVERY=false` 主动关闭签名，安装包会被 SmartScreen 拦截。涉及 `package.json` build 段、`scripts/package-win.cjs`、`release.yml`。
- [ ] **跟单事件动态消息全文本地化**：`SyncEvent.code` 已埋点（12 种稳定码），但含动态内容（品种/手数/ID）的消息需后端补充 `params` 字典 + 前端 `t(code, params)` 模板才能全文本地化。涉及 `python_service/app/local_copy_trading/*`、`src/renderer/src/pages/LocalCopyTradingPage.tsx`。
- [ ] **Node 版本对齐**：本机 v24 vs CI node-version 20（`ci.yml`/`release.yml`）。当前套件在 24 上全绿，但 vitest 1.6.1 官方不支持 24——建议统一 Node 20 LTS 或升级 vitest 2/3 系后同步 CI。

## 二、待做 — 后端（python_service）

- [ ] 回测初始资金参数化：`quant/backtest_service.py` 的 `INITIAL_EQUITY = 10_000.0` 仍为常量，未暴露为 `run_backtest` 参数（PnL 已计入合约乘数 ✅）。
- [ ] `db/__init__.py` 在 import 时执行 `init_db` 副作用，应移到 lifespan。
- [ ] `routes/mt5.py`：`/mt5/status` 每次调用跑两遍 `tasklist`（结果应缓存 1-2s）；`verify_alert` 的 `symbol_info/symbol_info_tick` 在锁外直呼全局 mt5。
- [ ] `notifier_service`：三个 webhook 函数各自新建 `AsyncClient`，应模块级复用并显式 `timeout=3s`（并发+8s 上限已做 ✅）。
- [ ] quant 事件日志进一步分级：`signal_generated` 可只留内存、仅 `order_sent`/`strategy_error` 落盘（当前是全量截断至 1000 条 ✅，但写放大仍在）。
- [ ] simulated 源账户注入假 XAUUSD 样例持仓（`source_adapter.py`）：与真实跟单账户组合时报 "copy volume must be greater than 0"，报错不可理解——验证并给出清晰错误或文档说明（UX 审计"待验证"项）。

## 三、待做 — 前端（src/renderer + src/main）

- [ ] dashboard 页对 5 个 store 全量解构订阅（无 selector），每 2 秒无条件全页重渲染；in-flight 守卫已加 ✅，selector 化 + `zustand/shallow` 未做（`dashboard-page.tsx`）。
- [ ] PythonQuantPage overview N+1 拉取每个 job 的 events，失败静默吞空（`PythonQuantPage.tsx` ~441）：应改后端批量端点或按 id 增量拉取。
- [ ] 关系创建时源账户品种存在性校验：品种自由文本拼错 → 永不匹配持仓且零事件零警告的静默失败（`LocalCopyTradingPage.tsx` 表单）。
- [ ] 事件表筛选/分页：仅显示最近 100 条，无状态/关系过滤（`LocalCopyTradingPage.tsx`）；事件表未展示跟单侧 `follower_position_id`。
- [ ] `last_error` 为单条瞬时值，成功一个 tick 即清除：应显示"最近错误 + 时间"而非"当前错误"（后端 `runtime` 状态 + 前端展示）。
- [ ] `<html lang="en">` 写死，应随语言切换 `document.documentElement.lang`（`index.html` + `I18nProvider`）。
- [ ] 启动闪屏硬编码中文"正在启动 MT5 交易终端服务…"（`src/main/index.ts` ~369），英文用户首屏见中文。
- [ ] `dialog:openFile` 把渲染层 `...options` 原样透传 `showOpenDialog` 且用 `mainWindow!` 非空断言（`src/main/index.ts` ~306）：应白名单字段 + 判空。
- [ ] 轮询间隔不可调：后端已支持 `poll_interval_seconds`，UI 只读展示（`LocalCopyTradingPage.tsx`）。
- [ ] 启动 reconcile 在 `enabled=False` 时也会连接所有 follower 终端（`local_copy_trading/loop.py` 启动段）——按需延迟到首次启用。
- [ ] WatchlistCard "共 6 个监控品种" 的 6 是字面量，应来自实际监控列表长度。

## 四、待做 — 工程 / CI / 文档

- [ ] ESLint 排除 `*.cjs`/`*.config.ts`，`scripts/package-win.cjs` 等关键打包脚本无检查；`verify-packaging.ps1` 未断言 audio/tray-icon 等其余 extraResources。
- [ ] `RELEASE_NOTES.md`（停在 5 月）与 release.yml 的 `generate_release_notes: true` 双轨并存：确定单一来源，废弃或建立同步流程。
- [ ] `tests/e2e`（Playwright）不在 PR CI 内（需先 `npm run build`），可考虑 CI 里加 build+e2e job。
- [ ] 打包版预检：`file://` Origin 的 CORS 预检是否真的需要 PUT/DELETE（Phase 1 改动后待实测打包版确认，审计标"待验证"）。
- [ ] 升级路径验证：已安装旧版的打包升级后，`APP_STORAGE_DIR` 生效但旧的安装目录 storage 数据（kline 缓存等）不会自动迁移——评估是否需要一次性迁移脚本（settings 已有首启拷贝逻辑可参照）。
