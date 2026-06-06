import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAccountManagementStore } from '@/stores/account-management-store'

global.fetch = vi.fn()

describe('Account Management Store', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useAccountManagementStore.setState({
      overview: {
        accounts: [],
      },
      isLoading: false,
      error: null,
    })
  })

  it('loads account lists from the local copy trading overview endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'simulated', terminal_path: '', login: '', server: '', password: '', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useAccountManagementStore())
    await act(async () => {
      await result.current.fetchOverview()
    })

    expect(result.current.overview.accounts).toHaveLength(2)
    expect(result.current.overview.accounts[0]?.name).toBe('Main A')
  })

  it('posts accounts to the dedicated account module store', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/accounts')
      expect(init?.method).toBe('POST')
      expect(init?.body).toContain('Main A')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useAccountManagementStore())
    let success = false
    await act(async () => {
      success = await result.current.createAccount({ name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true })
    })

    expect(success).toBe(true)
    expect(result.current.overview.accounts[0]?.name).toBe('Main A')
  })

  it('surfaces backend validation detail for invalid account credentials', async () => {
    ;(fetch as any).mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'MT5 credential verification failed' }),
    })

    const { result } = renderHook(() => useAccountManagementStore())
    let success = true
    await act(async () => {
      success = await result.current.createAccount({ name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/terminal64.exe', login: '1001', server: 'demo', password: 'secret', is_active: true })
    })

    expect(success).toBe(false)
    expect(result.current.error).toContain('MT5 credential verification failed')
  })

  it('deletes accounts through the account management endpoint', async () => {
    ;(fetch as any).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('http://127.0.0.1:8765/local-copy-trading/accounts/src-1')
      expect(init?.method).toBe('DELETE')
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 1, last_error: null, last_checked_at: null },
          accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    })

    const { result } = renderHook(() => useAccountManagementStore())
    let success = false
    await act(async () => {
      success = await result.current.deleteAccount('src-1')
    })

    expect(success).toBe(true)
    expect(result.current.overview.accounts).toHaveLength(0)
  })

  it('stores an error when account overview loading fails', async () => {
    ;(fetch as any).mockResolvedValue({ ok: false })

    const { result } = renderHook(() => useAccountManagementStore())
    await act(async () => {
      await result.current.fetchOverview()
    })

    await waitFor(() => {
      expect(result.current.error).toContain('Failed to fetch account list')
    })
  })
})
