export const LOCAL_COPY_TRADING_API_BASE = '/local-copy-trading'

export interface LocalCopyTradingRuntime {
  enabled: boolean
  poll_interval_seconds: number
  last_error: string | null
  last_checked_at: string | null
}

export interface LocalCopyTradingAccount {
  id: string
  name: string
  connection_type: string
  terminal_path: string
  login: string
  server: string
  password: string
  is_active: boolean
}

export type LocalCopyTradingSourceAccount = LocalCopyTradingAccount
export type LocalCopyTradingFollowerAccount = LocalCopyTradingAccount

export interface LocalCopyTradingRelationship {
  id: string
  source_account_id: string
  follower_account_id: string
  symbol: string
  source_symbol?: string
  follower_symbol?: string
  lot_multiplier: number
  volume_mode?: 'multiplier' | 'fixed' | 'equity_ratio' | 'risk_percent' | string
  max_lot?: number
  risk_percent?: number
  sync_sl_tp?: boolean
  is_active: boolean
}

export interface LocalCopyTradingEvent {
  id: string
  relationship_id: string
  source_account_id: string
  follower_account_id: string
  position_id: string
  follower_position_id?: string
  follower_order_id?: string
  symbol: string
  status: string
  message: string
  created_at: string
}

export interface LocalCopyTradingOverview {
  runtime: LocalCopyTradingRuntime
  accounts: LocalCopyTradingAccount[]
  relationships: LocalCopyTradingRelationship[]
  events: LocalCopyTradingEvent[]
  open_record_counts?: Record<string, number>
}

export interface LocalCopyTradingAccountOverview {
  accounts: LocalCopyTradingAccount[]
  relationships: LocalCopyTradingRelationship[]
  open_record_counts: Record<string, number>
}

export const DEFAULT_LOCAL_COPY_TRADING_OVERVIEW: LocalCopyTradingOverview = {
  runtime: {
    enabled: false,
    poll_interval_seconds: 1,
    last_error: null,
    last_checked_at: null,
  },
  accounts: [],
  relationships: [],
  events: [],
  open_record_counts: {},
}

export const DEFAULT_LOCAL_COPY_TRADING_ACCOUNT_OVERVIEW: LocalCopyTradingAccountOverview = {
  accounts: [],
  relationships: [],
  open_record_counts: {},
}

export async function parseLocalCopyTradingOverviewResponse(
  response: Response,
  fallbackMessage = 'Failed to fetch local copy trading overview',
): Promise<LocalCopyTradingOverview> {
  if (!response.ok) {
    let detail = fallbackMessage
    try {
      const payload = await response.json()
      if (payload && typeof payload === 'object' && 'detail' in payload) {
        const rawDetail = (payload as { detail: unknown }).detail
        if (typeof rawDetail === 'string') {
          detail = rawDetail
        } else if (Array.isArray(rawDetail)) {
          detail = rawDetail
            .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
            .join('; ')
        }
      }
    } catch {
    }
    throw new Error(detail)
  }

  const payload = {
    ...DEFAULT_LOCAL_COPY_TRADING_OVERVIEW,
    ...(await response.json() as Record<string, unknown>),
  } as LocalCopyTradingOverview & {
    source_accounts?: LocalCopyTradingAccount[]
    follower_accounts?: LocalCopyTradingAccount[]
  }

  const accounts = payload.accounts.length > 0
    ? payload.accounts
    : [...(payload.source_accounts ?? []), ...(payload.follower_accounts ?? [])]

  return {
    ...payload,
    accounts,
  }
}

export function pickLocalCopyTradingAccountOverview(
  overview: LocalCopyTradingOverview,
): LocalCopyTradingAccountOverview {
  return {
    accounts: overview.accounts,
    relationships: overview.relationships,
    open_record_counts: overview.open_record_counts ?? {},
  }
}

export interface CopyTradingRiskSettings {
  max_volume_per_symbol: number
  max_positions_per_symbol: number
  max_daily_open_count: number
  max_daily_loss: number
  min_margin_level: number
  max_consecutive_failures: number
}

export const DEFAULT_COPY_TRADING_RISK_SETTINGS: CopyTradingRiskSettings = {
  max_volume_per_symbol: 0,
  max_positions_per_symbol: 0,
  max_daily_open_count: 0,
  max_daily_loss: 0,
  min_margin_level: 0,
  max_consecutive_failures: 3,
}

export async function parseRiskSettingsResponse(
  response: Response,
  fallbackMessage = 'Failed to fetch risk settings',
): Promise<CopyTradingRiskSettings> {
  if (!response.ok) {
    let detail = fallbackMessage
    try {
      const payload = await response.json()
      if (payload && typeof payload === 'object' && 'detail' in payload) {
        const rawDetail = (payload as { detail: unknown }).detail
        if (typeof rawDetail === 'string') {
          detail = rawDetail
        } else if (Array.isArray(rawDetail)) {
          detail = rawDetail
            .map((item) => (item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : String(item)))
            .join('; ')
        }
      }
    } catch {
    }
    throw new Error(detail)
  }

  const payload = await response.json() as Record<string, unknown>
  const numericEntries = Object.entries(payload).filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
  return {
    ...DEFAULT_COPY_TRADING_RISK_SETTINGS,
    ...Object.fromEntries(numericEntries),
  } as CopyTradingRiskSettings
}
