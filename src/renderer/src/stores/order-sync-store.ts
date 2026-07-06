import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

const API_BASE = '/order-sync'

export interface TopStepAccountCredential {
  id: string
  name: string
  user_name: string
  api_key: string
  account_id: number
  live: boolean
  is_active: boolean
}

export interface OrderSymbolMapping {
  id: string
  mt5_symbol: string
  topstep_contract_id: string
  topstep_display_name: string
  quantity_multiplier: number
  mt5_lots: number
  topstep_contracts: number
  is_active: boolean
}

export interface SyncedOrder {
  mt5_ticket: number
  mt5_symbol: string
  mt5_volume: number
  topstep_account_id: number
  topstep_contract_id: string
  topstep_order_id: number | null
  side: 'buy' | 'sell'
  size: number
  status: 'open' | 'closed' | 'error' | 'blocked'
  opened_at: string
  closed_at: string | null
  last_error: string | null
  blocked_reason: string | null
}

export interface OrderSyncStateData {
  enabled: boolean
  poll_interval_seconds: number
  block_high_frequency_orders: boolean
  high_frequency_window_seconds: number
  credentials: TopStepAccountCredential[]
  mappings: OrderSymbolMapping[]
  synced_orders: SyncedOrder[]
  last_error: string | null
  last_checked_at: string | null
}

interface OrderSyncState {
  config: OrderSyncStateData
  isLoading: boolean
  error: string | null
  fetchConfig: (options?: { silent?: boolean }) => Promise<void>
  saveConfig: (config: Pick<OrderSyncStateData, 'enabled' | 'poll_interval_seconds' | 'block_high_frequency_orders' | 'high_frequency_window_seconds' | 'credentials' | 'mappings'>) => Promise<boolean>
  runTick: () => Promise<void>
}

const DEFAULT_CONFIG: OrderSyncStateData = {
  enabled: false,
  poll_interval_seconds: 1,
  block_high_frequency_orders: false,
  high_frequency_window_seconds: 5,
  credentials: [],
  mappings: [],
  synced_orders: [],
  last_error: null,
  last_checked_at: null,
}

export const useOrderSyncStore = create<OrderSyncState>((set, get) => ({
  config: DEFAULT_CONFIG,
  isLoading: false,
  error: null,
  fetchConfig: async (options) => {
    if (!options?.silent) {
      set({ isLoading: true, error: null })
    }
    try {
      const response = await apiFetch(API_BASE)
      if (!response.ok) throw new Error('Failed to fetch order sync config')
      const config = await response.json()
      set({ config: { ...DEFAULT_CONFIG, ...config }, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
  saveConfig: async (config) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(API_BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (!response.ok) throw new Error('Failed to save order sync config')
      const savedConfig = await response.json()
      set({ config: { ...DEFAULT_CONFIG, ...savedConfig }, isLoading: false })
      return true
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
      return false
    }
  },
  runTick: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiFetch(`${API_BASE}/tick`, { method: 'POST' })
      if (!response.ok) throw new Error('Failed to run order sync')
      const config = await response.json()
      set({ config: { ...get().config, ...config }, isLoading: false })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : String(error), isLoading: false })
    }
  },
}))
