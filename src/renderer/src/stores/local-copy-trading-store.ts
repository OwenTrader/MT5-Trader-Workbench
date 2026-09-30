import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

import {
  DEFAULT_COPY_TRADING_RISK_SETTINGS,
  DEFAULT_LOCAL_COPY_TRADING_OVERVIEW,
  LOCAL_COPY_TRADING_API_BASE,
  parseLocalCopyTradingOverviewResponse,
  parseRiskSettingsResponse,
  type CopyTradingRiskSettings,
  type LocalCopyTradingOverview,
  type LocalCopyTradingRelationship,
} from '@/lib/local-copy-trading'

interface LocalCopyTradingStore {
  overview: LocalCopyTradingOverview
  isLoading: boolean
  error: string | null
  riskSettings: CopyTradingRiskSettings
  isSavingRiskSettings: boolean
  fetchOverview: (options?: { silent?: boolean }) => Promise<void>
  updateRuntime: (payload: { enabled?: boolean; poll_interval_seconds?: number }) => Promise<boolean>
  createRelationship: (payload: Omit<LocalCopyTradingRelationship, 'id'> & { id?: string }) => Promise<boolean>
  deleteRelationship: (relationshipId: string) => Promise<boolean>
  fetchRiskSettings: () => Promise<void>
  updateRiskSettings: (payload: CopyTradingRiskSettings) => Promise<boolean>
}

export const useLocalCopyTradingStore = create<LocalCopyTradingStore>((set) => ({
  overview: DEFAULT_LOCAL_COPY_TRADING_OVERVIEW,
  isLoading: false,
  error: null,
  riskSettings: DEFAULT_COPY_TRADING_RISK_SETTINGS,
  isSavingRiskSettings: false,
  fetchOverview: async (options) => {
    const silent = options?.silent === true
    set(silent ? { error: null } : { isLoading: true, error: null })
    try {
      const response = await apiFetch(LOCAL_COPY_TRADING_API_BASE)
      const overview = await parseLocalCopyTradingOverviewResponse(response)
      set({ overview, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
  updateRuntime: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/runtime`, {
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
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/relationships`, {
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
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/relationships/${relationshipId}`, {
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
  fetchRiskSettings: async () => {
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/risk-settings`)
      const riskSettings = await parseRiskSettingsResponse(response)
      set({ riskSettings })
    } catch {
      // Risk settings are optional; the card simply keeps its defaults.
    }
  },
  updateRiskSettings: async (payload) => {
    set({ isSavingRiskSettings: true })
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/risk-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const riskSettings = await parseRiskSettingsResponse(response)
      set({ riskSettings, isSavingRiskSettings: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isSavingRiskSettings: false })
      return false
    }
  },
}))
