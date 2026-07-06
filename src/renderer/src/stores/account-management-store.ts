import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

import {
  DEFAULT_LOCAL_COPY_TRADING_ACCOUNT_OVERVIEW,
  LOCAL_COPY_TRADING_API_BASE,
  pickLocalCopyTradingAccountOverview,
  parseLocalCopyTradingOverviewResponse,
  type LocalCopyTradingAccount,
  type LocalCopyTradingAccountOverview,
} from '@/lib/local-copy-trading'

interface AccountManagementStore {
  overview: LocalCopyTradingAccountOverview
  isLoading: boolean
  error: string | null
  fetchOverview: () => Promise<void>
  createAccount: (payload: Omit<LocalCopyTradingAccount, 'id'> & { id?: string }) => Promise<boolean>
  updateAccount: (accountId: string, payload: Omit<LocalCopyTradingAccount, 'id'>) => Promise<boolean>
  deleteAccount: (accountId: string) => Promise<boolean>
}

async function handleAccountOverviewResponse(
  response: Response,
  fallbackMessage = 'Failed to fetch account list',
): Promise<LocalCopyTradingAccountOverview> {
  const overview = await parseLocalCopyTradingOverviewResponse(response, fallbackMessage)
  return pickLocalCopyTradingAccountOverview(overview)
}

export const useAccountManagementStore = create<AccountManagementStore>((set) => ({
  overview: DEFAULT_LOCAL_COPY_TRADING_ACCOUNT_OVERVIEW,
  isLoading: false,
  error: null,
  fetchOverview: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(LOCAL_COPY_TRADING_API_BASE)
      const overview = await handleAccountOverviewResponse(response)
      set({ overview, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
  createAccount: async (payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleAccountOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  updateAccount: async (accountId, payload) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/accounts/${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const overview = await handleAccountOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  deleteAccount: async (accountId) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(`${LOCAL_COPY_TRADING_API_BASE}/accounts/${accountId}`, {
        method: 'DELETE',
      })
      const overview = await handleAccountOverviewResponse(response)
      set({ overview, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
}))
