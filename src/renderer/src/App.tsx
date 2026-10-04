import React, { Suspense, lazy } from 'react'
import { useI18n } from '@/i18n'
import { HashRouter, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { WorkbenchShell } from '@/layouts/workbench-shell'
import { OverlayDisplayPage } from '@/pages/overlay-display-page'
import { Toaster } from '@/components/ui/sonner'
import { ThemeProvider } from 'next-themes'

/** Lazily load a named export as a default-exported component for React.lazy. */
function lazyNamed<M extends Record<string, React.ComponentType<any>>>(
  loader: () => Promise<M>,
  name: keyof M,
): React.LazyExoticComponent<React.ComponentType<any>> {
  return lazy(() => loader().then((mod) => ({ default: mod[name] })))
}

// Route-level code splitting: each page becomes its own chunk so the initial
// bundle only needs the shell + dashboard, not all 24 pages + charting libs.
const DashboardPage = lazyNamed(() => import('@/pages/dashboard-page'), 'DashboardPage')
const AlertsCenterPage = lazyNamed(() => import('@/pages/alerts/AlertsCenterPage'), 'AlertsCenterPage')
const AutomationCenterPage = lazyNamed(() => import('@/pages/automation/AutomationCenterPage'), 'AutomationCenterPage')
const QuantLabPage = lazyNamed(() => import('@/pages/quant/QuantLabPage'), 'QuantLabPage')
const PythonQuantPage = lazyNamed(() => import('@/pages/PythonQuantPage'), 'PythonQuantPage')
const QuantBacktestPage = lazyNamed(() => import('@/pages/QuantBacktestPage'), 'QuantBacktestPage')
const OrderBroadcastPage = lazyNamed(() => import('@/pages/OrderBroadcastPage'), 'OrderBroadcastPage')
const SettingsPage = lazyNamed(() => import('@/pages/SettingsPage'), 'SettingsPage')
const PriceAlertsPage = lazyNamed(() => import('@/pages/PriceAlertsPage'), 'PriceAlertsPage')
const VolatilityPage = lazyNamed(() => import('@/pages/VolatilityPage'), 'VolatilityPage')
const IndicatorAlertsPage = lazyNamed(() => import('@/pages/IndicatorAlertsPage'), 'IndicatorAlertsPage')
const OrderCenterPage = lazyNamed(() => import('@/pages/OrderCenterPage'), 'OrderCenterPage')
const RiskControlPage = lazyNamed(() => import('@/pages/RiskControlPage'), 'RiskControlPage')
const TechnicalAnalysisPage = lazyNamed(() => import('@/pages/TechnicalAnalysisPage'), 'TechnicalAnalysisPage')
const OrderSyncPage = lazyNamed(() => import('@/pages/OrderSyncPage'), 'OrderSyncPage')
const SponsorPage = lazyNamed(() => import('@/pages/SponsorPage'), 'SponsorPage')
const LocalCopyTradingPage = lazyNamed(() => import('@/pages/LocalCopyTradingPage'), 'LocalCopyTradingPage')
const EventLogPage = lazyNamed(() => import('@/pages/EventLogPage'), 'EventLogPage')
const AccountListPage = lazyNamed(() => import('@/pages/AccountListPage'), 'AccountListPage')
const DataManagementPage = lazyNamed(() => import('@/pages/DataManagementPage'), 'DataManagementPage')
const TradingReviewPage = lazyNamed(() => import('@/pages/TradingReviewPage'), 'TradingReviewPage')

const VALID_MODULES = new Set([
  'dashboard',
  'alerts',
  'automation',
  'quant',
  'quant-lab',
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

function PageFallback() {
  const { t } = useI18n()
  return (
    <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
      {t('common.loading')}
    </div>
  )
}

function ModuleRoute() {
  const navigate = useNavigate()
  const { module = 'dashboard' } = useParams()
  const activeModule = VALID_MODULES.has(module) ? module : 'dashboard'

  if (activeModule !== module) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <WorkbenchShell activeModule={activeModule} onModuleChange={(nextModule) => navigate(`/${nextModule}`)}>
      <Suspense fallback={<PageFallback />}>
        {activeModule === 'dashboard' && <DashboardPage />}
        {activeModule === 'alerts' && <AlertsCenterPage />}
        {activeModule === 'automation' && <AutomationCenterPage />}
        {activeModule === 'quant' && <QuantLabPage />}
        {activeModule === 'quant-lab' && <QuantLabPage />}
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
      </Suspense>
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
