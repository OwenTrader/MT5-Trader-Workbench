import { create } from 'zustand'
import { apiFetch } from '@/lib/api'

export interface KlineSummary {
  symbol: string
  timeframe: string
  count: number
  min_time: number
  max_time: number
}

interface DataManagementState {
  summary: KlineSummary[]
  loading: boolean
  error: string | null
  fetchSummary: () => Promise<void>
  syncData: (symbol: string, timeframe: string, startAt: string, endAt: string) => Promise<{success: boolean, count: number}>
  deleteData: (symbol: string, timeframe: string) => Promise<void>
}

export const useDataManagementStore = create<DataManagementState>((set) => ({
  summary: [],
  loading: false,
  error: null,
  fetchSummary: async () => {
    set({ loading: true, error: null })
    try {
      const res = await apiFetch('/data-management/summary')
      if (!res.ok) throw new Error('Failed to fetch summary')
      const data = await res.json()
      set({ summary: data, loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },
  syncData: async (symbol, timeframe, startAt, endAt) => {
    const res = await apiFetch('/data-management/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, timeframe, start_at: startAt, end_at: endAt }),
      timeout: 120000 // large timeout for syncing
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Sync failed')
    }
    return await res.json()
  },
  deleteData: async (symbol, timeframe) => {
    const res = await apiFetch(`/data-management/${symbol}/${timeframe}`, {
      method: 'DELETE'
    })
    if (!res.ok) throw new Error('Delete failed')
  }
}))
