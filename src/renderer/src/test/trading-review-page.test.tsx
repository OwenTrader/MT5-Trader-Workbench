import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TradingReviewPage } from '@/pages/TradingReviewPage'
import { useTradingReviewStore } from '@/stores/trading-review-store'
import { I18nProvider } from '@/i18n'
import { MemoryRouter } from 'react-router-dom'

// Mock TradingChart
vi.mock('@/components/trading-chart', () => ({
  TradingChart: () => <div data-testid="mock-trading-chart">Trading Chart Mock</div>,
}))

// Mock apiFetch
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from '@/lib/api'

function renderPage() {
  return render(
    <MemoryRouter>
      <I18nProvider>
        <TradingReviewPage />
      </I18nProvider>
    </MemoryRouter>
  )
}

describe('TradingReviewPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useTradingReviewStore.setState({
      sessions: [],
      currentSession: null,
      trades: [],
      klines: [],
      loading: false,
      error: null,
      isPlaying: false,
      playbackSpeed: 1,
    })
  })

  it('renders session list and creation form with cached dataset helper', async () => {
    ;(apiFetch as any).mockImplementation(async (url: string) => {
      if (url.includes('/data-management/summary')) {
        return {
          ok: true,
          json: async () => [
            { symbol: 'XAUUSD', timeframe: 'M15', count: 1200, min_time: 1700000000, max_time: 1700100000 },
          ],
        }
      }
      if (url.includes('/trading-review/sessions')) {
        return {
          ok: true,
          json: async () => [
            {
              id: 1,
              symbol: 'XAUUSD',
              timeframe: 'M15',
              start_time: 1700000000,
              end_time: 1700100000,
              initial_balance: 10000,
              current_balance: 10250,
              current_time: 1700050000,
              created_at: 1700000000,
            },
          ],
        }
      }
      return { ok: true, json: async () => ({}) }
    })

    renderPage()

    expect(await screen.findByText('XAUUSD')).toBeInTheDocument()
    expect(screen.getByText('$10250.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /开始复盘|Start Review/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /继续复盘|Resume/i })).toBeInTheDocument()
  })

  it('renders active workspace with trade controls, chart, and hotkey guide', async () => {
    useTradingReviewStore.setState({
      currentSession: {
        id: 1,
        symbol: 'XAUUSD',
        timeframe: 'M15',
        start_time: 1700000000,
        end_time: 1700100000,
        initial_balance: 10000,
        current_balance: 10000,
        current_time: 1700000000,
        created_at: 1700000000,
      },
      klines: [
        { time: 1700000000, open: 2000, high: 2010, low: 1990, close: 2005, tick_volume: 100 },
      ],
      trades: [],
    })

    renderPage()

    expect(screen.getByTestId('mock-trading-chart')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /做多|Buy/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /做空|Sell/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('SL')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('TP')).toBeInTheDocument()
    expect(screen.getByText(/Space:/i)).toBeInTheDocument()
  })

  it('switches to analytics tab and displays performance metrics', async () => {
    const user = userEvent.setup()

    useTradingReviewStore.setState({
      currentSession: {
        id: 1,
        symbol: 'XAUUSD',
        timeframe: 'M15',
        start_time: 1700000000,
        end_time: 1700100000,
        initial_balance: 10000,
        current_balance: 10300,
        current_time: 1700000000,
        created_at: 1700000000,
      },
      klines: [
        { time: 1700000000, open: 2000, high: 2010, low: 1990, close: 2005, tick_volume: 100 },
      ],
      trades: [
        { id: 1, session_id: 1, type: 'buy', open_time: 1000, open_price: 2000, close_time: 1100, close_price: 2030, lots: 0.1, profit: 300 },
      ],
    })

    renderPage()

    const analyticsTab = screen.getByRole('tab', { name: /战绩统计|Performance/i })
    await user.click(analyticsTab)

    expect(screen.getByText('100.0%')).toBeInTheDocument()
    expect(screen.getByText('+$300.00 (3.0%)')).toBeInTheDocument()
  })
})
