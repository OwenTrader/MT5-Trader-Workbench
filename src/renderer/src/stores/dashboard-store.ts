import { create } from 'zustand'

interface AccountInfo {
  balance: number
  equity: number
  margin_level: number
  profit: number
}

interface MT5Status {
  is_running: boolean
  is_connected: boolean
}

interface DashboardState {
  account: AccountInfo | null
  status: MT5Status
  isLoading: boolean
  fetchStatus: () => Promise<void>
  fetchAccount: () => Promise<void>
  startPolling: (interval?: number) => void
  stopPolling: () => void
}

let pollingInterval: NodeJS.Timeout | null = null

export const useDashboardStore = create<DashboardState>((set, get) => ({
  account: null,
  status: { is_running: false, is_connected: false },
  isLoading: false,

  fetchStatus: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/mt5/status')
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
      const res = await fetch('http://127.0.0.1:8765/mt5/account')
      if (res.ok) {
        const data = await res.json()
        set({ account: data })
      }
    } catch (error) {
      console.error('Failed to fetch account info:', error)
    }
  },

  startPolling: (interval: number = 2000) => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
    }
    get().fetchStatus()
    get().fetchAccount()
    pollingInterval = setInterval(() => {
      get().fetchStatus()
      get().fetchAccount()
    }, interval)
  },

  stopPolling: () => {
    if (pollingInterval) {
      clearInterval(pollingInterval)
      pollingInterval = null
    }
  }
}))
