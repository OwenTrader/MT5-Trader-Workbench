import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useI18n } from '@/i18n'
import { PageHeader } from '@/components/page-header'
import { LineChart, PlayCircle, Database, BookOpen, Bot } from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PythonQuantPage } from '../PythonQuantPage'
import { QuantBacktestPage } from '../QuantBacktestPage'
import { DataManagementPage } from '../DataManagementPage'
import { TradingReviewPage } from '../TradingReviewPage'
import { TechnicalAnalysisPage } from '../TechnicalAnalysisPage'

interface QuantLabPageProps {
  defaultTab?: 'python-quant' | 'backtest' | 'data-management' | 'trading-review' | 'tech-analysis'
}

export const QuantLabPage: React.FC<QuantLabPageProps> = ({ defaultTab = 'python-quant' }) => {
  const { t } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  const paramTab = searchParams.get('tab')
  
  const resolveTab = (tabValue: string | null): string => {
    if (tabValue === 'backtest') return 'backtest'
    if (tabValue === 'live-jobs' || tabValue === 'python-quant') return 'python-quant'
    if (tabValue === 'data-management') return 'data-management'
    if (tabValue === 'trading-review') return 'trading-review'
    if (tabValue === 'tech-analysis') return 'tech-analysis'
    return defaultTab
  }

  const [activeTab, setActiveTab] = useState<string>(() => resolveTab(paramTab))

  useEffect(() => {
    if (paramTab) {
      setActiveTab(resolveTab(paramTab))
    }
  }, [paramTab])

  const handleTabChange = (value: string) => {
    setActiveTab(value)
    setSearchParams({ tab: value })
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <PageHeader title={t('quant.title') || t('nav.quantLab')} description={t('quant.description')} icon={LineChart} />
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <div className="border-b bg-card/50 px-1 backdrop-blur-sm rounded-lg border">
          <TabsList className="h-12 w-full justify-start gap-2 bg-transparent p-1">
            <TabsTrigger
              value="python-quant"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <LineChart className="h-4 w-4" />
              <span>{t('nav.pythonQuant')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="backtest"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Bot className="h-4 w-4" />
              <span>{t('nav.quantBacktest')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="data-management"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <Database className="h-4 w-4" />
              <span>{t('nav.dataManagement')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="trading-review"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <PlayCircle className="h-4 w-4" />
              <span>{t('nav.tradingReview')}</span>
            </TabsTrigger>

            <TabsTrigger
              value="tech-analysis"
              className="gap-2 px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all rounded-md"
            >
              <BookOpen className="h-4 w-4" />
              <span>{t('nav.technicalAnalysis')}</span>
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="python-quant" className="m-0 focus-visible:outline-none">
          <PythonQuantPage />
        </TabsContent>

        <TabsContent value="backtest" className="m-0 focus-visible:outline-none">
          <QuantBacktestPage />
        </TabsContent>

        <TabsContent value="data-management" className="m-0 focus-visible:outline-none">
          <DataManagementPage />
        </TabsContent>

        <TabsContent value="trading-review" className="m-0 focus-visible:outline-none">
          <TradingReviewPage />
        </TabsContent>

        <TabsContent value="tech-analysis" className="m-0 focus-visible:outline-none">
          <TechnicalAnalysisPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
