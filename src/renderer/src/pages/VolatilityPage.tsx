import React, { useEffect, useState, useRef } from 'react'
import { useI18n } from '@/i18n'
import { useAlertsStore, VolatilityAlert } from '@/stores/alerts-store'
import { useSettingsStore } from '@/stores/settings-store'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Trash2, Play, Pause, Edit3, RefreshCw, TrendingUp } from 'lucide-react'
import { cn, debounce } from '@/lib/utils'
import { toast } from 'sonner'

export const VolatilityPage: React.FC = () => {
  const { t } = useI18n()
  const { 
    volatilityAlerts, 
    fetchVolatilityAlerts, 
    addVolatilityAlert, 
    updateVolatilityAlert, 
    deleteVolatilityAlert, 
    isLoading 
  } = useAlertsStore()
  const { settings, fetchSettings } = useSettingsStore()
  const prevTriggeredRef = useRef<Set<string>>(new Set())
  
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<Omit<VolatilityAlert, 'id' | 'is_active' | 'is_triggered'>>({
    symbol: 'XAUUSD',
    threshold_points: 50,
    timeframe_seconds: 300 // 5 minutes
  })

  useEffect(() => {
    fetchSettings()
    fetchVolatilityAlerts()
    
    const interval = settings.api_refresh_interval || 2000
    const timer = setInterval(() => {
      fetchVolatilityAlerts({ silent: true })
    }, interval)
    return () => clearInterval(timer)
  }, [settings.api_refresh_interval])

  // Play sound when alert triggers
  useEffect(() => {
    const newlyTriggered = volatilityAlerts.filter(a => a.is_triggered && !prevTriggeredRef.current.has(a.id))
    if (newlyTriggered.length > 0) {
      if (settings.alert_sound_enabled && settings.alert_sound_path) {
        const audio = new Audio(`local-file://${settings.alert_sound_path}`)
        audio.volume = settings.alert_sound_volume || 0.5
        audio.play().catch(console.error)
      }

      // Request notification permission and show silent notification
      if (Notification.permission === 'granted') {
        new Notification(t('volatility.notificationTitle'), { 
          body: t('volatility.notificationBody', {
            symbol: newlyTriggered[0].symbol,
            threshold: newlyTriggered[0].threshold_points,
            seconds: newlyTriggered[0].timeframe_seconds,
          }),
          silent: true 
        })
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            new Notification(t('volatility.notificationTitle'), { 
              body: t('volatility.notificationBody', {
                symbol: newlyTriggered[0].symbol,
                threshold: newlyTriggered[0].threshold_points,
                seconds: newlyTriggered[0].timeframe_seconds,
              }),
              silent: true 
            })
          }
        })
      }
    }
    prevTriggeredRef.current = new Set(volatilityAlerts.filter(a => a.is_triggered).map(a => a.id))
  }, [volatilityAlerts])

  const handleSubmit = async () => {
    setError(null)
    const upperSymbol = formData.symbol.toUpperCase()
    
    // Note: MT5 validation for volatility could be added here similar to price alerts
    
    const finalData = { ...formData, symbol: upperSymbol }

    if (editingId) {
      const original = volatilityAlerts.find(a => a.id === editingId)
      if (original) {
        await updateVolatilityAlert({ 
          ...original, 
          ...finalData, 
          is_triggered: false 
        })
      }
      setEditingId(null)
    } else {
      await addVolatilityAlert({ ...finalData, is_active: true })
    }
    // Reset form
    setFormData({ symbol: 'XAUUSD', threshold_points: 50, timeframe_seconds: 300 })
  }

  const startEdit = (alert: VolatilityAlert) => {
    setEditingId(alert.id)
    setFormData({
      symbol: alert.symbol,
      threshold_points: alert.threshold_points,
      timeframe_seconds: alert.timeframe_seconds
    })
  }

  const toggleStatus = async (alert: VolatilityAlert, active: boolean) => {
    await updateVolatilityAlert({ ...alert, is_active: active })
    if (active) {
      toast.success(t('volatility.toastStarted', { symbol: alert.symbol }))
    } else {
      toast.info(t('volatility.toastPaused', { symbol: alert.symbol }))
    }
  }

  const resetTrigger = async (alert: VolatilityAlert) => {
    await updateVolatilityAlert({ ...alert, is_triggered: false, is_active: true })
    toast.success(t('volatility.toastReset', { symbol: alert.symbol }))
  }

  const debouncedRefresh = React.useMemo(
    () => debounce(() => {
      void fetchVolatilityAlerts()
    }, 400),
    [fetchVolatilityAlerts]
  )

  useEffect(() => {
    return () => {
      debouncedRefresh.cancel()
    }
  }, [debouncedRefresh])

  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <PageHeader
        title={t('volatility.title')}
        icon={TrendingUp}
        actions={(
          <Button variant="outline" size="sm" onClick={debouncedRefresh} disabled={isLoading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            {t('volatility.refresh')}
          </Button>
        )}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        {/* 左侧：设置表单 */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {editingId ? t('volatility.editTitle') : t('volatility.createTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>{t('volatility.symbol')}</Label>
                <Input 
                  value={formData.symbol} 
                  onChange={(e) => setFormData({...formData, symbol: e.target.value})} 
                  className="uppercase"
                  placeholder={t('volatility.symbolPlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('volatility.threshold')}</Label>
                <Input 
                  type="number" 
                  value={formData.threshold_points} 
                  onChange={(e) => setFormData({...formData, threshold_points: parseFloat(e.target.value)})} 
                />
              </div>
              <div className="space-y-2">
                <Label>{t('volatility.duration')}</Label>
                <Input 
                  type="number" 
                  value={formData.timeframe_seconds / 60} 
                  onChange={(e) => setFormData({...formData, timeframe_seconds: parseInt(e.target.value) * 60})} 
                />
              </div>

              {error && (
                <div className="p-3 text-xs font-medium bg-destructive/10 text-destructive rounded-lg border border-destructive/20 animate-in fade-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              <div className="pt-2 flex gap-2">
                <Button onClick={handleSubmit} className="flex-1">
                  {editingId ? t('volatility.update') : t('volatility.create')}
                </Button>
                {editingId && (
                  <Button variant="outline" onClick={() => {
                    setEditingId(null)
                    setFormData({ symbol: 'XAUUSD', threshold_points: 50, timeframe_seconds: 300 })
                  }}>
                    {t('volatility.cancel')}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 右侧：监控列表 */}
        <div className="lg:col-span-2 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <CardTitle className="text-lg">{t('volatility.listTitle')}</CardTitle>
              <div className="text-xs text-muted-foreground">{t('volatility.count', { count: volatilityAlerts.length })}</div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto pt-0 pb-4">
              <div className="space-y-3">
                {volatilityAlerts.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed rounded-lg">
                    {t('volatility.empty')}
                  </div>
                ) : (
                  volatilityAlerts.map((alert) => (
                    <div 
                      key={alert.id} 
                      className={cn(
                        "flex items-center justify-between p-4 rounded-xl border transition-all",
                        alert.is_triggered ? "bg-orange-500/5 border-orange-500/20" : "bg-card border-border",
                        !alert.is_active && "opacity-60"
                      )}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{alert.symbol}</span>
                          {alert.is_triggered && (
                            <span className="bg-orange-500 text-white text-[10px] px-2 py-0.5 rounded-full font-bold animate-pulse">
                              {t('volatility.triggered')}
                            </span>
                          )}
                          {!alert.is_active && !alert.is_triggered && (
                            <span className="bg-muted text-muted-foreground text-[10px] px-2 py-0.5 rounded-full font-bold">
                              {t('volatility.paused')}
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-muted-foreground font-medium">
                          {t('volatility.thresholdLabel')} <span className="text-foreground font-mono">{t('volatility.thresholdValue', { value: alert.threshold_points })}</span>
                          <span className="mx-2">/</span>
                          {t('volatility.durationLabel')} <span className="text-foreground font-mono">{t('volatility.durationValue', { value: alert.timeframe_seconds / 60 })}</span>
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
                              ? "bg-orange-600 text-white hover:bg-orange-700 shadow-lg shadow-orange-500/30" 
                              : alert.is_active 
                                ? "bg-blue-600/10 text-blue-600 hover:bg-blue-600/20" 
                                : "text-muted-foreground/40 hover:text-muted-foreground"
                          )}
                          onClick={() => alert.is_triggered ? resetTrigger(alert) : toggleStatus(alert, true)}
                          title={alert.is_triggered ? t('volatility.actionResetPlay') : t('volatility.actionStart')}
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
                          title={t('volatility.actionPause')}
                        >
                          <Pause className={cn("w-4 h-4 fill-current", (alert.is_active || alert.is_triggered) && "fill-none")} />
                        </Button>

                        {/* 编辑按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-blue-500 hover:text-blue-600 hover:bg-blue-50"
                          onClick={() => startEdit(alert)}
                          title={t('volatility.actionEdit')}
                        >
                          <Edit3 className="w-4 h-4" />
                        </Button>

                        {/* 删除按钮 */}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="w-9 h-9 rounded-full text-destructive hover:bg-destructive/10"
                          onClick={() => deleteVolatilityAlert(alert.id)}
                          title={t('volatility.actionDelete')}
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
