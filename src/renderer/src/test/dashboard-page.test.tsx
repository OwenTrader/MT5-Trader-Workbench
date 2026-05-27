import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from '@/App'
import { I18nProvider } from '@/i18n'
import { useAlertsStore } from '@/stores/alerts-store'
import { useLocalCopyTradingStore } from '@/stores/local-copy-trading-store'
import { useOrderSyncStore } from '@/stores/order-sync-store'
import { useSettingsStore } from '@/stores/settings-store'
import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('sonner', () => ({
  Toaster: () => null,
  toast: {
    error: vi.fn(),
  },
}))

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
    useAlertsStore.setState(useAlertsStore.getInitialState())
    useLocalCopyTradingStore.setState(useLocalCopyTradingStore.getInitialState())
    useOrderSyncStore.setState(useOrderSyncStore.getInitialState())

    Object.defineProperty(window, 'electron', {
      configurable: true,
      value: {
        ipcRenderer: {
          invoke: vi.fn(async (channel: string) => {
            if (channel === 'overlay:is-visible') return true
            return undefined
          }),
          on: vi.fn(() => () => undefined),
        },
      },
    })

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            language: 'en',
            dingtalk_enabled: true,
            dingtalk_token: 'token',
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

      if (url.endsWith('/alerts/price')) {
        return {
          ok: true,
          json: async () => ([{ id: 'price-1', symbol: 'XAUUSD', price: 3000, condition: 'above', is_active: true, is_triggered: false, comment: '' }]),
        } as Response
      }

      if (url.endsWith('/alerts/volatility')) {
        return {
          ok: true,
          json: async () => ([]),
        } as Response
      }

      if (url.endsWith('/alerts/indicator')) {
        return {
          ok: true,
          json: async () => ([{ id: 'indicator-1', symbol: 'XAUUSD', timeframe: 'M5', indicator_type: 'rsi', period: 14, condition: 'below', threshold: 30, is_active: false, is_triggered: false, comment: '' }]),
        } as Response
      }

      if (url.endsWith('/order-sync')) {
        return {
          ok: true,
          json: async () => ({
            enabled: true,
            mappings: [{ id: 'map-1', mt5_symbol: 'XAUUSD', topstep_contract_id: 'GC', topstep_display_name: 'Gold', quantity_multiplier: 1, mt5_lots: 0.1, topstep_contracts: 1, is_active: true }],
            synced_orders: [{ mt5_ticket: 91001, mt5_symbol: 'XAUUSD', mt5_volume: 0.1, topstep_account_id: 100, topstep_contract_id: 'GC', topstep_order_id: 7001, side: 'buy', size: 1, status: 'open', opened_at: '2026-05-20T10:00:00Z', closed_at: null, last_error: null, blocked_reason: null }],
          }),
        } as Response
      }

      if (url.endsWith('/local-copy-trading')) {
        return {
          ok: true,
          json: async () => ({
            events: [{ id: 'evt-1', relationship_id: 'rel-1', source_account_id: 'source-1', follower_account_id: 'follower-1', position_id: 'pos-1', symbol: 'EURUSD', status: 'copied', message: 'Follower order copied', created_at: '2026-05-20T10:01:00Z' }],
          }),
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
    expect(screen.getByTitle('Event Log')).toBeInTheDocument()
    expect(screen.getByTitle('Order Center')).toBeInTheDocument()
    expect(screen.getByTitle('Support Me')).toBeInTheDocument()
    expect(screen.getByTitle('Settings')).toBeInTheDocument()
  })

  it('shows disconnected backend state on first launch', async () => {
    render(<TestRoot />)
    expect((await screen.findAllByText('Stopped')).length).toBeGreaterThan(0)
  })

  it('renders dashboard heading in English after settings load', async () => {
    render(<TestRoot />)

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  it('surfaces running status center details', async () => {
    render(<TestRoot />)

    expect(await screen.findByText('Running Status Center')).toBeInTheDocument()
    expect(screen.getByText('Price Overlay')).toBeInTheDocument()
    expect(await screen.findByText('Visible')).toBeInTheDocument()
    expect(await screen.findByText('1 active')).toBeInTheDocument()
    expect(await screen.findByText('3 push types enabled')).toBeInTheDocument()
    expect(await screen.findByText('Enabled at 50%')).toBeInTheDocument()
    expect(await screen.findByText('Enabled with 1 mappings')).toBeInTheDocument()
  })

  it('shows notifications disabled when no bot transport is configured', async () => {
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
        return { ok: true, json: async () => ({ is_running: false, is_connected: false }) } as Response
      }

      if (url.endsWith('/mt5/account')) {
        return { ok: true, json: async () => ({ balance: 0, equity: 0, margin_level: 0, profit: 0 }) } as Response
      }

      if (url.endsWith('/order-sync')) {
        return { ok: true, json: async () => ({ enabled: false, mappings: [] }) } as Response
      }

      return { ok: true, json: async () => [] } as Response
    }) as any

    render(<TestRoot />)

    expect(await screen.findByText('Push notifications disabled')).toBeInTheDocument()
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
    expect(await within(nav).findByRole('button', { name: 'Event Log' })).toBeInTheDocument()
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
    expect(await screen.findByText('Generate AI Analysis')).toBeInTheDocument()
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

  it('navigates to and renders available recent events from the sidebar', async () => {
    const user = userEvent.setup()
    render(<TestRoot />)

    const trigger = await getSidebarTrigger()
    await user.click(trigger)

    const nav = getSidebarNav()
    expect(nav).not.toBeNull()
    if (!nav) throw new Error('Sidebar navigation not found')
    await user.click(await within(nav).findByRole('button', { name: 'Event Log' }))

    expect(window.location.hash).toContain('/event-log')
    expect(await screen.findByRole('heading', { name: 'Event Log' })).toBeInTheDocument()
    expect(await screen.findByText('This lightweight event log only aggregates local copy trading events, order sync records, and the latest errors currently available to the renderer. It is not a complete audit history.')).toBeInTheDocument()
    expect(await screen.findByText('Follower order copied')).toBeInTheDocument()
    expect(await screen.findByText('TopStep #7001')).toBeInTheDocument()
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
