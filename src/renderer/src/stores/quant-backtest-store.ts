import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

import {
  getPythonQuantErrorMessage,
  parseQuantBacktestResult,
  parseQuantBacktestStrategies,
  QUANT_BACKTEST_API_BASE,
  type QuantBacktestResult,
  type QuantBacktestRunPayload,
  type QuantBacktestStrategy,
} from '@/lib/quant-backtest'

interface QuantBacktestStore {
  strategies: QuantBacktestStrategy[]
  result: QuantBacktestResult | null
  error: string | null
  isLoadingStrategies: boolean
  isRunning: boolean
  fetchStrategies: () => Promise<void>
  runBacktest: (payload: QuantBacktestRunPayload) => Promise<boolean>
  clearResult: () => void
}

export const useQuantBacktestStore = create<QuantBacktestStore>((set) => ({
  strategies: [],
  result: null,
  error: null,
  isLoadingStrategies: false,
  isRunning: false,
  fetchStrategies: async () => {
    set({ isLoadingStrategies: true, error: null })
    try {
      const response = await apiFetch(`${QUANT_BACKTEST_API_BASE}/strategies`)
      if (!response.ok) {
        throw new Error(await getPythonQuantErrorMessage(response, 'Failed to fetch quant backtest strategies'))
      }

      set({
        strategies: parseQuantBacktestStrategies(await response.json()),
        isLoadingStrategies: false,
        error: null,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : String(error),
        isLoadingStrategies: false,
      })
    }
  },
  runBacktest: async (payload) => {
    set({ isRunning: true, error: null, result: null })
    try {
      const response = await apiFetch(`${QUANT_BACKTEST_API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(await getPythonQuantErrorMessage(response, 'Failed to run quant backtest'))
      }

      set({
        result: parseQuantBacktestResult(await response.json()),
        isRunning: false,
        error: null,
      })
      return true
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : String(error),
        isRunning: false,
      })
      return false
    }
  },
  clearResult: () => set({ result: null }),
}))
