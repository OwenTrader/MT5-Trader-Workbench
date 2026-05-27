import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { useAlertsStore, PriceAlert } from '@/stores/alerts-store'
import { useSettingsStore } from '@/stores/settings-store'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Trash2, Play, Pause, Edit3, Plus, RefreshCw, Bell } from 'lucide-react'
import { cn, debounce } from '@/lib/utils'
import { useAlertTriggerEffects } from '@/hooks/use-alert-trigger-effects'

type PriceAlertFormData = Omit<PriceAlert, 'id' | 'is_active' | 'is_triggered' | 'price'> & { price: string }

type PriceAlertTemplate = {
  label: string
  description: string
  value: PriceAlertFormData
}

export const PriceAlertsPage: React.FC = () => {
  const { t } = useI18n()
  const { priceAlerts, fetchAlerts, addPriceAlert, updatePriceAlert, deletePriceAlert, isLoading } = useAlertsStore()
  const { settings, fetchSettings } = useSettingsStore()
  
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const emptyFormData: PriceAlertFormData = {
    symbol: 'XAUUSD',
    price: '',
    condition: 'above',
    comment: ''
  }

  const [formData, setFormData] = useState(emptyFormData)

  const templates: PriceAlertTemplate[] = [
    {
      label: t('priceAlerts.templates.breakoutUpLabel'),
      description: t('priceAlerts.templates.breakoutUpDescription'),
      value: {
        symbol: 'XAUUSD',
        price: '3335',
        condition: 'above',
        comment: t('priceAlerts.templates.adjustBeforeSave'),
      },
    },
    {
      label: t('priceAlerts.templates.breakoutDownLabel'),
      description: t('priceAlerts.templates.breakoutDownDescription'),
      value: {
        symbol: 'XAUUSD',
        price: '3320',
        condition: 'below',
        comment: t('priceAlerts.templates.adjustBeforeSave'),
      },
    },
    {
      label: t('priceAlerts.templates.retestLabel'),
      description: t('priceAlerts.templates.retestDescription'),
      value: {
        symbol: 'EURUSD',
        price: '1.0850',
        condition: 'above',
        comment: t('priceAlerts.templates.adjustBeforeSave'),
      },
    },
  ]

  const formatCommentSuffix = (comment: string) => {
    const trimmedComment = comment.trim()
    return trimmedComment ? `\n${t('priceAlerts.notePrefix')}: ${trimmedComment}` : ''
  }

  const getConditionText = (condition: 'above' | 'below', display: 'option' | 'badge') => {
    if (display === 'option') {
      return condition === 'above' ? t('priceAlerts.conditionAbove') : t('priceAlerts.conditionBelow')
    }

    return condition === 'above' ? t('priceAlerts.displayAbove') : t('priceAlerts.displayBelow')
  }

  useEffect(() => {
    fetchSettings()
    fetchAlerts()
    
    const interval = settings.api_refresh_interval || 2000
    const timer = setInterval(() => {
      fetchAlerts({ silent: true })
    }, interval)
    return () => clearInterval(timer)
  }, [settings.api_refresh_interval])

  useAlertTriggerEffects({
    alerts: priceAlerts,
    isSoundEnabled: settings.alert_sound_enabled,
    soundPath: settings.alert_sound_path,
    soundVolume: settings.alert_sound_volume,
    notificationTitle: t('priceAlerts.notificationTitle'),
    buildBody: (alert) => t('priceAlerts.notificationBody', {
      symbol: alert.symbol,
      condition: getConditionText(alert.condition, 'badge'),
      price: alert.price,
    }) + formatCommentSuffix(alert.comment),
  })

  const handleSubmit = async () => {
    setError(null)
    const upperSymbol = formData.symbol.trim().toUpperCase()
    const targetPrice = Number(formData.price)

    if (!upperSymbol) {
      setError(t('priceAlerts.symbolRequired'))
      return
    }

    if (!Number.isFinite(targetPrice) || targetPrice <= 0) {
      setError(t('priceAlerts.targetPriceRequired'))
      return
    }
    
    // 1. Validate with Backend
    try {
      const verifyRes = await fetch('http://127.0.0.1:8765/mt5/verify_alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          symbol: upperSymbol, 
          price: targetPrice,
          condition: formData.condition
        })
      })
      const verifyData = await verifyRes.json()
      
      if (verifyData.status === 'error') {
        setError(verifyData.message)
        return
      }
    } catch (e) {
      setError(t('priceAlerts.verifyUnavailable'))
      return
    }

    // 2. Proceed with submission
    const finalData = { ...formData, symbol: upperSymbol, price: targetPrice, comment: formData.comment.trim() }

    if (editingId) {
      const original = priceAlerts.find(a => a.id === editingId)
      if (original) {
        await updatePriceAlert({ 
          ...original, 
          ...finalData, 
          is_triggered: false // Reset trigger if price/condition changed
        })
      }
      setEditingId(null)
    } else {
      await addPriceAlert({ ...finalData, is_active: true })
    }
    // Reset form
    setFormData(emptyFormData)
  }

  const startEdit = (alert: PriceAlert) => {
    setEditingId(alert.id)
    setFormData({
      symbol: alert.symbol,
      price: String(alert.price),
      condition: alert.condition,
      comment: alert.comment
    })
  }

  const toggleStatus = async (alert: PriceAlert, active: boolean) => {
    await updatePriceAlert({ ...alert, is_active: active })
  }

  const resetTrigger = async (alert: PriceAlert) => {
    await updatePriceAlert({ ...alert, is_triggered: false, is_active: true })
  }

  const confirmDelete = (alert: PriceAlert) => {
    const message = t('priceAlerts.confirmDelete', {
      symbol: alert.symbol,
      price: alert.price,
    })

    if (!window.confirm(message)) {
      return
    }

    void deletePriceAlert(alert.id)
  }

  const handleTestNotification = async () => {
    try {
      await fetch('http://127.0.0.1:8765/notifications/test', {
        method: 'POST'
      })
    } catch (e) {
      console.error('Failed to send test notification:', e)
      setError(t('priceAlerts.testNotificationFailed'))
    }
  }

  const applyTemplate = (template: PriceAlertTemplate) => {
    setEditingId(null)
    setError(null)
    setFormData(template.value)
  }

  const debouncedRefresh = React.useMemo(
    () => debounce(() => {
      void fetchAlerts()
    }, 400),
    [fetchAlerts]
  )

  useEffect(() => {
    return () => {
      debouncedRefresh.cancel()
    }
  }, [debouncedRefresh])

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <PageHeader
        title={t('priceAlerts.title')}
        icon={Bell}
        actions={(
          <Button variant="outline" size="sm" onClick={debouncedRefresh} disabled={isLoading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            {t('priceAlerts.refresh')}
          </Button>
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        {/* 左侧：设置表单 */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {editingId ? t('priceAlerts.editTitle') : t('priceAlerts.createTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="price-alert-symbol">{t('priceAlerts.symbol')}</Label>
                <Input 
                  id="price-alert-symbol"
                  value={formData.symbol} 
                  onChange={(e) => setFormData({...formData, symbol: e.target.value})} 
                  className="uppercase"
                  placeholder={t('priceAlerts.symbolPlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="price-alert-target-price">{t('priceAlerts.targetPrice')}</Label>
                <Input 
                  id="price-alert-target-price"
                  type="number" 
                  step="0.00001" 
                  min="0"
                  value={formData.price} 
                  onChange={(e) => setFormData({...formData, price: e.target.value})}
                  placeholder={t('priceAlerts.targetPricePlaceholder')}
                />
                <p className="text-xs text-muted-foreground">
                  {t('priceAlerts.validationAssist')}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="price-alert-condition">{t('priceAlerts.triggerCondition')}</Label>
                <Select
                  value={formData.condition} 
                  onValueChange={(value: 'above' | 'below') => setFormData({ ...formData, condition: value })}
                >
                  <SelectTrigger id="price-alert-condition">
                    <SelectValue placeholder={t('priceAlerts.triggerCondition')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="above">{getConditionText('above', 'option')}</SelectItem>
                      <SelectItem value="below">{getConditionText('below', 'option')}</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="price-alert-comment">{t('priceAlerts.note')}</Label>
                <Input
                  id="price-alert-comment"
                  value={formData.comment}
                  onChange={(e) => setFormData({ ...formData, comment: e.target.value })}
                  placeholder={t('priceAlerts.notePlaceholder')}
                />
              </div>

              <div className="space-y-3 rounded-xl border border-dashed bg-muted/30 p-3">
                <div className="space-y-1">
                  <div className="text-sm font-medium">{t('priceAlerts.templatesTitle')}</div>
                  <p className="text-xs text-muted-foreground">{t('priceAlerts.templatesHint')}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {templates.map((template) => (
                    <Button
                      key={template.label}
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-auto flex-col items-start gap-1 border-border/70 px-3 py-2 text-left"
                      onClick={() => applyTemplate(template)}
                    >
                      <span className="text-xs font-semibold uppercase tracking-wide text-primary">{template.label}</span>
                      <span className="text-[11px] leading-tight text-muted-foreground">{template.description}</span>
                    </Button>
                  ))}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t('priceAlerts.templatesAdjustNotice')}
                </div>
              </div>

              {error && (
                <div role="alert" className="p-3 text-xs font-medium bg-destructive/10 text-destructive rounded-lg border border-destructive/20 animate-in fade-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              <div className="pt-2 flex flex-col gap-2">
                <div className="flex gap-2">
                  <Button onClick={handleSubmit} className="flex-1">
                    {editingId ? t('priceAlerts.update') : t('priceAlerts.create')}
                  </Button>
                  {editingId && (
                    <Button variant="outline" onClick={() => {
                      setEditingId(null)
                      setFormData(emptyFormData)
                    }}>
                      {t('priceAlerts.cancel')}
                    </Button>
                  )}
                </div>
                
                {!editingId && (
                  <Button 
                    variant="outline" 
                    className="w-full border-dashed" 
                    onClick={handleTestNotification}
                  >
                    <Bell className="w-4 h-4 mr-2" />
                    {t('priceAlerts.testNotification')}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 右侧：预警列表 */}
        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">{t('priceAlerts.listTitle')}</CardTitle>
              <div className="text-xs text-muted-foreground">{t('priceAlerts.count', { count: priceAlerts.length })}</div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-0 pb-4">
              <div className="space-y-3">
                {priceAlerts.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                    {t('priceAlerts.empty')}
                  </div>
                ) : (
                  priceAlerts.map((alert) => (
                    <div 
                      key={alert.id} 
                      className={cn(
                        "flex items-center justify-between p-4 rounded-xl border transition-all",
                        alert.is_triggered ? "bg-red-500/5 border-red-500/20" : "bg-card border-border",
                        !alert.is_active && "opacity-60"
                      )}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{alert.symbol}</span>
                          {alert.is_triggered && (
                            <span className="bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full font-bold animate-pulse">
                              {t('priceAlerts.triggered')}
                            </span>
                          )}
                          {!alert.is_active && !alert.is_triggered && (
                            <span className="bg-muted text-muted-foreground text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {t('priceAlerts.paused')}
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground font-medium">
                          {getConditionText(alert.condition, 'badge')}
                          <span className="ml-2 text-foreground font-mono text-base">{alert.price}</span>
                        </div>
                        {alert.comment.trim() && (
                          <div className="text-xs text-muted-foreground">
                            {t('priceAlerts.notePrefix')}: {alert.comment}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1">
                        {/* 播放按钮 (代表“活动”状态) */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className={cn(
                            "w-9 h-9 rounded-full transition-all",
                            alert.is_triggered 
                              ? "bg-red-600 text-white hover:bg-red-700 shadow-lg shadow-red-500/30" 
                              : alert.is_active 
                                ? "bg-blue-600/10 text-blue-600 hover:bg-blue-600/20" 
                                : "text-muted-foreground/40 hover:text-muted-foreground"
                          )}
                          onClick={() => alert.is_triggered ? resetTrigger(alert) : toggleStatus(alert, true)}
                          title={alert.is_triggered ? t('priceAlerts.actionResetPlay') : t('priceAlerts.actionStart')}
                        >
                          <Play className={cn("w-4 h-4 fill-current", !alert.is_active && !alert.is_triggered && "fill-none")} />
                        </Button>

                        {/* 暂停按钮 (代表“暂停”状态) */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className={cn(
                            "w-9 h-9 rounded-full transition-all",
                            (!alert.is_active && !alert.is_triggered) 
                              ? "bg-gray-500 text-white hover:bg-gray-600 shadow-md" 
                              : "text-muted-foreground/40 hover:text-muted-foreground"
                          )}
                          onClick={() => toggleStatus(alert, false)}
                          title={t('priceAlerts.actionPause')}
                        >
                          <Pause className={cn("w-4 h-4 fill-current", (alert.is_active || alert.is_triggered) && "fill-none")} />
                        </Button>

                        {/* 编辑按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-blue-500 hover:text-blue-600 hover:bg-blue-50"
                          onClick={() => startEdit(alert)}
                          title={t('priceAlerts.actionEdit')}
                        >
                          <Edit3 className="w-4 h-4" />
                        </Button>

                        {/* 删除按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-destructive hover:bg-destructive/10"
                          onClick={() => confirmDelete(alert)}
                          title={t('priceAlerts.actionDelete')}
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
