import React from 'react'
import { HashRouter, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { WorkbenchShell } from '@/layouts/workbench-shell'
import { DashboardPage } from '@/pages/dashboard-page'
import { QuantPage } from '@/pages/QuantPage'
import { PythonQuantPage } from '@/pages/PythonQuantPage'
import { QuantBacktestPage } from '@/pages/QuantBacktestPage'
import { OrderBroadcastPage } from './pages/OrderBroadcastPage'
import { SettingsPage } from './pages/SettingsPage'
import { PriceAlertsPage } from './pages/PriceAlertsPage'
import { VolatilityPage } from './pages/VolatilityPage'
import { IndicatorAlertsPage } from './pages/IndicatorAlertsPage'
import { OrderCenterPage } from './pages/OrderCenterPage'
import { RiskControlPage } from './pages/RiskControlPage'
import { TechnicalAnalysisPage } from './pages/TechnicalAnalysisPage'
import { OrderSyncPage } from './pages/OrderSyncPage'
import { SponsorPage } from './pages/SponsorPage'
import { OverlayDisplayPage } from './pages/overlay-display-page'
import { LocalCopyTradingPage } from './pages/LocalCopyTradingPage'
import { EventLogPage } from './pages/EventLogPage'
import { AccountListPage } from './pages/AccountListPage'
import { DataManagementPage } from './pages/DataManagementPage'
import { TradingReviewPage } from './pages/TradingReviewPage'
import { Toaster } from '@/components/ui/sonner'
import { ThemeProvider } from 'next-themes'

const VALID_MODULES = new Set([
  'dashboard',
  'quant',
  'python-quant',
  'quant-backtest',
  'order-broadcast',
  'order-sync',
  'account-list',
  'local-copy-trading',
  'event-log',
  'order-center',
  'price-alerts',
  'volatility',
  'indicator-alerts',
  'risk-control',
  'tech-analysis',
  'sponsor',
  'settings',
  'data-management',
  'trading-review',
])

function ModuleRoute() {
  const navigate = useNavigate()
  const { module = 'dashboard' } = useParams()
  const activeModule = VALID_MODULES.has(module) ? module : 'dashboard'

  if (activeModule !== module) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <WorkbenchShell activeModule={activeModule} onModuleChange={(nextModule) => navigate(`/${nextModule}`)}>
      {activeModule === 'dashboard' && <DashboardPage />}
      {activeModule === 'quant' && <QuantPage />}
      {activeModule === 'python-quant' && <PythonQuantPage />}
      {activeModule === 'quant-backtest' && <QuantBacktestPage />}
      {activeModule === 'order-broadcast' && <OrderBroadcastPage />}
      {activeModule === 'order-sync' && <OrderSyncPage />}
      {activeModule === 'account-list' && <AccountListPage />}
      {activeModule === 'local-copy-trading' && <LocalCopyTradingPage />}
      {activeModule === 'event-log' && <EventLogPage />}
      {activeModule === 'data-management' && <DataManagementPage />}
      {activeModule === 'trading-review' && <TradingReviewPage />}
      {activeModule === 'order-center' && <OrderCenterPage />}
      {activeModule === 'price-alerts' && <PriceAlertsPage />}
      {activeModule === 'volatility' && <VolatilityPage />}
      {activeModule === 'indicator-alerts' && <IndicatorAlertsPage />}
      {activeModule === 'risk-control' && <RiskControlPage />}
      {activeModule === 'tech-analysis' ? <TechnicalAnalysisPage /> : null}
      {activeModule === 'sponsor' && <SponsorPage />}
      {activeModule === 'settings' && <SettingsPage />}
    </WorkbenchShell>
  )
}

export function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <HashRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/:module" element={<ModuleRoute />} />
          <Route path="/overlay-display" element={<OverlayDisplayPage />} />
        </Routes>
      </HashRouter>
      <Toaster />
    </ThemeProvider>
  )
}
