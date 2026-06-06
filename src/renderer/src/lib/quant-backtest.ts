import {
  getPythonQuantErrorMessage,
  PYTHON_QUANT_API_BASE,
  PYTHON_QUANT_TIMEFRAMES,
  type PythonQuantTimeframe,
} from '@/lib/python-quant'

export const QUANT_BACKTEST_API_BASE = `${PYTHON_QUANT_API_BASE}/backtests`

export interface QuantBacktestStrategy {
  id: string
  name: string
  description: string
  timeframes: string[]
  module_path?: string
}

export interface QuantBacktestRunPayload {
  account_id: string
  strategy_id: string
  symbol: string
  timeframe: PythonQuantTimeframe
  start_at: string
  end_at: string
}

export interface QuantBacktestSummary {
  total_return_pct: number
  trade_count: number
  win_rate_pct: number
  max_drawdown_pct: number
}

export interface QuantBacktestEquityPoint {
  time: string
  equity: number
}

export interface QuantBacktestTrade {
  entry_time: string
  exit_time: string
  side: string
  pnl: number
}

export interface QuantBacktestResult {
  strategy: {
    id: string
    name: string
  }
  symbol: string
  timeframe: PythonQuantTimeframe
  range: {
    start_at: string
    end_at: string
  }
  summary: QuantBacktestSummary
  equity_curve: QuantBacktestEquityPoint[]
  trades: QuantBacktestTrade[]
}

export type QuantBacktestDateRangeInput = {
  startDate: string
  endDate: string
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

function readStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function readTimeframe(value: unknown): PythonQuantTimeframe {
  return typeof value === 'string' && (PYTHON_QUANT_TIMEFRAMES as readonly string[]).includes(value)
    ? value as PythonQuantTimeframe
    : 'M15'
}

function parseStrategy(value: unknown): QuantBacktestStrategy | null {
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

function parseEquityPoint(value: unknown): QuantBacktestEquityPoint | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }

  const time = readString(record.time)
  if (!time) {
    return null
  }

  return {
    time,
    equity: readNumber(record.equity),
  }
}

function parseTrade(value: unknown): QuantBacktestTrade | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }

  const entryTime = readString(record.entry_time)
  const exitTime = readString(record.exit_time)
  if (!entryTime || !exitTime) {
    return null
  }

  return {
    entry_time: entryTime,
    exit_time: exitTime,
    side: readString(record.side),
    pnl: readNumber(record.pnl),
  }
}

export function createDefaultQuantBacktestDateRange(): QuantBacktestDateRangeInput {
  const endDate = new Date()
  const startDate = new Date(endDate)
  startDate.setDate(startDate.getDate() - 30)

  return {
    startDate: startDate.toISOString().slice(0, 10),
    endDate: endDate.toISOString().slice(0, 10),
  }
}

export function buildQuantBacktestRangePayload(startDate: string, endDate: string): { start_at: string; end_at: string } | string {
  if (!startDate) {
    return 'Select a start date.'
  }

  if (!endDate) {
    return 'Select an end date.'
  }

  if (startDate > endDate) {
    return 'Start date must be on or before end date.'
  }

  return {
    start_at: `${startDate}T00:00:00Z`,
    end_at: `${endDate}T23:59:59Z`,
  }
}

export function parseQuantBacktestStrategies(payload: unknown): QuantBacktestStrategy[] {
  return Array.isArray(payload)
    ? payload.map(parseStrategy).filter((item): item is QuantBacktestStrategy => item !== null)
    : []
}

export function parseQuantBacktestResult(payload: unknown): QuantBacktestResult {
  const record = asRecord(payload)
  if (!record) {
    throw new Error('Invalid quant backtest response payload')
  }

  const strategyRecord = asRecord(record.strategy)
  const rangeRecord = asRecord(record.range)
  const summaryRecord = asRecord(record.summary)
  if (!strategyRecord || !rangeRecord || !summaryRecord) {
    throw new Error('Invalid quant backtest response payload')
  }

  const strategyId = readString(strategyRecord.id)
  const symbol = readString(record.symbol)
  if (!strategyId || !symbol) {
    throw new Error('Invalid quant backtest response payload')
  }

  return {
    strategy: {
      id: strategyId,
      name: readString(strategyRecord.name, strategyId),
    },
    symbol,
    timeframe: readTimeframe(record.timeframe),
    range: {
      start_at: readString(rangeRecord.start_at),
      end_at: readString(rangeRecord.end_at),
    },
    summary: {
      total_return_pct: readNumber(summaryRecord.total_return_pct),
      trade_count: readNumber(summaryRecord.trade_count),
      win_rate_pct: readNumber(summaryRecord.win_rate_pct),
      max_drawdown_pct: readNumber(summaryRecord.max_drawdown_pct),
    },
    equity_curve: Array.isArray(record.equity_curve)
      ? record.equity_curve.map(parseEquityPoint).filter((item): item is QuantBacktestEquityPoint => item !== null)
      : [],
    trades: Array.isArray(record.trades)
      ? record.trades.map(parseTrade).filter((item): item is QuantBacktestTrade => item !== null)
      : [],
  }
}

export { getPythonQuantErrorMessage }
