import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useQuantBacktestStore } from '@/stores/quant-backtest-store'

global.fetch = vi.fn()

describe('Quant Backtest Store', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useQuantBacktestStore.setState({
      strategies: [],
      result: null,
      error: null,
      isLoadingStrategies: false,
      isRunning: false,
    })
  })

  it('loads backtest strategies from the backend', async () => {
    ;(fetch as any).mockResolvedValue({
      ok: true,
      json: async () => [
        { id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M5', 'M15'] },
      ],
    })

    const { result } = renderHook(() => useQuantBacktestStore())

    await act(async () => {
      await result.current.fetchStrategies()
    })

    expect(result.current.strategies[0]?.id).toBe('sma_cross')
    expect(result.current.strategies[0]?.timeframes).toEqual(['M5', 'M15'])
  })

  it('posts backtest requests and stores results', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/python-quant/backtests/run')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('sma_cross')
      expect(init?.body).toContain('2026-05-01T00:00:00Z')

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
            trade_count: 18,
            win_rate_pct: 55.56,
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
    })

    const { result } = renderHook(() => useQuantBacktestStore())

    let success = false
    await act(async () => {
      success = await result.current.runBacktest({
        strategy_id: 'sma_cross',
        account_id: 'acc-1',
        symbol: 'XAUUSD',
        timeframe: 'M15',
        start_at: '2026-05-01T00:00:00Z',
        end_at: '2026-05-31T23:59:59Z',
      })
    })

    expect(success).toBe(true)
    await waitFor(() => {
      expect(result.current.result?.summary.trade_count).toBe(18)
    })
    expect(result.current.result?.trades[0]?.side).toBe('buy')
  })
})
