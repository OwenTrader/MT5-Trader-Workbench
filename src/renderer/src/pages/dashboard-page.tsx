import React, { useEffect } from 'react'
import { useI18n } from '@/i18n'
import { Badge } from '@/components/ui/badge'
import { useDashboardStore } from '@/stores/dashboard-store'
import { useAlertsStore } from '@/stores/alerts-store'
import { useOrderStore } from '@/stores/order-store'
import { useOrderSyncStore } from '@/stores/order-sync-store'
import { useSettingsStore } from '@/stores/settings-store'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { cn } from '@/lib/utils'
import { Bell, DollarSign, Eye, LayoutDashboard, Radio, ShieldCheck, TrendingDown, TrendingUp, Volume2 } from 'lucide-react'
import { toast } from 'sonner'

export function DashboardPage() {
  const { t } = useI18n()
  const { status, account, startPolling, stopPolling, fetchStatus } = useDashboardStore()
  const {
    priceAlerts,
    volatilityAlerts,
    indicatorAlerts,
    fetchAlerts,
    fetchVolatilityAlerts,
    fetchIndicatorAlerts,
  } = useAlertsStore()
  const { overview, fetchOverview } = useOrderStore()
  const { config: orderSyncConfig, fetchConfig: fetchOrderSyncConfig } = useOrderSyncStore()
  const { settings, fetchSettings, error } = useSettingsStore()
  const [isOverlayVisible, setIsOverlayVisible] = React.useState(false)

  useEffect(() => {
    void fetchSettings(t('dashboard.errors.backendUnavailable'))
    void fetchOverview()
    void fetchAlerts({ silent: true })
    void fetchVolatilityAlerts({ silent: true })
    void fetchIndicatorAlerts({ silent: true })
    void fetchOrderSyncConfig({ silent: true })
    
    let removeVisibilityListener: (() => void) | undefined
    let removeSettingsListener: (() => void) | undefined

    if ((window as any).electron?.ipcRenderer) {
      // Listen for settings change
      removeSettingsListener = (window as any).electron.ipcRenderer.on('settings:changed', () => {
        void fetchSettings(t('dashboard.errors.backendUnavailable'))
      })

      // Check initial visibility
      const checkVisibility = async () => {
        try {
          const visible = await (window as any).electron.ipcRenderer.invoke('overlay:is-visible')
          setIsOverlayVisible(visible)
        } catch (e) {
          console.error('Failed to check overlay visibility:', e)
        }
      }
      checkVisibility()

      // Listen for visibility changes
      removeVisibilityListener = (window as any).electron.ipcRenderer.on('overlay:visibility-changed', (visible: boolean) => {
        setIsOverlayVisible(visible)
      })
    }

    return () => {
      removeSettingsListener?.()
      removeVisibilityListener?.()
    }
  }, [fetchSettings, fetchOverview, fetchAlerts, fetchVolatilityAlerts, fetchIndicatorAlerts, fetchOrderSyncConfig, t])

  useEffect(() => {
    if (error) {
      toast.error(error)
    }
  }, [error])

  useEffect(() => {
    startPolling(settings.api_refresh_interval)
    return () => stopPolling()
  }, [settings.api_refresh_interval])

  const handleReconnect = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8765/mt5/launch', { method: 'POST' })
      const result = await response.json()
      
      if (result.status === 'error') {
        toast.error(result.message)
      } else {
        // Wait a bit for terminal to fully initialize before fetching status
        setTimeout(fetchStatus, 3000)
      }
    } catch (error) {
      console.error('Reconnect failed:', error)
      toast.error(t('dashboard.errors.backendUnavailable'))
    }
  }

  const toggleOverlay = async () => {
    const nextVisible = !isOverlayVisible
    await (window as any).electron.ipcRenderer.invoke('overlay:toggle-visible', nextVisible)
    setIsOverlayVisible(nextVisible)
  }

  const activeAlertCount = [priceAlerts, volatilityAlerts, indicatorAlerts]
    .flat()
    .filter((alert) => alert.is_active).length
  const hasNotificationTransport = Boolean(
    (settings.dingtalk_enabled && settings.dingtalk_token.trim())
      || (settings.wecom_enabled && settings.wecom_webhook_url.trim())
      || (settings.feishu_enabled && settings.feishu_webhook_url.trim())
  )
  const botPushCount = [settings.push_price_alerts, settings.push_volatility_alerts, settings.push_indicator_alerts]
    .filter(Boolean).length
  const enabledNotificationCount = hasNotificationTransport ? botPushCount : 0
  const notificationSummary = enabledNotificationCount > 0
    ? t('dashboard.statusCenter.notificationsEnabled', { count: enabledNotificationCount })
    : t('dashboard.statusCenter.notificationsDisabled')
  const soundSummary = settings.alert_sound_enabled
    ? t('dashboard.statusCenter.soundEnabled', { volume: Math.round(settings.alert_sound_volume * 100) })
    : t('dashboard.statusCenter.soundDisabled')
  const orderSyncSummary = orderSyncConfig.enabled
    ? t('dashboard.statusCenter.syncEnabled', { count: orderSyncConfig.mappings.filter((mapping) => mapping.is_active).length })
    : t('dashboard.statusCenter.syncDisabled')

  return (
    <div className="space-y-6">
      <PageHeader title={t('dashboard.title')} icon={LayoutDashboard} />
      
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="h-full">
          <CardContent className="flex h-full flex-col justify-center pt-6">
            <div className="text-sm font-medium text-muted-foreground mb-1">{t('dashboard.cards.mt5Status')}</div>
            <div className={cn("text-2xl font-bold", 
              status.is_connected ? "text-green-500" : (status.is_running ? "text-yellow-500" : "text-muted-foreground")
            )}>
              {status.is_running
                ? (status.is_connected ? t('dashboard.status.connected') : t('dashboard.status.runningNotLoggedIn'))
                : t('dashboard.status.stopped')}
            </div>
          </CardContent>
        </Card>

        <Card className="h-full">
          <CardContent className="flex h-full flex-col justify-center pt-6">
            <div className="text-sm font-medium text-muted-foreground mb-1">{t('dashboard.cards.balance')}</div>
            <div className="text-2xl font-bold">
              ${account?.balance?.toFixed(2) || '0.00'}
            </div>
          </CardContent>
        </Card>

        <Card className="h-full">
          <CardContent className="flex h-full flex-col justify-center pt-6">
            <div className="text-sm font-medium text-muted-foreground mb-1">{t('dashboard.cards.equityProfit')}</div>
            <div className={cn("text-2xl font-bold", (account?.profit || 0) >= 0 ? "text-green-500" : "text-red-500")}>
              ${account?.equity?.toFixed(2) || '0.00'} ({(account?.profit || 0) >= 0 ? '+' : ''}{account?.profit?.toFixed(2) || '0.00'})
            </div>
          </CardContent>
        </Card>

      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ProfitCard title={t('orderCenter.today')} value={overview.today} icon={<DollarSign />} />
        <ProfitCard title={t('orderCenter.week')} value={overview.week} icon={<TrendingUp />} />
        <ProfitCard title={t('orderCenter.month')} value={overview.month} icon={<TrendingDown />} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('dashboard.statusCenter.title')}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          <StatusItem
            icon={<Radio className="h-4 w-4" />}
            label={t('dashboard.statusCenter.mt5')}
            value={status.is_running
              ? (status.is_connected ? t('dashboard.status.connected') : t('dashboard.status.runningNotLoggedIn'))
              : t('dashboard.status.stopped')}
            active={status.is_connected}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
          <StatusItem
            icon={<Eye className="h-4 w-4" />}
            label={t('dashboard.statusCenter.overlay')}
            value={isOverlayVisible ? t('dashboard.statusCenter.visible') : t('dashboard.statusCenter.hidden')}
            active={isOverlayVisible}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
          <StatusItem
            icon={<Bell className="h-4 w-4" />}
            label={t('dashboard.statusCenter.activeAlerts')}
            value={t('dashboard.statusCenter.alertCount', { count: activeAlertCount })}
            active={activeAlertCount > 0}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
          <StatusItem
            icon={<Bell className="h-4 w-4" />}
            label={t('dashboard.statusCenter.notifications')}
            value={notificationSummary}
            active={enabledNotificationCount > 0}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
          <StatusItem
            icon={<Volume2 className="h-4 w-4" />}
            label={t('dashboard.statusCenter.sound')}
            value={soundSummary}
            active={settings.alert_sound_enabled}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
          <StatusItem
            icon={<ShieldCheck className="h-4 w-4" />}
            label={t('dashboard.statusCenter.orderSync')}
            value={orderSyncSummary}
            active={orderSyncConfig.enabled}
            activeLabel={t('dashboard.statusCenter.on')}
            inactiveLabel={t('dashboard.statusCenter.off')}
          />
        </CardContent>
      </Card>

      <div className="flex gap-4">
        <Button onClick={handleReconnect} variant="outline">{t('dashboard.actions.reconnect')}</Button>
        <Button 
          onClick={toggleOverlay} 
          variant={isOverlayVisible ? "destructive" : "default"}
        >
          {isOverlayVisible ? t('dashboard.actions.hideOverlay') : t('dashboard.actions.showOverlay')}
        </Button>
      </div>
    </div>
  )
}

interface StatusItemProps {
  icon: React.ReactNode
  label: string
  value: string
  active: boolean
  activeLabel: string
  inactiveLabel: string
}

function StatusItem({ icon, label, value, active, activeLabel, inactiveLabel }: StatusItemProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border bg-card p-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className={cn('rounded-full p-2', active ? 'bg-green-500/10 text-green-600' : 'bg-muted text-muted-foreground')}>
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium">{label}</div>
          <div className="truncate text-sm text-muted-foreground">{value}</div>
        </div>
      </div>
      <Badge variant={active ? 'default' : 'secondary'}>
        {active ? activeLabel : inactiveLabel}
      </Badge>
    </div>
  )
}

interface ProfitCardProps {
  title: string
  value: number
  icon: React.ReactNode
}

function ProfitCard({ title, value, icon }: ProfitCardProps) {
  const displayValue = Number.isFinite(value) ? value : 0

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {displayValue > 0 ? '+' : ''}{displayValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </div>
      </CardContent>
    </Card>
  )
}
