import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useTradingReviewStore,
  calculatePerformanceMetrics,
  getContractMultiplier,
  calculateFloatingPnL,
} from '@/stores/trading-review-store'

global.fetch = vi.fn()

describe('Trading Review Store & Metrics', () => {
  beforeEach(() => {
    vi.resetAllMocks()
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

  it('calculates contract multiplier correctly across asset classes', () => {
    expect(getContractMultiplier('XAUUSD')).toBe(100)
    expect(getContractMultiplier('GOLD')).toBe(100)
    expect(getContractMultiplier('EURUSD')).toBe(100000)
    expect(getContractMultiplier('GBPUSD')).toBe(100000)
    expect(getContractMultiplier('BTCUSD')).toBe(1)
    expect(getContractMultiplier('US30')).toBe(1)
  })

  it('calculates accurate floating PnL', () => {
    const activeTrades = [
      {
        id: 1,
        session_id: 1,
        type: 'buy' as const,
        open_time: 1000,
        open_price: 2000.0,
        close_time: null,
        close_price: null,
        lots: 0.1,
        profit: null,
        sl: 1990,
        tp: 2020,
      },
    ]

    const pnlGold = calculateFloatingPnL('XAUUSD', activeTrades, 2010.0)
    // 0.1 lot * (2010 - 2000) * 100 = 100.0
    expect(pnlGold).toBeCloseTo(100.0)

    const pnlForex = calculateFloatingPnL('EURUSD', [{
      id: 2,
      session_id: 1,
      type: 'sell' as const,
      open_time: 1000,
      open_price: 1.0850,
      close_time: null,
      close_price: null,
      lots: 0.2,
      profit: null,
    }], 1.0800)
    // 0.2 lot * (1.0850 - 1.0800) * 100,000 = +100.0
    expect(pnlForex).toBeCloseTo(100.0)
  })

  it('calculates comprehensive performance metrics', () => {
    const trades = [
      { id: 1, session_id: 1, type: 'buy' as const, open_time: 1000, open_price: 2000, close_time: 1100, close_price: 2020, lots: 0.1, profit: 200 },
      { id: 2, session_id: 1, type: 'buy' as const, open_time: 1200, open_price: 2020, close_time: 1300, close_price: 2010, lots: 0.1, profit: -100 },
      { id: 3, session_id: 1, type: 'sell' as const, open_time: 1400, open_price: 2010, close_time: 1500, close_price: 1980, lots: 0.1, profit: 300 },
    ]

    const metrics = calculatePerformanceMetrics(trades, 10000)
    expect(metrics.totalTrades).toBe(3)
    expect(metrics.winTrades).toBe(2)
    expect(metrics.lossTrades).toBe(1)
    expect(metrics.winRate).toBeCloseTo(66.67, 1)
    expect(metrics.netProfit).toBe(400)
    expect(metrics.returnPercent).toBeCloseTo(4.0, 1)
    expect(metrics.profitFactor).toBe(5.0) // (200 + 300) / 100 = 5.0
    expect(metrics.avgWin).toBe(250)
    expect(metrics.avgLoss).toBe(100)
  })

  it('creates session and executes trade with SL and TP', async () => {
    ;(fetch as any).mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/trading-review/sessions') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ success: true, session_id: 42 }),
        }
      }
      if (url.includes('/trading-review/sessions/42/trade') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string)
        expect(body.sl).toBe(1990)
        expect(body.tp).toBe(2030)
        return {
          ok: true,
          json: async () => ({ success: true, trade_id: 101 }),
        }
      }
      if (url.includes('/trading-review/sessions/42/state')) {
        return {
          ok: true,
          json: async () => ({
            session: { id: 42, symbol: 'XAUUSD', timeframe: 'M15', current_balance: 10000, start_time: 1000, current_time: 1000 },
            trades: [
              { id: 101, session_id: 42, type: 'buy', open_time: 1000, open_price: 2000, close_time: null, close_price: null, lots: 0.1, profit: null, sl: 1990, tp: 2030 }
            ],
            klines: [{ time: 1000, open: 2000, high: 2005, low: 1995, close: 2000 }],
          }),
        }
      }
      return { ok: true, json: async () => ({}) }
    })

    const { result } = renderHook(() => useTradingReviewStore())

    let sessionId: number = 0
    await act(async () => {
      sessionId = await result.current.createSession('XAUUSD', 'M15', '2023-01-01', '2023-01-02', 10000)
    })
    expect(sessionId).toBe(42)

    await act(async () => {
      await result.current.loadSessionState(42)
    })
    expect(result.current.currentSession?.symbol).toBe('XAUUSD')

    await act(async () => {
      await result.current.openTrade('buy', 0.1, 2000, 1000, 1990, 2030)
    })
    expect(result.current.trades.length).toBe(1)
    expect(result.current.trades[0].sl).toBe(1990)
    expect(result.current.trades[0].tp).toBe(2030)
  })
})
