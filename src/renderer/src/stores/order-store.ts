import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

export interface DailyOrderStat {
  date: string
  total_lots: number
  min_lot: number
  max_lot: number
  trades_count: number
  profit: number
  profit_pct: number
  balance: number
}

export interface PerformanceOverview {
  today: number
  week: number
  month: number
}

interface OrderState {
  dailyStats: DailyOrderStat[]
  overview: PerformanceOverview
  isOverviewLoading: boolean
  isDailyLoading: boolean
  dateRange: { from: string; to: string }
  
  fetchOverview: () => Promise<void>
  fetchDailyStats: (from?: string, to?: string) => Promise<void>
  setDateRange: (range: { from: string; to: string }) => void
}

export const useOrderStore = create<OrderState>((set, get) => ({
  dailyStats: [],
  overview: { today: 0, week: 0, month: 0 },
  isOverviewLoading: false,
  isDailyLoading: false,
  dateRange: {
    from: new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0],
    to: new Date().toISOString().split('T')[0]
  },

  setDateRange: (range) => set({ dateRange: range }),

  fetchOverview: async () => {
    set({ isOverviewLoading: true })
    try {
      const res = await apiFetch('/history/overview')
      if (res.ok) {
        set({ overview: await res.json() })
      }
    } catch (error) {
      console.error('Failed to fetch overview:', error)
    } finally {
      set({ isOverviewLoading: false })
    }
  },

  fetchDailyStats: async (from, to) => {
    set({ isDailyLoading: true })
    try {
      const { from: f, to: t } = get().dateRange
      const query = new URLSearchParams({
        from_date: from || f,
        to_date: to || t
      })
      const res = await apiFetch(`/history/daily?${query}`)
      if (res.ok) {
        set({ dailyStats: await res.json() })
      }
    } catch (error) {
      console.error('Failed to fetch daily stats:', error)
    } finally {
      set({ isDailyLoading: false })
    }
  }
}))
