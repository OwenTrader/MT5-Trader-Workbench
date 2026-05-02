import React, { useState, useEffect, useRef } from 'react'
import { useI18n } from '@/i18n'
import { useAlertsStore, IndicatorAlert } from '@/stores/alerts-store'
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
import { RefreshCw, Play, Pause, Trash2, Edit3, Plus, LineChart } from 'lucide-react'
import { cn, debounce } from '@/lib/utils'

export const IndicatorAlertsPage: React.FC = () => {
  const { t } = useI18n()
  const { 
    indicatorAlerts, 
    fetchIndicatorAlerts, 
    addIndicatorAlert, 
    deleteIndicatorAlert, 
    updateIndicatorAlert, 
    isLoading 
  } = useAlertsStore()
  const { settings, fetchSettings } = useSettingsStore()
  const prevTriggeredRef = useRef<Set<string>>(new Set())
  
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<Omit<IndicatorAlert, 'id' | 'is_active' | 'is_triggered'>>({
    symbol: 'XAUUSD',
    timeframe: 'H1',
    indicator_type: 'RSI',
    period: 14,
    condition: 'below',
    threshold: 30,
    comment: ''
  })

  const getConditionText = (condition: 'above' | 'below', display: 'option' | 'badge') => {
    if (display === 'option') {
      return condition === 'above' ? t('indicatorAlerts.conditionAbove') : t('indicatorAlerts.conditionBelow')
    }

    return condition === 'above' ? t('indicatorAlerts.displayAbove') : t('indicatorAlerts.displayBelow')
  }

  useEffect(() => {
    fetchSettings()
    fetchIndicatorAlerts()
    
    const interval = settings.api_refresh_interval || 2000
    const timer = setInterval(() => {
      fetchIndicatorAlerts({ silent: true })
    }, interval)
    return () => clearInterval(timer)
  }, [settings.api_refresh_interval])

  // Play sound when alert triggers
  useEffect(() => {
    const newlyTriggered = indicatorAlerts.filter(a => a.is_triggered && !prevTriggeredRef.current.has(a.id))
    if (newlyTriggered.length > 0) {
      if (settings.alert_sound_enabled && settings.alert_sound_path) {
        const audio = new Audio(`local-file://${settings.alert_sound_path}`)
        audio.volume = settings.alert_sound_volume || 0.5
        audio.play().catch(console.error)
      }

      // Request notification permission and show silent notification
      if (Notification.permission === 'granted') {
        new Notification(t('indicatorAlerts.notificationTitle'), { 
          body: t('indicatorAlerts.notificationBody', {
            symbol: newlyTriggered[0].symbol,
            timeframe: newlyTriggered[0].timeframe,
            indicator: newlyTriggered[0].indicator_type,
            condition: getConditionText(newlyTriggered[0].condition, 'badge'),
            threshold: newlyTriggered[0].threshold,
          }),
          silent: true 
        })
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            new Notification(t('indicatorAlerts.notificationTitle'), { 
              body: t('indicatorAlerts.notificationBody', {
                symbol: newlyTriggered[0].symbol,
                timeframe: newlyTriggered[0].timeframe,
                indicator: newlyTriggered[0].indicator_type,
                condition: getConditionText(newlyTriggered[0].condition, 'badge'),
                threshold: newlyTriggered[0].threshold,
              }),
              silent: true 
            })
          }
        })
      }
    }
    prevTriggeredRef.current = new Set(indicatorAlerts.filter(a => a.is_triggered).map(a => a.id))
  }, [indicatorAlerts])

  const handleSubmit = async () => {
    setError(null)
    const upperSymbol = formData.symbol.toUpperCase()
    const finalData = { ...formData, symbol: upperSymbol }

    if (editingId) {
      const original = indicatorAlerts.find(a => a.id === editingId)
      if (original) {
        await updateIndicatorAlert({ 
          ...original, 
          ...finalData, 
          is_triggered: false 
        })
      }
      setEditingId(null)
    } else {
      await addIndicatorAlert({ ...finalData, is_active: true })
    }
    
    // Reset form to defaults
    setFormData({
      symbol: 'XAUUSD',
      timeframe: 'H1',
      indicator_type: 'RSI',
      period: 14,
      condition: 'below',
      threshold: 30,
      comment: ''
    })
  }

  const startEdit = (alert: IndicatorAlert) => {
    setEditingId(alert.id)
    setFormData({
      symbol: alert.symbol,
      timeframe: alert.timeframe,
      indicator_type: alert.indicator_type,
      period: alert.period,
      condition: alert.condition,
      threshold: alert.threshold,
      comment: alert.comment
    })
  }

  const toggleStatus = async (alert: IndicatorAlert, active: boolean) => {
    await updateIndicatorAlert({ ...alert, is_active: active })
  }

  const resetTrigger = async (alert: IndicatorAlert) => {
    await updateIndicatorAlert({ ...alert, is_triggered: false, is_active: true })
  }

  const debouncedRefresh = React.useMemo(
    () => debounce(() => {
      void fetchIndicatorAlerts()
    }, 400),
    [fetchIndicatorAlerts]
  )

  useEffect(() => {
    return () => {
      debouncedRefresh.cancel()
    }
  }, [debouncedRefresh])

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <PageHeader
        title={t('indicatorAlerts.title')}
        icon={LineChart}
        actions={(
          <Button variant="outline" size="sm" onClick={debouncedRefresh} disabled={isLoading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            {t('indicatorAlerts.refresh')}
          </Button>
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        {/* 左侧：设置表单 */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader className="py-4">
              <CardTitle className="text-lg">
                {editingId ? t('indicatorAlerts.editTitle') : t('indicatorAlerts.createTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>{t('indicatorAlerts.symbol')}</Label>
                <Input 
                  value={formData.symbol} 
                  onChange={(e) => setFormData({...formData, symbol: e.target.value})} 
                  className="uppercase"
                  placeholder={t('indicatorAlerts.symbolPlaceholder')}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="indicator-timeframe">{t('indicatorAlerts.timeframe')}</Label>
                  <Select
                    value={formData.timeframe}
                    onValueChange={(value) => setFormData({ ...formData, timeframe: value })}
                  >
                    <SelectTrigger id="indicator-timeframe">
                      <SelectValue placeholder={t('indicatorAlerts.timeframe')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="M1">{t('indicatorAlerts.timeframeM1')}</SelectItem>
                        <SelectItem value="M5">{t('indicatorAlerts.timeframeM5')}</SelectItem>
                        <SelectItem value="M15">{t('indicatorAlerts.timeframeM15')}</SelectItem>
                        <SelectItem value="M30">{t('indicatorAlerts.timeframeM30')}</SelectItem>
                        <SelectItem value="H1">{t('indicatorAlerts.timeframeH1')}</SelectItem>
                        <SelectItem value="H4">{t('indicatorAlerts.timeframeH4')}</SelectItem>
                        <SelectItem value="D1">{t('indicatorAlerts.timeframeD1')}</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="indicator-type">{t('indicatorAlerts.indicatorType')}</Label>
                  <Select
                    value={formData.indicator_type}
                    onValueChange={(value) => setFormData({ ...formData, indicator_type: value })}
                  >
                    <SelectTrigger id="indicator-type">
                      <SelectValue placeholder={t('indicatorAlerts.indicatorType')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="RSI">RSI</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t('indicatorAlerts.period')}</Label>
                <Input 
                  type="number" 
                  value={formData.period} 
                  onChange={(e) => setFormData({...formData, period: parseInt(e.target.value)})} 
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="indicator-condition">{t('indicatorAlerts.triggerCondition')}</Label>
                  <Select
                    value={formData.condition}
                    onValueChange={(value: 'above' | 'below') => setFormData({ ...formData, condition: value })}
                  >
                    <SelectTrigger id="indicator-condition">
                      <SelectValue placeholder={t('indicatorAlerts.triggerCondition')} />
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
                  <Label>{t('indicatorAlerts.threshold')}</Label>
                  <Input 
                    type="number" 
                    value={formData.threshold} 
                    onChange={(e) => setFormData({...formData, threshold: parseFloat(e.target.value)})} 
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 text-xs font-medium bg-destructive/10 text-destructive rounded-lg border border-destructive/20 animate-in fade-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              <div className="pt-2 flex flex-col gap-2">
                <Button onClick={handleSubmit} className="w-full" disabled={isLoading}>
                  {editingId ? <><Edit3 className="w-4 h-4 mr-2" />{t('indicatorAlerts.update')}</> : <><Plus className="w-4 h-4 mr-2" />{t('indicatorAlerts.create')}</>}
                </Button>
                {editingId && (
                  <Button variant="ghost" className="w-full" onClick={() => {
                    setEditingId(null)
                    setFormData({
                      symbol: 'XAUUSD',
                      timeframe: 'H1',
                      indicator_type: 'RSI',
                      period: 14,
                      condition: 'below',
                      threshold: 30,
                      comment: ''
                    })
                  }}>{t('indicatorAlerts.cancel')}</Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 右侧：预警列表 */}
        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">{t('indicatorAlerts.listTitle')}</CardTitle>
              <div className="text-xs text-muted-foreground">{t('indicatorAlerts.count', { count: indicatorAlerts.length })}</div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-0 pb-4">
              <div className="space-y-3">
                {indicatorAlerts.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                    {t('indicatorAlerts.empty')}
                  </div>
                ) : (
                  indicatorAlerts.map((alert) => (
                    <div 
                      key={alert.id} 
                      className={cn(
                        "flex items-center justify-between p-4 rounded-xl border transition-all hover:border-primary/20",
                        alert.is_triggered ? "bg-red-500/5 border-red-500/20" : "bg-card border-border",
                        !alert.is_active && "opacity-60"
                      )}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{alert.symbol}</span>
                          <span className="text-xs bg-secondary px-2 py-0.5 rounded text-secondary-foreground font-bold">
                            {alert.timeframe}
                          </span>
                          {alert.is_triggered && (
                            <span className="bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full font-bold animate-pulse">
                              {t('indicatorAlerts.triggered')}
                            </span>
                          )}
                          {!alert.is_active && !alert.is_triggered && (
                            <span className="bg-muted text-muted-foreground text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {t('indicatorAlerts.paused')}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground font-medium">
                          <span className="bg-primary/10 text-primary px-1.5 py-0.5 rounded text-xs">
                            {alert.indicator_type}({alert.period})
                          </span>
                          <span>{getConditionText(alert.condition, 'badge')}</span>
                          <span className="text-foreground font-mono font-bold">{alert.threshold}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        {/* 播放按钮 */}
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
                          title={alert.is_triggered ? t('indicatorAlerts.actionResetPlay') : t('indicatorAlerts.actionStart')}
                        >
                          <Play className={cn("w-4 h-4 fill-current", !alert.is_active && !alert.is_triggered && "fill-none")} />
                        </Button>

                        {/* 暂停按钮 */}
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
                          title={t('indicatorAlerts.actionPause')}
                        >
                          <Pause className={cn("w-4 h-4 fill-current", (alert.is_active || alert.is_triggered) && "fill-none")} />
                        </Button>

                        {/* 编辑按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-blue-500 hover:text-blue-600 hover:bg-blue-50"
                          onClick={() => startEdit(alert)}
                          title={t('indicatorAlerts.actionEdit')}
                        >
                          <Edit3 className="w-4 h-4" />
                        </Button>

                        {/* 删除按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-destructive hover:bg-destructive/10"
                          onClick={() => deleteIndicatorAlert(alert.id)}
                          title={t('indicatorAlerts.actionDelete')}
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
