# MT5-Workbench 全项目审查与优化路线图（2026-10-01）

> 审查方法：三个并行深度审查（Python 后端 / Electron+React 前端 / 工程基建），共 **81 条发现：P0=6，P1=19，P2=31，P3=25**。所有 P0/P1 均经人工二次核验源码行号。本仓两轮 local-copy-trading 专项审计（后端正确性、UX）已在此前完成修复，不在本文重复。

## 一、核心结论

1. **安全边界是最大短板**：后端 CORS 守卫只"不发头"不拒绝执行（B-1）；Electron `openExternal`/`local-file` 协议两处可被渲染层滥用（F-1/2/3）；两个窗口无 `setWindowOpenHandler`（F-4）。四条叠加构成"恶意网页→本地 API→下单/起进程"的完整链路。
2. **进程级 MT5 连接的会话所有权被绕过**（B-2）：`verify_mt5_credentials`/`get_mt5_client` 等路径切换全局连接不通知 `mt5_session`，跟单可能复用错误/断开的连接——实盘资金风险。
3. **事件循环阻塞未修完**：`order_sync`（B-3）与 `quant`（B-4）仍在 async 里同步跑 MT5/回测，每 0.5–2s 冻结整个后端数百毫秒到数秒。
4. **依赖管理半迁移状态**（I-1）：pnpm 与 npm 双锁并存且树不同（vitest 1.6.1 从未支持 Node 24），是本地两个测试挂起的最可能根因；仓库锁文件烧死腾讯镜像 URL（I-2）。
5. **CI 形同虚设**（I-3）：无 push/PR 触发的工作流，lint/typecheck/electron e2e 任何流水线都不跑。
6. 前端整体架构健康（preload 白名单、轮询收敛、进程管理完善），问题集中在**局部安全加固、i18n 残留（约 40+ 行硬编码中文）、store 错误处理模式割裂、4 处复制粘贴的预警行组件**。

## 二、Phase 1 —— 安全与正确性速赢（本轮执行）

| # | 项 | 来源 | 文件 |
|---|---|---|---|
| 1.1 | origin_guard：非白名单 Origin 的非预检请求直接 403；Allow-Methods 补 PUT/DELETE | B-1 | `python_service/app/main.py:152-167` |
| 1.2 | MT5 会话失效通知：`verify_mt5_credentials`/`verify_mt5_path_connection`/`_init_mt5_unlocked`/`shutdown_mt5` 切换全局连接后调用 `mt5_session.reset_session_tracking()`（惰性导入避免环） | B-2 | `mt5_service.py` |
| 1.3 | 已连接健康时短路重连：`_init_mt5_unlocked` 先查 `terminal_info()`，避免 ~1Hz 的 shutdown+initialize 风暴 | B-9 | `mt5_service.py:159-186` |
| 1.4 | order_sync tick 的 `get_positions()` 走 `asyncio.to_thread` | B-3 | `order_sync_service.py:160` |
| 1.5 | quant `run_job_once` 走 `asyncio.to_thread` | B-4 | `quant/runtime.py:273` |
| 1.6 | `app:openExternal` 仅放行 `https?://` | F-1 | `src/main/index.ts:327-329` |
| 1.7 | `app:register-local-root` 仅接受 userData 内目录；`local-file` 前缀匹配补路径边界 | F-2/3 | `src/main/index.ts:336-341,452-469` |
| 1.8 | 主窗口与 overlay 窗口加 `setWindowOpenHandler`（https 经 openExternal，其余 deny）+ `will-navigate` 拦截 | F-4 | `index.ts:345`、`overlay-window.ts:8` |
| 1.9 | "使用教程"按钮改走 IPC（当前调不存在的 API，静默失效） | F-5 | `workbench-shell.tsx:23` |
| 1.10 | 全局 ErrorBoundary（页面级，含重试） | F-6 | `src/renderer/src/main.tsx`、新增组件 |
| 1.11 | pytest 全局 cwd 隔离（conftest autouse chdir），消除测试污染 git 跟踪的 storage 文件 | I-4 | `tests/python/conftest.py` |
| 1.12 | AGENTS.md 三处过时信息更正 | I-6 | `AGENTS.md:9-10,48` |
| 1.13 | 新增 push/PR 触发的 `ci.yml`（lint+typecheck+test:frontend+pytest） | I-3 | `.github/workflows/` |

## 三、Phase 2 —— 依赖与工程收口（下一轮，需一个用户决策）

- **决策点：包管理器二选一**（I-1/I-7/I-8）。推荐：收口 **pnpm**（提交 `pnpm-lock.yaml`+`pnpm-workspace.yaml`，CI 改 `pnpm i --frozen-lockfile`，加 `packageManager` 字段），或回归 npm 单锁。本地 Node 24 vs CI Node 20 错位需一并定（I-9，vitest 1.6.1 不支持 Node 24——升级 vitest 或统一 Node 20）。
- 用公共 registry 重新生成锁文件，去除烧死的 mirrors.tencent.com resolved（I-2）。
- `typecheck` 覆盖 src/main+src/preload（`tsconfig.node.json` include 现指向不存在的 `electron` 目录，I-5）；`tsc --build` 连 references。
- release CI 注入 `BUILD_NUMBER`（I-10，当前 tag 构建恒为 1.0.0）。
- 删除 `node_modules.npm.bak/`（迁移收口后）、`tests/electron/` 空目录（I-13/I-14）；修 README test 前置说明与废弃 spec 引用（I-11/I-12）。
- requirements.txt 关键包锁版本（I-15：fastapi/pyinstaller/pydantic 至少 pin 大版本）。

## 四、Phase 3 —— 后端健壮性

按价值排序：WS 端点 Origin 校验（B-5）→ quant_loop 加异常保护防静默死亡（B-6）→ quant events.json 环形截断+按事件类型落盘（B-7，当前 ~4.3 万条/天/任务）→ settings 内存缓存（B-14）→ `data_management`/`history` 路由改同步 def 进线程池并持锁（B-11/B-12）→ notifier `asyncio.gather` 并发+短超时（B-17）→ alerts 共享列表加锁（B-15）→ 波动预警点数量纲修复（B-16，用 symbol_info.point）→ kline_db 连接 try/finally（B-24）→ /health 反映各循环心跳（B-22）→ 统一 logging 替换 30 处 print（B-21）→ 存储路径统一从单一 env 派生（B-18，打包写 Program Files 会失败）→ overlay import 加 schema（B-25）。

## 五、Phase 4 —— 前端一致性

dashboard store selector 订阅 + in-flight 守卫（F-9/F-8）→ alerts store 变更失败反馈（F-10）→ 抽取 `AlertRowActions` 公共组件消灭 4 处复制（F-12）→ position-table/command-palette i18n（F-13/F-14）→ CSP meta（F-7）→ overlay WS try/catch+重连竞态（F-17）→ i18n key 编译期校验（F-20）→ 40+ 行散落硬编码中文迁移（F-21）→ icon 按钮 aria-label 补齐（F-18）→ `protocol.handle` 迁移（F-19，Electron 30 前置）。

## 六、Phase 5 —— 产品深化（需要产品判断）

券商凭据 DPAPI/密钥环加密（B-26 延期项）→ 跟单事件 message code 化支持全文本地化（UX 审计延期项）→ 关系创建时源账户品种存在性校验 → 复盘合约乘数改从 `symbol_info` 读取（B-23）→ 回测 PnL 计入手数与乘数（B-27）→ 安装包代码签名（I-16）→ Pyarmor 表述与实现对齐（I-17）。

## 验收与回归

Phase 1 完成标准：后端 pytest 全绿（新增 origin-guard 403 与会话失效测试）、前端受影响测试全绿、`npm run typecheck`/`lint` 零问题、ci.yml 在 GitHub Actions 首跑通过（push 后观察）。
