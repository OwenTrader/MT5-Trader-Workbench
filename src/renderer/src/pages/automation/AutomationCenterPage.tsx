import React, { useState } from 'react'
import { useI18n } from '@/i18n'
import { PageHeader } from '@/components/page-header'
import { Link2, Users, ShieldCheck, RefreshCw, ShoppingBag } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LocalCopyTradingPage } from '../LocalCopyTradingPage'
import { AccountListPage } from '../AccountListPage'
import { OrderSyncPage } from '../OrderSyncPage'
import { RiskControlPage } from '../RiskControlPage'
import { OrderCenterPage } from '../OrderCenterPage'

interface AutomationCenterPageProps {
  defaultTab?: 'copy-trading' | 'accounts' | 'order-sync' | 'risk-control' | 'orders'
}

export const AutomationCenterPage: React.FC<AutomationCenterPageProps> = ({ defaultTab = 'copy-trading' }) => {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<string>(defaultTab)

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <PageHeader title={t('nav.automationHub')} icon={Link2} />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <div className="border-b bg-card/50 px-1 backdrop-blur-sm rounded-lg border">
          <TabsList className="h-12 w-full justify-start gap-2 bg-transparent p-1">
            <TabsTrigger
              value="copy-trading"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Link2 className="h-4 w-4" />
              <span>{t('nav.localCopyTrading')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="accounts"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Users className="h-4 w-4" />
              <span>{t('nav.accountList')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="order-sync"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <RefreshCw className="h-4 w-4" />
              <span>{t('nav.orderSync')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="risk-control"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <ShieldCheck className="h-4 w-4" />
              <span>{t('nav.riskControl')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="orders"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <ShoppingBag className="h-4 w-4" />
              <span>{t('nav.orderCenter')}</span>
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="copy-trading" className="m-0 focus-visible:outline-none">
          <LocalCopyTradingPage />
        </TabsContent>

        <TabsContent value="accounts" className="m-0 focus-visible:outline-none">
          <AccountListPage />
        </TabsContent>

        <TabsContent value="order-sync" className="m-0 focus-visible:outline-none">
          <OrderSyncPage />
        </TabsContent>

        <TabsContent value="risk-control" className="m-0 focus-visible:outline-none">
          <RiskControlPage />
        </TabsContent>

        <TabsContent value="orders" className="m-0 focus-visible:outline-none">
          <OrderCenterPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
