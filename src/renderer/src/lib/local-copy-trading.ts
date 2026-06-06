export const LOCAL_COPY_TRADING_API_BASE = 'http://127.0.0.1:8765/local-copy-trading'

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
}

export interface LocalCopyTradingAccountOverview {
  accounts: LocalCopyTradingAccount[]
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
}

export const DEFAULT_LOCAL_COPY_TRADING_ACCOUNT_OVERVIEW: LocalCopyTradingAccountOverview = {
  accounts: [],
}

export async function parseLocalCopyTradingOverviewResponse(
  response: Response,
  fallbackMessage = 'Failed to fetch local copy trading overview',
): Promise<LocalCopyTradingOverview> {
  if (!response.ok) {
    let detail = fallbackMessage
    try {
      const payload = await response.json()
      if (payload && typeof payload === 'object' && 'detail' in payload && typeof payload.detail === 'string') {
        detail = payload.detail
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
  }
}
