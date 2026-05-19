import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLocalCopyTradingStore } from '@/stores/local-copy-trading-store'

global.fetch = vi.fn()

describe('Local Copy Trading Store', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useLocalCopyTradingStore.setState({
      overview: {
        runtime: {
          enabled: false,
          poll_interval_seconds: 1,
          last_error: null,
          last_checked_at: null,
        },
        source_accounts: [],
        follower_accounts: [],
        relationships: [],
        events: [],
      },
      isLoading: false,
      error: null,
    })
  })

  it('loads overview data from the local copy trading endpoint only', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true }],
          follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true }],
          relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true }],
          events: [{ id: 'evt-1', relationship_id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', position_id: 'ticket-1', symbol: 'XAUUSD', status: 'copied', message: '', created_at: '2026-05-11T00:00:00+00:00' }],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    await result.current.fetchOverview()

    expect(result.current.overview.runtime.enabled).toBe(true)
    expect(result.current.overview.source_accounts[0]?.name).toBe('Main A')
  })

  it('stores an error when overview loading fails', async () => {
    ;(fetch as any).mockResolvedValue({ ok: false })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    await result.current.fetchOverview()

    await waitFor(() => {
      expect(result.current.error).toContain('Failed to fetch local copy trading overview')
    })
  })

  it('posts source accounts to the local copy trading source endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/source-accounts')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('Main A')
      expect(init?.body).toContain('mt5_terminal')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true }],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.createSourceAccount({ name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true })

    expect(success).toBe(true)
    expect(result.current.overview.source_accounts[0]?.name).toBe('Main A')
  })

  it('posts follower accounts to the local copy trading follower endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/follower-accounts')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('Follower A')
      expect(init?.body).toContain('mt5_terminal')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true }],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.createFollowerAccount({ name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true })

    expect(success).toBe(true)
    expect(result.current.overview.follower_accounts[0]?.name).toBe('Follower A')
  })

  it('posts relationships to the local copy trading relationship endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/relationships')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('XAUUSD')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [],
          relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true }],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.createRelationship({ source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true })

    expect(success).toBe(true)
    expect(result.current.overview.relationships[0]?.symbol).toBe('XAUUSD')
  })

  it('surfaces backend validation detail for invalid relationships', async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Relationship must reference existing source and follower accounts' }),
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.createRelationship({ source_account_id: 'missing', follower_account_id: 'missing', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true })

    expect(success).toBe(false)
    expect(result.current.error).toContain('Relationship must reference existing source and follower accounts')
  })

  it('surfaces backend validation detail for invalid source account credentials', async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'MT5 credential verification failed' }),
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.createSourceAccount({ name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/terminal64.exe', login: '1001', server: 'demo', password: 'secret', is_active: true })

    expect(success).toBe(false)
    expect(result.current.error).toContain('MT5 credential verification failed')
  })

  it('posts runtime updates to the runtime endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/runtime')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('"enabled":true')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.updateRuntime({ enabled: true })

    expect(success).toBe(true)
    expect(result.current.overview.runtime.enabled).toBe(true)
  })

  it('deletes source accounts through the local copy trading source endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/source-accounts/src-1')
      expect(init?.method).toBe('DELETE')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useLocalCopyTradingStore())
    const success = await result.current.deleteSourceAccount('src-1')

    expect(success).toBe(true)
    expect(result.current.overview.source_accounts).toHaveLength(0)
  })
})
