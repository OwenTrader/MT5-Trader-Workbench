import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

export interface AccountInfo {
  balance: number
  equity: number
  margin_level: number
  profit: number
}

export interface MT5Status {
  is_running: boolean
  is_connected: boolean
}

export interface MT5Position {
  ticket: number
  symbol: string
  type: number // 0: BUY, 1: SELL
  volume: number
  price_open: number
  price_current: number
  sl: number
  tp: number
  profit: number
  time?: number
}

interface DashboardState {
  account: AccountInfo | null
  status: MT5Status
  positions: MT5Position[]
  selectedSymbol: string
  isLoading: boolean
  setSelectedSymbol: (symbol: string) => void
  fetchStatus: () => Promise<void>
  fetchAccount: () => Promise<void>
  fetchPositions: () => Promise<void>
  startPolling: (interval?: number) => void
  stopPolling: () => void
}

let pollingInterval: NodeJS.Timeout | null = null

export const useDashboardStore = create<DashboardState>((set, get) => ({
  account: null,
  status: { is_running: false, is_connected: false },
  positions: [],
  selectedSymbol: 'XAUUSD',
  isLoading: false,

  setSelectedSymbol: (symbol: string) => set({ selectedSymbol: symbol }),

  fetchStatus: async () => {
    try {
      const res = await apiFetch('/mt5/status')
      if (res.ok) {
        const data = await res.json()
        set({ status: data })
      }
    } catch (error) {
      console.error('Failed to fetch MT5 status:', error)
    }
  },

  fetchAccount: async () => {
    try {
      const res = await apiFetch('/mt5/account')
      if (res.ok) {
        const data = await res.json()
        set({ account: data })
      }
    } catch (error) {
      console.error('Failed to fetch account info:', error)
    }
  },

  fetchPositions: async () => {
    try {
      const res = await apiFetch('/mt5/positions')
      if (res.ok) {
        const data = await res.json()
        set({ positions: Array.isArray(data) ? data : [] })
      }
    } catch (error) {
      console.error('Failed to fetch positions:', error)
    }
  },

  startPolling: (interval: number = 2000) => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
    }
    get().fetchStatus()
    get().fetchAccount()
    get().fetchPositions()
    pollingInterval = setInterval(() => {
      get().fetchStatus()
      get().fetchAccount()
      get().fetchPositions()
    }, interval)
  },

  stopPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      pollingInterval = null
    }
  }
}))
