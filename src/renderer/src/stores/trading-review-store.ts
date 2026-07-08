import { create } from 'zustand'
import { apiFetch } from '@/lib/api'

export interface ReviewSession {
  id: number
  symbol: string
  timeframe: string
  start_time: number
  end_time: number
  initial_balance: number
  current_balance: number
  current_time: number
  created_at: number
}

export interface ReviewTrade {
  id: number
  session_id: number
  type: 'buy' | 'sell'
  open_time: number
  open_price: number
  close_time: number | null
  close_price: number | null
  lots: number
  profit: number | null
}

export interface Kline {
  time: number
  open: number
  high: number
  low: number
  close: number
}

interface TradingReviewState {
  sessions: ReviewSession[]
  currentSession: ReviewSession | null
  trades: ReviewTrade[]
  klines: Kline[]
  loading: boolean
  error: string | null
  
  // Playback state
  isPlaying: boolean
  playbackSpeed: number
  
  fetchSessions: () => Promise<void>
  createSession: (symbol: string, timeframe: string, startAt: string, endAt: string, initialBalance: number) => Promise<number>
  deleteSession: (id: number) => Promise<void>
  loadSessionState: (id: number) => Promise<void>
  nextCandle: (limit?: number) => Promise<{finished: boolean}>
  openTrade: (type: 'buy' | 'sell', lots: number, price: number, time: number) => Promise<void>
  closeTrade: (tradeId: number, price: number, time: number) => Promise<void>
  
  // Playback actions
  togglePlayback: () => void
  setPlaybackSpeed: (speed: number) => void
}

export const useTradingReviewStore = create<TradingReviewState>((set, get) => ({
  sessions: [],
  currentSession: null,
  trades: [],
  klines: [],
  loading: false,
  error: null,
  isPlaying: false,
  playbackSpeed: 1,

  fetchSessions: async () => {
    set({ loading: true, error: null })
    try {
      const res = await apiFetch('/trading-review/sessions')
      if (!res.ok) throw new Error('Failed to fetch sessions')
      set({ sessions: await res.json(), loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  createSession: async (symbol, timeframe, startAt, endAt, initialBalance) => {
    const res = await apiFetch('/trading-review/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, timeframe, start_at: startAt, end_at: endAt, initial_balance: initialBalance })
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to create session')
    }
    const data = await res.json()
    return data.session_id
  },

  deleteSession: async (id) => {
    const res = await apiFetch(`/trading-review/sessions/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('Failed to delete session')
  },

  loadSessionState: async (id) => {
    set({ loading: true, error: null })
    try {
      const res = await apiFetch(`/trading-review/sessions/${id}/state`)
      if (!res.ok) throw new Error('Failed to load session state')
      const data = await res.json()
      set({
        currentSession: data.session,
        trades: data.trades,
        klines: data.klines,
        loading: false
      })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  nextCandle: async (limit = 1) => {
    const { currentSession, klines } = get()
    if (!currentSession) return { finished: true }

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/next`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit })
    })
    if (!res.ok) throw new Error('Failed to get next candle')
    
    const data = await res.json()
    if (data.klines && data.klines.length > 0) {
      set({
        klines: [...klines, ...data.klines],
        currentSession: { ...currentSession, current_time: data.klines[data.klines.length - 1].time }
      })
    }
    return { finished: data.finished }
  },

  openTrade: async (type, lots, price, time) => {
    const { currentSession } = get()
    if (!currentSession) return

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, lots, open_price: price, open_time: time })
    })
    if (!res.ok) throw new Error('Failed to open trade')
    
    // Reload state to get updated trades
    await get().loadSessionState(currentSession.id)
  },

  closeTrade: async (tradeId, price, time) => {
    const { currentSession } = get()
    if (!currentSession) return

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade_id: tradeId, close_price: price, close_time: time })
    })
    if (!res.ok) throw new Error('Failed to close trade')
    
    // Reload state
    await get().loadSessionState(currentSession.id)
  },

  togglePlayback: () => set((state) => ({ isPlaying: !state.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed })
}))
