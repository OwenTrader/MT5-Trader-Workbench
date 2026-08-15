import React, { useState } from 'react'
import { useI18n } from '@/i18n'
import { PageHeader } from '@/components/page-header'
import { Bell, TrendingUp, LineChart, Megaphone, CheckCircle2, AlertCircle } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { PriceAlertsPage } from '../PriceAlertsPage'
import { VolatilityPage } from '../VolatilityPage'
import { IndicatorAlertsPage } from '../IndicatorAlertsPage'
import { OrderBroadcastPage } from '../OrderBroadcastPage'
import { useAlertsStore } from '@/stores/alerts-store'
import { useSettingsStore } from '@/stores/settings-store'

interface AlertsCenterPageProps {
  defaultTab?: 'price' | 'volatility' | 'indicator' | 'broadcast'
}

export const AlertsCenterPage: React.FC<AlertsCenterPageProps> = ({ defaultTab = 'price' }) => {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<string>(defaultTab)
  const { priceAlerts, volatilityAlerts, indicatorAlerts } = useAlertsStore()
  const { settings } = useSettingsStore()

  const activePriceCount = Array.isArray(priceAlerts) ? priceAlerts.filter((a) => a.is_active).length : 0
  const activeVolCount = Array.isArray(volatilityAlerts) ? volatilityAlerts.filter((a) => a.is_active).length : 0
  const activeIndCount = Array.isArray(indicatorAlerts) ? indicatorAlerts.filter((a) => a.is_active).length : 0

  const hasBotEnabled = Boolean(
    (settings.dingtalk_enabled && settings.dingtalk_token.trim()) ||
    (settings.wecom_enabled && settings.wecom_webhook_url.trim()) ||
    (settings.feishu_enabled && settings.feishu_webhook_url.trim())
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <PageHeader title={t('nav.alertsHub')} icon={Bell} />
        
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
            <span className="text-foreground font-semibold">活跃规则:</span>
            <span>{activePriceCount + activeVolCount + activeIndCount} 个</span>
          </div>

          <div className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
            <span>推送通道:</span>
            {hasBotEnabled ? (
              <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" /> 已就绪
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <AlertCircle className="h-3.5 w-3.5" /> 仅声音/弹窗
              </span>
            )}
          </div>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <div className="border-b bg-card/50 px-1 backdrop-blur-sm rounded-lg border">
          <TabsList className="h-12 w-full justify-start gap-2 bg-transparent p-1">
            <TabsTrigger
              value="price"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Bell className="h-4 w-4" />
              <span>{t('nav.priceAlerts')}</span>
              {activePriceCount > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0.2 text-xs">
                  {activePriceCount}
                </Badge>
              )}
            </TabsTrigger>

            <TabsTrigger
              value="volatility"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <TrendingUp className="h-4 w-4" />
              <span>{t('nav.volatility')}</span>
              {activeVolCount > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0.2 text-xs">
                  {activeVolCount}
                </Badge>
              )}
            </TabsTrigger>

            <TabsTrigger
              value="indicator"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <LineChart className="h-4 w-4" />
              <span>{t('nav.indicatorAlerts')}</span>
              {activeIndCount > 0 && (
                <Badge variant="secondary" className="ml-1 px-1.5 py-0.2 text-xs">
                  {activeIndCount}
                </Badge>
              )}
            </TabsTrigger>

            <TabsTrigger
              value="broadcast"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Megaphone className="h-4 w-4" />
              <span>{t('nav.orderBroadcast')}</span>
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="price" className="m-0 focus-visible:outline-none">
          <PriceAlertsPage />
        </TabsContent>

        <TabsContent value="volatility" className="m-0 focus-visible:outline-none">
          <VolatilityPage />
        </TabsContent>

        <TabsContent value="indicator" className="m-0 focus-visible:outline-none">
          <IndicatorAlertsPage />
        </TabsContent>

        <TabsContent value="broadcast" className="m-0 focus-visible:outline-none">
          <OrderBroadcastPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
