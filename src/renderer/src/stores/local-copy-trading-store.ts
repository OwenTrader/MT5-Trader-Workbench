import { create } from 'zustand'

const API_BASE = 'http://127.0.0.1:8765/local-copy-trading'

export interface LocalCopyTradingRuntime {
  enabled: boolean
  poll_interval_seconds: number
  last_error: string | null
  last_checked_at: string | null
}

export interface LocalCopyTradingSourceAccount {
  id: string
  name: string
  connection_type: string
  terminal_path: string
  login: string
  server: string
  password: string
  is_active: boolean
}

export interface LocalCopyTradingFollowerAccount {
  id: string
  name: string
  connection_type: string
  terminal_path: string
  login: string
  server: string
  password: string
  is_active: boolean
}

export interface LocalCopyTradingRelationship {
  id: string
  source_account_id: string
  follower_account_id: string
  symbol: string
  source_symbol?: string
  follower_symbol?: string
  lot_multiplier: number
  is_active: boolean
}

export interface LocalCopyTradingEvent {
  id: string
  relationship_id: string
  source_account_id: string
  follower_account_id: string
  position_id: string
  follower_position_id?: string
  follower_order_id?: string
  symbol: string
  status: string
  message: string
  created_at: string
}

export interface LocalCopyTradingOverview {
  runtime: LocalCopyTradingRuntime
  source_accounts: LocalCopyTradingSourceAccount[]
  follower_accounts: LocalCopyTradingFollowerAccount[]
  relationships: LocalCopyTradingRelationship[]
  events: LocalCopyTradingEvent[]
}

interface LocalCopyTradingStore {
  overview: LocalCopyTradingOverview
  isLoading: boolean
  error: string | null
  fetchOverview: () => Promise<void>
  updateRuntime: (payload: { enabled?: boolean; poll_interval_seconds?: number }) => Promise<boolean>
  createSourceAccount: (payload: Omit<LocalCopyTradingSourceAccount, 'id'> & { id?: string }) => Promise<boolean>
  createFollowerAccount: (payload: Omit<LocalCopyTradingFollowerAccount, 'id'> & { id?: string }) => Promise<boolean>
  updateSourceAccount: (accountId: string, payload: Omit<LocalCopyTradingSourceAccount, 'id'>) => Promise<boolean>
  updateFollowerAccount: (accountId: string, payload: Omit<LocalCopyTradingFollowerAccount, 'id'>) => Promise<boolean>
  createRelationship: (payload: Omit<LocalCopyTradingRelationship, 'id'> & { id?: string }) => Promise<boolean>
  deleteSourceAccount: (accountId: string) => Promise<boolean>
  deleteFollowerAccount: (accountId: string) => Promise<boolean>
  deleteRelationship: (relationshipId: string) => Promise<boolean>
}

const DEFAULT_OVERVIEW: LocalCopyTradingOverview = {
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
}

async function handleOverviewResponse(response: Response): Promise<LocalCopyTradingOverview> {
  if (!response.ok) {
    let detail = 'Failed to fetch local copy trading overview'
    try {
      const payload = await response.json()
      if (payload && typeof payload === 'object' && 'detail' in payload && typeof payload.detail === 'string') {
        detail = payload.detail
      }
    } catch {
    }
    throw new Error(detail)
  }

  return {
    ...DEFAULT_OVERVIEW,
    ...(await response.json()),
  }
}

export const useLocalCopyTradingStore = create<LocalCopyTradingStore>((set) => ({
  overview: DEFAULT_OVERVIEW,
  isLoading: false,
  error: null,
  fetchOverview: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(API_BASE)
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
  updateRuntime: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/runtime`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  createSourceAccount: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/source-accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  createFollowerAccount: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/follower-accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  updateSourceAccount: async (accountId, payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/source-accounts/${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  updateFollowerAccount: async (accountId, payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/follower-accounts/${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  createRelationship: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/relationships`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  deleteSourceAccount: async (accountId) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/source-accounts/${accountId}`, {
        method: 'DELETE',
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  deleteFollowerAccount: async (accountId) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/follower-accounts/${accountId}`, {
        method: 'DELETE',
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  deleteRelationship: async (relationshipId) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${API_BASE}/relationships/${relationshipId}`, {
        method: 'DELETE',
      })
      const overview = await handleOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
}))
