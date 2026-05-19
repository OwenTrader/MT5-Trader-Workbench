import React, { useEffect } from 'react'
import { Trash2 } from 'lucide-react'

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

type AccountFormState = {
  name: string
  terminalPath: string
  login: string
  password: string
  server: string
}

type DeleteTarget =
  | { type: 'source'; id: string }
  | { type: 'follower'; id: string }
  | { type: 'relationship'; id: string }

type AccountRole = 'source' | 'follower'

const EMPTY_ACCOUNT_FORM: AccountFormState = {
  name: '',
  terminalPath: '',
  login: '',
  password: '',
  server: '',
}

function isAccountFormComplete(form: AccountFormState) {
  return Boolean(
    form.name.trim()
      && form.terminalPath.trim()
      && form.login.trim()
      && form.password
      && form.server.trim()
  )
}

function isRelationshipFormComplete(sourceId: string, followerId: string, symbol: string, lotMultiplier: string) {
  return Boolean(sourceId.trim() && followerId.trim() && symbol.trim() && Number(lotMultiplier) > 0)
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

export function LocalCopyTradingPage() {
  const {
    overview,
    error,
    fetchOverview,
    updateRuntime,
    createSourceAccount,
    createFollowerAccount,
    createRelationship,
    deleteSourceAccount,
    deleteFollowerAccount,
    deleteRelationship,
  } = useLocalCopyTradingStore()
  const { t } = useI18n()
  const [sourceDialogOpen, setSourceDialogOpen] = React.useState(false)
  const [followerDialogOpen, setFollowerDialogOpen] = React.useState(false)
  const [relationshipDialogOpen, setRelationshipDialogOpen] = React.useState(false)
  const [sourceForm, setSourceForm] = React.useState<AccountFormState>(EMPTY_ACCOUNT_FORM)
  const [followerForm, setFollowerForm] = React.useState<AccountFormState>(EMPTY_ACCOUNT_FORM)
  const [sourceSubmitError, setSourceSubmitError] = React.useState<string | null>(null)
  const [followerSubmitError, setFollowerSubmitError] = React.useState<string | null>(null)
  const [isSubmittingSource, setIsSubmittingSource] = React.useState(false)
  const [isSubmittingFollower, setIsSubmittingFollower] = React.useState(false)
  const [pendingDelete, setPendingDelete] = React.useState<DeleteTarget | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)
  const [pendingRuntimeEnabled, setPendingRuntimeEnabled] = React.useState(false)
  const [runtimeSubmitError, setRuntimeSubmitError] = React.useState<string | null>(null)
  const [relationshipSymbol, setRelationshipSymbol] = React.useState('XAUUSD')
  const [relationshipLotMultiplier, setRelationshipLotMultiplier] = React.useState('1')
  const [selectedSourceId, setSelectedSourceId] = React.useState('')
  const [selectedFollowerId, setSelectedFollowerId] = React.useState('')

  const hasSourceAccounts = overview.source_accounts.length > 0
  const hasFollowerAccounts = overview.follower_accounts.length > 0
  const hasRelationships = overview.relationships.length > 0
  const canCreateRelationship = hasSourceAccounts && hasFollowerAccounts
  const canEnableRuntime = hasSourceAccounts && hasFollowerAccounts && hasRelationships

  const closeSourceDialog = React.useCallback(() => {
    setSourceDialogOpen(false)
    setSourceForm(EMPTY_ACCOUNT_FORM)
    setSourceSubmitError(null)
    setIsSubmittingSource(false)
  }, [])

  const closeFollowerDialog = React.useCallback(() => {
    setFollowerDialogOpen(false)
    setFollowerForm(EMPTY_ACCOUNT_FORM)
    setFollowerSubmitError(null)
    setIsSubmittingFollower(false)
  }, [])

  useEffect(() => {
    void fetchOverview()
  }, [fetchOverview])

  const handleCreateSource = async () => {
    setSourceSubmitError(null)
    setIsSubmittingSource(true)
    const success = await createSourceAccount({
      name: sourceForm.name.trim(),
      connection_type: 'mt5_terminal',
      terminal_path: sourceForm.terminalPath.trim(),
      login: sourceForm.login.trim(),
      server: sourceForm.server.trim(),
      password: sourceForm.password,
      is_active: true,
    })
    if (success) {
      closeSourceDialog()
      return
    }
    setSourceSubmitError(useLocalCopyTradingStore.getState().error)
    setIsSubmittingSource(false)
  }

  const handleCreateFollower = async () => {
    setFollowerSubmitError(null)
    setIsSubmittingFollower(true)
    const success = await createFollowerAccount({
      name: followerForm.name.trim(),
      connection_type: 'mt5_terminal',
      terminal_path: followerForm.terminalPath.trim(),
      login: followerForm.login.trim(),
      server: followerForm.server.trim(),
      password: followerForm.password,
      is_active: true,
    })
    if (success) {
      closeFollowerDialog()
      return
    }
    setFollowerSubmitError(useLocalCopyTradingStore.getState().error)
    setIsSubmittingFollower(false)
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
      symbol: relationshipSymbol,
      lot_multiplier: Number(relationshipLotMultiplier),
      is_active: true,
    })
    if (success) {
      setRelationshipDialogOpen(false)
      setRelationshipSymbol('XAUUSD')
      setRelationshipLotMultiplier('1')
      setSelectedSourceId('')
      setSelectedFollowerId('')
    }
  }

  const handleRuntimeToggle = (checked: boolean) => {
    setRuntimeSubmitError(null)
    if (!checked) {
      void updateRuntime({ enabled: false })
      return
    }

    if (!canEnableRuntime) {
      setRuntimeSubmitError(t('localCopyTrading.enableRequirements'))
      return
    }

    setPendingRuntimeEnabled(true)
  }

  const handleConfirmEnableRuntime = async () => {
    const success = await updateRuntime({ enabled: true })
    if (!success) {
      setRuntimeSubmitError(useLocalCopyTradingStore.getState().error)
    }
    setPendingRuntimeEnabled(false)
  }

  const handleBrowseTerminalPath = async (role: AccountRole) => {
    if (!(window as any).electron?.ipcRenderer) {
      return
    }

    const path = await (window as any).electron.ipcRenderer.invoke('dialog:openFile', {
      filters: [{ name: 'MetaTrader 5 Terminal', extensions: ['exe'] }],
    })
    if (!path) {
      return
    }

    if (role === 'source') {
      setSourceForm((current) => ({ ...current, terminalPath: path }))
      return
    }

    setFollowerForm((current) => ({ ...current, terminalPath: path }))
  }

  const handleConfirmDelete = async () => {
    if (!pendingDelete) {
      return
    }

    setIsDeleting(true)

    if (pendingDelete.type === 'source') {
      await deleteSourceAccount(pendingDelete.id)
    } else if (pendingDelete.type === 'follower') {
      await deleteFollowerAccount(pendingDelete.id)
    } else {
      await deleteRelationship(pendingDelete.id)
    }

    setPendingDelete(null)
    setIsDeleting(false)
  }

  const pendingDeleteLabel = pendingDelete?.type === 'source'
    ? getAccountLabelById(overview.source_accounts, pendingDelete.id)
    : pendingDelete?.type === 'follower'
      ? getAccountLabelById(overview.follower_accounts, pendingDelete.id)
      : pendingDelete?.id ?? ''

  const deleteDescription = pendingDelete?.type === 'source'
    ? t('localCopyTrading.confirmDeleteSource', { name: pendingDeleteLabel })
    : pendingDelete?.type === 'follower'
      ? t('localCopyTrading.confirmDeleteFollower', { name: pendingDeleteLabel })
      : t('localCopyTrading.confirmDeleteRelationship', { name: pendingDeleteLabel })

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
            <label className="flex items-center gap-2 text-sm">
              <span>{t('localCopyTrading.enabled')}</span>
              <Switch checked={overview.runtime.enabled} onCheckedChange={handleRuntimeToggle} />
            </label>
            <Button variant="outline" size="sm" onClick={() => setSourceDialogOpen(true)}>{t('localCopyTrading.addSource')}</Button>
            <Button variant="outline" size="sm" onClick={() => setFollowerDialogOpen(true)}>{t('localCopyTrading.addFollower')}</Button>
            <Button variant="outline" size="sm" disabled={!canCreateRelationship} onClick={() => setRelationshipDialogOpen(true)}>{t('localCopyTrading.addRelationship')}</Button>
          </div>
          <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            {t('localCopyTrading.configurationModeDescription')}
          </div>
          {runtimeSubmitError ? <p className="mt-3 text-sm text-destructive">{runtimeSubmitError}</p> : null}
          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>

      <Tabs defaultValue="sources">
        <TabsList>
          <TabsTrigger value="sources">{t('localCopyTrading.tabs.sources')}</TabsTrigger>
          <TabsTrigger value="followers">{t('localCopyTrading.tabs.followers')}</TabsTrigger>
          <TabsTrigger value="relationships">{t('localCopyTrading.tabs.relationships')}</TabsTrigger>
          <TabsTrigger value="events">{t('localCopyTrading.tabs.events')}</TabsTrigger>
        </TabsList>

        <TabsContent value="sources">
          <Card>
            <CardHeader>
              <CardTitle>{t('localCopyTrading.tabs.sources')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('localCopyTrading.columns.name')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.connection')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.login')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.server')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.terminalPath')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {overview.source_accounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell>{account.name}</TableCell>
                      <TableCell>{account.connection_type}</TableCell>
                      <TableCell>{account.login || '-'}</TableCell>
                      <TableCell>{account.server || '-'}</TableCell>
                      <TableCell className="max-w-[22rem] truncate">{account.terminal_path || '-'}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="text-destructive" onClick={() => setPendingDelete({ type: 'source', id: account.id })}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!hasSourceAccounts ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">{t('localCopyTrading.emptySources')}</TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="followers">
          <Card>
            <CardHeader>
              <CardTitle>{t('localCopyTrading.tabs.followers')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('localCopyTrading.columns.name')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.connection')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.login')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.server')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.terminalPath')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {overview.follower_accounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell>{account.name}</TableCell>
                      <TableCell>{account.connection_type}</TableCell>
                      <TableCell>{account.login || '-'}</TableCell>
                      <TableCell>{account.server || '-'}</TableCell>
                      <TableCell className="max-w-[22rem] truncate">{account.terminal_path || '-'}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="text-destructive" onClick={() => setPendingDelete({ type: 'follower', id: account.id })}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!hasFollowerAccounts ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">{t('localCopyTrading.emptyFollowers')}</TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

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
                    <TableHead>{t('localCopyTrading.columns.symbol')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.lotMultiplier')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.status')}</TableHead>
                    <TableHead>{t('localCopyTrading.columns.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {overview.relationships.map((relationship) => (
                    <TableRow key={relationship.id}>
                      <TableCell>{getAccountLabelById(overview.source_accounts, relationship.source_account_id)}</TableCell>
                      <TableCell>{getAccountLabelById(overview.follower_accounts, relationship.follower_account_id)}</TableCell>
                      <TableCell>{relationship.symbol}</TableCell>
                      <TableCell>{relationship.lot_multiplier}</TableCell>
                      <TableCell>{relationship.is_active ? t('localCopyTrading.active') : t('localCopyTrading.inactive')}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="text-destructive" onClick={() => setPendingDelete({ type: 'relationship', id: relationship.id })}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!hasRelationships ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">{canCreateRelationship ? t('localCopyTrading.emptyRelationships') : t('localCopyTrading.emptyRelationshipsNeedsAccounts')}</TableCell>
                    </TableRow>
                  ) : null}
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
                  {overview.events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell>{event.symbol}</TableCell>
                      <TableCell>{event.status}</TableCell>
                      <TableCell>{getAccountLabelById(overview.source_accounts, event.source_account_id)}</TableCell>
                      <TableCell>{getAccountLabelById(overview.follower_accounts, event.follower_account_id)}</TableCell>
                      <TableCell>{event.position_id || '-'}</TableCell>
                      <TableCell>{event.message || '-'}</TableCell>
                      <TableCell>{formatDateTime(event.created_at)}</TableCell>
                    </TableRow>
                  ))}
                  {overview.events.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">{t('localCopyTrading.emptyEvents')}</TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={sourceDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeSourceDialog()
            return
          }
          setSourceDialogOpen(true)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.addSource')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.sourceDescription')}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.sourceName')}</span>
              <Input aria-label={t('localCopyTrading.sourceName')} value={sourceForm.name} onChange={(event) => setSourceForm((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.terminalPath')}</span>
              <div className="flex gap-2">
                <Input
                  aria-label={t('localCopyTrading.terminalPath')}
                  placeholder={t('localCopyTrading.terminalPathPlaceholder')}
                  value={sourceForm.terminalPath}
                  onChange={(event) => setSourceForm((current) => ({ ...current, terminalPath: event.target.value }))}
                />
                <Button type="button" variant="outline" onClick={() => void handleBrowseTerminalPath('source')}>{t('localCopyTrading.browse')}</Button>
              </div>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.login')}</span>
              <Input aria-label={t('localCopyTrading.login')} value={sourceForm.login} onChange={(event) => setSourceForm((current) => ({ ...current, login: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.password')}</span>
              <Input type="password" aria-label={t('localCopyTrading.password')} value={sourceForm.password} onChange={(event) => setSourceForm((current) => ({ ...current, password: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.server')}</span>
              <Input aria-label={t('localCopyTrading.server')} value={sourceForm.server} onChange={(event) => setSourceForm((current) => ({ ...current, server: event.target.value }))} />
            </label>
            {sourceSubmitError ? <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs font-medium text-destructive">{sourceSubmitError}</div> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={isSubmittingSource} onClick={closeSourceDialog}>{t('priceAlerts.cancel')}</Button>
            <Button disabled={isSubmittingSource || !isAccountFormComplete(sourceForm)} onClick={() => void handleCreateSource()}>{isSubmittingSource ? t('localCopyTrading.savingSource') : t('localCopyTrading.saveSource')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={followerDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeFollowerDialog()
            return
          }
          setFollowerDialogOpen(true)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.addFollower')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.followerDescription')}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.followerName')}</span>
              <Input aria-label={t('localCopyTrading.followerName')} value={followerForm.name} onChange={(event) => setFollowerForm((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.terminalPath')}</span>
              <div className="flex gap-2">
                <Input
                  aria-label={t('localCopyTrading.terminalPath')}
                  placeholder={t('localCopyTrading.terminalPathPlaceholder')}
                  value={followerForm.terminalPath}
                  onChange={(event) => setFollowerForm((current) => ({ ...current, terminalPath: event.target.value }))}
                />
                <Button type="button" variant="outline" onClick={() => void handleBrowseTerminalPath('follower')}>{t('localCopyTrading.browse')}</Button>
              </div>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.login')}</span>
              <Input aria-label={t('localCopyTrading.login')} value={followerForm.login} onChange={(event) => setFollowerForm((current) => ({ ...current, login: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.password')}</span>
              <Input type="password" aria-label={t('localCopyTrading.password')} value={followerForm.password} onChange={(event) => setFollowerForm((current) => ({ ...current, password: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.server')}</span>
              <Input aria-label={t('localCopyTrading.server')} value={followerForm.server} onChange={(event) => setFollowerForm((current) => ({ ...current, server: event.target.value }))} />
            </label>
            {followerSubmitError ? <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs font-medium text-destructive">{followerSubmitError}</div> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={isSubmittingFollower} onClick={closeFollowerDialog}>{t('priceAlerts.cancel')}</Button>
            <Button disabled={isSubmittingFollower || !isAccountFormComplete(followerForm)} onClick={() => void handleCreateFollower()}>{isSubmittingFollower ? t('localCopyTrading.savingFollower') : t('localCopyTrading.saveFollower')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={relationshipDialogOpen} onOpenChange={setRelationshipDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.addRelationship')}</DialogTitle>
            <DialogDescription>{t('localCopyTrading.relationshipDescription')}</DialogDescription>
          </DialogHeader>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipSource')}</span>
            <Select value={selectedSourceId} onValueChange={setSelectedSourceId}>
              <SelectTrigger aria-label={t('localCopyTrading.relationshipSource')}>
                <SelectValue placeholder={t('localCopyTrading.relationshipSourcePlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {overview.source_accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>{getAccountOptionLabel(account)}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipFollower')}</span>
            <Select value={selectedFollowerId} onValueChange={setSelectedFollowerId}>
              <SelectTrigger aria-label={t('localCopyTrading.relationshipFollower')}>
                <SelectValue placeholder={t('localCopyTrading.relationshipFollowerPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {overview.follower_accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id}>{getAccountOptionLabel(account)}</SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.relationshipSymbol')}</span>
            <Input aria-label={t('localCopyTrading.relationshipSymbol')} value={relationshipSymbol} onChange={(event) => setRelationshipSymbol(event.target.value)} />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span>{t('localCopyTrading.lotMultiplier')}</span>
            <Input type="number" min="0.01" step="0.01" aria-label={t('localCopyTrading.lotMultiplier')} value={relationshipLotMultiplier} onChange={(event) => setRelationshipLotMultiplier(event.target.value)} />
          </label>
          <DialogFooter>
            <Button disabled={!isRelationshipFormComplete(selectedSourceId, selectedFollowerId, relationshipSymbol, relationshipLotMultiplier)} onClick={() => void handleCreateRelationship()}>{t('localCopyTrading.saveRelationship')}</Button>
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

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && !isDeleting && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.confirmDeleteTitle')}</DialogTitle>
            <DialogDescription>{deleteDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={isDeleting} onClick={() => setPendingDelete(null)}>{t('priceAlerts.cancel')}</Button>
            <Button variant="destructive" disabled={isDeleting} onClick={() => void handleConfirmDelete()}>{t('localCopyTrading.delete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
