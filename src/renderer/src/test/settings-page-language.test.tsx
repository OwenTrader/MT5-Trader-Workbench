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
            language: 'zh-CN',
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

    fireEvent.click(screen.getByLabelText('界面语言'))
    fireEvent.click(await screen.findByRole('option', { name: 'English' }))
    const saveButtons = await screen.findAllByRole('button', { name: /保存设置|Save Settings/ })
    fireEvent.click(saveButtons[0])

    await waitFor(() => {
      expect(useSettingsStore.getState().settings.language).toBe('en')
    })

    await waitFor(() => {
      expect(screen.getByText('System Settings')).toBeInTheDocument()
    })

    expect(screen.getByText('Connection')).toBeInTheDocument()
  })
})
