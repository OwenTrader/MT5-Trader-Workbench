import { Activity, LayoutDashboard, Settings, Bell, TrendingUp, ShieldCheck, LineChart, Megaphone, ShoppingBag, BookOpen, Link2, HeartHandshake, Users } from 'lucide-react'
import { useI18n } from '@/i18n'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
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

  const primaryNavItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    { id: 'python-quant', label: t('nav.pythonQuant'), icon: LineChart },
    { id: 'price-alerts', label: t('nav.priceAlerts'), icon: Bell },
    { id: 'volatility', label: t('nav.volatility'), icon: TrendingUp },
    { id: 'indicator-alerts', label: t('nav.indicatorAlerts'), icon: LineChart },
    { id: 'risk-control', label: t('nav.riskControl'), icon: ShieldCheck },
    { id: 'order-center', label: t('nav.orderCenter'), icon: ShoppingBag },
    { id: 'tech-analysis', label: t('nav.technicalAnalysis'), icon: BookOpen },
    { id: 'order-broadcast', label: t('nav.orderBroadcast'), icon: Megaphone },
    { id: 'order-sync', label: t('nav.orderSync'), icon: Link2 },
  ]

  const copyTradingNavItems = [
    { id: 'account-list', label: t('nav.accountList'), icon: Users },
    { id: 'local-copy-trading', label: t('nav.localCopyTrading'), icon: Link2 },
  ]

  const secondaryNavItems = [
    { id: 'event-log', label: t('nav.eventLog'), icon: Activity },
    { id: 'sponsor', label: t('nav.sponsor'), icon: HeartHandshake },
    { id: 'settings', label: t('nav.settings'), icon: Settings },
  ]

  const renderMenuItems = (items: typeof primaryNavItems) => items.map((item) => {
    const Icon = item.icon

    return (
      <SidebarMenuItem key={item.id}>
        <SidebarMenuButton
          type="button"
          size="lg"
          className="gap-3 px-3 text-base group-data-[collapsible=icon]:!size-12 group-data-[collapsible=icon]:!gap-0 group-data-[collapsible=icon]:!p-[14px] [&>svg]:size-5"
          tooltip={item.label}
          title={item.label}
          isActive={activeModule === item.id}
          onClick={() => onModuleChange(item.id)}
        >
          <Icon data-testid={`sidebar-icon-${item.id}`} />
          <span>{item.label}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  })

  return (
    <Sidebar collapsible="icon" className="border-r">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {renderMenuItems(primaryNavItems)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>{t('nav.group.localCopyTrading')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {renderMenuItems(copyTradingNavItems)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {renderMenuItems(secondaryNavItems)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
