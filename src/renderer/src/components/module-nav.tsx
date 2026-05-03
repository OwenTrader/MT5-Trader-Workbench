import { LayoutDashboard, Settings, Bell, TrendingUp, ShieldCheck, LineChart, Megaphone, ShoppingBag, BookOpen } from 'lucide-react'
import { useI18n } from '@/i18n'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

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
    <Sidebar collapsible="icon" aria-label="Main navigation" className="border-r">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {navItems.map((item) => {
                const Icon = item.icon

                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      type="button"
                      tooltip={item.label}
                      title={item.label}
                      isActive={activeModule === item.id}
                      onClick={() => onModuleChange(item.id)}
                      className="h-10 min-h-10 gap-3 px-3 transition-[width] group-data-[collapsible=icon]:!h-10 group-data-[collapsible=icon]:!w-10 group-data-[collapsible=icon]:!justify-center group-data-[collapsible=icon]:!gap-0 group-data-[collapsible=icon]:!overflow-hidden group-data-[collapsible=icon]:!p-0 group-data-[collapsible=icon]:[&>span]:hidden [&>svg]:size-5"
                    >
                      <Icon data-testid={`sidebar-icon-${item.id}`} className="size-5 shrink-0" />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
