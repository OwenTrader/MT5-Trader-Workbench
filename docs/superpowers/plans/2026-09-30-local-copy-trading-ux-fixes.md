# Local Copy Trading UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 UX 审计（2026-09-30）中的必须修与应当修项：实时刷新、事件状态徽章、停用/删除持仓警告、Phase 2 仓位模式表单、风控设置 UI、账户启停开关、API 密码脱敏。

**Architecture:** 后端（FastAPI）只做三处小改：overview 附带 `open_record_counts`、API 响应脱敏密码、空密码编辑合并语义。前端（React + zustand + shadcn/ui）在既有页面/store/lib 上扩展，不动路由结构。事件 message 全文本地化机制（message code 化）明确**不在本计划内**——需要后端事件 schema 演进，留作后续计划。

**Tech Stack:** React 18 + TypeScript + zustand + shadcn/ui + i18n（`src/renderer/src/i18n/messages.ts` zh/en 双语）；FastAPI + pydantic；Vitest（jsdom）+ pytest。

## 环境与命令（重要）

- 前端单测（按文件）：`npx vitest run src/renderer/src/test/<file>.test.tsx`
- 前端全量：`npm run test:frontend`
- 类型检查：`npm run typecheck`（package.json 已有该 script；AGENTS.md 的"无 lint/typecheck"描述已过时）
- Lint：`npm run lint`
- Python 测试：本机 `python` 是 Windows 商店 stub（exit 49）。必须用：
  `uv run --python 3.14 --with-requirements python_service/requirements.txt -- python -m pytest tests/python -q`
- 测试约定：渲染层测试 mock `global.fetch`、`I18nProvider language="en"`、`MemoryRouter` 包裹、Select 组件被 mock 成原生 `<select>`（见 `src/renderer/src/test/local-copy-trading-page.test.tsx:7-118`）。断言用英文词条。
- Python 路由测试已有 autouse `monkeypatch.chdir(tmp_path)` 存储隔离（`tests/python/test_local_copy_trading_routes.py`）。
- 网络注意：向 github push 可能瞬时报 `Connection was reset`，重试 2-3 次即可。

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `python_service/app/local_copy_trading/routes.py` | `_open_record_counts()` + GET overview 附带；edit_account 空密码合并 | 修改 |
| `python_service/app/local_copy_trading/runtime.py` | `build_overview` 脱敏 password | 修改 |
| `src/renderer/src/lib/local-copy-trading.ts` | 类型扩展（open_record_counts、关系 Phase2 字段、RiskSettings）、422 数组 detail、pick 扩展 | 修改 |
| `src/renderer/src/stores/local-copy-trading-store.ts` | `fetchOverview({silent})`、riskSettings 状态与动作 | 修改 |
| `src/renderer/src/stores/account-management-store.ts` | pick 类型跟随 | 修改（仅类型，随 lib） |
| `src/renderer/src/pages/LocalCopyTradingPage.tsx` | 轮询+刷新按钮、状态徽章、停用/删除警告、Phase2 表单、风控卡片 | 修改 |
| `src/renderer/src/pages/AccountListPage.tsx` | 启停开关、删除持仓警告 | 修改 |
| `src/renderer/src/i18n/messages.ts` | zh/en 新词条 | 修改 |
| `tests/python/test_local_copy_trading_routes.py` | 后端新行为测试 | 修改 |
| `src/renderer/src/test/local-copy-trading-page.test.tsx` | 页面新行为测试 | 修改 |
| `src/renderer/src/test/local-copy-trading-store.test.ts`、`account-list-page.test.tsx`、`account-management-store.test.ts` | store/页面测试扩展 | 修改 |

任务顺序有依赖：Task 2（密码合并）必须先于 Task 9（启停开关发送空密码）；Task 1 先于 Task 6/9（警告用 counts）。

---

### Task 1: 后端 — GET overview 附带 open_record_counts

**Files:**
- Modify: `python_service/app/local_copy_trading/routes.py`
- Test: `tests/python/test_local_copy_trading_routes.py`

- [ ] **Step 1: 写失败测试**（追加到测试文件末尾）

```python
def test_get_overview_reports_open_record_counts_per_relationship(tmp_path, monkeypatch):
    reset_state()
    copy_trading_db.init_db()
    for client_key, relationship_id in (('rel-1:pos-1', 'rel-1'), ('rel-1:pos-2', 'rel-1'), ('rel-2:pos-1', 'rel-2')):
        copy_trading_db.insert_pending(
            client_key=client_key,
            relationship_id=relationship_id,
            source_account_id='src-1',
            follower_account_id='fol-1',
            source_position_id=client_key.split(':')[1],
            created_at='2026-09-18T00:00:00+00:00',
        )
    app = build_test_app()
    client = TestClient(app)

    response = client.get('/local-copy-trading')

    assert response.status_code == 200
    assert response.json()['open_record_counts'] == {'rel-1': 2, 'rel-2': 1}


def test_get_overview_works_before_the_order_map_exists(tmp_path, monkeypatch):
    """The overview is polled from app start; it must not 500 on a fresh install."""
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.get('/local-copy-trading')

    assert response.status_code == 200
    assert response.json()['open_record_counts'] == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run --python 3.14 --with-requirements python_service/requirements.txt -- python -m pytest tests/python/test_local_copy_trading_routes.py -q`
Expected: 2 FAILED（`KeyError: 'open_record_counts'` / 断言不等）

- [ ] **Step 3: 实现**（routes.py）

顶部 import 增加 `import sqlite3`。在 `_ensure_runtime_can_enable` 之前加：

```python
def _open_record_counts() -> dict[str, int]:
    """Open order-map records per relationship.

    Empty when the order map has never been initialised (fresh install): the
    overview is the UI's polling endpoint and must not fail there.
    """
    try:
        records = copy_trading_db.list_open_records()
    except sqlite3.OperationalError:
        return {}
    counts: dict[str, int] = {}
    for record in records:
        relationship_id = record['relationship_id']
        counts[relationship_id] = counts.get(relationship_id, 0) + 1
    return counts
```

`get_overview` 改为：

```python
@router.get('')
def get_overview():
    overview = build_overview(get_state())
    return {**overview, 'open_record_counts': _open_record_counts()}
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同 Step 2。Expected: 全部 PASS（含既有测试）

- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(local-copy-trading): expose open record counts in overview for UI warnings"`

---

### Task 2: 后端 — API 密码脱敏 + 空密码编辑合并

**Files:**
- Modify: `python_service/app/local_copy_trading/runtime.py`（build_overview）
- Modify: `python_service/app/local_copy_trading/routes.py`（edit_account）
- Test: `tests/python/test_local_copy_trading_routes.py`

- [ ] **Step 1: 写失败测试**（追加）

```python
def test_overview_does_not_return_account_passwords(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)
    client.post('/local-copy-trading/accounts', json={
        'name': 'Main A', 'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe', 'login': '1001',
        'server': 'demo', 'password': 'secret', 'is_active': True,
    })

    response = client.get('/local-copy-trading')

    assert response.json()['accounts'][0]['password'] == ''
    stored = get_state().accounts[0]
    assert stored.password == 'secret'  # storage keeps the real credential


def test_edit_account_with_empty_password_keeps_the_stored_one(tmp_path, monkeypatch):
    reset_state()
    captured = {}
    monkeypatch.setattr(
        local_copy_trading_routes,
        'verify_mt5_credentials',
        lambda **kwargs: (captured.update(kwargs), (True, None))[1],
    )
    app = build_test_app()
    client = TestClient(app)
    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1', 'name': 'Main A', 'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe', 'login': '1001',
        'server': 'demo', 'password': 'secret', 'is_active': True,
    })

    response = client.put('/local-copy-trading/accounts/src-1', json={
        'name': 'Main A', 'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe', 'login': '1001',
        'server': 'demo', 'password': '', 'is_active': True,
    })

    assert response.status_code == 200
    assert captured.get('password') == 'secret'  # verified with the merged credential
    assert get_state().accounts[0].password == 'secret'
```

注意：`get_state` 需加入该测试文件 import（`from python_service.app.local_copy_trading.runtime import get_state, reset_state`）。

- [ ] **Step 2: 运行确认失败**（同 Task 1 命令；期望 2 FAILED）
- [ ] **Step 3: 实现**

`runtime.py` `build_overview` 的 accounts 行改为：

```python
'accounts': [
    # API responses never carry the credential back out; storage keeps it.
    {**account.model_dump(), 'password': ''}
    for account in state.accounts
],
```

`routes.py` `edit_account` 改为：

```python
@router.put('/accounts/{account_id}')
def edit_account(account_id: str, account: Account):
    state = get_state()
    current = next((item for item in state.accounts if item.id == account_id), None)
    # The UI never receives the password back, so an empty password means
    # "keep the stored one", not "erase it".
    if current is not None and not account.password:
        account = account.model_copy(update={'password': current.password})
    _validate_account_connection(account)
    try:
        state = update_account(state, account_id, account)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    save_state(state)
    return build_overview(state)
```

- [ ] **Step 4: 更新受影响的既有断言**

`test_delete_account_route_removes_account_and_relationships` 中期望的账户 dict 里 `'password': 'secret'` → `'password': ''`。

- [ ] **Step 5: 跑全部 python 测试确认通过**，**Step 6: Commit** `fix(local-copy-trading): stop returning account passwords over the API; empty-password edits keep the stored credential`

---

### Task 3: 前端 lib/store — silent 刷新、类型扩展、422 消息

**Files:**
- Modify: `src/renderer/src/lib/local-copy-trading.ts`
- Modify: `src/renderer/src/stores/local-copy-trading-store.ts`
- Test: `src/renderer/src/test/local-copy-trading-store.test.ts`

- [ ] **Step 1: 写失败测试**（追加到该文件，沿用其 fetch mock 风格）

```ts
it('silent fetch does not flip isLoading', async () => {
  // arrange: mock global.fetch → 200 overview（参照文件内既有 mock 写法）
  let isLoadingDuringSilentFetch: boolean | undefined
  const unsub = useLocalCopyTradingStore.subscribe((state) => {
    if (state.isLoading) { isLoadingDuringSilentFetch = true }
  })
  await useLocalCopyTradingStore.getState().fetchOverview({ silent: true })
  unsub()
  expect(isLoadingDuringSilentFetch).toBeFalsy()
  expect(useLocalCopyTradingStore.getState().overview.accounts.length).toBeGreaterThan(0)
})

it('surfaces FastAPI 422 detail arrays as readable messages', async () => {
  global.fetch = vi.fn(async () => ({
    ok: false,
    status: 422,
    json: async () => ({ detail: [{ loc: ['body', 'lot_multiplier'], msg: 'Input should be greater than 0' }] }),
  })) as any
  await useLocalCopyTradingStore.getState().fetchOverview()
  expect(useLocalCopyTradingStore.getState().error).toContain('Input should be greater than 0')
})
```

- [ ] **Step 2: 运行确认失败**：`npx vitest run src/renderer/src/test/local-copy-trading-store.test.ts`
- [ ] **Step 3: 实现**

`lib/local-copy-trading.ts`：
1. `LocalCopyTradingRelationship` 增加 `volume_mode?: string`、`max_lot?: number`、`risk_percent?: number`、`sync_sl_tp?: boolean`。
2. `LocalCopyTradingOverview` 增加 `open_record_counts?: Record<string, number>`；`DEFAULT_LOCAL_COPY_TRADING_OVERVIEW` 加 `open_record_counts: {}`。
3. `LocalCopyTradingAccountOverview` 改为 `{ accounts; relationships; open_record_counts }`；`DEFAULT_LOCAL_COPY_TRADING_ACCOUNT_OVERVIEW = { accounts: [], relationships: [], open_record_counts: {} }`；`pickLocalCopyTradingAccountOverview` 返回三者。
4. detail 数组分支（`parseLocalCopyTradingOverviewResponse`）：

```ts
if (payload && typeof payload === 'object' && 'detail' in payload) {
  const detail = (payload as { detail: unknown }).detail
  if (typeof detail === 'string') {
    fallback = detail
  } else if (Array.isArray(detail)) {
    fallback = detail
      .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
      .join('; ')
  }
}
```

（保留外层 try/catch 与 `let detail = fallbackMessage` 结构，替换现有 string-only 分支。）

`stores/local-copy-trading-store.ts`：接口 `fetchOverview: (options?: { silent?: boolean }) => Promise<void>`；实现：

```ts
fetchOverview: async (options) => {
  const silent = options?.silent === true
  set(silent ? { error: null } : { isLoading: true, error: null })
  try {
    const response = await apiFetch(LOCAL_COPY_TRADING_API_BASE)
    const overview = await parseLocalCopyTradingOverviewResponse(response)
    set({ overview, isLoading: false })
  } catch (error) {
    set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
  }
},
```

- [ ] **Step 4: 跑测试通过**（store + page + account 既有测试不回归）
- [ ] **Step 5: Commit** `feat(local-copy-trading): silent overview fetch, richer types, readable 422 messages`

---

### Task 4: 页面 — 自动轮询 + 手动刷新按钮

**Files:**
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
it('refreshes the overview periodically while mounted', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  try {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        runtime: { enabled: false, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
        accounts: [], relationships: [], events: [], open_record_counts: {},
      }),
    }))
    global.fetch = fetchMock as any
    renderPage()
    expect(await screen.findByText('Local Copy Trading')).toBeInTheDocument()
    const afterMount = fetchMock.mock.calls.length
    await act(async () => { await vi.advanceTimersByTimeAsync(3200) })
    expect(fetchMock.mock.calls.length).toBeGreaterThan(afterMount)
  } finally {
    vi.useRealTimers()
  }
})

it('offers a manual refresh that refetches the overview', async () => {
  const user = userEvent.setup()
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => (/* 既有 beforeEach 同款 payload */) }))
  global.fetch = fetchMock as any
  renderPage()
  expect(await screen.findByRole('button', { name: 'Refresh' })).toBeInTheDocument()
  const before = fetchMock.mock.calls.length
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before))
})
```

（import 增加 `act, waitFor`；Refresh 测试的 json payload 复制 beforeEach 里的对象。若 fake timers 与 RTL 组合在该环境 flaky，允许将轮询断言改为直接调用 store 层验证 + 保留 Refresh 测试，并在提交信息注明。）

注意（评审追加）：`LocalCopyTradingAccountOverview` 变为必填三字段后，`src/renderer/src/test/account-management-store.test.ts` 的 `beforeEach` 里 `setState({ overview: { accounts: [] } })` 需同步扩为 `{ accounts: [], relationships: [], open_record_counts: {} }`，否则 `npm run typecheck` 报错。

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

组件顶部常量 `const OVERVIEW_POLL_INTERVAL_MS = 3000`。替换现有 mount effect：

```tsx
useEffect(() => {
  void fetchOverview()
  const interval = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      void fetchOverview({ silent: true })
    }
  }, OVERVIEW_POLL_INTERVAL_MS)
  return () => window.clearInterval(interval)
}, [fetchOverview])
```

头部按钮行加（import `RefreshCw` from lucide-react）：

```tsx
<Button variant="outline" size="sm" onClick={() => void fetchOverview()} disabled={isLoading}>
  <RefreshCw className={isLoading ? 'animate-spin' : ''} />
  {t('localCopyTrading.refresh')}
</Button>
```

i18n（zh/en，localCopyTrading 块内）：`refresh: '刷新'` / `refresh: 'Refresh'`。

- [ ] **Step 4: 跑页面测试通过** — **Step 5: Commit** `feat(local-copy-trading): live overview polling with visibility pause and manual refresh`

---

### Task 5: 页面 — 事件状态徽章正确映射 + 本地化

**Files:**
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
it('renders a destructive localized badge for failed events', async () => {
  // beforeEach 风格 mock，events 里加一条 status: 'failed', message: 'MT5 order_send failed'
  renderPage()
  await userEvent.click(screen.getByRole('tab', { name: 'Events' }))
  const badge = await screen.findByText('Failed')
  expect(badge).toBeInTheDocument()
  expect(badge.className).toContain('destructive')  // shadcn destructive badge class
})
```

- [ ] **Step 2: 确认失败**（当前显示原文 'failed'、中性样式）
- [ ] **Step 3: 实现**

```tsx
const STATUS_LABEL_KEYS: Record<string, string> = {
  copied: 'localCopyTrading.eventStatus.copied',
  closed: 'localCopyTrading.eventStatus.closed',
  failed: 'localCopyTrading.eventStatus.failed',
  skipped: 'localCopyTrading.eventStatus.skipped',
  queued: 'localCopyTrading.eventStatus.queued',
}

function getStatusBadge(status: string, t: (key: string) => string) {
  const label = STATUS_LABEL_KEYS[status] ? t(STATUS_LABEL_KEYS[status]) : status
  switch (status) {
    case 'copied':
      return <Badge variant="default" className="bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border-transparent dark:text-emerald-400">{label}</Badge>
    case 'closed':
      return <Badge variant="secondary">{label}</Badge>
    case 'failed':
      return <Badge variant="destructive">{label}</Badge>
    case 'skipped':
      return <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300">{label}</Badge>
    default:
      return <Badge variant="outline">{label}</Badge>
  }
}
```

调用处（事件表的 `getStatusBadge(event.status)`，`LocalCopyTradingPage.tsx:335`，仅此一处）改为 `getStatusBadge(event.status, t)`。先确认 `t` 的类型签名是否接受任意 string key（`src/renderer/src/i18n` 的 t 定义）；若为字面量联合类型，用 `STATUS_LABEL_KEYS[status] as Parameters<typeof t>[0]` 规避。

i18n：zh `eventStatus: { copied: '已复制', closed: '已平仓', failed: '失败', skipped: '已跳过', queued: '排队中' }`；en `{ copied: 'Copied', closed: 'Closed', failed: 'Failed', skipped: 'Skipped', queued: 'Queued' }`。

- [ ] **Step 4: 跑测试** — **Step 5: Commit** `fix(local-copy-trading): map real event statuses to localized badges; failures render destructive`

---

### Task 6: 页面 — 停用确认、删除警告、人类可读关系标签

**Files:**
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`

- [ ] **Step 1: 写失败测试**（3 个）

```tsx
it('warns before disabling when copied positions are still open', async () => {
  // mock overview: runtime.enabled=true, open_record_counts: { 'rel-1': 2 }, 账户/关系/事件同 beforeEach
  const user = userEvent.setup()
  let disableRequested = false
  // fetch mock: URL 为 /runtime 时断言 body 含 '"enabled":false'，disableRequested = true
  renderPage()
  await user.click(await screen.findByRole('switch', { name: 'Local Copy Trading' }))  // 需先给开关加 aria-label
  expect(await screen.findByText('Disable Local Copy Trading?')).toBeInTheDocument()
  expect(screen.getByText(/2 copied follower positions/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Disable' }))
  await waitFor(() => expect(disableRequested).toBe(true))
})

it('disables immediately when no copied positions are open', async () => {
  // mock open_record_counts: {} → 点开关直接 POST enabled:false，无对话框
})

it('warns about orphaned positions when deleting a relationship with open records', async () => {
  // mock open_record_counts: { 'rel-1': 1 }
  // 点删除 → 断言确认框出现 'Main A (10001) → Follower A (20001) · XAUUSD→XAUUSD.m' 与 'no longer be closed automatically'
})
```

既有测试更新：`deletes a relationship after confirmation` 中的确认文案断言改为新的人类可读标签（`'Delete relationship Main A (10001) → Follower A (20001) · XAUUSD→XAUUSD.m? Related events will also be removed.'`，mock 无 counts 时无追加警告）。`updates runtime enabled state` / `blocks enabling...` 中 `findByRole('switch')` 改为 `findByRole('switch', { name: 'Local Copy Trading' })`。

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

1. Runtime 开关加 aria-label：`<Switch aria-label={t('localCopyTrading.runtimeSwitch')} ... />`；i18n zh `runtimeSwitch: '本地跟单运行开关'` en `runtimeSwitch: 'Local Copy Trading'`。
2. 组件内：

```tsx
const totalOpenRecords = Object.values(overview.open_record_counts ?? {}).reduce((sum, count) => sum + count, 0)
const [pendingDisableRuntime, setPendingDisableRuntime] = React.useState(false)

// handleRuntimeToggle 的关闭分支：
if (!checked) {
  if (totalOpenRecords > 0) {
    setPendingDisableRuntime(true)
    return
  }
  void updateRuntime({ enabled: false })
  return
}

const handleConfirmDisableRuntime = async () => {
  await updateRuntime({ enabled: false })
  setPendingDisableRuntime(false)
}
```

3. 停用确认 Dialog（仿启用对话框结构）：

```tsx
<Dialog open={pendingDisableRuntime} onOpenChange={setPendingDisableRuntime}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>{t('localCopyTrading.confirmDisableTitle')}</DialogTitle>
      <DialogDescription>{t('localCopyTrading.confirmDisableDescription', { count: totalOpenRecords })}</DialogDescription>
    </DialogHeader>
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
      {t('localCopyTrading.confirmDisableWarning')}
    </div>
    <DialogFooter>
      <Button variant="outline" onClick={() => setPendingDisableRuntime(false)}>{t('priceAlerts.cancel')}</Button>
      <Button variant="destructive" onClick={() => void handleConfirmDisableRuntime()}>{t('localCopyTrading.confirmDisable')}</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

4. 关系人类可读标签 + 删除警告：

```tsx
function getRelationshipLabel(relationship, accounts) {
  return `${getAccountLabelById(accounts, relationship.source_account_id)} → ${getAccountLabelById(accounts, relationship.follower_account_id)} · ${getRelationshipSourceSymbol(relationship)}→${getRelationshipFollowerSymbol(relationship)}`
}

const openCountForPendingRelationship = overview.open_record_counts?.[pendingDeleteRelationshipId] ?? 0
const deleteDescription = pendingDeleteRelationshipId
  ? t('localCopyTrading.confirmDeleteRelationship', {
      name: getRelationshipLabel(
        overview.relationships.find((item) => item.id === pendingDeleteRelationshipId),
        overview.accounts,
      ),
    }) + (openCountForPendingRelationship > 0
      ? ' ' + t('localCopyTrading.confirmDeleteRelationshipOpenPositions', { count: openCountForPendingRelationship })
      : '')
  : ''
```

（`find` 可能返回 undefined——用 `?.` 与空数组兜底：`overview.relationships.find(...) ?? { source_account_id: '', follower_account_id: '', symbol: '' }` 的方式或提前 return，执行时以类型检查为准。）

5. `'Backend Engine Error'` → `{t('localCopyTrading.backendError')}`。

i18n zh：
```
confirmDisableTitle: '确认停用本地跟单'
confirmDisableDescription: '当前仍有 {count} 个已复制的跟单持仓。'
confirmDisableWarning: '停用后，主账户平仓时这些持仓将不再被自动平掉，需要手动管理。'
confirmDisable: '确认停用'
confirmDeleteRelationshipOpenPositions: '注意：该关系下仍有 {count} 个已复制持仓，删除后将不再被自动平仓。'
backendError: '后端引擎错误'
```
en：
```
confirmDisableTitle: 'Disable Local Copy Trading?'
confirmDisableDescription: '{count} copied follower positions are still open.'
confirmDisableWarning: 'After disabling, these positions will no longer be closed automatically when the source closes. You will need to manage them manually.'
confirmDisable: 'Disable'
confirmDeleteRelationshipOpenPositions: 'Warning: {count} copied positions still exist under this relationship; they will no longer be closed automatically.'
backendError: 'Backend Engine Error'
```

- [ ] **Step 4: 跑页面测试** — **Step 5: Commit** `feat(local-copy-trading): confirm disable and relationship deletion when copied positions remain open`

---

### Task 7: 页面 — 关系表单暴露 Phase 2 仓位模式

**Files:**
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/local-copy-trading-page.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
it('submits phase-2 sizing fields with a new relationship', async () => {
  // URL-aware fetch mock 捕获 POST /relationships body
  renderPage()
  await user.click(await screen.findByRole('button', { name: 'Add Relationship' }))
  await user.selectOptions(await screen.findByLabelText('Source Account'), 'src-1')
  await user.selectOptions(screen.getByLabelText('Follower Account'), 'fol-1')
  await user.selectOptions(screen.getByLabelText('Volume Mode'), 'risk_percent')
  await user.clear(screen.getByLabelText('Risk Percent (%)'))
  await user.type(screen.getByLabelText('Risk Percent (%)'), '2')
  await user.clear(screen.getByLabelText('Max Lot per Position'))
  await user.type(screen.getByLabelText('Max Lot per Position'), '1')
  await user.click(screen.getByRole('switch', { name: 'Sync Stop Loss / Take Profit' }))
  await user.click(screen.getByRole('button', { name: 'Save Relationship' }))
  await waitFor(() => expect(relationshipPayload).toMatchObject({
    volume_mode: 'risk_percent', risk_percent: 2, max_lot: 1, sync_sl_tp: true, lot_multiplier: 1,
  }))
})

it('shows the volume mode column in the relationships table', async () => {
  // mock 关系带 volume_mode: 'fixed' → 表格出现 'Fixed Lots'
})
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

1. 状态：`volumeMode`（默认 `'multiplier'`）、`relationshipRiskPercent`（`'1'`）、`relationshipMaxLot`（`'0'`）、`syncSlTp`（`false`）；`closeRelationshipDialog` 一并重置。
2. 表单校验扩展：

```tsx
function isRelationshipFormComplete(...) {
  const multiplierOk = Boolean(...) // 现有逻辑
  const riskOk = volumeMode !== 'risk_percent' || Number(relationshipRiskPercent) > 0
  return multiplierOk && riskOk
}
```

（把新参数并入函数签名。）
3. Dialog 增加字段：仓位模式 Select（4 个 SelectItem，label 用 i18n）；lot multiplier 的 label 在 `fixed` 模式下换为 `t('localCopyTrading.fixedLots')`；`risk_percent` 输入仅 `volumeMode === 'risk_percent'` 时渲染；`max_lot` 数字输入（placeholder：0 = 不限制）+ 说明；`sync_sl_tp` Switch（带 aria-label）。
4. 提交 payload 增加：`volume_mode: volumeMode, max_lot: Number(relationshipMaxLot) || 0, risk_percent: Number(relationshipRiskPercent) || 1, sync_sl_tp: syncSlTp`。
5. 关系表增加"仓位模式"列：`renderVolumeModeLabel(relationship.volume_mode ?? 'multiplier', t)`（映射表同 STATUS_LABEL_KEYS 模式，未知值回退原字符串）。同步把该表 loading/空行 `colSpan={7}` 改为 `colSpan={8}`。

i18n zh：`volumeMode: '仓位模式'`；`volumeModes: { multiplier: '手数倍数', fixed: '固定手数', equity_ratio: '净值比例', risk_percent: '风险百分比' }`；`fixedLots: '固定手数（手）'`；`riskPercent: '风险百分比 (%)'`；`maxLot: '单仓手数上限'`；`maxLotHint: '0 表示不限制'`；`syncSlTp: '同步止损/止盈'`；`columns.volumeMode: '仓位模式'`。en 对应：`Volume Mode` / `{ Multiplier: 'Lot Multiplier', Fixed: 'Fixed Lots', 'Equity Ratio': 'Equity Ratio', 'Risk Percent': 'Risk Percent' }`（键保持 snake_case：multiplier/fixed/equity_ratio/risk_percent）/ `Fixed lots` / `Risk Percent (%)` / `Max Lot per Position` / `0 means no limit` / `Sync Stop Loss / Take Profit` / `Volume Mode`。

- [ ] **Step 4: 跑测试** — **Step 5: Commit** `feat(local-copy-trading): expose volume modes, max lot, risk percent, and SL/TP sync in the relationship form`

---

### Task 8: 页面 — 风控守卫设置卡片

**Files:**
- Modify: `src/renderer/src/lib/local-copy-trading.ts`（类型 + parse）
- Modify: `src/renderer/src/stores/local-copy-trading-store.ts`
- Modify: `src/renderer/src/pages/LocalCopyTradingPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/local-copy-trading-store.test.ts`、`local-copy-trading-page.test.tsx`

- [ ] **Step 1: 写失败测试**

store：
```ts
it('fetches and saves risk settings', async () => {
  // GET /local-copy-trading/risk-settings → mock 返回 {max_daily_loss: 500, ...}
  // PUT → 断言 body 正确、store 状态更新
})
```
page：
```tsx
it('renders the risk guard card and saves changes', async () => {
  // URL-aware fetch：/risk-settings GET 返回默认，PUT 捕获 body
  // 修改 Daily Loss 输入为 500 → 点 Save → 断言 PUT body { max_daily_loss: 500, ... }
})
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

lib：

```ts
export interface CopyTradingRiskSettings {
  max_volume_per_symbol: number
  max_positions_per_symbol: number
  max_daily_open_count: number
  max_daily_loss: number
  min_margin_level: number
  max_consecutive_failures: number
}

export const DEFAULT_COPY_TRADING_RISK_SETTINGS: CopyTradingRiskSettings = {
  max_volume_per_symbol: 0,
  max_positions_per_symbol: 0,
  max_daily_open_count: 0,
  max_daily_loss: 0,
  min_margin_level: 0,
  max_consecutive_failures: 3,
}

export async function parseRiskSettingsResponse(response: Response): Promise<CopyTradingRiskSettings> {
  if (!response.ok) { /* 同 overview 的 detail 提取，抛 Error */ }
  const payload = await response.json() as Record<string, unknown>
  return {
    ...DEFAULT_COPY_TRADING_RISK_SETTINGS,
    ...Object.fromEntries(Object.entries(payload).filter(([, value]) => typeof value === 'number')),
  } as CopyTradingRiskSettings
}
```

store：`riskSettings`、`isSavingRiskSettings`、`fetchRiskSettings()`、`updateRiskSettings(payload): Promise<boolean>`（GET/PUT `/risk-settings`）。页面 mount effect 里并行 `void fetchRiskSettings()`。

页面：runtime 卡片之后新增 Card：

```tsx
<Card>
  <CardHeader>
    <CardTitle>{t('localCopyTrading.riskGuards.title')}</CardTitle>
    <p className="text-sm text-muted-foreground">{t('localCopyTrading.riskGuards.description')}</p>
  </CardHeader>
  <CardContent>
    {/* 6 个数字输入，两列 grid；label + hint('0 表示不限制' / '0 表示不熔断')；保存按钮 isSavingRiskSettings 禁用；错误行 */}
  </CardContent>
</Card>
```

本地 state 用 6 个 string 字段（`useState(() => String(riskSettings.x))`，fetch 后同步——用 `useEffect([riskSettings])` 同步一次）。保存时 `Number(x) || 0`。成功/失败用 sonner `toast.success/toast.error`（项目已用 sonner，参照 `RiskControlPage.tsx`）。

i18n zh `riskGuards: { title: '开仓风控守卫', description: '下单前的硬性限制，0 表示该规则不启用。', maxVolumePerSymbol: '每品种最大持仓量（手）', maxPositionsPerSymbol: '每品种最大持仓数', maxDailyOpenCount: '每日最大开仓数', maxDailyLoss: '每日最大亏损', minMarginLevel: '最低保证金率（%）', maxConsecutiveFailures: '连续失败熔断次数', zeroMeansDisabled: '0 表示不限制', zeroMeansNoBreaker: '0 表示不熔断', save: '保存风控设置' }`；en 镜像（`Pre-trade Risk Guards` 等）。

- [ ] **Step 4: 跑测试** — **Step 5: Commit** `feat(local-copy-trading): risk guard settings card wired to /risk-settings`

---

### Task 9: 账户页 — 启停开关 + 删除持仓警告

**Files:**
- Modify: `src/renderer/src/pages/AccountListPage.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`
- Test: `src/renderer/src/test/account-list-page.test.tsx`

- [ ] **Step 1: 写失败测试**

```tsx
it('toggles account active state through the API', async () => {
  // mock 账户 is_active: true；点击行内 Switch（aria-label 'Enable Main A'）
  // 断言 PUT /accounts/xxx body 含 is_active: false 且 password: ''
})

it('warns about open copied positions when deleting an account', async () => {
  // mock overview: relationships 含 rel-1 (src-1→fol-1)，open_record_counts { rel-1: 3 }
  // 点删除 → 确认框含 '3' 与 'no longer be closed automatically'
})
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

1. 表头加 状态 列；每行 Switch：

```tsx
<Switch
  aria-label={t('accountList.activeToggle', { name: account.name })}
  checked={account.is_active}
  onCheckedChange={(checked) => void handleToggleAccount(account, checked)}
/>
```

```tsx
const handleToggleAccount = async (account: LocalCopyTradingAccount, isActive: boolean) => {
  await updateAccount(account.id, {
    name: account.name,
    connection_type: account.connection_type,
    terminal_path: account.terminal_path,
    login: account.login,
    server: account.server,
    password: '',  // 空密码 = 保留已存凭据（Task 2 语义）
    is_active: isActive,
  })
  void fetchOverview()
}
```

2. 删除警告：

```tsx
const openCountForAccount = (overview.relationships ?? [])
  .filter((rel) => rel.source_account_id === pendingDeleteId || rel.follower_account_id === pendingDeleteId)
  .reduce((sum, rel) => sum + (overview.open_record_counts?.[rel.id] ?? 0), 0)

const deleteDescription = pendingDeleteLabel
  ? t('accountList.confirmDelete', { name: getAccountOptionLabel(pendingDeleteLabel) })
    + (openCountForAccount > 0 ? ' ' + t('accountList.confirmDeleteOpenPositions', { count: openCountForAccount }) : '')
  : ''
```

i18n zh：`accountList.activeToggle: '启用 {name}'`、`accountList.confirmDeleteOpenPositions: '注意：该账户关联的跟单关系下仍有 {count} 个已复制持仓，删除后将不再被自动平仓。'`、`accountList.passwordKeepHint: '留空保持已存密码不变'`、`accountList.columns.status: '状态'`（若表头直接用现有 key 结构则加 `localCopyTrading.columns.status` 已存在'状态'，复用即可）。en 镜像（`Enable {name}` / `Warning: {count} copied positions ... no longer be closed automatically.` / `Leave blank to keep the stored password` / `Status`）。

密码编辑体验（随本任务）：密码输入框加 `placeholder={t('accountList.passwordKeepHint')}`；`isAccountFormComplete` 在 `editingAccountId` 非空时允许密码为空（创建仍必填）。同时把账户表空行 `colSpan={6}` 改为 `colSpan={7}`（新增状态列）。

注意：`updateAccount` 成功后 overview 由 store 刷新，行内 Switch 受控于 `overview.accounts`。

- [ ] **Step 4: 跑测试** — **Step 5: Commit** `feat(local-copy-trading): account active toggle and orphan-position warning on account deletion`

---

### Task 10: 全量验证 + 提交推送

- [ ] **Step 1: 全量前端**：`npm run test:frontend` — Expected: 全绿
- [ ] **Step 2: `npm run typecheck` 与 `npm run lint`** — Expected: 0 error / 0 problem
- [ ] **Step 3: 全量 Python**：`uv run --python 3.14 --with-requirements python_service/requirements.txt -- python -m pytest tests/python -q` — Expected: 全绿
- [ ] **Step 4: 检查工作区**：`git status` 确认无 `storage/` 污染、无意外文件
- [ ] **Step 5: push**：`git push origin main`（Connection reset 时重试 2-3 次），`git ls-remote origin refs/heads/main` 校验与本地一致

## 明确不做（本轮）

- 事件 message 全文本地化（需后端 SyncEvent 增加 message code/params，牵动 schema 与全部产生方，留独立计划）
- 轮询间隔可调 UI、事件表筛选/分页（P2，后续）
- simulated 源账户样例持仓行为（待验证项）
- 密码加密存储（已声明延期；本轮只做 API 不回传）
