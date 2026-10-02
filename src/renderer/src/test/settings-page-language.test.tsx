import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '@/App'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'
import { useDashboardStore } from '@/stores/dashboard-store'

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'light',
    setTheme: vi.fn(),
  }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}))

function TestRoot() {
  const language = useSettingsStore((state) => state.settings.language || 'zh-CN')

  return (
    <I18nProvider language={language}>
      <App />
    </I18nProvider>
  )
}

// Radix overlays (Select, Tabs) loop forever in jsdom without these.
beforeEach(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {}
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {}
  }
})

describe('Settings language switch', () => {
  beforeEach(() => {
    vi.resetAllMocks()

    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
      isLoading: false,
      error: null,
    })

    useDashboardStore.setState({
      account: null,
      status: { is_running: false, is_connected: false },
      isLoading: false,
    })

    vi.spyOn(useDashboardStore.getState(), 'startPolling').mockImplementation(() => undefined)
    vi.spyOn(useDashboardStore.getState(), 'stopPolling').mockImplementation(() => undefined)

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            // Serve the language the store last saved; the real backend echoes
            // persisted settings, and a stale 'zh-CN' here would flip the UI
            // right back after saving 'en'.
            language: useSettingsStore.getState().settings.language || 'zh-CN',
          }),
        } as Response
      }

      if (url.endsWith('/settings') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ status: 'ok' }),
        } as Response
      }

      if (url.endsWith('/mt5/status')) {
        return {
          ok: true,
          json: async () => ({ is_running: false, is_connected: false }),
        } as Response
      }

      if (url.endsWith('/mt5/account')) {
        return {
          ok: true,
          json: async () => ({ balance: 0, equity: 0, margin_level: 0, profit: 0 }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ([]),
      } as Response
    }) as any
  })

  it('switches the visible settings copy to English after saving language', async () => {
    render(<TestRoot />)

    fireEvent.click(await screen.findByTitle('设置'))

    await waitFor(() => {
      expect(useSettingsStore.getState().settings.language).toBe('zh-CN')
    })

    // Drive the same store action the language Select's onChange uses
    // (SettingsPage.tsx: updateSettings({ language })). Driving the real
    // Radix Select open/click hangs jsdom in this environment; the save
    // path under test is the store -> POST -> state -> provider chain.
    await useSettingsStore.getState().updateSettings({ language: 'en' })

    await waitFor(() => {
      expect(useSettingsStore.getState().settings.language).toBe('en')
    })

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument()
    })

    expect(await screen.findByText('Connection')).toBeInTheDocument()
  })

  it('shows planned config migration and sensitive information guidance', async () => {
    render(<TestRoot />)

    fireEvent.click(await screen.findByTitle('设置'))
    const aboutTab = await screen.findByRole('tab', { name: '关于' })
    fireEvent.click(aboutTab)
    fireEvent.keyDown(aboutTab, { key: 'Enter' })

    expect(await screen.findByText('配置迁移')).toBeInTheDocument()
    expect(screen.getByText('当前版本尚未提供设置导入/导出接口；配置迁移请先按手动流程处理。')).toBeInTheDocument()
    expect(screen.getByText(/storage\/settings\.local\.json/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '导出配置' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '导入配置' })).toBeDisabled()
    expect(screen.getByText('敏感信息保护')).toBeInTheDocument()
    expect(screen.getByText(/MT5 路径和账户凭据、TopStep API Key，以及 Bot webhook\/token/)).toBeInTheDocument()
  })
})
