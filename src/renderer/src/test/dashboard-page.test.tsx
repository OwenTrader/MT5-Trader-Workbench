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

async function getSidebarTrigger() {
  const triggers = await screen.findAllByRole('button', { name: /toggle sidebar/i })
  return triggers.find((trigger) => trigger.getAttribute('data-sidebar') === 'trigger') ?? triggers[0]
}

function getSidebarNav() {
  return document.querySelector('[data-sidebar="sidebar"]') as HTMLElement | null
}

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.location.hash = ''
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
    expect(screen.getByTitle('Local Copy Trading')).toBeInTheDocument()
    expect(screen.getByTitle('Order Center')).toBeInTheDocument()
    expect(screen.getByTitle('Support Me')).toBeInTheDocument()
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

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')
    expect(await within(nav).findByRole('button', { name: 'Dashboard' })).toBeInTheDocument()
    expect(await within(nav).findByRole('button', { name: 'Technical Analysis' })).toBeInTheDocument()
    expect(await within(nav).findByRole('button', { name: 'Support Me' })).toBeInTheDocument()
    expect(await within(nav).findByRole('button', { name: 'Settings' })).toBeInTheDocument()
  })

  it('renders support me before settings in the sidebar order', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')

    const buttons = within(nav).getAllByRole('button')
    const labels = buttons.map((button) => button.getAttribute('title'))
    expect(labels.indexOf('Support Me')).toBeLessThan(labels.indexOf('Settings'))
  })

  it('switches to the support me page from the sidebar menu', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')
    await user.click(await within(nav).findByRole('button', { name: 'Support Me' }))

    expect(await screen.findByRole('heading', { name: 'Support Me' })).toBeInTheDocument()
    expect(screen.getByText('Buy TradingView Membership From Me')).toBeInTheDocument()
    expect(screen.getByText('Sponsorship or Custom Features')).toBeInTheDocument()
  })

  it('switches modules from the shadcn sidebar menu', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')
    await user.click(await within(nav).findByRole('button', { name: 'Technical Analysis' }))

    expect(window.location.hash).toContain('/tech-analysis')
    expect(await screen.findByText('Generate Technical Analysis')).toBeInTheDocument()
  })

  it('navigates to and renders the local copy trading page from the sidebar', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')
    await user.click(await within(nav).findByRole('button', { name: 'Local Copy Trading' }))

    expect(window.location.hash).toContain('/local-copy-trading')
    expect(await screen.findByRole('heading', { name: 'Local Copy Trading' })).toBeInTheDocument()
  })

  it('renders sidebar icons for navigation items', async () => {
    render(<TestRoot />)

    const dashboardIcon = await screen.findByTestId('sidebar-icon-dashboard')
    expect(dashboardIcon).toBeInTheDocument()
  })

  it('does not write debug logs during normal app render', async () => {
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {})

    render(<TestRoot />)

    expect(logSpy).not.toHaveBeenCalled()
    logSpy.mockRestore()
  })
})
