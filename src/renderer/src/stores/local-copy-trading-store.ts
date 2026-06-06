import { create } from 'zustand'

import {
  DEFAULT_LOCAL_COPY_TRADING_OVERVIEW,
  LOCAL_COPY_TRADING_API_BASE,
  parseLocalCopyTradingOverviewResponse,
  type LocalCopyTradingOverview,
  type LocalCopyTradingRelationship,
} from '@/lib/local-copy-trading'

interface LocalCopyTradingStore {
  overview: LocalCopyTradingOverview
  isLoading: boolean
  error: string | null
  fetchOverview: () => Promise<void>
  updateRuntime: (payload: { enabled?: boolean; poll_interval_seconds?: number }) => Promise<boolean>
  createRelationship: (payload: Omit<LocalCopyTradingRelationship, 'id'> & { id?: string }) => Promise<boolean>
  deleteRelationship: (relationshipId: string) => Promise<boolean>
}

export const useLocalCopyTradingStore = create<LocalCopyTradingStore>((set) => ({
  overview: DEFAULT_LOCAL_COPY_TRADING_OVERVIEW,
  isLoading: false,
  error: null,
  fetchOverview: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(LOCAL_COPY_TRADING_API_BASE)
      const overview = await parseLocalCopyTradingOverviewResponse(response)
      set({ overview, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
  updateRuntime: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch(`${LOCAL_COPY_TRADING_API_BASE}/runtime`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await parseLocalCopyTradingOverviewResponse(response)
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
      const response = await fetch(`${LOCAL_COPY_TRADING_API_BASE}/relationships`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await parseLocalCopyTradingOverviewResponse(response)
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
      const response = await fetch(`${LOCAL_COPY_TRADING_API_BASE}/relationships/${relationshipId}`, {
        method: 'DELETE',
      })
      const overview = await parseLocalCopyTradingOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
}))
