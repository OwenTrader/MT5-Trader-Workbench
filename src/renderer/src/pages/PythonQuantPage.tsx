import { apiFetch } from '@/lib/api'
import React, { useEffect, useState } from 'react'
import {
  Database,
  LineChart,
  Pencil,
  Play,
  Square,
  Trash2,
  Code2,
  PlusCircle,
  Activity,
  Zap,
  Bot,
  Copy,
  Layers,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useI18n } from '@/i18n'
import {
  getPythonQuantErrorMessage,
  parsePythonQuantJobEvents,
  PYTHON_QUANT_API_BASE,
  PYTHON_QUANT_TIMEFRAMES,
  type PythonQuantExecutionMode,
  type PythonQuantJobEvent,
  type PythonQuantJob,
  type PythonQuantJobPayload,
  type PythonQuantTimeframe,
} from '@/lib/python-quant'
import { usePythonQuantStore } from '@/stores/python-quant-store'

type QuantJobFormState = {
  name: string
  accountId: string
  strategyId: string
  symbol: string
  timeframe: PythonQuantTimeframe
  lot: string
  executionMode: PythonQuantExecutionMode
}

const EMPTY_FORM: QuantJobFormState = {
  name: '',
  accountId: '',
  strategyId: '',
  symbol: 'XAUUSD',
  timeframe: 'M5',
  lot: '0.01',
  executionMode: 'paper',
}

const DEFAULT_CUSTOM_STRATEGY_TEMPLATE = `import backtrader as bt

STRATEGY_ID = 'custom_strategy'
STRATEGY_NAME = 'Custom Trend Strategy'
STRATEGY_DESCRIPTION = 'Custom quantitative strategy written in Backtrader.'
SUPPORTED_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']

class Strategy(bt.Strategy):
    params = (('period', 20),)

    def __init__(self):
        self.sma = bt.ind.SMA(self.data.close, period=self.p.period)
        self.signal_output = 'hold'

    def next(self):
        if self.data.close[0] > self.sma[0]:
            self.signal_output = 'buy'
        elif self.data.close[0] < self.sma[0]:
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
`

function getAccountLabel(account: { id: string; name: string; login: string }) {
  const name = account.name.trim() || account.id
  return account.login.trim() ? `${name} (${account.login})` : name
}

function formatDateTime(value: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

function getStatusVariant(status: PythonQuantJob['status']): 'default' | 'secondary' | 'destructive' {
  if (status === 'running') {
    return 'default'
  }

  if (status === 'error') {
    return 'destructive'
  }

  return 'secondary'
}

function normalizeTimeframes(timeframes: string[]) {
  const valid = timeframes.filter((value): value is PythonQuantTimeframe =>
    (PYTHON_QUANT_TIMEFRAMES as readonly string[]).includes(value)
  )

  return valid.length > 0 ? valid : [...PYTHON_QUANT_TIMEFRAMES]
}

function buildPayload(form: QuantJobFormState): PythonQuantJobPayload | string {
  const name = form.name.trim()
  const accountId = form.accountId.trim()
  const strategyId = form.strategyId.trim()
  const symbol = form.symbol.trim().toUpperCase()
  const lot = Number(form.lot)

  if (!name) {
    return 'Enter a job name.'
  }

  if (!accountId) {
    return 'Select an MT5 account.'
  }

  if (!strategyId) {
    return 'Select a Python strategy.'
  }

  if (!symbol) {
    return 'Enter a symbol.'
  }

  if (!Number.isFinite(lot) || lot <= 0) {
    return 'Enter a lot size greater than 0.'
  }

  return {
    name,
    account_id: accountId,
    strategy_id: strategyId,
    symbol,
    timeframe: form.timeframe,
    lot,
    execution_mode: form.executionMode,
  }
}

function buildBackfillPayload(form: QuantJobFormState): {
  account_id: string
  symbol: string
  timeframe: PythonQuantTimeframe
} | string {
  const accountId = form.accountId.trim()
  const strategyId = form.strategyId.trim()
  const symbol = form.symbol.trim().toUpperCase()

  if (!accountId) {
    return 'Select an MT5 account.'
  }

  if (!strategyId) {
    return 'Select a Python strategy.'
  }

  if (!symbol) {
    return 'Enter a symbol.'
  }

  return {
    account_id: accountId,
    symbol,
    timeframe: form.timeframe,
  }
}

type QuantJobFormFieldsProps = {
  form: QuantJobFormState
  onChange: React.Dispatch<React.SetStateAction<QuantJobFormState>>
  accountOptions: Array<{ id: string; name: string; login: string }>
  strategyOptions: Array<{ id: string; name: string; timeframes: string[] }>
  idPrefix: string
  labelPrefix?: string
}

function QuantJobFormFields({
  form,
  onChange,
  accountOptions,
  strategyOptions,
  idPrefix,
  labelPrefix,
}: QuantJobFormFieldsProps) {
  const { t } = useI18n()
  const selectedStrategy = strategyOptions.find((strategy) => strategy.id === form.strategyId)
  const timeframeOptions = normalizeTimeframes(selectedStrategy?.timeframes ?? [])
  const withLabelPrefix = (label: string) => (labelPrefix ? `${labelPrefix} ${label}` : label)

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="flex flex-col gap-2 md:col-span-2">
        <Label htmlFor={`${idPrefix}-python-quant-job-name`}>{t('pythonQuant.jobName')}</Label>
        <Input
          id={`${idPrefix}-python-quant-job-name`}
          aria-label={withLabelPrefix(t('pythonQuant.jobName'))}
          value={form.name}
          onChange={(event) => onChange((current) => ({ ...current, name: event.target.value }))}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-account`}>{t('pythonQuant.mt5Account')}</Label>
        <Select
          value={form.accountId}
          onValueChange={(value) => onChange((current) => ({ ...current, accountId: value }))}
        >
          <SelectTrigger
            id={`${idPrefix}-python-quant-account`}
            aria-label={withLabelPrefix(t('pythonQuant.mt5Account'))}
          >
            <SelectValue placeholder={t('pythonQuant.selectAccount')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {accountOptions.map((account) => (
                <SelectItem key={account.id} value={account.id}>
                  {getAccountLabel(account)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-strategy`}>{t('pythonQuant.strategy')}</Label>
        <Select
          value={form.strategyId}
          onValueChange={(value) => onChange((current) => ({ ...current, strategyId: value }))}
        >
          <SelectTrigger
            id={`${idPrefix}-python-quant-strategy`}
            aria-label={withLabelPrefix(t('pythonQuant.strategy'))}
          >
            <SelectValue placeholder={t('pythonQuant.selectStrategy')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {strategyOptions.map((strategy) => (
                <SelectItem key={strategy.id} value={strategy.id}>
                  {strategy.name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-symbol`}>{t('pythonQuant.symbol')}</Label>
        <Input
          id={`${idPrefix}-python-quant-symbol`}
          aria-label={withLabelPrefix(t('pythonQuant.symbol'))}
          value={form.symbol}
          onChange={(event) =>
            onChange((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))
          }
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-timeframe`}>{t('pythonQuant.timeframe')}</Label>
        <Select
          value={form.timeframe}
          onValueChange={(value) =>
            onChange((current) => ({ ...current, timeframe: value as PythonQuantTimeframe }))
          }
        >
          <SelectTrigger
            id={`${idPrefix}-python-quant-timeframe`}
            aria-label={withLabelPrefix(t('pythonQuant.timeframe'))}
          >
            <SelectValue placeholder={t('pythonQuant.selectTimeframe')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {timeframeOptions.map((timeframe) => (
                <SelectItem key={timeframe} value={timeframe}>
                  {timeframe}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-lot`}>{t('pythonQuant.lotSize')}</Label>
        <Input
          id={`${idPrefix}-python-quant-lot`}
          aria-label={withLabelPrefix(t('pythonQuant.lotSize'))}
          type="number"
          min="0"
          step="0.01"
          value={form.lot}
          onChange={(event) => onChange((current) => ({ ...current, lot: event.target.value }))}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-execution-mode`}>{t('pythonQuant.executionMode')}</Label>
        <Select
          value={form.executionMode}
          onValueChange={(value) =>
            onChange((current) => ({ ...current, executionMode: value as PythonQuantExecutionMode }))
          }
        >
          <SelectTrigger
            id={`${idPrefix}-python-quant-execution-mode`}
            aria-label={withLabelPrefix(t('pythonQuant.executionMode'))}
          >
            <SelectValue placeholder={t('pythonQuant.selectExecutionMode')} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="paper">{t('pythonQuant.paper')}</SelectItem>
              <SelectItem value="live">{t('pythonQuant.live')}</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}

export function PythonQuantPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const {
    overview,
    isLoading,
    error,
    fetchOverview,
    createJob,
    updateJob,
    startJob,
    stopJob,
    deleteJob,
    evaluateJobNow,
    backfillData,
    fetchStrategyCode,
    createCustomStrategy,
  } = usePythonQuantStore()

  const [createForm, setCreateForm] = React.useState<QuantJobFormState>(EMPTY_FORM)
  const [editForm, setEditForm] = React.useState<QuantJobFormState>(EMPTY_FORM)
  const [bars, setBars] = React.useState('500')
  const [formError, setFormError] = React.useState<string | null>(null)
  const [jobsError, setJobsError] = React.useState<string | null>(null)
  const [backfillError, setBackfillError] = React.useState<string | null>(null)
  const [backfillMessage, setBackfillMessage] = React.useState<string | null>(null)
  const [editingJob, setEditingJob] = React.useState<PythonQuantJob | null>(null)
  const [jobEvents, setJobEvents] = React.useState<Record<string, PythonQuantJobEvent[]>>({})

  // Strategy code inspection state
  const [viewingStrategy, setViewingStrategy] = useState<{ id: string; name: string } | null>(null)
  const [strategySourceCode, setStrategySourceCode] = useState<string | null>(null)
  const [loadingCode, setLoadingCode] = useState(false)

  // Custom strategy creator modal state
  const [isCreatingCustomStrategy, setIsCreatingCustomStrategy] = useState(false)
  const [customStratId, setCustomStratId] = useState('')
  const [customStratName, setCustomStratName] = useState('')
  const [customStratDesc, setCustomStratDesc] = useState('')
  const [customStratCode, setCustomStratCode] = useState(DEFAULT_CUSTOM_STRATEGY_TEMPLATE)
  const [customStratError, setCustomStratError] = useState<string | null>(null)

  useEffect(() => {
    void fetchOverview()
  }, [fetchOverview])

  useEffect(() => {
    setCreateForm((current) => {
      const nextAccountId = overview.accounts.some((account) => account.id === current.accountId)
        ? current.accountId
        : overview.accounts[0]?.id ?? ''
      const nextStrategyId = overview.strategies.some((strategy) => strategy.id === current.strategyId)
        ? current.strategyId
        : overview.strategies[0]?.id ?? ''
      const nextTimeframes = normalizeTimeframes(
        overview.strategies.find((strategy) => strategy.id === nextStrategyId)?.timeframes ?? []
      )
      const nextTimeframe = nextTimeframes.includes(current.timeframe) ? current.timeframe : nextTimeframes[0]

      if (
        nextAccountId === current.accountId &&
        nextStrategyId === current.strategyId &&
        nextTimeframe === current.timeframe
      ) {
        return current
      }

      return {
        ...current,
        accountId: nextAccountId,
        strategyId: nextStrategyId,
        timeframe: nextTimeframe,
      }
    })
  }, [overview.accounts, overview.strategies])

  useEffect(() => {
    if (overview.jobs.length === 0) {
      setJobEvents({})
      return
    }

    let cancelled = false

    const loadJobEvents = async () => {
      const entries = await Promise.all(
        overview.jobs.map(async (job) => {
          try {
            const response = await apiFetch(`${PYTHON_QUANT_API_BASE}/jobs/${job.id}/events`)
            if (!response.ok) {
              throw new Error(await getPythonQuantErrorMessage(response, 'Failed to fetch Python Quant job events'))
            }

            return [job.id, parsePythonQuantJobEvents(await response.json())] as const
          } catch {
            return [job.id, []] as const
          }
        })
      )

      if (!cancelled) {
        setJobEvents(Object.fromEntries(entries))
      }
    }

    void loadJobEvents()

    return () => {
      cancelled = true
    }
  }, [overview.jobs])

  const pageError = !formError && !jobsError && !backfillError ? error : null
  const hasAccounts = overview.accounts.length > 0
  const hasStrategies = overview.strategies.length > 0

  // Cockpit metric aggregates
  const totalJobs = overview.jobs.length
  const runningJobs = overview.jobs.filter((j) => j.status === 'running').length
  const liveJobs = overview.jobs.filter((j) => j.execution_mode === 'live' && j.status === 'running').length
  const paperJobs = overview.jobs.filter((j) => j.execution_mode === 'paper' && j.status === 'running').length
  const availableStrategiesCount = overview.strategies.length

  const closeEditDialog = React.useCallback(() => {
    setEditingJob(null)
    setEditForm(EMPTY_FORM)
    setFormError(null)
  }, [])

  const handleCreateJob = async () => {
    setFormError(null)
    setBackfillMessage(null)

    const payload = buildPayload(createForm)
    if (typeof payload === 'string') {
      setFormError(payload)
      return
    }

    const success = await createJob(payload)
    if (!success) {
      setFormError(usePythonQuantStore.getState().error)
      return
    }

    toast.success(t('pythonQuant.createJob'))
    setCreateForm((current) => ({
      ...EMPTY_FORM,
      accountId: current.accountId,
      strategyId: current.strategyId,
      timeframe: current.timeframe,
      executionMode: current.executionMode,
    }))
  }

  const handleOpenEdit = (job: PythonQuantJob) => {
    setJobsError(null)
    setFormError(null)
    setEditingJob(job)
    setEditForm({
      name: job.name,
      accountId: job.account_id,
      strategyId: job.strategy_id,
      symbol: job.symbol,
      timeframe: job.timeframe as PythonQuantTimeframe,
      lot: String(job.lot),
      executionMode: job.execution_mode,
    })
  }

  const handleUpdateJob = async () => {
    if (!editingJob) {
      return
    }

    setFormError(null)
    const payload = buildPayload(editForm)
    if (typeof payload === 'string') {
      setFormError(payload)
      return
    }

    const success = await updateJob(editingJob.id, {
      ...payload,
      enabled: editingJob.enabled,
    })
    if (!success) {
      setFormError(usePythonQuantStore.getState().error)
      return
    }

    toast.success(t('pythonQuant.saveChanges'))
    closeEditDialog()
  }

  const handleStartJob = async (jobId: string) => {
    setJobsError(null)
    const job = overview.jobs.find((item) => item.id === jobId)
    if (job?.execution_mode === 'live') {
      const confirmed = window.confirm(
        `Start live quant job "${job.name}" on ${job.symbol} with lot ${job.lot}?`
      )
      if (!confirmed) {
        return
      }
    }

    const success = await startJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
    } else {
      toast.success(t('pythonQuant.start'))
    }
  }

  const handleStopJob = async (jobId: string) => {
    setJobsError(null)
    const success = await stopJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
    } else {
      toast.info(t('pythonQuant.stop'))
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    setJobsError(null)
    const success = await deleteJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
    }
  }

  const handleEvaluateNow = async (job: PythonQuantJob) => {
    toast.info(t('pythonQuant.evaluating'))
    const success = await evaluateJobNow(job.id)
    if (success) {
      toast.success(t('pythonQuant.evaluatedSuccess', { signal: job.last_signal || 'Evaluated' }))
    } else {
      toast.error('Evaluation failed')
    }
  }

  const handleViewStrategyCode = async (strategy: { id: string; name: string }) => {
    setViewingStrategy(strategy)
    setLoadingCode(true)
    const code = await fetchStrategyCode(strategy.id)
    setStrategySourceCode(code)
    setLoadingCode(false)
  }

  const handleSaveCustomStrategy = async () => {
    setCustomStratError(null)
    if (!customStratId.trim() || !customStratName.trim()) {
      setCustomStratError('Please fill in Strategy ID and Display Name.')
      return
    }

    const success = await createCustomStrategy({
      id: customStratId.trim().toLowerCase(),
      name: customStratName.trim(),
      description: customStratDesc.trim() || 'Custom quantitative strategy',
      timeframes: ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
      code: customStratCode,
    })

    if (success) {
      toast.success('Custom strategy created successfully!')
      setIsCreatingCustomStrategy(false)
      setCustomStratId('')
      setCustomStratName('')
      setCustomStratDesc('')
      setCustomStratCode(DEFAULT_CUSTOM_STRATEGY_TEMPLATE)
    } else {
      setCustomStratError(usePythonQuantStore.getState().error)
    }
  }

  const handleBackfill = async () => {
    setBackfillError(null)
    setBackfillMessage(null)

    const payload = buildBackfillPayload(createForm)
    if (typeof payload === 'string') {
      setBackfillError(payload)
      return
    }

    const parsedBars = Number(bars)
    if (!Number.isFinite(parsedBars) || parsedBars <= 0) {
      setBackfillError('Enter a bars value greater than 0.')
      return
    }

    const insertedRows = await backfillData({
      account_id: payload.account_id,
      symbol: payload.symbol,
      timeframe: payload.timeframe,
      bars: parsedBars,
    })
    if (insertedRows === null) {
      setBackfillError(usePythonQuantStore.getState().error)
      return
    }

    setBackfillMessage(`Inserted ${insertedRows} rows`)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <PageHeader
          title={t('pythonQuant.title')}
          description={t('pythonQuant.description')}
          icon={LineChart}
        />
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsCreatingCustomStrategy(true)}
            className="gap-1.5"
          >
            <PlusCircle className="w-4 h-4 text-primary" />
            {t('pythonQuant.createCustomStrategy')}
          </Button>
        </div>
      </div>

      {/* Cockpit Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 border bg-card/60">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Activity className="w-4 h-4 text-primary" />
            <span>{t('pythonQuant.jobsTitle')}</span>
          </div>
          <div className="text-2xl font-bold font-mono mt-1">{totalJobs}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{t('pythonQuant.runningJobs', { count: runningJobs })}</div>
        </Card>

        <Card className="p-4 border bg-card/60">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Zap className="w-4 h-4 text-emerald-500" />
            <span>{t('pythonQuant.cockpitLive')}</span>
          </div>
          <div className="text-2xl font-bold font-mono mt-1 text-emerald-500">{liveJobs}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{t('pythonQuant.modeLive')}</div>
        </Card>

        <Card className="p-4 border bg-card/60">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Bot className="w-4 h-4 text-amber-500" />
            <span>{t('pythonQuant.cockpitPaper')}</span>
          </div>
          <div className="text-2xl font-bold font-mono mt-1 text-amber-500">{paperJobs}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{t('pythonQuant.modePaper')}</div>
        </Card>

        <Card className="p-4 border bg-card/60">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Layers className="w-4 h-4 text-sky-500" />
            <span>{t('pythonQuant.cockpitStrategies')}</span>
          </div>
          <div className="text-2xl font-bold font-mono mt-1 text-sky-500">{availableStrategiesCount}</div>
          <div className="text-xs text-muted-foreground mt-0.5">{t('pythonQuant.modeLibrary')}</div>
        </Card>
      </div>

      {/* Strategies Library Preview Section */}
      <Card>
        <CardHeader className="py-3 px-4 flex flex-row items-center justify-between border-b bg-muted/10">
          <div>
            <CardTitle className="text-base">{t('pythonQuant.cockpitStrategies')}</CardTitle>
            <p className="text-xs text-muted-foreground">{t('pythonQuant.libraryHint')}</p>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {overview.strategies.map((strategy) => (
              <div
                key={strategy.id}
                className="p-3 border rounded-lg bg-card/40 flex flex-col justify-between gap-2 hover:border-primary/40 transition-colors"
              >
                <div>
                  <div className="flex justify-between items-start">
                    <span className="font-semibold text-sm">{strategy.name}</span>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {strategy.id}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                    {strategy.description}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-1 border-t text-xs">
                  <span className="text-[11px] text-muted-foreground font-mono">
                    {strategy.timeframes.join(', ')}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs px-2"
                      onClick={() => handleViewStrategyCode(strategy)}
                    >
                      <Code2 className="w-3.5 h-3.5 mr-1 text-primary" />
                      {t('pythonQuant.viewCode')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 text-xs px-2"
                      onClick={() => navigate(`/quant?tab=backtest`)}
                    >
                      {t('pythonQuant.backtestThis')}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Create Job Form */}
      <Card>
        <CardHeader>
          <CardTitle>{t('pythonQuant.createJobHeader')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('pythonQuant.createJobSub')}</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            {t('pythonQuant.quantUsesAccountList')}
          </p>

          {!hasAccounts || !hasStrategies ? (
            <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              {!hasAccounts ? t('pythonQuant.noAccountsHint') : null}
              {!hasAccounts && !hasStrategies ? ' ' : null}
              {!hasStrategies ? t('pythonQuant.noStrategiesHint') : null}
            </div>
          ) : null}

          {pageError ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {pageError}
            </div>
          ) : null}

          <QuantJobFormFields
            form={createForm}
            onChange={setCreateForm}
            accountOptions={overview.accounts}
            strategyOptions={overview.strategies}
            idPrefix="create"
          />

          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px_auto] md:items-end">
            <div className="flex flex-col gap-2">
              <Label htmlFor="python-quant-bars">{t('pythonQuant.bars')}</Label>
              <Input
                id="python-quant-bars"
                type="number"
                min="1"
                step="1"
                value={bars}
                onChange={(event) => setBars(event.target.value)}
              />
            </div>

            <Button
              variant="outline"
              onClick={handleBackfill}
              disabled={isLoading || !hasAccounts || !hasStrategies}
            >
              <Database data-icon="inline-start" />
              {t('pythonQuant.backfillData')}
            </Button>

            <Button
              onClick={handleCreateJob}
              disabled={isLoading || !hasAccounts || !hasStrategies}
            >
              {t('pythonQuant.createJob')}
            </Button>
          </div>

          {formError ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {formError}
            </div>
          ) : null}

          {backfillError ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {backfillError}
            </div>
          ) : null}

          {backfillMessage ? (
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-foreground">
              {backfillMessage}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Jobs Table */}
      <Card>
        <CardHeader>
          <CardTitle>{t('pythonQuant.jobsTitle')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('pythonQuant.jobsSub')}</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {jobsError ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
            >
              {jobsError}
            </div>
          ) : null}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('pythonQuant.colJob')}</TableHead>
                <TableHead>{t('pythonQuant.colAccount')}</TableHead>
                <TableHead>{t('pythonQuant.colStrategy')}</TableHead>
                <TableHead>{t('pythonQuant.colStatus')}</TableHead>
                <TableHead>{t('pythonQuant.colActivity')}</TableHead>
                <TableHead>{t('pythonQuant.colLastSignal')}</TableHead>
                <TableHead>{t('pythonQuant.colLastError')}</TableHead>
                <TableHead>{t('pythonQuant.colLastBarTime')}</TableHead>
                <TableHead className="text-right">{t('pythonQuant.colActions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overview.jobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center text-muted-foreground">
                    {t('pythonQuant.emptyJobs')}
                  </TableCell>
                </TableRow>
              ) : (
                overview.jobs.map((job) => {
                  const accountLabel = getAccountLabel(
                    overview.accounts.find((account) => account.id === job.account_id) ?? {
                      id: job.account_id,
                      name: job.account_id,
                      login: '',
                    }
                  )
                  const strategyLabel =
                    overview.strategies.find((strategy) => strategy.id === job.strategy_id)?.name ??
                    job.strategy_id
                  const latestEvent = jobEvents[job.id]?.[0] ?? null

                  return (
                    <TableRow key={job.id}>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="font-medium">{job.name}</span>
                          <span className="text-xs text-muted-foreground font-mono">
                            {job.symbol} · {job.timeframe} · {job.lot} · {job.execution_mode}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{accountLabel}</TableCell>
                      <TableCell>{strategyLabel}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
                      </TableCell>
                      <TableCell>
                        {latestEvent ? (
                          <div className="flex max-w-56 flex-col gap-1 whitespace-normal break-words">
                            <span>{latestEvent.message}</span>
                            <span className="text-xs text-muted-foreground">
                              {formatDateTime(latestEvent.created_at)}
                            </span>
                          </div>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`font-mono text-xs ${
                            job.last_signal === 'buy'
                              ? 'border-emerald-500 text-emerald-500'
                              : job.last_signal === 'sell'
                              ? 'border-rose-500 text-rose-500'
                              : job.last_signal === 'close'
                              ? 'border-amber-500 text-amber-500'
                              : ''
                          }`}
                        >
                          {job.last_signal ?? '-'}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-56 whitespace-normal break-words text-destructive">
                        {job.last_error ?? '-'}
                      </TableCell>
                      <TableCell className="text-xs font-mono">{formatDateTime(job.last_bar_time)}</TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1.5">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleEvaluateNow(job)}
                            disabled={isLoading}
                            title={t('pythonQuant.stepNowTitle')}
                            aria-label={`Evaluate ${job.name}`}
                          >
                            <Zap className="w-3.5 h-3.5 mr-1 text-primary" />
                            {t('pythonQuant.evaluateNow')}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenEdit(job)}
                            aria-label={`Edit ${job.name}`}
                          >
                            <Pencil data-icon="inline-start" />
                            {t('priceAlerts.edit')}
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleStartJob(job.id)}
                            disabled={isLoading || job.status === 'running'}
                            aria-label={`Start ${job.name}`}
                          >
                            <Play data-icon="inline-start" />
                            {t('pythonQuant.start')}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleStopJob(job.id)}
                            disabled={isLoading || job.status !== 'running'}
                            aria-label={`Stop ${job.name}`}
                          >
                            <Square data-icon="inline-start" />
                            {t('pythonQuant.stop')}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDeleteJob(job.id)}
                            aria-label={`Delete ${job.name}`}
                          >
                            <Trash2 data-icon="inline-start" />
                            {t('priceAlerts.delete')}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Edit Job Dialog */}
      <Dialog
        open={editingJob !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeEditDialog()
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('pythonQuant.editJobTitle')}</DialogTitle>
            <DialogDescription>{t('pythonQuant.editJobSub')}</DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <QuantJobFormFields
              form={editForm}
              onChange={setEditForm}
              accountOptions={overview.accounts}
              strategyOptions={overview.strategies}
              idPrefix="edit"
              labelPrefix="Edit"
            />

            {formError ? (
              <div
                role="alert"
                className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"
              >
                {formError}
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeEditDialog}>
              {t('pythonQuant.cancel')}
            </Button>
            <Button onClick={handleUpdateJob} disabled={isLoading}>
              {t('pythonQuant.saveChanges')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Strategy Source Code Dialog */}
      <Dialog
        open={viewingStrategy !== null}
        onOpenChange={(open) => {
          if (!open) {
            setViewingStrategy(null)
            setStrategySourceCode(null)
          }
        }}
      >
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono">
              <Code2 className="w-5 h-5 text-primary" />
              {t('pythonQuant.codeViewerTitle', { name: viewingStrategy?.name || '' })}
            </DialogTitle>
            <DialogDescription>
              {t('pythonQuant.strategySourceTitle', { id: viewingStrategy?.id ?? '' })}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-auto bg-muted/40 rounded-lg p-4 border font-mono text-xs text-foreground select-text whitespace-pre">
            {loadingCode ? 'Loading source code...' : strategySourceCode || '# No code available'}
          </div>

          <DialogFooter className="flex justify-between items-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (strategySourceCode) {
                  navigator.clipboard.writeText(strategySourceCode)
                  toast.success('Code copied to clipboard')
                }
              }}
            >
              <Copy className="w-4 h-4 mr-1.5" />
              {t('pythonQuant.copyCode')}
            </Button>
            <Button variant="secondary" onClick={() => setViewingStrategy(null)}>
              {t('pythonQuant.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Custom Strategy Modal */}
      <Dialog open={isCreatingCustomStrategy} onOpenChange={setIsCreatingCustomStrategy}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <PlusCircle className="w-5 h-5 text-primary" />
              {t('pythonQuant.customStrategyTitle')}
            </DialogTitle>
            <DialogDescription>{t('pythonQuant.customStrategyDescription')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 flex-1 overflow-auto">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">{t('pythonQuant.strategyId')}</Label>
                <Input
                  className="h-8 text-xs font-mono"
                  placeholder="e.g. ema_scalper"
                  value={customStratId}
                  onChange={(e) => setCustomStratId(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{t('pythonQuant.strategyName')}</Label>
                <Input
                  className="h-8 text-xs"
                  placeholder="e.g. EMA Scalper Strategy"
                  value={customStratName}
                  onChange={(e) => setCustomStratName(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs">{t('pythonQuant.strategyDescription')}</Label>
              <Input
                className="h-8 text-xs"
                placeholder={t('pythonQuant.strategyDescPlaceholder')}
                value={customStratDesc}
                onChange={(e) => setCustomStratDesc(e.target.value)}
              />
            </div>

            <div className="space-y-1">
              <Label className="text-xs">{t('pythonQuant.strategyCode')}</Label>
              <Textarea
                className="font-mono text-xs h-64 resize-none bg-muted/20"
                value={customStratCode}
                onChange={(e) => setCustomStratCode(e.target.value)}
              />
            </div>

            {customStratError && (
              <div role="alert" className="p-2.5 rounded-md border border-destructive/30 bg-destructive/10 text-xs text-destructive">
                {customStratError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreatingCustomStrategy(false)}>
              {t('pythonQuant.cancel')}
            </Button>
            <Button onClick={handleSaveCustomStrategy} disabled={isLoading}>
              {t('pythonQuant.saveAndLoad')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
