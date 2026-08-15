# Electron App I18n Settings Language Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bilingual UI system so users can switch the Electron app between Simplified Chinese and English from the Settings page, with the choice persisted and applied to the most visible app surfaces needed to prove the feature works end to end.

**Architecture:** Reuse the existing settings persistence flow instead of creating a second preferences system. Add a small in-repo translation layer for `zh-CN` and `en`, expose the active language through a renderer provider/hook, and wire the same setting into the Electron main process so tray labels and window title update when settings change. Keep the first version intentionally narrow: no third-party i18n package, no dynamic locale downloads, and no pluralization framework unless the existing UI proves it necessary.

**Tech Stack:** Electron, React, TypeScript, Zustand, FastAPI, Pydantic, Vitest, React Testing Library, Playwright

---

## Scope Check

This request is one cohesive subsystem, not multiple unrelated projects:

- persisted language preference
- renderer text translation
- Settings page language switcher
- Electron main-process text translation
- tests and docs for the new behavior

Do not split this into separate plans unless the product later asks for a much larger localization program such as backend-generated copy, downloadable language packs, or more than two locales.

## File Structure

Planned file ownership before implementation:

- Modify: `python_service/app/models/settings.py`
  Responsibility: add `language` to the persisted settings contract returned by FastAPI.
- Modify: `python_service/app/routes/settings.py`
  Responsibility: keep the existing load/save route behavior, now including `language` in the JSON payload.

- Modify: `src/renderer/src/stores/settings-store.ts`
  Responsibility: include `language` in TypeScript settings types, defaults, fetch, and save behavior.
- Create: `src/renderer/src/i18n/messages.ts`
  Responsibility: define the full translation dictionary for `zh-CN` and `en` in one place.
- Create: `src/renderer/src/i18n/index.tsx`
  Responsibility: provide `I18nProvider`, `useI18n`, locale typing, fallback behavior, and optional helper utilities like `t()`.
- Modify: `src/renderer/src/main.tsx`
  Responsibility: wrap the app in the new provider.
- Modify: `src/renderer/src/App.tsx`
  Responsibility: use translated placeholder strings and pass translated shell content where needed.
- Modify: `src/renderer/src/layouts/workbench-shell.tsx`
  Responsibility: translate the app header title.
- Modify: `src/renderer/src/components/module-nav.tsx`
  Responsibility: translate navigation item labels and tooltip/title text.
- Modify: `src/renderer/src/pages/SettingsPage.tsx`
  Responsibility: add the user-facing language selector in Settings and translate all existing settings copy shown on this page.
- Modify: `src/renderer/src/pages/dashboard-page.tsx`
  Responsibility: translate dashboard headings, status text, button text, and alert messages.
- Create: `src/main/i18n.ts`
  Responsibility: define a tiny main-process translation helper for tray/menu/window text using the same locale values as the renderer.
- Modify: `src/main/index.ts`
  Responsibility: load the current language from the same settings file contract, localize tray labels/window title, and refresh those labels after `settings:notify-update`.

- Modify: `src/renderer/src/test/setup.ts`
  Responsibility: add any required mocks for `next-themes`, notifications, or provider wrappers if tests need them.
- Modify: `src/renderer/src/test/settings-store.test.ts`
  Responsibility: cover the new `language` setting in defaults, fetch, and save payloads.
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`
  Responsibility: stop assuming Chinese-only text and verify translated shell content.
- Create: `src/renderer/src/test/i18n-provider.test.tsx`
  Responsibility: verify locale selection and fallback behavior.
- Create: `src/renderer/src/test/settings-page-language.test.tsx`
  Responsibility: verify the Settings language selector updates visible UI copy.
- Modify: `tests/e2e/app-launch.spec.ts`
  Responsibility: keep smoke coverage resilient to either locale while still checking launch success.

Repository note:

- At plan-writing time, the repo had a mismatch between the on-disk Playwright spec path (`tests/e2e/app-launch.spec.ts`) and the `package.json` `test:electron` script. Align that script before or during execution so `npm run test:electron` points to the real spec file.

- Modify: `README.md`
  Responsibility: document the new bilingual UI capability.
- Modify: `README.zh-CN.md`
  Responsibility: document the same capability in Chinese.

Implementation constraints:

- Keep translation keys semantic, not page-position-based. Good: `settings.general.title`. Bad: `page1_label3`.
- Do not add `i18next`, `react-intl`, or another dependency for this two-locale feature unless a concrete need appears during implementation.
- Prefer one shared renderer dictionary file at first. Split by page later only if the file becomes hard to navigate.
- Preserve persisted settings backward compatibility by defaulting missing `language` values to `zh-CN`, because current UI is already Chinese-first.

## Testing Strategy

- Frontend unit tests: `vitest` and React Testing Library
- Electron smoke test: Playwright with `_electron`
- Manual verification: launch app, switch language in Settings, confirm navigation/header/settings/dashboard/tray text changes and persists after restart

## Translation Boundaries

Translate in this task:

- navigation labels
- layout header title
- settings page copy
- dashboard copy
- order-broadcast placeholder copy in `App.tsx`
- main-process tray/menu/window labels

Do not expand scope in this task:

- alert page headings, forms, notifications, toasts, and empty states
- technical analysis page content
- overlay route content
- order center and risk control page copy
- backend API error localization beyond strings surfaced directly by renderer-owned code
- document titles/content in `src/main/awakening-data.ts`
- generated report contents from technical analysis backend
- DingTalk payload localization rules

Follow-up note:

- Once this minimal bilingual slice ships, a second plan can localize feature pages such as price alerts, volatility, indicator alerts, technical analysis, and overlay-specific copy.

### Task 1: Persist Language In Existing Settings Contract

**Files:**
- Modify: `python_service/app/models/settings.py:3-18`
- Modify: `python_service/app/routes/settings.py:12-24`
- Modify: `src/renderer/src/stores/settings-store.ts:3-87`
- Modify: `src/renderer/src/test/settings-store.test.ts:1-46`

- [ ] **Step 1: Write the failing store test for the new default language**

```ts
it('initializes with zh-CN as the default language', () => {
  const { result } = renderHook(() => useSettingsStore())
  expect(result.current.settings.language).toBe('zh-CN')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/settings-store.test.ts`
Expected: FAIL because `language` does not exist on the settings object yet.

- [ ] **Step 3: Add `language` to the Python settings model with a backward-compatible default**

```py
class Settings(BaseModel):
    mt5_path: str = ''
    auto_connect: bool = False
    price_alerts_path: str = ''
    account_monitoring_interval: int = 5
    volatility_check_interval: int = 60
    overlay_font_size: int = 24
    overlay_font_color: str = "#4ade80"
    overlay_symbols: list[str] = ["XAUUSD", "USDJPY"]
    overlay_width: int = 320
    overlay_height: int = 250
    dingtalk_secret: str = ''
    theme: str = 'light'
    language: str = 'zh-CN'
    alert_sound_enabled: bool = True
    alert_sound_path: str = ''
    alert_sound_volume: float = 0.5
```

- [ ] **Step 4: Add `language` to the renderer settings type and defaults**

```ts
export interface Settings {
  mt5_path: string
  auto_connect: boolean
  price_alerts_path: string
  account_monitoring_interval: number
  volatility_check_interval: number
  overlay_font_size: number
  overlay_font_color: string
  overlay_symbols: string[]
  overlay_width: number
  overlay_height: number
  api_refresh_interval: number
  dingtalk_token: string
  dingtalk_secret: string
  theme: string
  language: 'zh-CN' | 'en'
  alert_sound_enabled: boolean
  alert_sound_path: string
  alert_sound_volume: number
}

const DEFAULT_SETTINGS: Settings = {
  // existing fields...
  theme: 'light',
  language: 'zh-CN',
  alert_sound_enabled: true,
  alert_sound_path: '',
  alert_sound_volume: 0.5,
}
```

- [ ] **Step 5: Expand fetch/save tests to verify language survives backend round-trips**

```ts
it('fetches language from backend', async () => {
  const mockSettings = { mt5_path: 'C:/MT5', auto_connect: true, language: 'en' }
  ;(fetch as any).mockResolvedValue({
    ok: true,
    json: async () => mockSettings,
  })

  const { result } = renderHook(() => useSettingsStore())
  await result.current.fetchSettings()

  expect(result.current.settings.language).toBe('en')
})

it('saves language to backend', async () => {
  ;(fetch as any).mockResolvedValue({ ok: true })

  const { result } = renderHook(() => useSettingsStore())
  await result.current.updateSettings({ language: 'en' })

  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining('/settings'),
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('"language":"en"'),
    })
  )
})
```

- [ ] **Step 6: Run the focused test file**

Run: `npm run test:frontend -- src/renderer/src/test/settings-store.test.ts`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add python_service/app/models/settings.py python_service/app/routes/settings.py src/renderer/src/stores/settings-store.ts src/renderer/src/test/settings-store.test.ts
git commit -m "feat: persist language in app settings"
```

### Task 2: Build The Minimal Renderer I18n Layer

**Files:**
- Create: `src/renderer/src/i18n/messages.ts`
- Create: `src/renderer/src/i18n/index.tsx`
- Modify: `src/renderer/src/main.tsx:1-10`
- Create: `src/renderer/src/test/i18n-provider.test.tsx`

- [ ] **Step 1: Write the failing provider test for default and English selection**

```tsx
import { render, screen } from '@testing-library/react'
import { I18nProvider, useI18n } from '@/i18n'

function Probe() {
  const { locale, t } = useI18n()
  return (
    <div>
      <span>{locale}</span>
      <span>{t('nav.settings')}</span>
    </div>
  )
}

it('uses zh-CN by default and can switch to English', () => {
  const { rerender } = render(
    <I18nProvider language="zh-CN">
      <Probe />
    </I18nProvider>
  )

  expect(screen.getByText('zh-CN')).toBeInTheDocument()
  expect(screen.getByText('设置')).toBeInTheDocument()

  rerender(
    <I18nProvider language="en">
      <Probe />
    </I18nProvider>
  )

  expect(screen.getByText('en')).toBeInTheDocument()
  expect(screen.getByText('Settings')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/i18n-provider.test.tsx`
Expected: FAIL because the provider module does not exist.

- [ ] **Step 3: Create a small typed dictionary file**

```ts
export const locales = ['zh-CN', 'en'] as const
export type Locale = (typeof locales)[number]

export const messages = {
  'zh-CN': {
    app: { title: 'Trader Workbench' },
    nav: { settings: '设置' },
  },
  en: {
    app: { title: 'Trader Workbench' },
    nav: { settings: 'Settings' },
  },
} as const
```

- [ ] **Step 4: Create the provider and translation helper**

```tsx
const I18nContext = createContext<{ locale: Locale; t: (key: string) => string } | null>(null)

export function I18nProvider({ language, children }: { language: Locale; children: React.ReactNode }) {
  const value = useMemo(() => ({
    locale: language,
    t: (key: string) => getMessage(messages[language], key) ?? getMessage(messages['zh-CN'], key) ?? key,
  }), [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within I18nProvider')
  return context
}
```

Use a tiny `getMessage` dot-path helper instead of adding a library.

- [ ] **Step 5: Wrap the app at the renderer entry with the provider using the settings store value**

```tsx
function Root() {
  const language = useSettingsStore((state) => state.settings.language || 'zh-CN')

  return (
    <I18nProvider language={language}>
      <App />
    </I18nProvider>
  )
}
```

If the store has not fetched remote settings yet, the default should still be `zh-CN` so the first paint is stable.

- [ ] **Step 6: Run the new provider test**

Run: `npm run test:frontend -- src/renderer/src/test/i18n-provider.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/i18n/messages.ts src/renderer/src/i18n/index.tsx src/renderer/src/main.tsx src/renderer/src/test/i18n-provider.test.tsx
git commit -m "feat: add renderer i18n provider"
```

### Task 3: Localize Navigation, Shell, And Settings Page With The Language Switcher

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx:1-44`
- Modify: `src/renderer/src/layouts/workbench-shell.tsx:1-28`
- Modify: `src/renderer/src/pages/SettingsPage.tsx:1-392`
- Modify: `src/renderer/src/App.tsx:1-53`
- Create: `src/renderer/src/test/settings-page-language.test.tsx`
- Modify: `src/renderer/src/i18n/messages.ts`

- [ ] **Step 1: Write the failing Settings page test for language switching**

```tsx
it('switches the visible settings copy to English after saving language', async () => {
  render(<App />)

  await userEvent.click(screen.getByTitle('设置'))
  await userEvent.selectOptions(screen.getByLabelText('界面语言'), 'en')
  await userEvent.click(screen.getAllByRole('button', { name: '保存设置' })[0])

  expect(await screen.findByText('System Settings')).toBeInTheDocument()
  expect(screen.getByText('General')).toBeInTheDocument()
})
```

Mock `fetch` to return and accept settings so the page can render deterministically in test.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/settings-page-language.test.tsx`
Expected: FAIL because there is no language field or translated copy yet.

- [ ] **Step 3: Add language labels and translated shell/navigation copy to the dictionary**

```ts
'zh-CN': {
  app: { title: 'Trader Workbench', comingSoon: '功能开发中，敬请期待...' },
  nav: {
    dashboard: '工作台总览',
    priceAlerts: '价格预警',
    volatility: '波动检测',
    indicatorAlerts: '指标预警',
    riskControl: '风控与账户',
    orderCenter: '订单中心',
    technicalAnalysis: '技术分析',
    orderBroadcast: '订单广播',
    settings: '设置',
  },
  settings: {
    title: '系统设置',
    tabs: { general: '通用', sound: '音效', bot: 'Bot预警' },
    language: {
      label: '界面语言',
      zhCN: '中文',
      en: '英文',
    },
    actions: { save: '保存设置', saving: '保存中...' },
  },
}

'en': {
  app: { title: 'Trader Workbench', comingSoon: 'Feature in progress' },
  nav: {
    dashboard: 'Dashboard',
    priceAlerts: 'Price Alerts',
    volatility: 'Volatility',
    indicatorAlerts: 'Indicator Alerts',
    riskControl: 'Risk & Account',
    orderCenter: 'Order Center',
    technicalAnalysis: 'Technical Analysis',
    orderBroadcast: 'Order Broadcast',
    settings: 'Settings',
  },
  settings: {
    title: 'System Settings',
    tabs: { general: 'General', sound: 'Sound', bot: 'Bot Alerts' },
    language: {
      label: 'Interface Language',
      zhCN: 'Chinese',
      en: 'English',
    },
    actions: { save: 'Save Settings', saving: 'Saving...' },
  },
}
```

- [ ] **Step 4: Localize `ModuleNav` and `WorkbenchShell`**

Replace hard-coded Chinese labels with `t(...)` lookups, for example:

```tsx
const { t } = useI18n()

const navItems = [
  { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
  { id: 'price-alerts', label: t('nav.priceAlerts'), icon: Bell },
  // ...
  { id: 'settings', label: t('nav.settings'), icon: Settings },
]
```

- [ ] **Step 5: Add the language selector to `SettingsPage` and localize its visible copy**

Add a new select near theme selection:

```tsx
<div className="space-y-2">
  <Label htmlFor="language-select">{t('settings.language.label')}</Label>
  <select
    id="language-select"
    value={localSettings.language || 'zh-CN'}
    onChange={(e) => setLocalSettings({ ...localSettings, language: e.target.value as 'zh-CN' | 'en' })}
  >
    <option value="zh-CN">{t('settings.language.zhCN')}</option>
    <option value="en">{t('settings.language.en')}</option>
  </select>
</div>
```

Then replace the page title, tab labels, save button copy, and any immediately visible general settings labels with `t(...)` calls. Do not try to move every translation key out of the file in one huge refactor; translate the page in-place against the shared dictionary.

- [ ] **Step 6: Make `App.tsx` translate the order-broadcast placeholder**

```tsx
<h3 className="text-xl font-medium">{t('nav.orderBroadcast')}</h3>
<p>{t('app.comingSoon')}</p>
```

- [ ] **Step 7: Run the focused page test**

Run: `npm run test:frontend -- src/renderer/src/test/settings-page-language.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/renderer/src/components/module-nav.tsx src/renderer/src/layouts/workbench-shell.tsx src/renderer/src/pages/SettingsPage.tsx src/renderer/src/App.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/settings-page-language.test.tsx
git commit -m "feat: add settings language switcher"
```

### Task 4: Localize Dashboard Copy Only

**Files:**
- Modify: `src/renderer/src/pages/dashboard-page.tsx:1-131`
- Modify: `src/renderer/src/i18n/messages.ts`
- Modify: `src/renderer/src/test/dashboard-page.test.tsx:1-18`

- [ ] **Step 1: Write the failing dashboard test against locale-aware navigation text**

```tsx
it('renders English navigation when language is en', async () => {
  ;(fetch as any).mockResolvedValue({
    ok: true,
    json: async () => ({ language: 'en', theme: 'light', api_refresh_interval: 1000 }),
  })

  render(<App />)

  expect(await screen.findByTitle('Price Alerts')).toBeInTheDocument()
  expect(screen.getByTitle('Settings')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: FAIL until dashboard and shell text actually consume the saved English language setting.

- [ ] **Step 3: Localize dashboard title and card headings**

Representative replacements:

```tsx
<h1 className="text-2xl font-bold">{t('dashboard.title')}</h1>
<div className="text-sm font-medium text-muted-foreground mb-1">{t('dashboard.cards.mt5Status')}</div>
<Button onClick={handleReconnect} variant="outline">{t('dashboard.actions.reconnect')}</Button>
<Button onClick={toggleOverlay} variant={isOverlayVisible ? 'destructive' : 'default'}>
  {isOverlayVisible ? t('dashboard.actions.hideOverlay') : t('dashboard.actions.showOverlay')}
</Button>
```

- [ ] **Step 4: Localize dashboard status labels only**

Representative replacements:

```tsx
<div className={cn('text-2xl font-bold', statusClassName)}>
  {status.is_running ? (status.is_connected ? t('dashboard.status.connected') : t('dashboard.status.runningNotLoggedIn')) : t('dashboard.status.stopped')}
</div>
```

- [ ] **Step 5: Localize dashboard action buttons and reconnect error text**

```tsx
<Button onClick={handleReconnect} variant="outline">{t('dashboard.actions.reconnect')}</Button>
<Button onClick={toggleOverlay} variant={isOverlayVisible ? 'destructive' : 'default'}>
  {isOverlayVisible ? t('dashboard.actions.hideOverlay') : t('dashboard.actions.showOverlay')}
</Button>
```

```tsx
window.alert(t('dashboard.errors.backendUnavailable'))
```

- [ ] **Step 6: Run the dashboard test and then the full frontend suite**

Run: `npm run test:frontend -- src/renderer/src/test/dashboard-page.test.tsx`
Expected: PASS.

Run: `npm run test:frontend`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/pages/dashboard-page.tsx src/renderer/src/i18n/messages.ts src/renderer/src/test/dashboard-page.test.tsx
git commit -m "feat: localize dashboard copy"
```

### Task 5: Localize Electron Main-Process Labels And Keep Them In Sync

**Files:**
- Create: `src/main/i18n.ts`
- Modify: `src/main/index.ts:1-251`
- Modify: `tests/e2e/app-launch.spec.ts:1-23`

- [ ] **Step 1: Write the failing smoke test assertion so launch works regardless of locale**

```ts
await expect(window).toHaveTitle(/Trader Workbench|交易工作台/)
```

If you keep the English app title in both locales, write the failing test instead against an element that will actually differ by locale, such as dashboard title text:

```ts
expect(dashboardTitle).toMatch(/工作台总览|Dashboard|Price Alerts|Indicator Alerts/)
```

- [ ] **Step 2: Run the smoke test to verify current assumptions**

Run: `npx playwright test tests/e2e/app-launch.spec.ts`
Expected: either FAIL on strict Chinese assumptions later in the file, or PASS and give you a baseline before edits.

- [ ] **Step 3: Create a tiny main-process translation helper**

```ts
export type MainLocale = 'zh-CN' | 'en'

export function tMain(locale: MainLocale, key: 'tray.showWindow' | 'tray.showOverlay' | 'tray.hideOverlay' | 'tray.quit' | 'window.title' | 'tray.tooltip') {
  const messages = {
    'zh-CN': {
      'tray.showWindow': '显示窗口',
      'tray.showOverlay': '开启浮窗',
      'tray.hideOverlay': '关闭浮窗',
      'tray.quit': '退出',
      'tray.tooltip': 'MT5 Trader Workbench',
      'window.title': 'Trader Workbench',
    },
    en: {
      'tray.showWindow': 'Show Window',
      'tray.showOverlay': 'Show Overlay',
      'tray.hideOverlay': 'Hide Overlay',
      'tray.quit': 'Quit',
      'tray.tooltip': 'MT5 Trader Workbench',
      'window.title': 'Trader Workbench',
    },
  } as const

  return messages[locale][key]
}
```

- [ ] **Step 4: Read the saved settings file or backend settings payload in `src/main/index.ts` to determine the current language**

Do this without adding a new backend endpoint. The main process already knows the app root and can read `storage/settings.json` directly with a safe fallback:

```ts
async function getCurrentLanguage(): Promise<'zh-CN' | 'en'> {
  try {
    const raw = await readFile(join(app.getAppPath(), 'storage', 'settings.json'), 'utf-8')
    const parsed = JSON.parse(raw)
    return parsed.language === 'en' ? 'en' : 'zh-CN'
  } catch {
    return 'zh-CN'
  }
}
```

If packaged path handling makes `app.getAppPath()` unreliable for `storage`, reuse the same storage-relative convention already used by the Python service and document the chosen path clearly in code comments.

- [ ] **Step 5: Apply translated text when building tray menus and the main window title, then refresh after settings change**

Representative shape:

```ts
let currentLanguage: MainLocale = 'zh-CN'

async function refreshLocalizedChrome() {
  currentLanguage = await getCurrentLanguage()
  mainWindow?.setTitle(tMain(currentLanguage, 'window.title'))
  tray?.setToolTip(tMain(currentLanguage, 'tray.tooltip'))
  updateTrayMenu()
}

ipcMain.handle('settings:notify-update', async () => {
  BrowserWindow.getAllWindows().forEach((win) => {
    win.webContents.send('settings:changed')
  })

  await refreshLocalizedChrome()
})
```

Then replace hard-coded tray labels with `tMain(currentLanguage, ...)`.

- [ ] **Step 6: Re-run the smoke test**

Run: `npx playwright test tests/e2e/app-launch.spec.ts`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/main/i18n.ts src/main/index.ts tests/e2e/app-launch.spec.ts
git commit -m "feat: localize electron tray and window labels"
```

### Task 6: Document And Manually Verify Persistence

**Files:**
- Modify: `README.md:7-25`
- Modify: `README.zh-CN.md:7-25`

- [ ] **Step 1: Update English README feature list**

Add a line such as:

```md
- Settings management for MT5 path, theme, interface language, auto-connect, refresh interval, overlay options, sound options, and DingTalk bot credentials
```

- [ ] **Step 2: Update Chinese README feature list**

Add a line such as:

```md
- 设置模块，支持 MT5 路径、主题、界面语言、自动连接、刷新频率、浮窗选项、音效选项和钉钉 Bot 凭据配置
```

- [ ] **Step 3: Run the relevant automated test suites one last time**

Run: `npm run test:frontend`
Expected: PASS.

Run: `npx playwright test tests/e2e/app-launch.spec.ts`
Expected: PASS.

- [ ] **Step 4: Perform manual verification**

Run: `npm run dev`

Manual checklist:

- open `设置` / `Settings`
- change language from Chinese to English
- click save
- confirm navigation tooltips switch to English immediately
- confirm Settings tab labels and page title switch to English immediately
- confirm Dashboard title and buttons switch to English
- confirm tray menu labels switch after settings save
- close and relaunch the app
- confirm English is still selected
- switch back to Chinese and repeat the same checks

- [ ] **Step 5: Commit**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: document settings language support"
```

## Notes For The Implementer

- Favor immediate UI updates by changing the local Zustand state before the POST request resolves, which the current settings store already does.
- Keep `language` values canonical and narrow: only `'zh-CN'` and `'en'`.
- If a backend response omits `language`, coerce it to `'zh-CN'` in the renderer store rather than letting `undefined` leak through the tree.
- Avoid a giant “translate everything in one edit” commit. Follow the task boundaries above.
- If tests become brittle because they assert exact Chinese copy from many places, update them to target one stable translated string per surface instead of duplicating the full UI.
