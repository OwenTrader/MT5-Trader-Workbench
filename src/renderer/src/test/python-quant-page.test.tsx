import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'

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

vi.mock('@/components/ui/select', () => {
  const SelectContext = React.createContext<{
    value?: string
    onValueChange?: (value: string) => void
    options: Array<{ value: string; label: string }>
    registerOption: (option: { value: string; label: string }) => void
  } | null>(null)

  function Select({ value, onValueChange, children }: { value?: string; onValueChange?: (value: string) => void; children: React.ReactNode }) {
    const [options, setOptions] = React.useState<Array<{ value: string; label: string }>>([])

    const registerOption = React.useCallback((option: { value: string; label: string }) => {
      setOptions((current) => (current.some((item) => item.value === option.value) ? current : [...current, option]))
    }, [])

    return <SelectContext.Provider value={{ value, onValueChange, options, registerOption }}>{children}</SelectContext.Provider>
  }

  function SelectTrigger({ 'aria-label': ariaLabel }: { children: React.ReactNode; 'aria-label'?: string }) {
    const context = React.useContext(SelectContext)
    if (!context) {
      return null
    }

    return (
      <select aria-label={ariaLabel} value={context.value ?? ''} onChange={(event) => context.onValueChange?.(event.target.value)}>
        <option value=""></option>
        {context.options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    )
  }

  function SelectValue() {
    return null
  }

  function SelectContent({ children }: { children: React.ReactNode }) {
    return <>{children}</>
  }

  function SelectGroup({ children }: { children: React.ReactNode }) {
    return <>{children}</>
  }

  function SelectItem({ value, children }: { value: string; children: React.ReactNode }) {
    const context = React.useContext(SelectContext)

    React.useEffect(() => {
      const label = typeof children === 'string' ? children : String(value)
      context?.registerOption({ value, label })
    }, [children, context, value])

    return <>{children}</>
  }

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectGroup,
    SelectItem,
  }
})

import { App } from '@/App'
import { I18nProvider } from '@/i18n'
import { PythonQuantPage } from '@/pages/PythonQuantPage'
import { usePythonQuantStore } from '@/stores/python-quant-store'

type TestOverview = {
  accounts: Array<{ id: string; name: string; login: string }>
  strategies: Array<{ id: string; name: string; description: string; timeframes: string[] }>
  jobs: Array<{
    id: string
    name: string
    account_id: string
    strategy_id: string
    symbol: string
    timeframe: string
    lot: number
    execution_mode: 'paper' | 'live'
    enabled: boolean
    status: 'stopped' | 'running' | 'error'
    last_signal: 'buy' | 'sell' | 'close' | 'hold' | null
    last_error: string | null
    last_bar_time: string | null
    updated_at: string
  }>
}

function renderPage() {
  return render(
    <I18nProvider language="en">
      <PythonQuantPage />
    </I18nProvider>
  )
}

function renderApp() {
  return render(
    <I18nProvider language="en">
      <App />
    </I18nProvider>
  )
}

function createOverview(): TestOverview {
  return {
    accounts: [{ id: 'acc-1', name: 'Main A', login: '10001' }],
    strategies: [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M5', 'M15'] }],
    jobs: [{
      id: 'job-1',
      name: 'Gold M5 Trend',
      account_id: 'acc-1',
      strategy_id: 'sma_cross',
      symbol: 'XAUUSD',
      timeframe: 'M5',
      lot: 0.01,
      execution_mode: 'live',
      enabled: false,
      status: 'stopped',
      last_signal: null,
      last_error: null,
      last_bar_time: '2026-06-05T08:35:00+00:00',
      updated_at: '2026-06-05T08:35:04+00:00',
    }],
  }
}

describe('PythonQuantPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.location.hash = ''
    vi.stubGlobal('confirm', vi.fn(() => true))
    usePythonQuantStore.setState({
      overview: {
        accounts: [],
        strategies: [],
        jobs: [],
      },
      isLoading: false,
      error: null,
    })
  })

  it('renders the python quant page heading', async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => createOverview(),
    })) as typeof fetch

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Python Quant', level: 1 })).toBeInTheDocument()
  })

  it('shows that Python Quant reuses Account List accounts for live assignments', async () => {
    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => createOverview(),
    })) as typeof fetch

    renderPage()

    expect(await screen.findByText(/already configured in Account List/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Backtest' })).not.toBeInTheDocument()
  })

  it('renders a unified Quant entry inside the account module group', async () => {
    const user = userEvent.setup()
    window.location.hash = '#/quant'

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/python-quant/overview')) {
        return { ok: true, json: async () => structuredClone(createOverview()) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/events')) {
        return { ok: true, json: async () => [] } as Response
      }

      if (url.endsWith('/python-quant/backtests/strategies')) {
        return {
          ok: true,
          json: async () => [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M15'] }],
        } as Response
      }

      throw new Error(`Unhandled request: ${url}`)
    }) as typeof fetch

    renderApp()

    const group = (await screen.findByText('Independent Accounts')).closest('[data-sidebar="group"]')
    expect(group).not.toBeNull()
    if (!group) {
      throw new Error('Independent Accounts group not found')
    }

    expect(within(group).getByRole('button', { name: 'Quant' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Quant', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Live Jobs' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Backtest' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Backtest' }))
    expect(window.location.hash).toContain('tab=backtest')
    expect(await screen.findByRole('heading', { name: 'Quant Backtest', level: 1 })).toBeInTheDocument()
  })

  it('creates, updates, starts, stops, deletes, and backfills jobs from the page', async () => {
    const user = userEvent.setup()
    const requests: Array<{ url: string; method: string; body?: string }> = []
    let overview = createOverview()

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      requests.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined })

      if (url.endsWith('/python-quant/overview')) {
        return { ok: true, json: async () => structuredClone(overview) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/events')) {
        return {
          ok: true,
          json: async () => [{
            id: 'event-1',
            job_id: 'job-1',
            event_type: 'signal_generated',
            message: 'buy signal evaluated for XAUUSD',
            details: {},
            created_at: '2026-06-05T08:35:10+00:00',
          }],
        } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-2/events')) {
        return { ok: true, json: async () => [] } as Response
      }

      if (url.endsWith('/python-quant/jobs') && method === 'POST') {
        const payload = JSON.parse(String(init?.body))
        overview = {
          ...overview,
          jobs: [
            ...overview.jobs,
            {
              id: 'job-2',
              enabled: false,
              status: 'stopped',
              last_signal: null,
              last_error: null,
              last_bar_time: null,
              updated_at: '2026-06-05T09:00:00+00:00',
              ...payload,
            },
          ],
        }
        return { ok: true, json: async () => ({ id: 'job-2' }) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1') && method === 'PUT') {
        const payload = JSON.parse(String(init?.body))
        overview = {
          ...overview,
          jobs: overview.jobs.map((job) => job.id === 'job-1'
            ? {
              ...job,
              ...payload,
            }
            : job),
        }
        return { ok: true, json: async () => ({ ok: true }) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/start') && method === 'POST') {
        overview = {
          ...overview,
          jobs: overview.jobs.map((job) => job.id === 'job-1' ? { ...job, enabled: true, status: 'running' } : job),
        }
        return { ok: true, json: async () => ({ ok: true }) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/stop') && method === 'POST') {
        overview = {
          ...overview,
          jobs: overview.jobs.map((job) => job.id === 'job-1' ? { ...job, enabled: false, status: 'stopped' } : job),
        }
        return { ok: true, json: async () => ({ ok: true }) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1') && method === 'DELETE') {
        overview = {
          ...overview,
          jobs: overview.jobs.filter((job) => job.id !== 'job-1'),
        }
        return { ok: true, json: async () => ({ ok: true }) } as Response
      }

      if (url.endsWith('/python-quant/data/backfill') && method === 'POST') {
        return { ok: true, json: async () => ({ inserted_rows: 321 }) } as Response
      }

      throw new Error(`Unhandled request: ${method} ${url}`)
    }) as typeof fetch

    renderPage()

    expect(await screen.findByText('Gold M5 Trend')).toBeInTheDocument()
    expect(await screen.findByText('buy signal evaluated for XAUUSD')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Job Name'), 'Silver M15 Mean Reversion')
    await user.clear(screen.getByLabelText('Symbol'))
    await user.type(screen.getByLabelText('Symbol'), 'XAGUSD')
    await user.selectOptions(screen.getByLabelText('Execution Mode'), 'live')
    await user.selectOptions(screen.getByLabelText('Timeframe'), 'M15')
    await user.clear(screen.getByLabelText('Lot Size'))
    await user.type(screen.getByLabelText('Lot Size'), '0.02')
    await user.click(screen.getByRole('button', { name: 'Create Job' }))

    await waitFor(() => {
      expect(screen.getByText('Silver M15 Mean Reversion')).toBeInTheDocument()
    })
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs') && request.method === 'POST' && request.body?.includes('Silver M15 Mean Reversion'))).toBe(true)
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs') && request.method === 'POST' && request.body?.includes('"execution_mode":"live"'))).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Edit Gold M5 Trend' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeInTheDocument()

    const dialogNameInput = within(dialog).getByLabelText('Edit Job Name')
    await user.clear(dialogNameInput)
    await user.type(dialogNameInput, 'Gold M5 Breakout')
    await user.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('Gold M5 Breakout')).toBeInTheDocument()
    })
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs/job-1') && request.method === 'PUT' && request.body?.includes('Gold M5 Breakout'))).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Start Gold M5 Breakout' }))
    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument()
    })
    expect(window.confirm).toHaveBeenCalled()
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs/job-1/start') && request.method === 'POST')).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Stop Gold M5 Breakout' }))
    await waitFor(() => {
      expect(screen.getAllByText('stopped').length).toBeGreaterThan(0)
    })
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs/job-1/stop') && request.method === 'POST')).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Delete Gold M5 Breakout' }))
    await waitFor(() => {
      expect(screen.queryByText('Gold M5 Breakout')).not.toBeInTheDocument()
    })
    expect(requests.some((request) => request.url.endsWith('/python-quant/jobs/job-1') && request.method === 'DELETE')).toBe(true)

    await user.clear(screen.getByLabelText('Bars'))
    await user.type(screen.getByLabelText('Bars'), '321')
    await user.click(screen.getByRole('button', { name: 'Backfill Data' }))

    expect(await screen.findByText('Inserted 321 rows')).toBeInTheDocument()
    expect(requests.some((request) => request.url.endsWith('/python-quant/data/backfill') && request.method === 'POST' && request.body?.includes('321'))).toBe(true)
  })

  it('shows inline backend errors when create, start, and backfill fail', async () => {
    const user = userEvent.setup()
    const overview = createOverview()

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (url.endsWith('/python-quant/overview')) {
        return { ok: true, json: async () => structuredClone(overview) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/events')) {
        return { ok: true, json: async () => [] } as Response
      }

      if (url.endsWith('/python-quant/jobs') && method === 'POST') {
        return { ok: false, json: async () => ({ detail: 'Only one enabled quant job per account and symbol is allowed in V1' }) } as Response
      }

      if (url.endsWith('/python-quant/jobs/job-1/start') && method === 'POST') {
        return { ok: false, json: async () => ({ detail: 'Strategy runtime is unavailable' }) } as Response
      }

      if (url.endsWith('/python-quant/data/backfill') && method === 'POST') {
        return { ok: false, json: async () => ({ detail: 'Unable to fetch MT5 bars for XAUUSD' }) } as Response
      }

      throw new Error(`Unhandled request: ${method} ${url}`)
    }) as typeof fetch

    renderPage()

    expect(await screen.findByText('Gold M5 Trend')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Job Name'), 'Duplicate XAUUSD job')
    await user.click(screen.getByRole('button', { name: 'Create Job' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Only one enabled quant job per account and symbol is allowed in V1')

    await user.click(screen.getByRole('button', { name: 'Start Gold M5 Trend' }))
    await waitFor(() => {
      expect(screen.getAllByRole('alert').some((node) => node.textContent?.includes('Strategy runtime is unavailable'))).toBe(true)
    })

    await user.click(screen.getByRole('button', { name: 'Backfill Data' }))
    await waitFor(() => {
      expect(screen.getAllByRole('alert').some((node) => node.textContent?.includes('Unable to fetch MT5 bars for XAUUSD'))).toBe(true)
    })
  })
})
