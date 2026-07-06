import { apiFetch } from '@/lib/api'
import { create } from 'zustand'

export interface PriceAlert {
  id: string
  symbol: string
  price: number
  condition: 'above' | 'below'
  is_active: boolean
  is_triggered: boolean
  comment: string
}

export interface VolatilityAlert {
  id: string
  symbol: string
  threshold_points: number
  timeframe_seconds: number
  is_active: boolean
  is_triggered: boolean
}

export interface IndicatorAlert {
  id: string
  symbol: string
  timeframe: string
  indicator_type: string
  period: number
  condition: 'above' | 'below'
  threshold: number
  is_active: boolean
  is_triggered: boolean
  comment: string
}

export interface OrderBroadcastRule {
  id: string
  symbol: string
  is_active: boolean
}

type OrderBroadcastRuleMutationResult =
  | { ok: true }
  | { ok: false; code: 'duplicate_symbol' | 'request_failed' }

interface AlertsState {
  priceAlerts: PriceAlert[]
  volatilityAlerts: VolatilityAlert[]
  indicatorAlerts: IndicatorAlert[]
  orderBroadcastRules: OrderBroadcastRule[]
  isLoading: boolean
  fetchAlerts: (options?: { silent?: boolean }) => Promise<void>
  addPriceAlert: (alert: Omit<PriceAlert, 'id' | 'is_triggered'>) => Promise<void>
  updatePriceAlert: (alert: PriceAlert) => Promise<void>
  deletePriceAlert: (id: string) => Promise<void>
  
  fetchVolatilityAlerts: (options?: { silent?: boolean }) => Promise<void>
  addVolatilityAlert: (alert: Omit<VolatilityAlert, 'id' | 'is_triggered'>) => Promise<void>
  updateVolatilityAlert: (alert: VolatilityAlert) => Promise<void>
  deleteVolatilityAlert: (id: string) => Promise<void>

  fetchIndicatorAlerts: (options?: { silent?: boolean }) => Promise<void>
  addIndicatorAlert: (alert: Omit<IndicatorAlert, 'id' | 'is_triggered'>) => Promise<void>
  updateIndicatorAlert: (alert: IndicatorAlert) => Promise<void>
  deleteIndicatorAlert: (id: string) => Promise<void>

  fetchOrderBroadcastRules: (options?: { silent?: boolean }) => Promise<void>
  addOrderBroadcastRule: (rule: Omit<OrderBroadcastRule, 'id'>) => Promise<OrderBroadcastRuleMutationResult>
  updateOrderBroadcastRule: (rule: OrderBroadcastRule) => Promise<OrderBroadcastRuleMutationResult>
  deleteOrderBroadcastRule: (id: string) => Promise<void>
}

async function parseOrderBroadcastMutationFailure(res: Response): Promise<OrderBroadcastRuleMutationResult> {
  if (res.status === 409) {
    const payload = await res.json().catch(() => null) as { detail?: { code?: string } } | null
    if (payload?.detail?.code === 'duplicate_symbol') {
      return { ok: false, code: 'duplicate_symbol' }
    }
  }

  return { ok: false, code: 'request_failed' }
}

export const useAlertsStore = create<AlertsState>((set, get) => ({
  priceAlerts: [],
  volatilityAlerts: [],
  indicatorAlerts: [],
  orderBroadcastRules: [],
  isLoading: false,

  fetchAlerts: async (options) => {
    if (!options?.silent) {
      set({ isLoading: true })
    }
    try {
      const res = await apiFetch('/alerts/price')
      if (res.ok) {
        const data = await res.json()
        set({ priceAlerts: data })
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error)
    } finally {
      if (!options?.silent) {
        set({ isLoading: false })
      }
    }
  },

  addPriceAlert: async (alert) => {
    try {
      const res = await apiFetch('/alerts/price', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...alert, id: "" })
      })
      if (res.ok) {
        get().fetchAlerts()
      }
    } catch (error) {
      console.error('Failed to add alert:', error)
    }
  },

  updatePriceAlert: async (alert) => {
    try {
      const res = await apiFetch(`/alerts/price/${alert.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alert)
      })
      if (res.ok) {
        get().fetchAlerts()
      }
    } catch (error) {
      console.error('Failed to update alert:', error)
    }
  },

  deletePriceAlert: async (id) => {
    try {
      await apiFetch(`/alerts/price/${id}`, { method: 'DELETE' })
      set((state) => ({
        priceAlerts: state.priceAlerts.filter((a) => a.id !== id)
      }))
    } catch (error) {
      console.error('Failed to delete alert:', error)
    }
  },

  fetchVolatilityAlerts: async (options) => {
    if (!options?.silent) {
      set({ isLoading: true })
    }
    try {
      const res = await apiFetch('/alerts/volatility')
      if (res.ok) {
        const data = await res.json()
        set({ volatilityAlerts: data })
      }
    } catch (error) {
      console.error('Failed to fetch volatility alerts:', error)
    } finally {
      if (!options?.silent) {
        set({ isLoading: false })
      }
    }
  },

  addVolatilityAlert: async (alert) => {
    try {
      const res = await apiFetch('/alerts/volatility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...alert, id: "" })
      })
      if (res.ok) {
        get().fetchVolatilityAlerts()
      }
    } catch (error) {
      console.error('Failed to add volatility alert:', error)
    }
  },

  updateVolatilityAlert: async (alert) => {
    try {
      const res = await apiFetch(`/alerts/volatility/${alert.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alert)
      })
      if (res.ok) {
        get().fetchVolatilityAlerts()
      }
    } catch (error) {
      console.error('Failed to update volatility alert:', error)
    }
  },

  deleteVolatilityAlert: async (id) => {
    try {
      await apiFetch(`/alerts/volatility/${id}`, { method: 'DELETE' })
      set((state) => ({
        volatilityAlerts: state.volatilityAlerts.filter((a) => a.id !== id)
      }))
    } catch (error) {
      console.error('Failed to delete volatility alert:', error)
    }
  },

  fetchIndicatorAlerts: async (options) => {
    if (!options?.silent) {
      set({ isLoading: true })
    }
    try {
      const res = await apiFetch('/alerts/indicator')
      if (res.ok) {
        const data = await res.json()
        set({ indicatorAlerts: data })
      }
    } catch (error) {
      console.error('Failed to fetch indicator alerts:', error)
    } finally {
      if (!options?.silent) {
        set({ isLoading: false })
      }
    }
  },

  addIndicatorAlert: async (alert) => {
    try {
      const res = await apiFetch('/alerts/indicator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...alert, id: "" })
      })
      if (res.ok) {
        get().fetchIndicatorAlerts()
      }
    } catch (error) {
      console.error('Failed to add indicator alert:', error)
    }
  },

  updateIndicatorAlert: async (alert) => {
    try {
      const res = await apiFetch(`/alerts/indicator/${alert.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(alert)
      })
      if (res.ok) {
        get().fetchIndicatorAlerts()
      }
    } catch (error) {
      console.error('Failed to update indicator alert:', error)
    }
  },

  deleteIndicatorAlert: async (id) => {
    try {
      await apiFetch(`/alerts/indicator/${id}`, { method: 'DELETE' })
      set((state) => ({
        indicatorAlerts: state.indicatorAlerts.filter((a) => a.id !== id)
      }))
    } catch (error) {
      console.error('Failed to delete indicator alert:', error)
    }
  },

  fetchOrderBroadcastRules: async (options) => {
    if (!options?.silent) {
      set({ isLoading: true })
    }
    try {
      const res = await apiFetch('/alerts/order-broadcast')
      if (res.ok) {
        const data = await res.json()
        set({ orderBroadcastRules: data })
      }
    } catch (error) {
      console.error('Failed to fetch order broadcast rules:', error)
    } finally {
      if (!options?.silent) {
        set({ isLoading: false })
      }
    }
  },

  addOrderBroadcastRule: async (rule) => {
    try {
      const res = await apiFetch('/alerts/order-broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...rule, id: '' })
      })

      if (!res.ok) {
        void get().fetchOrderBroadcastRules({ silent: true })
        return parseOrderBroadcastMutationFailure(res)
      }

      await get().fetchOrderBroadcastRules()
      return { ok: true }
    } catch (error) {
      console.error('Failed to add order broadcast rule:', error)
      return { ok: false, code: 'request_failed' }
    }
  },

  updateOrderBroadcastRule: async (rule) => {
    try {
      const res = await apiFetch(`/alerts/order-broadcast/${rule.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rule)
      })

      if (!res.ok) {
        void get().fetchOrderBroadcastRules({ silent: true })
        return parseOrderBroadcastMutationFailure(res)
      }

      await get().fetchOrderBroadcastRules()
      return { ok: true }
    } catch (error) {
      console.error('Failed to update order broadcast rule:', error)
      return { ok: false, code: 'request_failed' }
    }
  },

  deleteOrderBroadcastRule: async (id) => {
    try {
      await apiFetch(`/alerts/order-broadcast/${id}`, { method: 'DELETE' })
      set((state) => ({
        orderBroadcastRules: state.orderBroadcastRules.filter((rule) => rule.id !== id)
      }))
    } catch (error) {
      console.error('Failed to delete order broadcast rule:', error)
    }
  }
}))
