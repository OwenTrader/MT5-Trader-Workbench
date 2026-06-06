import React, { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/page-header'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { useI18n } from '@/i18n'
import { cn, debounce } from '@/lib/utils'
import { OrderSymbolMapping, TopStepAccountCredential, useOrderSyncStore } from '@/stores/order-sync-store'
import { Edit3, Link2, Pause, Play, RefreshCw, RotateCw, Trash2 } from 'lucide-react'

const DEFAULT_CREDENTIAL: Omit<TopStepAccountCredential, 'id' | 'is_active'> = {
  name: 'TopStep',
  user_name: '',
  api_key: '',
  account_id: 0,
  live: false,
}

const DEFAULT_MAPPING: Omit<OrderSymbolMapping, 'id' | 'is_active'> = {
  mt5_symbol: 'XAUUSD',
  topstep_contract_id: '',
  topstep_display_name: 'Gold',
  quantity_multiplier: 1,
  mt5_lots: 0.1,
  topstep_contracts: 1,
}

function maskSecret(value: string) {
  if (!value) return ''
  if (value.length <= 6) return '******'
  return `${value.slice(0, 3)}***${value.slice(-3)}`
}

export const OrderSyncPage: React.FC = () => {
  const { t } = useI18n()
  const { config, fetchConfig, saveConfig, runTick, isLoading, error } = useOrderSyncStore()
  const [credentialForm, setCredentialForm] = useState(DEFAULT_CREDENTIAL)
  const [mappingForm, setMappingForm] = useState(DEFAULT_MAPPING)
  const [editingCredentialId, setEditingCredentialId] = useState<string | null>(null)
  const [editingMappingId, setEditingMappingId] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [pendingEnableSync, setPendingEnableSync] = useState(false)

  useEffect(() => {
    fetchConfig()
    const timer = setInterval(() => fetchConfig({ silent: true }), 2000)
    return () => clearInterval(timer)
  }, [])

  const debouncedRefresh = React.useMemo(
    () => debounce(() => {
      void fetchConfig()
    }, 400),
    [fetchConfig]
  )

  useEffect(() => () => debouncedRefresh.cancel(), [debouncedRefresh])

  const persist = async (nextConfig: Partial<typeof config>) => {
    return saveConfig({
      enabled: nextConfig.enabled ?? config.enabled,
      poll_interval_seconds: nextConfig.poll_interval_seconds ?? config.poll_interval_seconds,
      block_high_frequency_orders: nextConfig.block_high_frequency_orders ?? config.block_high_frequency_orders,
      high_frequency_window_seconds: nextConfig.high_frequency_window_seconds ?? config.high_frequency_window_seconds,
      credentials: nextConfig.credentials ?? config.credentials,
      mappings: nextConfig.mappings ?? config.mappings,
    })
  }

  const submitCredential = async () => {
    setFormError(null)
    if (!credentialForm.user_name.trim() || !credentialForm.api_key.trim() || !credentialForm.account_id) {
      setFormError(t('orderSync.credentialRequired'))
      return
    }
    const credential: TopStepAccountCredential = {
      id: editingCredentialId ?? '',
      ...credentialForm,
      user_name: credentialForm.user_name.trim(),
      api_key: credentialForm.api_key.trim(),
      account_id: Number(credentialForm.account_id),
      is_active: true,
    }
    const credentials = editingCredentialId
      ? config.credentials.map((item) => item.id === editingCredentialId ? credential : item)
      : [...config.credentials, credential]
    if (await persist({ credentials })) {
      setEditingCredentialId(null)
      setCredentialForm(DEFAULT_CREDENTIAL)
    }
  }

  const submitMapping = async () => {
    setFormError(null)
    if (!mappingForm.mt5_symbol.trim() || !mappingForm.topstep_contract_id.trim()) {
      setFormError(t('orderSync.mappingRequired'))
      return
    }
    const mt5Symbol = mappingForm.mt5_symbol.trim().toUpperCase()
    const mapping: OrderSymbolMapping = {
      id: editingMappingId ?? '',
      ...mappingForm,
      mt5_symbol: mt5Symbol,
      topstep_contract_id: mappingForm.topstep_contract_id.trim(),
      topstep_display_name: mappingForm.topstep_display_name.trim(),
      quantity_multiplier: 1,
      mt5_lots: Number(mappingForm.mt5_lots) || 1,
      topstep_contracts: Math.max(1, Math.floor(Number(mappingForm.topstep_contracts) || 1)),
      is_active: true,
    }
    const mappings = editingMappingId
      ? config.mappings.map((item) => item.id === editingMappingId ? mapping : item)
      : [...config.mappings, mapping]
    if (await persist({ mappings })) {
      setEditingMappingId(null)
      setMappingForm(DEFAULT_MAPPING)
    }
  }

  const startEditCredential = (credential: TopStepAccountCredential) => {
    setEditingCredentialId(credential.id)
    setCredentialForm({
      name: credential.name,
      user_name: credential.user_name,
      api_key: credential.api_key,
      account_id: credential.account_id,
      live: credential.live,
    })
  }

  const startEditMapping = (mapping: OrderSymbolMapping) => {
    setEditingMappingId(mapping.id)
    setMappingForm({
      mt5_symbol: mapping.mt5_symbol,
      topstep_contract_id: mapping.topstep_contract_id,
      topstep_display_name: mapping.topstep_display_name,
      quantity_multiplier: mapping.quantity_multiplier,
      mt5_lots: mapping.mt5_lots,
      topstep_contracts: mapping.topstep_contracts,
    })
  }

  const handleRuntimeToggle = (enabled: boolean) => {
    if (!enabled) {
      void persist({ enabled: false })
      return
    }

    setPendingEnableSync(true)
  }

  const confirmEnableSync = async () => {
    const success = await persist({ enabled: true })
    if (success) {
      setPendingEnableSync(false)
    }
  }

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <PageHeader
        title={t('orderSync.title')}
        icon={Link2}
        actions={(
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => runTick()} disabled={isLoading}>
              <RotateCw className={cn('w-4 h-4 mr-2', isLoading && 'animate-spin')} />
              {t('orderSync.syncNow')}
            </Button>
            <Button variant="outline" size="sm" onClick={debouncedRefresh} disabled={isLoading}>
              <RefreshCw className={cn('w-4 h-4 mr-2', isLoading && 'animate-spin')} />
              {t('orderSync.refresh')}
            </Button>
          </div>
        )}
      />

      <Card className="border-amber-500/30 bg-amber-500/10">
        <CardContent className="p-4 text-sm text-amber-700 dark:text-amber-200">
          {t('orderSync.boundaryNotice')}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        <ScrollArea className="lg:col-span-1 min-h-0">
          <div className="space-y-4 pr-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t('orderSync.runtimeTitle')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label htmlFor="order-sync-enabled">{t('orderSync.enabled')}</Label>
                    <div className="text-xs text-muted-foreground">{t('orderSync.enabledHint')}</div>
                  </div>
                  <Switch id="order-sync-enabled" checked={config.enabled} onCheckedChange={handleRuntimeToggle} />
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <Label htmlFor="order-sync-block-high-frequency">{t('orderSync.blockHighFrequency')}</Label>
                    <div className="text-xs text-muted-foreground">{t('orderSync.blockHighFrequencyHint')}</div>
                  </div>
                  <Switch
                    id="order-sync-block-high-frequency"
                    checked={config.block_high_frequency_orders}
                    onCheckedChange={(block_high_frequency_orders) => persist({ block_high_frequency_orders })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="order-sync-poll">{t('orderSync.pollInterval')}</Label>
                  <Input
                    id="order-sync-poll"
                    type="number"
                    min="0.5"
                    step="0.5"
                    value={config.poll_interval_seconds}
                    onChange={(event) => persist({ poll_interval_seconds: Number(event.target.value) || 1 })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="order-sync-high-frequency-window">{t('orderSync.highFrequencyWindow')}</Label>
                  <Input
                    id="order-sync-high-frequency-window"
                    type="number"
                    min="1"
                    step="1"
                    value={config.high_frequency_window_seconds}
                    onChange={(event) => persist({ high_frequency_window_seconds: Number(event.target.value) || 5 })}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{editingCredentialId ? t('orderSync.editCredential') : t('orderSync.addCredential')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('orderSync.credentialName')}</Label>
                  <Input value={credentialForm.name} onChange={(event) => setCredentialForm({ ...credentialForm, name: event.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.userName')}</Label>
                  <Input value={credentialForm.user_name} onChange={(event) => setCredentialForm({ ...credentialForm, user_name: event.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.apiKey')}</Label>
                  <Input type="password" value={credentialForm.api_key} onChange={(event) => setCredentialForm({ ...credentialForm, api_key: event.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.accountId')}</Label>
                  <Input type="number" value={credentialForm.account_id} onChange={(event) => setCredentialForm({ ...credentialForm, account_id: Number(event.target.value) })} />
                </div>
                <Button className="w-full" onClick={submitCredential}>{editingCredentialId ? t('orderSync.update') : t('orderSync.create')}</Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{editingMappingId ? t('orderSync.editMapping') : t('orderSync.addMapping')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('orderSync.mt5Symbol')}</Label>
                  <Input className="uppercase" value={mappingForm.mt5_symbol} onChange={(event) => setMappingForm({ ...mappingForm, mt5_symbol: event.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.topstepContract')}</Label>
                  <Input value={mappingForm.topstep_contract_id} onChange={(event) => setMappingForm({ ...mappingForm, topstep_contract_id: event.target.value })} placeholder="CON.F.US.GC..." />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.topstepName')}</Label>
                  <Input value={mappingForm.topstep_display_name} onChange={(event) => setMappingForm({ ...mappingForm, topstep_display_name: event.target.value })} placeholder="Gold" />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.mt5Lots')}</Label>
                  <Input type="number" min="0.01" step="0.01" value={mappingForm.mt5_lots} onChange={(event) => setMappingForm({ ...mappingForm, mt5_lots: Number(event.target.value) })} />
                </div>
                <div className="space-y-2">
                  <Label>{t('orderSync.topstepContracts')}</Label>
                  <Input type="number" min="1" step="1" value={mappingForm.topstep_contracts} onChange={(event) => setMappingForm({ ...mappingForm, topstep_contracts: Number(event.target.value) })} />
                </div>
                {(formError || error) ? <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs font-medium text-destructive">{formError || error}</div> : null}
                <Button className="w-full" onClick={submitMapping}>{editingMappingId ? t('orderSync.update') : t('orderSync.create')}</Button>
              </CardContent>
            </Card>
          </div>
        </ScrollArea>

        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">{t('orderSync.listTitle')}</CardTitle>
              <div className="text-xs text-muted-foreground">{t('orderSync.count', { count: config.synced_orders.length })}</div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-0 pb-4">
              <div className="space-y-4">
                <section className="space-y-3">
                  <h3 className="text-sm font-semibold">{t('orderSync.credentialsTitle')}</h3>
                  {config.credentials.map((credential) => (
                    <div key={credential.id} className="flex items-center justify-between rounded-xl border p-4">
                      <div>
                        <div className="font-bold">{credential.name || credential.user_name}</div>
                        <div className="text-sm text-muted-foreground">{credential.user_name} / #{credential.account_id} / {maskSecret(credential.api_key)}</div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => persist({ credentials: config.credentials.map((item) => item.id === credential.id ? { ...item, is_active: true } : item) })}><Play className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => persist({ credentials: config.credentials.map((item) => item.id === credential.id ? { ...item, is_active: false } : item) })}><Pause className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => startEditCredential(credential)}><Edit3 className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" className="text-destructive" onClick={() => persist({ credentials: config.credentials.filter((item) => item.id !== credential.id) })}><Trash2 className="w-4 h-4" /></Button>
                      </div>
                    </div>
                  ))}
                </section>

                <section className="space-y-3">
                  <h3 className="text-sm font-semibold">{t('orderSync.mappingsTitle')}</h3>
                  {config.mappings.map((mapping) => (
                    <div key={mapping.id} className="flex items-center justify-between rounded-xl border p-4">
                      <div>
                        <div className="flex items-center gap-2"><span className="font-bold">{mapping.mt5_symbol}</span><span className="text-muted-foreground">→</span><span className="font-bold">{mapping.topstep_display_name || mapping.topstep_contract_id}</span></div>
                        <div className="text-sm text-muted-foreground">{mapping.topstep_contract_id}</div>
                        <div className="text-sm text-muted-foreground">{t('orderSync.mappingRatioHint')}: {mapping.mt5_lots} → {mapping.topstep_contracts}</div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => persist({ mappings: config.mappings.map((item) => item.id === mapping.id ? { ...item, is_active: true } : item) })}><Play className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => persist({ mappings: config.mappings.map((item) => item.id === mapping.id ? { ...item, is_active: false } : item) })}><Pause className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => startEditMapping(mapping)}><Edit3 className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" className="text-destructive" onClick={() => persist({ mappings: config.mappings.filter((item) => item.id !== mapping.id) })}><Trash2 className="w-4 h-4" /></Button>
                      </div>
                    </div>
                  ))}
                </section>

                <section className="space-y-3">
                  <h3 className="text-sm font-semibold">{t('orderSync.syncedTitle')}</h3>
                  {config.synced_orders.length === 0 ? <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed rounded-lg">{t('orderSync.empty')}</div> : null}
                  {config.synced_orders.map((order) => (
                    <div key={`${order.mt5_ticket}-${order.opened_at}`} className="flex items-center justify-between rounded-xl border p-4">
                      <div>
                        <div className="flex items-center gap-2"><span className="font-bold">#{order.mt5_ticket}</span><Badge variant="secondary">{order.side}</Badge><Badge variant={order.status === 'blocked' ? 'outline' : 'default'}>{order.status === 'blocked' ? t('orderSync.blocked') : order.status}</Badge></div>
                        <div className="text-sm text-muted-foreground">{order.mt5_symbol} → {order.topstep_contract_id} / {t('orderSync.size', { size: order.size })}</div>
                        {order.blocked_reason ? <div className="text-xs text-muted-foreground">{order.blocked_reason}</div> : null}
                        {order.last_error ? <div className="text-xs text-destructive">{order.last_error}</div> : null}
                      </div>
                      <div className="text-xs text-muted-foreground">{order.status === 'blocked' ? t('orderSync.blocked') : order.topstep_order_id ? `TopStep #${order.topstep_order_id}` : '-'}</div>
                    </div>
                  ))}
                </section>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={pendingEnableSync} onOpenChange={setPendingEnableSync}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('orderSync.confirmEnableTitle')}</DialogTitle>
            <DialogDescription>{t('orderSync.confirmEnableDescription')}</DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-200">
            {t('orderSync.boundaryNotice')}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingEnableSync(false)}>{t('priceAlerts.cancel')}</Button>
            <Button onClick={() => void confirmEnableSync()}>{t('orderSync.confirmEnable')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
