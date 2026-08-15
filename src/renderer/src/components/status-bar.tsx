import React, { useState, useEffect } from 'react'
import { useI18n } from '@/i18n'
import { useDashboardStore } from '@/stores/dashboard-store'
import { useSettingsStore } from '@/stores/settings-store'
import { useAlertsStore } from '@/stores/alerts-store'
import { Activity, Bell, Command, Radio, Wifi, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatusBarProps {
  onOpenCommandPalette?: () => void
}

export const StatusBar: React.FC<StatusBarProps> = ({ onOpenCommandPalette }) => {
  const { t, locale } = useI18n()
  const { status, account } = useDashboardStore()
  const { settings } = useSettingsStore()
  const { priceAlerts, volatilityAlerts, indicatorAlerts } = useAlertsStore()
  const [timeStr, setTimeStr] = useState<string>('')

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setTimeStr(now.toLocaleTimeString(locale === 'zh-CN' ? 'zh-CN' : 'en-US', { hour12: false }))
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [locale])

  const totalActiveAlerts = (priceAlerts || []).concat(volatilityAlerts || [], indicatorAlerts || []).filter(a => a.is_active).length

  const isConnected = status.is_connected
  const isRunning = status.is_running

  return (
    <footer className="flex h-7 w-full shrink-0 select-none items-center justify-between border-t bg-muted/40 px-3 text-[11px] text-muted-foreground backdrop-blur-md">
      {/* Left items: Connection status & Server indicators */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 font-medium">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              isConnected
                ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse"
                : isRunning
                ? "bg-amber-500"
                : "bg-rose-500"
            )}
          />
          <span className="text-foreground">
            MT5: {isConnected ? '已连接' : isRunning ? '就绪未登录' : '未连接'}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-1">
          <Radio className="h-3 w-3 text-muted-foreground/70" />
          <span>推流服务: 127.0.0.1:8765</span>
        </div>

        {totalActiveAlerts > 0 && (
          <div className="hidden md:flex items-center gap-1 text-primary">
            <Bell className="h-3 w-3" />
            <span>{totalActiveAlerts} 活跃告警</span>
          </div>
        )}
      </div>

      {/* Right items: Command shortcut hint & Time */}
      <div className="flex items-center gap-3">
        {onOpenCommandPalette && (
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="hidden sm:flex items-center gap-1 hover:text-foreground transition-colors px-1 py-0.5 rounded border bg-background/60 text-[10px]"
          >
            <Command className="h-2.5 w-2.5" />
            <span>Ctrl + K 快捷指令</span>
          </button>
        )}

        <div className="flex items-center gap-1 font-mono text-[11px]">
          <Clock className="h-3 w-3 text-muted-foreground/70" />
          <span>{timeStr || '--:--:--'}</span>
        </div>
      </div>
    </footer>
  )
}
