import { LayoutDashboard, Settings, Bell, TrendingUp, ShieldCheck, LineChart, Megaphone, ShoppingBag, BookOpen } from 'lucide-react'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

interface ModuleNavProps {
  activeModule: string
  onModuleChange: (module: string) => void
}

export const ModuleNav: React.FC<ModuleNavProps> = ({ activeModule, onModuleChange }) => {
  const { t } = useI18n()

  const navItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'price-alerts', label: t('nav.priceAlerts'), icon: Bell },
    { id: 'volatility', label: t('nav.volatility'), icon: TrendingUp },
    { id: 'indicator-alerts', label: t('nav.indicatorAlerts'), icon: LineChart },
    { id: 'risk-control', label: t('nav.riskControl'), icon: ShieldCheck },
    { id: 'order-center', label: t('nav.orderCenter'), icon: ShoppingBag },
    { id: 'tech-analysis', label: t('nav.technicalAnalysis'), icon: BookOpen },
    { id: 'order-broadcast', label: t('nav.orderBroadcast'), icon: Megaphone },
    { id: 'settings', label: t('nav.settings'), icon: Settings },
  ]

  return (
    <nav className="w-16 flex flex-col items-center py-4 bg-muted/30 border-r gap-4">
      {navItems.map((item) => {
        const Icon = item.icon
        return (
          <button
            key={item.id}
            onClick={() => onModuleChange(item.id)}
            className={cn(
              "p-3 rounded-lg transition-colors",
              activeModule === item.id 
                ? "bg-primary text-primary-foreground shadow-lg" 
                : "text-muted-foreground hover:bg-muted"
            )}
            title={item.label}
          >
            <Icon className="w-5 h-5" />
          </button>
        )
      })}
    </nav>
  )
}
