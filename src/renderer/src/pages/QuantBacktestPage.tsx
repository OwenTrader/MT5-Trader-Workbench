import React, { useEffect } from 'react'
import { LineChart, Play } from 'lucide-react'

import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useI18n } from '@/i18n'
import {
  buildQuantBacktestRangePayload,
  createDefaultQuantBacktestDateRange,
  type QuantBacktestEquityPoint,
} from '@/lib/quant-backtest'
import { PYTHON_QUANT_TIMEFRAMES, type PythonQuantTimeframe } from '@/lib/python-quant'
import { useQuantBacktestStore } from '@/stores/quant-backtest-store'
import { usePythonQuantStore } from '@/stores/python-quant-store'

type BacktestFormState = {
  accountId: string
  strategyId: string
  symbol: string
  timeframe: PythonQuantTimeframe
  startDate: string
  endDate: string
}

function createInitialFormState(): BacktestFormState {
  const range = createDefaultQuantBacktestDateRange()

  return {
    accountId: '',
    strategyId: '',
    symbol: 'XAUUSD',
    timeframe: 'M15',
    startDate: range.startDate,
    endDate: range.endDate,
  }
}

function getAccountLabel(account: { id: string; name: string; login: string }) {
  const name = account.name.trim() || account.id
  return account.login.trim() ? `${name} (${account.login})` : name
}

function normalizeTimeframes(timeframes: string[]) {
  const valid = timeframes.filter((value): value is PythonQuantTimeframe => (
    PYTHON_QUANT_TIMEFRAMES as readonly string[]
  ).includes(value))

  return valid.length > 0 ? valid : [...PYTHON_QUANT_TIMEFRAMES]
}

function formatPercent(value: number) {
  return `${value.toFixed(2)}%`
}

function formatNumber(value: number) {
  return value.toFixed(2)
}

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

function getEquitySummary(points: QuantBacktestEquityPoint[]) {
  if (points.length === 0) {
    return null
  }

  let peak = points[0].equity
  let trough = points[0].equity

  for (const point of points) {
    peak = Math.max(peak, point.equity)
    trough = Math.min(trough, point.equity)
  }

  return {
    start: points[0].equity,
    end: points[points.length - 1].equity,
    peak,
    trough,
    points: points.length,
  }
}

export function QuantBacktestPage() {
  const { t } = useI18n()
  const { overview, isLoading: isLoadingAccounts, error: accountsError, fetchOverview } = usePythonQuantStore()
  const {
    strategies,
    result,
    error,
    isLoadingStrategies,
    isRunning,
    fetchStrategies,
    runBacktest,
  } = useQuantBacktestStore()
  const [form, setForm] = React.useState<BacktestFormState>(() => createInitialFormState())
  const [formError, setFormError] = React.useState<string | null>(null)

  useEffect(() => {
    void fetchOverview()
    void fetchStrategies()
  }, [fetchOverview, fetchStrategies])

  useEffect(() => {
    setForm((current) => {
      let next = current

      if (!next.accountId && overview.accounts[0]) {
        next = { ...next, accountId: overview.accounts[0].id }
      }

      if (!next.strategyId && strategies[0]) {
        next = { ...next, strategyId: strategies[0].id }
      }

      const selectedStrategy = strategies.find((strategy) => strategy.id === next.strategyId) ?? strategies[0]
      if (!selectedStrategy) {
        return next
      }

      const timeframeOptions = normalizeTimeframes(selectedStrategy.timeframes)
      if (next.strategyId !== selectedStrategy.id || !timeframeOptions.includes(next.timeframe)) {
        next = {
          ...next,
          strategyId: selectedStrategy.id,
          timeframe: timeframeOptions[0],
        }
      }

      return next
    })
  }, [overview.accounts, strategies])

  const selectedStrategy = strategies.find((strategy) => strategy.id === form.strategyId)
  const timeframeOptions = normalizeTimeframes(selectedStrategy?.timeframes ?? [])
  const equitySummary = getEquitySummary(result?.equity_curve ?? [])
  const isBusy = isLoadingAccounts || isLoadingStrategies || isRunning

  const handleRunBacktest = async () => {
    const accountId = form.accountId.trim()
    const strategyId = form.strategyId.trim()
    const symbol = form.symbol.trim().toUpperCase()
    const rangePayload = buildQuantBacktestRangePayload(form.startDate, form.endDate)

    if (!accountId) {
      setFormError('Select an MT5 account.')
      return
    }

    if (!strategyId) {
      setFormError('Select a strategy.')
      return
    }

    if (!symbol) {
      setFormError('Enter a symbol.')
      return
    }

    if (typeof rangePayload === 'string') {
      setFormError(rangePayload)
      return
    }

    setFormError(null)
    await runBacktest({
      account_id: accountId,
      strategy_id: strategyId,
      symbol,
      timeframe: form.timeframe,
      ...rangePayload,
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t('quantBacktest.title')}
        icon={LineChart}
        actions={(
          <Button onClick={() => void handleRunBacktest()} disabled={isBusy}>
            <Play data-icon="inline-start" />
            {isRunning ? 'Running...' : t('quantBacktest.run')}
          </Button>
        )}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t('quantBacktest.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('quantBacktest.description')}</p>
          <p className="text-sm text-muted-foreground">
            Accounts come from Account List and are shared with Python Quant live assignments.
          </p>
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            Uses cached MT5 bars and simplified signal replay for strategy validation.
            This view does not include spread, slippage, fees, or contract-specific PnL.
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-account">MT5 Account</Label>
              <Select value={form.accountId} onValueChange={(value) => setForm((current) => ({ ...current, accountId: value }))}>
                <SelectTrigger id="quant-backtest-account" aria-label="MT5 Account">
                  <SelectValue placeholder="Select account" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {overview.accounts.map((account) => (
                      <SelectItem key={account.id} value={account.id}>{getAccountLabel(account)}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-strategy">Strategy</Label>
              <Select value={form.strategyId} onValueChange={(value) => setForm((current) => ({ ...current, strategyId: value }))}>
                <SelectTrigger id="quant-backtest-strategy" aria-label="Strategy">
                  <SelectValue placeholder="Select strategy" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {strategies.map((strategy) => (
                      <SelectItem key={strategy.id} value={strategy.id}>{strategy.name}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-symbol">Symbol</Label>
              <Input
                id="quant-backtest-symbol"
                aria-label="Symbol"
                value={form.symbol}
                onChange={(event) => setForm((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-timeframe">Timeframe</Label>
              <Select value={form.timeframe} onValueChange={(value) => setForm((current) => ({ ...current, timeframe: value as PythonQuantTimeframe }))}>
                <SelectTrigger id="quant-backtest-timeframe" aria-label="Timeframe">
                  <SelectValue placeholder="Select timeframe" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {timeframeOptions.map((timeframe) => (
                      <SelectItem key={timeframe} value={timeframe}>{timeframe}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-start-date">Start Date</Label>
              <Input
                id="quant-backtest-start-date"
                aria-label="Start Date"
                type="date"
                value={form.startDate}
                onChange={(event) => setForm((current) => ({ ...current, startDate: event.target.value }))}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="quant-backtest-end-date">End Date</Label>
              <Input
                id="quant-backtest-end-date"
                aria-label="End Date"
                type="date"
                value={form.endDate}
                onChange={(event) => setForm((current) => ({ ...current, endDate: event.target.value }))}
              />
            </div>
          </div>

          {formError ? <p className="mt-4 text-sm text-destructive">{formError}</p> : null}
          {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}
          {accountsError ? <p className="mt-4 text-sm text-destructive">{accountsError}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Simplified Replay Return</p>
                <p className="text-2xl font-semibold">{formatPercent(result.summary.total_return_pct)}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Trades</p>
                <p className="text-2xl font-semibold">{result.summary.trade_count}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Win Rate</p>
                <p className="text-2xl font-semibold">{formatPercent(result.summary.win_rate_pct)}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Max Drawdown</p>
                <p className="text-2xl font-semibold">{formatPercent(result.summary.max_drawdown_pct)}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Run a backtest to view the summary, equity curve, and trades.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Equity Curve</CardTitle>
        </CardHeader>
        <CardContent>
          {result && equitySummary ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <div>
                <p className="text-sm text-muted-foreground">Start Equity</p>
                <p className="font-medium">{formatNumber(equitySummary.start)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">End Equity</p>
                <p className="font-medium">{formatNumber(equitySummary.end)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Peak</p>
                <p className="font-medium">{formatNumber(equitySummary.peak)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Trough</p>
                <p className="font-medium">{formatNumber(equitySummary.trough)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Points</p>
                <p className="font-medium">{equitySummary.points}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No equity curve yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Trades</CardTitle>
        </CardHeader>
        <CardContent>
          {result && result.trades.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entry</TableHead>
                  <TableHead>Exit</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead className="text-right">PnL</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.trades.map((trade, index) => (
                  <TableRow key={`${trade.entry_time}-${trade.exit_time}-${index}`}>
                    <TableCell>{formatDateTime(trade.entry_time)}</TableCell>
                    <TableCell>{formatDateTime(trade.exit_time)}</TableCell>
                    <TableCell>{trade.side}</TableCell>
                    <TableCell className="text-right">{formatNumber(trade.pnl)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No trades to display.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
