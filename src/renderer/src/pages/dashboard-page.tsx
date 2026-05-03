import React, { useEffect } from 'react'
import { useI18n } from '@/i18n'
import { useDashboardStore } from '@/stores/dashboard-store'
import { useOrderStore } from '@/stores/order-store'
import { useSettingsStore } from '@/stores/settings-store'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { cn } from '@/lib/utils'
import { DollarSign, LayoutDashboard, TrendingDown, TrendingUp } from 'lucide-react'

export function DashboardPage() {
  const { t } = useI18n()
  const { status, account, startPolling, stopPolling, fetchStatus } = useDashboardStore()
  const { overview, fetchOverview } = useOrderStore()
  const { settings, fetchSettings, error } = useSettingsStore()
  const [isOverlayVisible, setIsOverlayVisible] = React.useState(false)

  useEffect(() => {
    void fetchSettings(t('dashboard.errors.backendUnavailable'))
    void fetchOverview()
    
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
  }, [fetchSettings, fetchOverview, t])

  useEffect(() => {
    if (error) {
      window.alert(error)
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
        window.alert(result.message)
      } else {
        // Wait a bit for terminal to fully initialize before fetching status
        setTimeout(fetchStatus, 3000)
      }
    } catch (error) {
      console.error('Reconnect failed:', error)
      window.alert(t('dashboard.errors.backendUnavailable'))
    }
  }

  const toggleOverlay = async () => {
    const nextVisible = !isOverlayVisible
    await (window as any).electron.ipcRenderer.invoke('overlay:toggle-visible', nextVisible)
    setIsOverlayVisible(nextVisible)
  }

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
