import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePythonQuantStore } from '@/stores/python-quant-store'

global.fetch = vi.fn()

describe('Python Quant Store', () => {
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
  })

  it('loads quant overview from the backend', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/python-quant/overview')
      return {
        ok: true,
        json: async () => ({
          accounts: [{ id: 'acc-1', name: 'Main A', login: '10001' }],
          strategies: [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M5'] }],
          jobs: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => usePythonQuantStore())

    await act(async () => {
      await result.current.fetchOverview()
    })

    expect(result.current.overview.accounts[0]?.name).toBe('Main A')
    expect(result.current.overview.jobs).toHaveLength(0)
  })

  it('creates a job and refreshes overview', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === 'http://127.0.0.1:8765/python-quant/jobs') {
        expect(init?.method).toBe('POST')
        expect(init?.body).toContain('Gold M5 Trend')
        return {
          ok: true,
          json: async () => ({
            id: 'job-1',
          }),
        } as Response
      }

      expect(url).toBe('http://127.0.0.1:8765/python-quant/overview')
      return {
        ok: true,
        json: async () => ({
          accounts: [{ id: 'acc-1', name: 'Main A', login: '10001' }],
          strategies: [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M5'] }],
          jobs: [{
            id: 'job-1',
            name: 'Gold M5 Trend',
            account_id: 'acc-1',
            strategy_id: 'sma_cross',
            symbol: 'XAUUSD',
            timeframe: 'M5',
            lot: 0.01,
            enabled: false,
            status: 'stopped',
            last_signal: null,
            last_error: null,
            last_bar_time: null,
            updated_at: '2026-06-05T08:35:04+00:00',
          }],
        }),
      } as Response
    })

    const { result } = renderHook(() => usePythonQuantStore())

    let success = false
    await act(async () => {
      success = await result.current.createJob({
        name: 'Gold M5 Trend',
        account_id: 'acc-1',
        strategy_id: 'sma_cross',
        symbol: 'XAUUSD',
        timeframe: 'M5',
        lot: 0.01,
      })
    })

    expect(success).toBe(true)
    expect(result.current.overview.jobs[0]?.id).toBe('job-1')
  })

  it('surfaces backend validation detail when starting a job fails', async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Only one enabled quant job per account and symbol is allowed in V1' }),
    })

    const { result } = renderHook(() => usePythonQuantStore())

    let success = true
    await act(async () => {
      success = await result.current.startJob('job-1')
    })

    expect(success).toBe(false)
    await waitFor(() => {
      expect(result.current.error).toContain('Only one enabled quant job per account and symbol is allowed in V1')
    })
  })

  it('posts backfill requests and returns inserted rows', async () => {
    let overviewRequests = 0
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/python-quant/data/backfill') {
        expect(init?.method).toBe('POST')
        expect(init?.body).toContain('XAUUSD')
        return {
          ok: true,
          json: async () => ({ inserted_rows: 250 }),
        } as Response
      }

      expect(url).toBe('http://127.0.0.1:8765/python-quant/overview')
      overviewRequests += 1
      return {
        ok: true,
        json: async () => ({
          accounts: [{ id: 'acc-1', name: 'Main A', login: '10001' }],
          strategies: [{ id: 'sma_cross', name: 'SMA Cross', description: 'Trend strategy', timeframes: ['M5'] }],
          jobs: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => usePythonQuantStore())

    let insertedRows: number | null = null
    await act(async () => {
      insertedRows = await result.current.backfillData({
        account_id: 'acc-1',
        symbol: 'XAUUSD',
        timeframe: 'M5',
        bars: 250,
      })
    })

    expect(insertedRows).toBe(250)
    expect(overviewRequests).toBe(1)
  })
})
