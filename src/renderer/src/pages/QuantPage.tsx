import React from 'react'
import { LineChart } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { PageHeader } from '@/components/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PythonQuantPage } from '@/pages/PythonQuantPage'
import { QuantBacktestPage } from '@/pages/QuantBacktestPage'

type QuantPageProps = {
  defaultTab?: 'live-jobs' | 'backtest'
}

export function QuantPage({ defaultTab = 'live-jobs' }: QuantPageProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const currentTab = searchParams.get('tab') === 'backtest' ? 'backtest' : defaultTab

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Quant"
        description="Manage live jobs and run backtests from one workflow entry."
        icon={LineChart}
      />

      <Tabs value={currentTab} onValueChange={(value) => setSearchParams({ tab: value })} className="flex flex-col gap-6">
        <TabsList>
          <TabsTrigger value="live-jobs">Live Jobs</TabsTrigger>
          <TabsTrigger value="backtest">Backtest</TabsTrigger>
        </TabsList>

        <TabsContent value="live-jobs">
          <PythonQuantPage />
        </TabsContent>

        <TabsContent value="backtest">
          <QuantBacktestPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
