import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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

import { I18nProvider } from '@/i18n'
import { QuantBacktestPage } from '@/pages/QuantBacktestPage'
import { useQuantBacktestStore } from '@/stores/quant-backtest-store'
import { usePythonQuantStore } from '@/stores/python-quant-store'

function renderPage() {
  return render(
    <I18nProvider language="en">
      <QuantBacktestPage />
    </I18nProvider>
  )
}

describe('QuantBacktestPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    usePythonQuantStore.setState({
      overview: {
        accounts: [],
        strategies: [],
        jobs: [],
      },
      isLoading: false,
      error: null,
    })
    useQuantBacktestStore.setState({
      strategies: [],
      result: null,
      error: null,
      isLoadingStrategies: false,
      isRunning: false,
    })
  })

  it('runs a backtest and renders summary, equity, and trades', async () => {
    const user = userEvent.setup()
    const requests: Array<{ url: string; method: string; body?: string }> = []

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      requests.push({ url, method, body: typeof init?.body === 'string' ? init.body : undefined })

      if (url.endsWith('/python-quant/overview')) {
        return {
          ok: true,
          json: async () => ({
            accounts: [{ id: 'acc-1', name: 'Main A', login: '10001' }],
            strategies: [],
            jobs: [],
          }),
        } as Response
      }

      if (url.endsWith('/python-quant/backtests/strategies')) {
        return {
          ok: true,
          json: async () => [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M15'] }],
        } as Response
      }

      if (url.endsWith('/python-quant/backtests/run') && method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            strategy: { id: 'sma_cross', name: 'SMA Cross' },
            symbol: 'XAUUSD',
            timeframe: 'M15',
            range: {
              start_at: '2026-05-01T00:00:00Z',
              end_at: '2026-05-31T23:59:59Z',
            },
            summary: {
              total_return_pct: 4.52,
              trade_count: 2,
              win_rate_pct: 50,
              max_drawdown_pct: -2.14,
            },
            equity_curve: [
              { time: '2026-05-01T00:00:00Z', equity: 10000 },
              { time: '2026-05-02T00:00:00Z', equity: 10031.2 },
            ],
            trades: [
              {
                entry_time: '2026-05-02T08:00:00Z',
                exit_time: '2026-05-02T10:30:00Z',
                side: 'buy',
                pnl: 31.2,
              },
            ],
          }),
        } as Response
      }

      throw new Error(`Unhandled request: ${method} ${url}`)
    }) as typeof fetch

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Quant Backtest', level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/shared with Python Quant live assignments/i)).toBeInTheDocument()
    expect(screen.getByText(/uses cached mt5 bars and simplified signal replay/i)).toBeInTheDocument()
    expect(screen.getByText(/does not include spread, slippage, fees, or contract-specific pnl/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByLabelText('MT5 Account')).toHaveValue('acc-1')
      expect(screen.getByLabelText('Strategy')).toHaveValue('sma_cross')
    })

    await user.selectOptions(screen.getByLabelText('Timeframe'), 'M15')
    fireEvent.change(screen.getByLabelText('Start Date'), { target: { value: '2026-05-01' } })
    fireEvent.change(screen.getByLabelText('End Date'), { target: { value: '2026-05-31' } })
    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))

    expect(await screen.findByText('4.52%')).toBeInTheDocument()
    expect(screen.getByText('Simplified Replay Return')).toBeInTheDocument()
    expect(screen.getAllByText('2')).toHaveLength(2)
    expect(screen.getAllByText('10031.20')).toHaveLength(2)
    expect(screen.getByText('buy')).toBeInTheDocument()

    const runRequest = requests.find((request) => request.url.endsWith('/python-quant/backtests/run'))
    expect(runRequest?.body).toContain('"account_id":"acc-1"')
    expect(runRequest?.body).toContain('"strategy_id":"sma_cross"')
    expect(runRequest?.body).toContain('"start_at":"2026-05-01T00:00:00Z"')
    expect(runRequest?.body).toContain('"end_at":"2026-05-31T23:59:59Z"')
  })
})
