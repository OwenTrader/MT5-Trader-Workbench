import React, { useEffect } from 'react'
import { Pencil, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useI18n } from '@/i18n'
import { useAccountManagementStore } from '@/stores/account-management-store'

type AccountFormState = {
  name: string
  terminalPath: string
  login: string
  password: string
  server: string
}

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
      && form.server.trim(),
  )
}

function getAccountOptionLabel(account: { name: string; login: string; id: string }) {
  const name = account.name.trim() || account.id
  const login = account.login.trim()
  return login ? `${name} (${login})` : name
}

export function AccountListPage() {
  const {
    overview,
    error,
    fetchOverview,
    createAccount,
    updateAccount,
    deleteAccount,
  } = useAccountManagementStore()
  const { t } = useI18n()
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [form, setForm] = React.useState<AccountFormState>(EMPTY_ACCOUNT_FORM)
  const [submitError, setSubmitError] = React.useState<string | null>(null)
  const [editingAccountId, setEditingAccountId] = React.useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null)
  const [isDeleting, setIsDeleting] = React.useState(false)

  const hasAccounts = overview.accounts.length > 0

  const closeDialog = React.useCallback(() => {
    setDialogOpen(false)
    setForm(EMPTY_ACCOUNT_FORM)
    setSubmitError(null)
    setIsSubmitting(false)
    setEditingAccountId(null)
  }, [])

  useEffect(() => {
    void fetchOverview()
  }, [fetchOverview])

  const handleSaveAccount = async () => {
    setSubmitError(null)
    setIsSubmitting(true)
    const payload = {
      name: form.name.trim(),
      connection_type: 'mt5_terminal',
      terminal_path: form.terminalPath.trim(),
      login: form.login.trim(),
      server: form.server.trim(),
      password: form.password,
      is_active: true,
    }
    const success = editingAccountId
      ? await updateAccount(editingAccountId, payload)
      : await createAccount(payload)
    if (success) {
      closeDialog()
      return
    }
    setSubmitError(useAccountManagementStore.getState().error)
    setIsSubmitting(false)
  }

  const startEdit = (account: typeof overview.accounts[number]) => {
    setEditingAccountId(account.id)
    setForm({
      name: account.name,
      terminalPath: account.terminal_path,
      login: account.login,
      password: account.password,
      server: account.server,
    })
    setSubmitError(null)
    setDialogOpen(true)
  }

  const handleBrowseTerminalPath = async () => {
    if (!(window as any).electron?.ipcRenderer) {
      return
    }

    const path = await (window as any).electron.ipcRenderer.invoke('dialog:openFile', {
      filters: [{ name: 'MetaTrader 5 Terminal', extensions: ['exe'] }],
    })
    if (!path) {
      return
    }

    setForm((current) => ({ ...current, terminalPath: path }))
  }

  const handleConfirmDelete = async () => {
    if (!pendingDeleteId) {
      return
    }

    setIsDeleting(true)
    const success = await deleteAccount(pendingDeleteId)
    if (success) {
      setPendingDeleteId(null)
    }
    setIsDeleting(false)
  }

  const pendingDeleteLabel = overview.accounts.find((account) => account.id === pendingDeleteId)
  const deleteDescription = pendingDeleteLabel
    ? t('accountList.confirmDelete', { name: getAccountOptionLabel(pendingDeleteLabel) })
    : ''

  return (
    <div className="grid gap-6 xl:grid-cols-[22rem_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>{t('accountList.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('accountList.description')}</p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <Badge variant="outline">{t('accountList.accountCount', { count: overview.accounts.length })}</Badge>
            <Button onClick={() => setDialogOpen(true)}>{t('accountList.addAccount')}</Button>
            <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
              {t('accountList.assignmentHint')}
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('accountList.accounts')}</CardTitle>
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
              {overview.accounts.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>{account.name}</TableCell>
                  <TableCell>{account.connection_type}</TableCell>
                  <TableCell>{account.login || '-'}</TableCell>
                  <TableCell>{account.server || '-'}</TableCell>
                  <TableCell className="max-w-[22rem] truncate">{account.terminal_path || '-'}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" aria-label={t('accountList.editAccount')} onClick={() => startEdit(account)}>
                      <Pencil />
                    </Button>
                    <Button variant="ghost" size="icon" aria-label={t('localCopyTrading.confirmDeleteTitle')} className="text-destructive" onClick={() => setPendingDeleteId(account.id)}>
                      <Trash2 />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!hasAccounts ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">{t('accountList.emptyAccounts')}</TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeDialog()
            return
          }
          setDialogOpen(true)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingAccountId ? t('accountList.editAccount') : t('accountList.addAccount')}</DialogTitle>
            <DialogDescription>{t('accountList.accountDescription')}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('accountList.accountName')}</span>
              <Input aria-label={t('accountList.accountName')} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.terminalPath')}</span>
              <div className="flex gap-2">
                <Input
                  aria-label={t('localCopyTrading.terminalPath')}
                  placeholder={t('localCopyTrading.terminalPathPlaceholder')}
                  value={form.terminalPath}
                  onChange={(event) => setForm((current) => ({ ...current, terminalPath: event.target.value }))}
                />
                <Button type="button" variant="outline" onClick={() => void handleBrowseTerminalPath()}>{t('localCopyTrading.browse')}</Button>
              </div>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.login')}</span>
              <Input aria-label={t('localCopyTrading.login')} value={form.login} onChange={(event) => setForm((current) => ({ ...current, login: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.password')}</span>
              <Input type="password" aria-label={t('localCopyTrading.password')} value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span>{t('localCopyTrading.server')}</span>
              <Input aria-label={t('localCopyTrading.server')} value={form.server} onChange={(event) => setForm((current) => ({ ...current, server: event.target.value }))} />
            </label>
            {submitError ? <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs font-medium text-destructive">{submitError}</div> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={isSubmitting} onClick={closeDialog}>{t('priceAlerts.cancel')}</Button>
            <Button disabled={isSubmitting || !isAccountFormComplete(form)} onClick={() => void handleSaveAccount()}>{isSubmitting ? t('accountList.savingAccount') : editingAccountId ? t('accountList.updateAccount') : t('accountList.saveAccount')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={pendingDeleteId !== null} onOpenChange={(open) => !open && !isDeleting && setPendingDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('localCopyTrading.confirmDeleteTitle')}</DialogTitle>
            <DialogDescription>{deleteDescription}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={isDeleting} onClick={() => setPendingDeleteId(null)}>{t('priceAlerts.cancel')}</Button>
            <Button variant="destructive" disabled={isDeleting} onClick={() => void handleConfirmDelete()}>{t('localCopyTrading.delete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
