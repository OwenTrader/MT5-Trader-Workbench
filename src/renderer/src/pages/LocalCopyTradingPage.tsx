import React, { useEffect } from 'react'
import { Trash2, Loader2, AlertTriangle, RefreshCw } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useI18n } from '@/i18n'
import { useLocalCopyTradingStore } from '@/stores/local-copy-trading-store'
import { toast } from 'sonner'

function isRelationshipFormComplete(
  sourceId: string,
  followerId: string,
  sourceSymbol: string,
  followerSymbol: string,
  lotMultiplier: string,
  volumeMode: string,
  riskPercent: string,
) {
  const sizingOk = Boolean(sourceId.trim() && followerId.trim() && sourceSymbol.trim() && followerSymbol.trim() && Number(lotMultiplier) > 0)
  const riskOk = volumeMode !== 'risk_percent' || Number(riskPercent) > 0
  return sizingOk && riskOk
}

const VOLUME_MODE_LABEL_KEYS: Record<string, string> = {
  multiplier: 'localCopyTrading.volumeModes.multiplier',
  fixed: 'localCopyTrading.volumeModes.fixed',
  equity_ratio: 'localCopyTrading.volumeModes.equity_ratio',
  risk_percent: 'localCopyTrading.volumeModes.risk_percent',
}

function renderVolumeModeLabel(
  volumeMode: string | undefined,
  t: (key: string, params?: Record<string, string | number>) => string,
) {
  const mode = volumeMode ?? 'multiplier'
  return VOLUME_MODE_LABEL_KEYS[mode] ? t(VOLUME_MODE_LABEL_KEYS[mode]) : mode
}

const STATUS_LABEL_KEYS: Record<string, string> = {
  copied: 'localCopyTrading.eventStatus.copied',
  closed: 'localCopyTrading.eventStatus.closed',
  failed: 'localCopyTrading.eventStatus.failed',
  skipped: 'localCopyTrading.eventStatus.skipped',
  queued: 'localCopyTrading.eventStatus.queued',
}

function getStatusBadge(status: string, t: (key: string, params?: Record<string, string | number>) => string) {
  const label = STATUS_LABEL_KEYS[status] ? t(STATUS_LABEL_KEYS[status]) : status
  switch (status) {
    case 'copied':
      return <Badge variant="default" className="bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border-transparent dark:text-emerald-400">{label}</Badge>
    case 'closed':
      return <Badge variant="secondary">{label}</Badge>
    case 'failed':
      return <Badge variant="destructive">{label}</Badge>
    case 'skipped':
      return <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300">{label}</Badge>
    default:
      return <Badge variant="outline">{label}</Badge>
  }
}

function getRelationshipSourceSymbol(relationship: { symbol: string; source_symbol?: string }) {
  return (relationship.source_symbol || relationship.symbol).trim()
}

function getRelationshipFollowerSymbol(relationship: { symbol: string; source_symbol?: string; follower_symbol?: string }) {
  return (relationship.follower_symbol || relationship.source_symbol || relationship.symbol).trim()
}

function getAccountOptionLabel(account: { name: string; login: string; id: string }) {
  const name = account.name.trim() || account.id
  const login = account.login.trim()
  return login ? `${name} (${login})` : name
}

function getAccountLabelById(
  accounts: Array<{ id: string; name: string; login: string }>,
  accountId: string,
) {
  const account = accounts.find((item) => item.id === accountId)
  if (!account) {
    return accountId
  }

  return getAccountOptionLabel(account)
}

function getRelationshipLabel(
  relationship: { source_account_id: string; follower_account_id: string; symbol: string; source_symbol?: string; follower_symbol?: string } | undefined,
  accounts: Array<{ id: string; name: string; login: string }>,
) {
  if (!relationship) {
    return ''
  }
  return `${getAccountLabelById(accounts, relationship.source_account_id)} → ${getAccountLabelById(accounts, relationship.follower_account_id)} · ${getRelationshipSourceSymbol(relationship)}→${getRelationshipFollowerSymbol(relationship)}`
}

function formatDateTime(value: string) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

const OVERVIEW_POLL_INTERVAL_MS = 3000

export function LocalCopyTradingPage() {
  const navigate = useNavigate()
  const {
    overview,
    isLoading,
    error,
    riskSettings,
    isSavingRiskSettings,
    fetchOverview,
    fetchRiskSettings,
    updateRuntime,
    updateRiskSettings,
    createRelationship,
    deleteRelationship,
  } = useLocalCopyTradingStore()
  const { t } = useI18n()
  const [relationshipDialogOpen, setRelationshipDialogOpen] = React.useState(false)
  const [pendingDeleteRelationshipId, setPendingDeleteRelationshipId] = React.useState<string | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)
  const [pendingRuntimeEnabled, setPendingRuntimeEnabled] = React.useState(false)
  const [pendingRuntimeDisabled, setPendingRuntimeDisabled] = React.useState(false)
  const [runtimeSubmitError, setRuntimeSubmitError] = React.useState<string | null>(null)
  const [relationshipSourceSymbol, setRelationshipSourceSymbol] = React.useState('XAUUSD')
  const [relationshipFollowerSymbol, setRelationshipFollowerSymbol] = React.useState('XAUUSD')
  const [relationshipLotMultiplier, setRelationshipLotMultiplier] = React.useState('1')
  const [relationshipVolumeMode, setRelationshipVolumeMode] = React.useState('multiplier')
  const [relationshipRiskPercent, setRelationshipRiskPercent] = React.useState('1')
  const [relationshipMaxLot, setRelationshipMaxLot] = React.useState('0')
  const [relationshipSyncSlTp, setRelationshipSyncSlTp] = React.useState(false)
  const [selectedSourceId, setSelectedSourceId] = React.useState('')
  const [selectedFollowerId, setSelectedFollowerId] = React.useState('')

  const hasAccounts = overview.accounts.length > 1
  const hasRelationships = overview.relationships.length > 0
  const canCreateRelationship = hasAccounts
  const canEnableRuntime = hasAccounts && hasRelationships
  const totalOpenRecords = Object.values(overview.open_record_counts ?? {}).reduce((sum, count) => sum + count, 0)

  const closeRelationshipDialog = React.useCallback(() => {
    setRelationshipDialogOpen(false)
    setRelationshipSourceSymbol('XAUUSD')
    setRelationshipFollowerSymbol('XAUUSD')
    setRelationshipLotMultiplier('1')
    setRelationshipVolumeMode('multiplier')
    setRelationshipRiskPercent('1')
    setRelationshipMaxLot('0')
    setRelationshipSyncSlTp(false)
    setSelectedSourceId('')
    setSelectedFollowerId('')
  }, [])

  useEffect(() => {
    void fetchOverview()
    void fetchRiskSettings()
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void fetchOverview({ silent: true })
      }
    }, OVERVIEW_POLL_INTERVAL_MS)
    return () => window.clearInterval(interval)
  }, [fetchOverview, fetchRiskSettings])

  const [riskForm, setRiskForm] = React.useState({
    max_volume_per_symbol: '0',
    max_positions_per_symbol: '0',
    max_daily_open_count: '0',
    max_daily_loss: '0',
    min_margin_level: '0',
    max_consecutive_failures: '3',
  })

  useEffect(() => {
    setRiskForm({
      max_volume_per_symbol: String(riskSettings.max_volume_per_symbol),
      max_positions_per_symbol: String(riskSettings.max_positions_per_symbol),
      max_daily_open_count: String(riskSettings.max_daily_open_count),
      max_daily_loss: String(riskSettings.max_daily_loss),
      min_margin_level: String(riskSettings.min_margin_level),
      max_consecutive_failures: String(riskSettings.max_consecutive_failures),
    })
  }, [riskSettings])

  const handleSaveRiskSettings = async () => {
    const success = await updateRiskSettings({
      max_volume_per_symbol: Number(riskForm.max_volume_per_symbol) || 0,
      max_positions_per_symbol: Math.trunc(Number(riskForm.max_positions_per_symbol) || 0),
      max_daily_open_count: Math.trunc(Number(riskForm.max_daily_open_count) || 0),
      max_daily_loss: Number(riskForm.max_daily_loss) || 0,
      min_margin_level: Number(riskForm.min_margin_level) || 0,
      max_consecutive_failures: Math.trunc(Number(riskForm.max_consecutive_failures) || 0),
    })
    if (success) {
      toast.success(t('localCopyTrading.riskGuards.saved'))
      return
    }
    toast.error(useLocalCopyTradingStore.getState().error ?? t('localCopyTrading.riskGuards.saveFailed'))
  }

  const handleCreateRelationship = async () => {
    const sourceId = selectedSourceId.trim()
    const followerId = selectedFollowerId.trim()
    if (!sourceId || !followerId) {
      return
    }
    const success = await createRelationship({
      source_account_id: sourceId,
      follower_account_id: followerId,
      symbol: relationshipSourceSymbol,
      source_symbol: relationshipSourceSymbol,
      follower_symbol: relationshipFollowerSymbol,
      lot_multiplier: Number(relationshipLotMultiplier),
      volume_mode: relationshipVolumeMode,
      max_lot: Number(relationshipMaxLot) || 0,
      risk_percent: Number(relationshipRiskPercent) || 1,
      sync_sl_tp: relationshipSyncSlTp,
      is_active: true,
    })
    if (success) {
      closeRelationshipDialog()
    }
  }

  const handleRuntimeToggle = (checked: boolean) => {
    setRuntimeSubmitError(null)
    if (!checked) {
      // Disabling stops the automatic closes; make the exposure explicit
      // while copied positions are still open.
      if (totalOpenRecords > 0) {
        setPendingRuntimeDisabled(true)
        return
      }
      void updateRuntime({ enabled: false })
      return
    }

    if (!canEnableRuntime) {
      setRuntimeSubmitError(t('localCopyTrading.enableRequirements'))
      return
    }

    setPendingRuntimeEnabled(true)
  }

  const handleConfirmDisableRuntime = async () => {
    await updateRuntime({ enabled: false })
    setPendingRuntimeDisabled(false)
  }

  const handleConfirmEnableRuntime = async () => {
    const success = await updateRuntime({ enabled: true })
    if (!success) {
      setRuntimeSubmitError(useLocalCopyTradingStore.getState().error)
    }
    setPendingRuntimeEnabled(false)
  }

  const handleConfirmDelete = async () => {
    if (!pendingDeleteRelationshipId) {
      return
    }

    setIsDeleting(true)
    const success = await deleteRelationship(pendingDeleteRelationshipId)
    if (success) {
      setPendingDeleteRelationshipId(null)
    }
    setIsDeleting(false)
  }

  const handleSourceChange = (value: string) => {
    setSelectedSourceId(value)
    if (value === selectedFollowerId) {
      setSelectedFollowerId('')
    }
  }

  const handleFollowerChange = (value: string) => {
    setSelectedFollowerId(value)
    if (value === selectedSourceId) {
      setSelectedSourceId('')
    }
  }

  const openCountForPendingRelationship = overview.open_record_counts?.[pendingDeleteRelationshipId] ?? 0
  const deleteDescription = pendingDeleteRelationshipId
    ? t('localCopyTrading.confirmDeleteRelationship', {
        name: getRelationshipLabel(
          overview.relationships.find((item) => item.id === pendingDeleteRelationshipId),
          overview.accounts,
        ),
      }) + (openCountForPendingRelationship > 0
        ? ' ' + t('localCopyTrading.confirmDeleteRelationshipOpenPositions', { count: openCountForPendingRelationship })
        : '')
    : ''

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('localCopyTrading.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('localCopyTrading.description')}</p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Badge>{overview.runtime.enabled ? t('localCopyTrading.enabled') : t('localCopyTrading.disabled')}</Badge>
            <Badge variant="outline">{t('localCopyTrading.configurationMode')}</Badge>
            <Badge variant="secondary">{t('localCopyTrading.poll', { seconds: overview.runtime.poll_interval_seconds })}</Badge>
            {overview.runtime.last_checked_at ? (
              <Badge variant="secondary" className="font-mono">
                🕒 {formatDateTime(overview.runtime.last_checked_at)}
              </Badge>
            ) : null}
             <Badge variant="outline">{t('accountList.accountCount', { count: overview.accounts.length })}</Badge>
            <label className="flex items-center gap-2 text-sm">
              <span>{t('localCopyTrading.enabled')}</span>
              <Switch aria-label={t('localCopyTrading.runtimeSwitch')} checked={overview.runtime.enabled} onCheckedChange={handleRuntimeToggle} />
            </label>
            <Button variant="outline" size="sm" onClick={() => navigate('/account-list')}>{t('localCopyTrading.manageAccounts')}</Button>
            <Button variant="outline" size="sm" disabled={!canCreateRelationship} onClick={() => setRelationshipDialogOpen(true)}>{t('localCopyTrading.addRelationship')}</Button>
            <Button variant="outline" size="sm" onClick={() => void fetchOverview()} disabled={isLoading}>
              <RefreshCw className={isLoading ? 'animate-spin' : ''} />
              {t('localCopyTrading.refresh')}
            </Button>
          </div>
          {overview.runtime.last_error ? (
            <div className="mt-4 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive flex items-start gap-2">
              <AlertTriangle className="size-4 mt-0.5 shrink-0" />
              <div>
                <div className="font-semibold mb-1">{t('localCopyTrading.backendError')}</div>
                <div className="break-all">{overview.runtime.last_error}</div>
              </div>
            </div>
          ) : null}
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            {t('localCopyTrading.configurationModeDescription')}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{t('localCopyTrading.accountListHint')}</p>
          {runtimeSubmitError ? <p className="mt-3 text-sm text-destructive">{runtimeSubmitError}</p> : null}
          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('localCopyTrading.riskGuards.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('localCopyTrading.riskGuards.description')}</p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.maxVolumePerSymbol')}</span>
              <Input type="number" min="0" step="0.01" aria-label={t('localCopyTrading.riskGuards.maxVolumePerSymbol')} value={riskForm.max_volume_per_symbol} onChange={(event) => setRiskForm((current) => ({ ...current, max_volume_per_symbol: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansDisabled')}</span>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.maxPositionsPerSymbol')}</span>
              <Input type="number" min="0" step="1" aria-label={t('localCopyTrading.riskGuards.maxPositionsPerSymbol')} value={riskForm.max_positions_per_symbol} onChange={(event) => setRiskForm((current) => ({ ...current, max_positions_per_symbol: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansDisabled')}</span>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.maxDailyOpenCount')}</span>
              <Input type="number" min="0" step="1" aria-label={t('localCopyTrading.riskGuards.maxDailyOpenCount')} value={riskForm.max_daily_open_count} onChange={(event) => setRiskForm((current) => ({ ...current, max_daily_open_count: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansDisabled')}</span>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.maxDailyLoss')}</span>
              <Input type="number" min="0" step="1" aria-label={t('localCopyTrading.riskGuards.maxDailyLoss')} value={riskForm.max_daily_loss} onChange={(event) => setRiskForm((current) => ({ ...current, max_daily_loss: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansDisabled')}</span>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.minMarginLevel')}</span>
              <Input type="number" min="0" step="1" aria-label={t('localCopyTrading.riskGuards.minMarginLevel')} value={riskForm.min_margin_level} onChange={(event) => setRiskForm((current) => ({ ...current, min_margin_level: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansDisabled')}</span>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskGuards.maxConsecutiveFailures')}</span>
              <Input type="number" min="0" step="1" aria-label={t('localCopyTrading.riskGuards.maxConsecutiveFailures')} value={riskForm.max_consecutive_failures} onChange={(event) => setRiskForm((current) => ({ ...current, max_consecutive_failures: event.target.value }))} />
              <span className="text-xs text-muted-foreground">{t('localCopyTrading.riskGuards.zeroMeansNoBreaker')}</span>
            </label>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <Button size="sm" disabled={isSavingRiskSettings} onClick={() => void handleSaveRiskSettings()}>
              {isSavingRiskSettings ? t('localCopyTrading.riskGuards.saving') : t('localCopyTrading.riskGuards.save')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="relationships">
        <TabsList>
          <TabsTrigger value="relationships">{t('localCopyTrading.tabs.relationships')}</TabsTrigger>
          <TabsTrigger value="events">{t('localCopyTrading.tabs.events')}</TabsTrigger>
        </TabsList>

        <TabsContent value="relationships">
          <Card>
            <CardHeader>
              <CardTitle>{t('localCopyTrading.tabs.relationships')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('localCopyTrading.columns.source')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.follower')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.sourceSymbol')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.followerSymbol')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.volumeMode')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.lotMultiplier')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.status')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={8} className="py-8 text-center text-sm text-muted-foreground">
                        <div className="flex items-center justify-center gap-2">
                          <Loader2 className="size-4 animate-spin" />
                          {t('common.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : overview.relationships.length > 0 ? (
                    overview.relationships.map((relationship) => (
                      <TableRow key={relationship.id}>
                         <TableCell>{getAccountLabelById(overview.accounts, relationship.source_account_id)}</TableCell>
                         <TableCell>{getAccountLabelById(overview.accounts, relationship.follower_account_id)}</TableCell>
                        <TableCell>{getRelationshipSourceSymbol(relationship)}</TableCell>
                        <TableCell>{getRelationshipFollowerSymbol(relationship)}</TableCell>
                        <TableCell>{renderVolumeModeLabel(relationship.volume_mode, t)}</TableCell>
                        <TableCell>{relationship.lot_multiplier}</TableCell>
                        <TableCell>{relationship.is_active ? t('localCopyTrading.active') : t('localCopyTrading.inactive')}</TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" aria-label={t('localCopyTrading.confirmDeleteTitle')} className="text-destructive" onClick={() => setPendingDeleteRelationshipId(relationship.id)}>
                            <Trash2 />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                       <TableCell colSpan={8} className="py-8 text-center text-sm text-muted-foreground">
                         {canCreateRelationship ? (
                           t('localCopyTrading.emptyRelationships')
                         ) : (
                           <div className="flex flex-col items-center gap-3">
                             <span>{t('localCopyTrading.emptyRelationshipsNeedsAccounts')}</span>
                             <Button variant="outline" size="sm" onClick={() => navigate('/account-list')}>
                               {t('localCopyTrading.manageAccounts')}
                             </Button>
                           </div>
                         )}
                       </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="events">
          <Card>
            <CardHeader>
              <CardTitle>{t('localCopyTrading.tabs.events')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('localCopyTrading.columns.symbol')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.status')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.source')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.follower')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.position')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.message')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.created')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                        <div className="flex items-center justify-center gap-2">
                          <Loader2 className="size-4 animate-spin" />
                          {t('common.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : overview.events.length > 0 ? (
                    [...overview.events].reverse().slice(0, 100).map((event) => (
                      <TableRow key={event.id}>
                        <TableCell>{event.symbol}</TableCell>
                        <TableCell>{getStatusBadge(event.status, t)}</TableCell>
                         <TableCell>{getAccountLabelById(overview.accounts, event.source_account_id)}</TableCell>
                         <TableCell>{getAccountLabelById(overview.accounts, event.follower_account_id)}</TableCell>
                        <TableCell>{event.position_id || '-'}</TableCell>
                        <TableCell>{event.message || '-'}</TableCell>
                        <TableCell>{formatDateTime(event.created_at)}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">{t('localCopyTrading.emptyEvents')}</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={relationshipDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeRelationshipDialog()
            return
          }
          setRelationshipDialogOpen(true)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.addRelationship')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.relationshipDescription')}</DialogDescription>
          </DialogHeader>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipSource')}</span>
            <Select value={selectedSourceId} onValueChange={handleSourceChange}>
              <SelectTrigger aria-label={t('localCopyTrading.relationshipSource')}>
                <SelectValue placeholder={t('localCopyTrading.relationshipSourcePlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {overview.accounts.filter((account) => account.id !== selectedFollowerId).map((account) => (
                    <SelectItem key={account.id} value={account.id}>{getAccountOptionLabel(account)}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipFollower')}</span>
            <Select value={selectedFollowerId} onValueChange={handleFollowerChange}>
              <SelectTrigger aria-label={t('localCopyTrading.relationshipFollower')}>
                <SelectValue placeholder={t('localCopyTrading.relationshipFollowerPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {overview.accounts.filter((account) => account.id !== selectedSourceId).map((account) => (
                    <SelectItem key={account.id} value={account.id}>{getAccountOptionLabel(account)}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipSourceSymbol')}</span>
            <Input aria-label={t('localCopyTrading.relationshipSourceSymbol')} value={relationshipSourceSymbol} onChange={(event) => setRelationshipSourceSymbol(event.target.value)} />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipFollowerSymbol')}</span>
            <Input aria-label={t('localCopyTrading.relationshipFollowerSymbol')} value={relationshipFollowerSymbol} onChange={(event) => setRelationshipFollowerSymbol(event.target.value)} />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.volumeMode')}</span>
            <Select value={relationshipVolumeMode} onValueChange={setRelationshipVolumeMode}>
              <SelectTrigger aria-label={t('localCopyTrading.volumeMode')}>
                <SelectValue placeholder={t('localCopyTrading.volumeMode')} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {Object.entries(VOLUME_MODE_LABEL_KEYS).map(([mode, key]) => (
                    <SelectItem key={mode} value={mode}>{t(key)}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{relationshipVolumeMode === 'fixed' ? t('localCopyTrading.fixedLots') : t('localCopyTrading.lotMultiplier')}</span>
            <Input type="number" min="0.01" step="0.01" aria-label={t('localCopyTrading.lotMultiplier')} value={relationshipLotMultiplier} onChange={(event) => setRelationshipLotMultiplier(event.target.value)} />
          </label>
          {relationshipVolumeMode === 'risk_percent' ? (
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.riskPercent')}</span>
              <Input type="number" min="0.01" step="0.01" aria-label={t('localCopyTrading.riskPercent')} value={relationshipRiskPercent} onChange={(event) => setRelationshipRiskPercent(event.target.value)} />
            </label>
          ) : null}
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.maxLot')}</span>
            <Input type="number" min="0" step="0.01" aria-label={t('localCopyTrading.maxLot')} value={relationshipMaxLot} onChange={(event) => setRelationshipMaxLot(event.target.value)} />
            <span className="text-xs text-muted-foreground">{t('localCopyTrading.maxLotHint')}</span>
          </label>
          <label className="flex items-center justify-between gap-2 text-sm">
            <span>{t('localCopyTrading.syncSlTp')}</span>
            <Switch aria-label={t('localCopyTrading.syncSlTp')} checked={relationshipSyncSlTp} onCheckedChange={setRelationshipSyncSlTp} />
          </label>
          <DialogFooter>
            <Button variant="outline" onClick={closeRelationshipDialog}>{t('priceAlerts.cancel')}</Button>
            <Button disabled={!isRelationshipFormComplete(selectedSourceId, selectedFollowerId, relationshipSourceSymbol, relationshipFollowerSymbol, relationshipLotMultiplier, relationshipVolumeMode, relationshipRiskPercent)} onClick={() => void handleCreateRelationship()}>{t('localCopyTrading.saveRelationship')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pendingRuntimeEnabled} onOpenChange={setPendingRuntimeEnabled}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.confirmEnableTitle')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.confirmEnableDescription')}</DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            {t('localCopyTrading.configurationModeDescription')}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingRuntimeEnabled(false)}>{t('priceAlerts.cancel')}</Button>
            <Button onClick={() => void handleConfirmEnableRuntime()}>{t('localCopyTrading.confirmEnable')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pendingRuntimeDisabled} onOpenChange={setPendingRuntimeDisabled}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.confirmDisableTitle')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.confirmDisableDescription', { count: totalOpenRecords })}</DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            {t('localCopyTrading.confirmDisableWarning')}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingRuntimeDisabled(false)}>{t('priceAlerts.cancel')}</Button>
            <Button variant="destructive" onClick={() => void handleConfirmDisableRuntime()}>{t('localCopyTrading.confirmDisable')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pendingDeleteRelationshipId !== null} onOpenChange={(open) => !open && !isDeleting && setPendingDeleteRelationshipId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.confirmDeleteTitle')}</DialogTitle>
            <DialogDescription>{deleteDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={isDeleting} onClick={() => setPendingDeleteRelationshipId(null)}>{t('priceAlerts.cancel')}</Button>
            <Button variant="destructive" disabled={isDeleting} onClick={() => void handleConfirmDelete()}>{t('localCopyTrading.delete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
