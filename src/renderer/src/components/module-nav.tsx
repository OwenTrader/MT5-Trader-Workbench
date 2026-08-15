import {
  LayoutDashboard,
  Bell,
  Link2,
  LineChart,
  Settings,
  Activity,
  HeartHandshake,
} from 'lucide-react'
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

  const workspaceNavItems = [
    { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard, testId: 'sidebar-icon-dashboard' },
    { id: 'alerts', label: t('nav.alertsHub'), icon: Bell, testId: 'sidebar-icon-alerts' },
    { id: 'automation', label: t('nav.automationHub'), icon: Link2, testId: 'sidebar-icon-automation' },
    { id: 'quant', label: t('nav.quantLab'), icon: LineChart, testId: 'sidebar-icon-quant' },
  ]

  const systemNavItems = [
    { id: 'event-log', label: t('nav.eventLog'), icon: Activity, testId: 'sidebar-icon-event-log' },
    { id: 'sponsor', label: t('nav.sponsor'), icon: HeartHandshake, testId: 'sidebar-icon-sponsor' },
    { id: 'settings', label: t('nav.settings'), icon: Settings, testId: 'sidebar-icon-settings' },
  ]

  const isItemActive = (itemId: string) => {
    if (itemId === activeModule) return true
    if (itemId === 'alerts' && ['alerts', 'price-alerts', 'volatility', 'indicator-alerts', 'order-broadcast'].includes(activeModule)) return true
    if (itemId === 'automation' && ['automation', 'local-copy-trading', 'account-list', 'order-sync', 'risk-control', 'order-center'].includes(activeModule)) return true
    if (itemId === 'quant' && ['quant', 'quant-lab', 'python-quant', 'quant-backtest', 'data-management', 'trading-review', 'tech-analysis'].includes(activeModule)) return true
    return false
  }

  const renderMenuItems = (items: typeof workspaceNavItems) =>
    items.map((item) => {
      const Icon = item.icon
      const active = isItemActive(item.id)

      return (
        <SidebarMenuItem key={item.id}>
          <SidebarMenuButton
            type="button"
            size="lg"
            className="gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all group-data-[collapsible=icon]:!size-11 group-data-[collapsible=icon]:!gap-0 group-data-[collapsible=icon]:!p-2.5 [&>svg]:size-5 hover:bg-accent/80 hover:text-accent-foreground data-[active=true]:bg-primary/10 data-[active=true]:text-primary data-[active=true]:font-semibold"
            tooltip={item.label}
            title={item.label}
            isActive={active}
            onClick={() => onModuleChange(item.id)}
          >
            <Icon data-testid={item.testId} />
            <span className="truncate">{item.label}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      )
    })

  return (
    <Sidebar collapsible="icon" className="border-r bg-sidebar select-none">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs uppercase tracking-wider text-muted-foreground px-3 py-1 font-semibold">
            {t('nav.group.workspaces')}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1 px-2">
              {renderMenuItems(workspaceNavItems)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-xs uppercase tracking-wider text-muted-foreground px-3 py-1 font-semibold">
            {t('nav.group.systemSupport')}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1 px-2">
              {renderMenuItems(systemNavItems)}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
