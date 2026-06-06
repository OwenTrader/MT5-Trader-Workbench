import React, { useEffect } from 'react'
import { Database, LineChart, Pencil, Play, Square, Trash2 } from 'lucide-react'

import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useI18n } from '@/i18n'
import {
  PYTHON_QUANT_TIMEFRAMES,
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
}

const EMPTY_FORM: QuantJobFormState = {
  name: '',
  accountId: '',
  strategyId: '',
  symbol: 'XAUUSD',
  timeframe: 'M5',
  lot: '0.01',
}

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
  const valid = timeframes.filter((value): value is PythonQuantTimeframe => (
    PYTHON_QUANT_TIMEFRAMES as readonly string[]
  ).includes(value))

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

function QuantJobFormFields({ form, onChange, accountOptions, strategyOptions, idPrefix, labelPrefix }: QuantJobFormFieldsProps) {
  const selectedStrategy = strategyOptions.find((strategy) => strategy.id === form.strategyId)
  const timeframeOptions = normalizeTimeframes(selectedStrategy?.timeframes ?? [])
  const withLabelPrefix = (label: string) => (labelPrefix ? `${labelPrefix} ${label}` : label)

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="flex flex-col gap-2 md:col-span-2">
        <Label htmlFor={`${idPrefix}-python-quant-job-name`}>Job Name</Label>
        <Input
          id={`${idPrefix}-python-quant-job-name`}
          aria-label={withLabelPrefix('Job Name')}
          value={form.name}
          onChange={(event) => onChange((current) => ({ ...current, name: event.target.value }))}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-account`}>MT5 Account</Label>
        <Select value={form.accountId} onValueChange={(value) => onChange((current) => ({ ...current, accountId: value }))}>
          <SelectTrigger id={`${idPrefix}-python-quant-account`} aria-label={withLabelPrefix('MT5 Account')}>
            <SelectValue placeholder="Select account" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {accountOptions.map((account) => (
                <SelectItem key={account.id} value={account.id}>{getAccountLabel(account)}</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-strategy`}>Strategy</Label>
        <Select value={form.strategyId} onValueChange={(value) => onChange((current) => ({ ...current, strategyId: value }))}>
          <SelectTrigger id={`${idPrefix}-python-quant-strategy`} aria-label={withLabelPrefix('Strategy')}>
            <SelectValue placeholder="Select strategy" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {strategyOptions.map((strategy) => (
                <SelectItem key={strategy.id} value={strategy.id}>{strategy.name}</SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-symbol`}>Symbol</Label>
        <Input
          id={`${idPrefix}-python-quant-symbol`}
          aria-label={withLabelPrefix('Symbol')}
          value={form.symbol}
          onChange={(event) => onChange((current) => ({ ...current, symbol: event.target.value.toUpperCase() }))}
        />
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor={`${idPrefix}-python-quant-timeframe`}>Timeframe</Label>
        <Select value={form.timeframe} onValueChange={(value) => onChange((current) => ({ ...current, timeframe: value as PythonQuantTimeframe }))}>
          <SelectTrigger id={`${idPrefix}-python-quant-timeframe`} aria-label={withLabelPrefix('Timeframe')}>
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
        <Label htmlFor={`${idPrefix}-python-quant-lot`}>Lot Size</Label>
        <Input
          id={`${idPrefix}-python-quant-lot`}
          aria-label={withLabelPrefix('Lot Size')}
          type="number"
          min="0"
          step="0.01"
          value={form.lot}
          onChange={(event) => onChange((current) => ({ ...current, lot: event.target.value }))}
        />
      </div>
    </div>
  )
}

export function PythonQuantPage() {
  const { t } = useI18n()
  const { overview, isLoading, error, fetchOverview, createJob, updateJob, startJob, stopJob, deleteJob, backfillData } = usePythonQuantStore()
  const [createForm, setCreateForm] = React.useState<QuantJobFormState>(EMPTY_FORM)
  const [editForm, setEditForm] = React.useState<QuantJobFormState>(EMPTY_FORM)
  const [bars, setBars] = React.useState('500')
  const [formError, setFormError] = React.useState<string | null>(null)
  const [jobsError, setJobsError] = React.useState<string | null>(null)
  const [backfillError, setBackfillError] = React.useState<string | null>(null)
  const [backfillMessage, setBackfillMessage] = React.useState<string | null>(null)
  const [editingJob, setEditingJob] = React.useState<PythonQuantJob | null>(null)

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
      const nextTimeframes = normalizeTimeframes(overview.strategies.find((strategy) => strategy.id === nextStrategyId)?.timeframes ?? [])
      const nextTimeframe = nextTimeframes.includes(current.timeframe) ? current.timeframe : nextTimeframes[0]

      if (
        nextAccountId === current.accountId
        && nextStrategyId === current.strategyId
        && nextTimeframe === current.timeframe
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

  const pageError = !formError && !jobsError && !backfillError ? error : null
  const hasAccounts = overview.accounts.length > 0
  const hasStrategies = overview.strategies.length > 0

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

    setCreateForm((current) => ({
      ...EMPTY_FORM,
      accountId: current.accountId,
      strategyId: current.strategyId,
      timeframe: current.timeframe,
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

    closeEditDialog()
  }

  const handleStartJob = async (jobId: string) => {
    setJobsError(null)
    const success = await startJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
    }
  }

  const handleStopJob = async (jobId: string) => {
    setJobsError(null)
    const success = await stopJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    setJobsError(null)
    const success = await deleteJob(jobId)
    if (!success) {
      setJobsError(usePythonQuantStore.getState().error)
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
      <PageHeader title={t('pythonQuant.title')} icon={LineChart} />

      <Card>
        <CardHeader>
          <CardTitle>Create Job</CardTitle>
          <p className="text-sm text-muted-foreground">{t('pythonQuant.description')}</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Python Quant uses MT5 accounts already configured in Local Copy Trading.
          </p>

          {!hasAccounts || !hasStrategies ? (
            <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
              {!hasAccounts ? 'Add at least one Local Copy Trading MT5 account before creating a quant job.' : null}
              {!hasAccounts && !hasStrategies ? ' ' : null}
              {!hasStrategies ? 'No Python strategies are currently available.' : null}
            </div>
          ) : null}

          {pageError ? (
            <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
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
              <Label htmlFor="python-quant-bars">Bars</Label>
              <Input
                id="python-quant-bars"
                type="number"
                min="1"
                step="1"
                value={bars}
                onChange={(event) => setBars(event.target.value)}
              />
            </div>

            <Button variant="outline" onClick={handleBackfill} disabled={isLoading || !hasAccounts || !hasStrategies}>
              <Database data-icon="inline-start" />
              Backfill Data
            </Button>

            <Button onClick={handleCreateJob} disabled={isLoading || !hasAccounts || !hasStrategies}>
              {t('pythonQuant.createJob')}
            </Button>
          </div>

          {formError ? (
            <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
              {formError}
            </div>
          ) : null}

          {backfillError ? (
            <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
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

      <Card>
        <CardHeader>
          <CardTitle>Jobs</CardTitle>
          <p className="text-sm text-muted-foreground">Start, stop, edit, or remove strategy jobs without leaving the page.</p>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {jobsError ? (
            <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
              {jobsError}
            </div>
          ) : null}

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Signal</TableHead>
                <TableHead>Last Error</TableHead>
                <TableHead>Last Bar Time</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {overview.jobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">
                    No Python Quant jobs yet.
                  </TableCell>
                </TableRow>
              ) : overview.jobs.map((job) => {
                const accountLabel = getAccountLabel(overview.accounts.find((account) => account.id === job.account_id) ?? {
                  id: job.account_id,
                  name: job.account_id,
                  login: '',
                })
                const strategyLabel = overview.strategies.find((strategy) => strategy.id === job.strategy_id)?.name ?? job.strategy_id

                return (
                  <TableRow key={job.id}>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <span className="font-medium">{job.name}</span>
                        <span className="text-xs text-muted-foreground">{job.symbol} · {job.timeframe} · {job.lot}</span>
                      </div>
                    </TableCell>
                    <TableCell>{accountLabel}</TableCell>
                    <TableCell>{strategyLabel}</TableCell>
                    <TableCell>
                      <Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
                    </TableCell>
                    <TableCell>{job.last_signal ?? '-'}</TableCell>
                    <TableCell className="max-w-56 whitespace-normal break-words text-destructive">{job.last_error ?? '-'}</TableCell>
                    <TableCell>{formatDateTime(job.last_bar_time)}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => handleOpenEdit(job)} aria-label={`Edit ${job.name}`}>
                          <Pencil data-icon="inline-start" />
                          Edit
                        </Button>
                        <Button size="sm" onClick={() => handleStartJob(job.id)} disabled={isLoading || job.status === 'running'} aria-label={`Start ${job.name}`}>
                          <Play data-icon="inline-start" />
                          {t('pythonQuant.start')}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleStopJob(job.id)} disabled={isLoading || job.status !== 'running'} aria-label={`Stop ${job.name}`}>
                          <Square data-icon="inline-start" />
                          {t('pythonQuant.stop')}
                        </Button>
                        <Button variant="destructive" size="sm" onClick={() => handleDeleteJob(job.id)} aria-label={`Delete ${job.name}`}>
                          <Trash2 data-icon="inline-start" />
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={editingJob !== null} onOpenChange={(open) => {
        if (!open) {
          closeEditDialog()
        }
      }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Python Quant Job</DialogTitle>
            <DialogDescription>Update the job settings and save the changes back to the backend.</DialogDescription>
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
              <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
                {formError}
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeEditDialog}>Cancel</Button>
            <Button onClick={handleUpdateJob} disabled={isLoading}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
