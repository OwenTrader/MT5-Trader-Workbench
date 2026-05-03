import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from '@/App'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'
import { describe, it, expect, beforeEach, vi } from 'vitest'

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

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
      isLoading: false,
      error: null,
    })

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            language: 'en',
          }),
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

  it('renders English navigation when language is en', async () => {
    render(<TestRoot />)

    expect(await screen.findByTitle('Price Alerts')).toBeInTheDocument()
    expect(screen.getByTitle('Order Center')).toBeInTheDocument()
    expect(screen.getByTitle('Settings')).toBeInTheDocument()
  })

  it('shows disconnected backend state on first launch', async () => {
    render(<TestRoot />)
    expect(await screen.findByText('Stopped')).toBeInTheDocument()
  })

  it('renders dashboard heading in English after settings load', async () => {
    render(<TestRoot />)

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('renders shadcn sidebar navigation labels after expanding the menu', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await screen.findByRole('button', { name: /toggle main navigation/i })
    await user.click(trigger)

    const nav = screen.getByLabelText('Main navigation')
    expect(await within(nav).findByRole('button', { name: 'Dashboard' })).toBeInTheDocument()
    expect(await within(nav).findByRole('button', { name: 'Technical Analysis' })).toBeInTheDocument()
    expect(await within(nav).findByRole('button', { name: 'Settings' })).toBeInTheDocument()
  })

  it('switches modules from the shadcn sidebar menu', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await screen.findByRole('button', { name: /toggle main navigation/i })
    await user.click(trigger)

    const nav = screen.getByLabelText('Main navigation')
    await user.click(await within(nav).findByRole('button', { name: 'Technical Analysis' }))

    expect(await screen.findByText('Generate Technical Analysis')).toBeInTheDocument()
  })

  it('uses desktop-sized sidebar icons rather than tiny web sidebar icons', async () => {
    render(<TestRoot />)

    const dashboardIcon = await screen.findByTestId('sidebar-icon-dashboard')
    expect(dashboardIcon).toHaveClass('size-5')
  })
})
