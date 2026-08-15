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
  sl?: number | null
  tp?: number | null
}

export interface Kline {
  time: number
  open: number
  high: number
  low: number
  close: number
  tick_volume?: number
}

export interface PerformanceMetrics {
  totalTrades: number
  winTrades: number
  lossTrades: number
  winRate: number
  netProfit: number
  returnPercent: number
  profitFactor: number
  maxDrawdown: number
  maxDrawdownPercent: number
  avgWin: number
  avgLoss: number
  equityCurve: { time: number; balance: number }[]
}

export function getContractMultiplier(symbol: string): number {
  const s = (symbol || '').toUpperCase()
  if (s.includes('XAU') || s.includes('GOLD')) return 100
  if (s.includes('XAG') || s.includes('SILVER')) return 5000
  if (s.includes('BTC') || s.includes('ETH') || s.includes('SOL') || s.includes('CRYPTO')) return 1
  if (s.includes('US30') || s.includes('NAS100') || s.includes('USTEC') || s.includes('SPX500') || s.includes('WS30')) return 1
  if (s.includes('OIL') || s.includes('WTI') || s.includes('BRENT')) return 1000
  return 100000
}

export function calculateFloatingPnL(symbol: string, activeTrades: ReviewTrade[], currentPrice: number): number {
  const mult = getContractMultiplier(symbol)
  let totalPnL = 0
  for (const trade of activeTrades) {
    const diff = trade.type === 'buy' ? currentPrice - trade.open_price : trade.open_price - currentPrice
    totalPnL += diff * trade.lots * mult
  }
  return totalPnL
}

export function calculatePerformanceMetrics(trades: ReviewTrade[], initialBalance: number): PerformanceMetrics {
  const closed = trades.filter((t) => t.close_time !== null && t.profit !== null)
  const totalTrades = closed.length
  if (totalTrades === 0) {
    return {
      totalTrades: 0,
      winTrades: 0,
      lossTrades: 0,
      winRate: 0,
      netProfit: 0,
      returnPercent: 0,
      profitFactor: 0,
      maxDrawdown: 0,
      maxDrawdownPercent: 0,
      avgWin: 0,
      avgLoss: 0,
      equityCurve: [{ time: 0, balance: initialBalance }],
    }
  }

  let winTrades = 0
  let lossTrades = 0
  let grossProfit = 0
  let grossLoss = 0
  let netProfit = 0

  let currentBalance = initialBalance
  let peakBalance = initialBalance
  let maxDrawdown = 0
  let maxDrawdownPercent = 0

  const equityCurve: { time: number; balance: number }[] = [{ time: closed[0].open_time, balance: initialBalance }]

  for (const trade of closed) {
    const p = trade.profit || 0
    netProfit += p
    currentBalance += p
    equityCurve.push({ time: trade.close_time || trade.open_time, balance: currentBalance })

    if (p > 0) {
      winTrades += 1
      grossProfit += p
    } else if (p < 0) {
      lossTrades += 1
      grossLoss += Math.abs(p)
    }

    if (currentBalance > peakBalance) {
      peakBalance = currentBalance
    }
    const dd = peakBalance - currentBalance
    if (dd > maxDrawdown) {
      maxDrawdown = dd
      maxDrawdownPercent = peakBalance > 0 ? (dd / peakBalance) * 100 : 0
    }
  }

  const winRate = totalTrades > 0 ? (winTrades / totalTrades) * 100 : 0
  const returnPercent = initialBalance > 0 ? (netProfit / initialBalance) * 100 : 0
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? grossProfit : 0
  const avgWin = winTrades > 0 ? grossProfit / winTrades : 0
  const avgLoss = lossTrades > 0 ? grossLoss / lossTrades : 0

  return {
    totalTrades,
    winTrades,
    lossTrades,
    winRate,
    netProfit,
    returnPercent,
    profitFactor,
    maxDrawdown,
    maxDrawdownPercent,
    avgWin,
    avgLoss,
    equityCurve,
  }
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
  nextCandle: (limit?: number) => Promise<{ finished: boolean; triggeredCount: number }>
  openTrade: (type: 'buy' | 'sell', lots: number, price: number, time: number, sl?: number, tp?: number) => Promise<void>
  closeTrade: (tradeId: number, price: number, time: number) => Promise<void>
  closeAllTrades: (currentPrice: number, currentTime: number) => Promise<void>

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
      body: JSON.stringify({ symbol, timeframe, start_at: startAt, end_at: endAt, initial_balance: initialBalance }),
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
        trades: data.trades || [],
        klines: data.klines || [],
        loading: false,
      })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },

  nextCandle: async (limit = 1) => {
    const { currentSession, klines } = get()
    if (!currentSession) return { finished: true, triggeredCount: 0 }

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/next`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit }),
    })
    if (!res.ok) throw new Error('Failed to get next candle')

    const data = await res.json()
    const triggeredCount = (data.triggered_trades || []).length

    if (data.klines && data.klines.length > 0) {
      const updatedBalance = data.current_balance !== undefined ? data.current_balance : currentSession.current_balance
      set({
        klines: [...klines, ...data.klines],
        currentSession: {
          ...currentSession,
          current_time: data.klines[data.klines.length - 1].time,
          current_balance: updatedBalance,
        },
      })
      if (triggeredCount > 0) {
        // Sync trades if auto SL/TP triggers fired
        const stateRes = await apiFetch(`/trading-review/sessions/${currentSession.id}/state`)
        if (stateRes.ok) {
          const stateData = await stateRes.json()
          set({ trades: stateData.trades || [] })
        }
      }
    }
    return { finished: data.finished, triggeredCount }
  },

  openTrade: async (type, lots, price, time, sl, tp) => {
    const { currentSession } = get()
    if (!currentSession) return

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/trade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type,
        lots,
        open_price: price,
        open_time: time,
        sl: sl !== undefined ? sl : null,
        tp: tp !== undefined ? tp : null,
      }),
    })
    if (!res.ok) throw new Error('Failed to open trade')

    await get().loadSessionState(currentSession.id)
  },

  closeTrade: async (tradeId, price, time) => {
    const { currentSession } = get()
    if (!currentSession) return

    const res = await apiFetch(`/trading-review/sessions/${currentSession.id}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade_id: tradeId, close_price: price, close_time: time }),
    })
    if (!res.ok) throw new Error('Failed to close trade')

    await get().loadSessionState(currentSession.id)
  },

  closeAllTrades: async (currentPrice, currentTime) => {
    const { currentSession, trades, closeTrade } = get()
    if (!currentSession) return
    const active = trades.filter((t) => t.close_time === null)
    for (const t of active) {
      await closeTrade(t.id, currentPrice, currentTime)
    }
  },

  togglePlayback: () => set((state) => ({ isPlaying: !state.isPlaying })),
  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
}))
