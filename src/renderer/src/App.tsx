import React, { useState } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'
import { WorkbenchShell } from '@/layouts/workbench-shell'
import { DashboardPage } from '@/pages/dashboard-page'
import { OrderBroadcastPage } from './pages/OrderBroadcastPage'
import { SettingsPage } from './pages/SettingsPage'
import { PriceAlertsPage } from './pages/PriceAlertsPage'
import { VolatilityPage } from './pages/VolatilityPage'
import { IndicatorAlertsPage } from './pages/IndicatorAlertsPage'
import { OrderCenterPage } from './pages/OrderCenterPage'
import { RiskControlPage } from './pages/RiskControlPage'
import { TechnicalAnalysisPage } from './pages/TechnicalAnalysisPage'
import { OverlayDisplayPage } from './pages/overlay-display-page'
import { Toaster } from '@/components/ui/sonner'
import { ThemeProvider } from 'next-themes'
import { useI18n } from '@/i18n'

export function App() {
  const [activeModule, setActiveModule] = useState('dashboard')
  const { t } = useI18n()
  
  React.useEffect(() => {
    console.log('activeModule CHANGED to:', activeModule)
  }, [activeModule])

  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <HashRouter>
        <Routes>
          <Route path="/" element={
            <WorkbenchShell activeModule={activeModule} onModuleChange={setActiveModule}>
              {activeModule === 'dashboard' && <DashboardPage />}
              {activeModule === 'order-broadcast' && <OrderBroadcastPage />}
              {activeModule === 'order-center' && <OrderCenterPage />}
              {activeModule === 'price-alerts' && <PriceAlertsPage />}
              {activeModule === 'volatility' && <VolatilityPage />}
              {activeModule === 'indicator-alerts' && <IndicatorAlertsPage />}
              {activeModule === 'risk-control' && <RiskControlPage />}
              {activeModule === 'tech-analysis' ? <TechnicalAnalysisPage /> : null}
              {activeModule === 'settings' && <SettingsPage />}
            </WorkbenchShell>
          } />
          <Route path="/overlay-display" element={<OverlayDisplayPage />} />
        </Routes>
      </HashRouter>
      <Toaster />
    </ThemeProvider>
  )
}
