import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { useAlertsStore, OrderBroadcastRule } from '@/stores/alerts-store'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RefreshCw, Megaphone, Edit3, Trash2, Play, Pause } from 'lucide-react'
import { cn, debounce } from '@/lib/utils'

const DEFAULT_SYMBOL = 'XAUUSD'

function normalizeSymbol(value: string) {
  return value.trim().toUpperCase()
}

export const OrderBroadcastPage: React.FC = () => {
  const { t } = useI18n()
  const {
    orderBroadcastRules,
    fetchOrderBroadcastRules,
    addOrderBroadcastRule,
    updateOrderBroadcastRule,
    deleteOrderBroadcastRule,
    isLoading,
  } = useAlertsStore()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({ symbol: DEFAULT_SYMBOL })

  useEffect(() => {
    fetchOrderBroadcastRules()

    const timer = setInterval(() => {
      fetchOrderBroadcastRules({ silent: true })
    }, 2000)
    return () => clearInterval(timer)
  }, [])

  const handleSubmit = async () => {
    setError(null)
    const symbol = normalizeSymbol(formData.symbol)
    if (!symbol) {
      setError(t('orderBroadcast.symbolRequired'))
      return
    }

    const duplicateRule = orderBroadcastRules.find((rule) => normalizeSymbol(rule.symbol) === symbol && rule.id !== editingId)
    if (duplicateRule) {
      setError(t('orderBroadcast.duplicateSymbol', { symbol }))
      return
    }

    const original = editingId ? orderBroadcastRules.find((rule) => rule.id === editingId) : null
    if (editingId && !original) {
      setError(t('orderBroadcast.saveFailed'))
      return
    }

    const mutationResult = editingId && original
      ? await updateOrderBroadcastRule({ ...original, symbol })
      : await addOrderBroadcastRule({ symbol, is_active: true })

    if (!mutationResult.ok) {
      setError(mutationResult.code === 'duplicate_symbol'
        ? t('orderBroadcast.duplicateSymbol', { symbol })
        : t('orderBroadcast.saveFailed'))
      return
    }

    setEditingId(null)
    setFormData({ symbol: DEFAULT_SYMBOL })
  }

  const startEdit = (rule: OrderBroadcastRule) => {
    setError(null)
    setEditingId(rule.id)
    setFormData({ symbol: rule.symbol })
  }

  const toggleStatus = async (rule: OrderBroadcastRule, active: boolean) => {
    await updateOrderBroadcastRule({ ...rule, is_active: active })
  }

  const debouncedRefresh = React.useMemo(
    () => debounce(() => {
      void fetchOrderBroadcastRules()
    }, 400),
    [fetchOrderBroadcastRules]
  )

  useEffect(() => {
    return () => {
      debouncedRefresh.cancel()
    }
  }, [debouncedRefresh])

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <PageHeader
        title={t('orderBroadcast.title')}
        icon={Megaphone}
        actions={(
          <Button variant="outline" size="sm" onClick={debouncedRefresh} disabled={isLoading}>
            <RefreshCw className={cn('w-4 h-4 mr-2', isLoading && 'animate-spin')} />
            {t('orderBroadcast.refresh')}
          </Button>
        )}
      />

      <Card className="border-amber-500/30 bg-amber-500/10">
        <CardContent className="p-4 text-sm text-amber-700 dark:text-amber-200">
          {t('orderBroadcast.boundaryNotice')}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {editingId ? t('orderBroadcast.editTitle') : t('orderBroadcast.createTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="order-broadcast-symbol">{t('orderBroadcast.symbol')}</Label>
                <Input
                  id="order-broadcast-symbol"
                  value={formData.symbol}
                  onChange={(e) => {
                    setError(null)
                    setFormData({ symbol: e.target.value })
                  }}
                  className="uppercase"
                  placeholder={t('orderBroadcast.symbolPlaceholder')}
                />
              </div>

              {error ? (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs font-medium text-destructive">
                  {error}
                </div>
              ) : null}

              <div className="pt-2 flex gap-2">
                <Button onClick={handleSubmit} className="flex-1">
                  {editingId ? t('orderBroadcast.update') : t('orderBroadcast.create')}
                </Button>
                {editingId ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setError(null)
                      setEditingId(null)
                      setFormData({ symbol: DEFAULT_SYMBOL })
                    }}
                  >
                    {t('orderBroadcast.cancel')}
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">{t('orderBroadcast.listTitle')}</CardTitle>
              <div className="text-xs text-muted-foreground">{t('orderBroadcast.count', { count: orderBroadcastRules.length })}</div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-0 pb-4">
              <div className="space-y-3">
                {orderBroadcastRules.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                    {t('orderBroadcast.empty')}
                  </div>
                ) : (
                  orderBroadcastRules.map((rule) => (
                    <div
                      key={rule.id}
                      className={cn(
                        'flex items-center justify-between p-4 rounded-xl border transition-all',
                        rule.is_active ? 'bg-card border-border' : 'opacity-60 bg-card border-border'
                      )}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{rule.symbol}</span>
                          {!rule.is_active ? (
                            <span className="bg-muted text-muted-foreground text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {t('orderBroadcast.paused')}
                            </span>
                          ) : null}
                        </div>
                        <div className="text-sm text-muted-foreground font-medium">
                          {t('orderBroadcast.listDescription')}
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn(
                            'w-9 h-9 rounded-full transition-all',
                            rule.is_active ? 'bg-blue-600/10 text-blue-600 hover:bg-blue-600/20' : 'text-muted-foreground/40 hover:text-muted-foreground'
                          )}
                          onClick={() => toggleStatus(rule, true)}
                          title={t('orderBroadcast.actionStart')}
                        >
                          <Play className={cn('w-4 h-4 fill-current', !rule.is_active && 'fill-none')} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className={cn(
                            'w-9 h-9 rounded-full transition-all',
                            !rule.is_active ? 'bg-gray-500 text-white hover:bg-gray-600 shadow-md' : 'text-muted-foreground/40 hover:text-muted-foreground'
                          )}
                          onClick={() => toggleStatus(rule, false)}
                          title={t('orderBroadcast.actionPause')}
                        >
                          <Pause className={cn('w-4 h-4 fill-current', rule.is_active && 'fill-none')} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-9 h-9 rounded-full text-blue-500 hover:text-blue-600 hover:bg-blue-50"
                          onClick={() => startEdit(rule)}
                          title={t('orderBroadcast.actionEdit')}
                        >
                          <Edit3 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-9 h-9 rounded-full text-destructive hover:bg-destructive/10"
                          onClick={() => deleteOrderBroadcastRule(rule.id)}
                          title={t('orderBroadcast.actionDelete')}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
