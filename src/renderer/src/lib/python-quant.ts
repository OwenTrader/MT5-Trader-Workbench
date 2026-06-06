export const PYTHON_QUANT_API_BASE = 'http://127.0.0.1:8765/python-quant'

export const PYTHON_QUANT_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'] as const

export type PythonQuantTimeframe = (typeof PYTHON_QUANT_TIMEFRAMES)[number]
export type PythonQuantJobStatus = 'stopped' | 'running' | 'error'
export type PythonQuantSignalAction = 'buy' | 'sell' | 'close' | 'hold'

const PYTHON_QUANT_JOB_STATUSES: PythonQuantJobStatus[] = ['stopped', 'running', 'error']
const PYTHON_QUANT_SIGNAL_ACTIONS: PythonQuantSignalAction[] = ['buy', 'sell', 'close', 'hold']

export interface PythonQuantAccount {
  id: string
  name: string
  login: string
  server?: string
  terminal_path?: string
  connection_type?: string
}

export interface PythonQuantStrategy {
  id: string
  name: string
  description: string
  timeframes: string[]
  module_path?: string
}

export interface PythonQuantJob {
  id: string
  name: string
  account_id: string
  strategy_id: string
  symbol: string
  timeframe: string
  lot: number
  enabled: boolean
  status: PythonQuantJobStatus
  last_signal: PythonQuantSignalAction | null
  last_error: string | null
  last_bar_time: string | null
  updated_at: string
}

export interface PythonQuantOverview {
  accounts: PythonQuantAccount[]
  strategies: PythonQuantStrategy[]
  jobs: PythonQuantJob[]
}

export interface PythonQuantJobPayload {
  name: string
  account_id: string
  strategy_id: string
  symbol: string
  timeframe: PythonQuantTimeframe
  lot: number
}

export interface PythonQuantJobUpdatePayload extends PythonQuantJobPayload {
  enabled?: boolean
}

export interface PythonQuantBackfillPayload {
  account_id: string
  symbol: string
  timeframe: PythonQuantTimeframe
  bars?: number
}

export function createEmptyPythonQuantOverview(): PythonQuantOverview {
  return {
    accounts: [],
    strategies: [],
    jobs: [],
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  return value as Record<string, unknown>
}

function readString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function readNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function readBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function readStatus(value: unknown): PythonQuantJobStatus {
  return typeof value === 'string' && PYTHON_QUANT_JOB_STATUSES.includes(value as PythonQuantJobStatus)
    ? value as PythonQuantJobStatus
    : 'stopped'
}

function readSignalAction(value: unknown): PythonQuantSignalAction | null {
  return typeof value === 'string' && PYTHON_QUANT_SIGNAL_ACTIONS.includes(value as PythonQuantSignalAction)
    ? value as PythonQuantSignalAction
    : null
}

function parseAccount(value: unknown): PythonQuantAccount | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }

  const id = readString(record.id)
  if (!id) {
    return null
  }

  return {
    id,
    name: readString(record.name, id),
    login: readString(record.login),
    server: readString(record.server) || undefined,
    terminal_path: readString(record.terminal_path) || undefined,
    connection_type: readString(record.connection_type) || undefined,
  }
}

function parseStrategy(value: unknown): PythonQuantStrategy | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }

  const id = readString(record.id)
  if (!id) {
    return null
  }

  return {
    id,
    name: readString(record.name, id),
    description: readString(record.description),
    timeframes: readStringArray(record.timeframes),
    module_path: readString(record.module_path) || undefined,
  }
}

function parseJob(value: unknown): PythonQuantJob | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }

  const id = readString(record.id)
  if (!id) {
    return null
  }

  return {
    id,
    name: readString(record.name, id),
    account_id: readString(record.account_id),
    strategy_id: readString(record.strategy_id),
    symbol: readString(record.symbol),
    timeframe: readString(record.timeframe),
    lot: readNumber(record.lot),
    enabled: readBoolean(record.enabled),
    status: readStatus(record.status),
    last_signal: readSignalAction(record.last_signal),
    last_error: readString(record.last_error) || null,
    last_bar_time: readString(record.last_bar_time) || null,
    updated_at: readString(record.updated_at),
  }
}

export function parsePythonQuantOverview(payload: unknown): PythonQuantOverview {
  const record = asRecord(payload)
  if (!record) {
    return createEmptyPythonQuantOverview()
  }

  return {
    accounts: Array.isArray(record.accounts)
      ? record.accounts.map(parseAccount).filter((item): item is PythonQuantAccount => item !== null)
      : [],
    strategies: Array.isArray(record.strategies)
      ? record.strategies.map(parseStrategy).filter((item): item is PythonQuantStrategy => item !== null)
      : [],
    jobs: Array.isArray(record.jobs)
      ? record.jobs.map(parseJob).filter((item): item is PythonQuantJob => item !== null)
      : [],
  }
}

export function parsePythonQuantBackfillResult(payload: unknown): number {
  const record = asRecord(payload)
  return readNumber(record?.inserted_rows)
}

export async function getPythonQuantErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json()
    const record = asRecord(payload)
    if (record && typeof record.detail === 'string' && record.detail.trim()) {
      return record.detail
    }
  } catch {
  }

  return fallback
}
