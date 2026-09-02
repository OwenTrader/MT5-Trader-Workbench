import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  LayoutDashboard,
  Bell,
  Link2,
  LineChart,
  Settings,
  Activity,
  HeartHandshake,
  Eye,
  Languages,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onOpenChange }) => {
  const navigate = useNavigate()
  const { t, locale } = useI18n()
  const { updateSettings } = useSettingsStore()
  const [search, setSearch] = useState('')

  const commands = [
    {
      id: 'nav-dashboard',
      title: '交易工作台 (Trading Cockpit)',
      category: '工作区导航',
      icon: LayoutDashboard,
      action: () => {
        navigate('/dashboard')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-alerts',
      title: '智能告警中心 (Alerts Hub)',
      category: '工作区导航',
      icon: Bell,
      action: () => {
        navigate('/alerts')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-automation',
      title: '自动化与跟单中心 (Automation & Copy)',
      category: '工作区导航',
      icon: Link2,
      action: () => {
        navigate('/automation')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-quant',
      title: '量化与复盘实验室 (Quant Lab)',
      category: '工作区导航',
      icon: LineChart,
      action: () => {
        navigate('/quant')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-settings',
      title: '系统设置与日志 (Settings & Logs)',
      category: '工作区导航',
      icon: Settings,
      action: () => {
        navigate('/settings')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-event-log',
      title: '全景事件日志 (Event Log)',
      category: '快捷工具',
      icon: Activity,
      action: () => {
        navigate('/event-log')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-sponsor',
      title: '关于与赞助开发者 (Support Me)',
      category: '快捷工具',
      icon: HeartHandshake,
      action: () => {
        navigate('/sponsor')
        onOpenChange(false)
      },
    },
    {
      id: 'action-overlay',
      title: '切换桌面悬浮窗 (Toggle Overlay)',
      category: '快捷操作',
      icon: Eye,
      action: async () => {
        if ((window as any).electron?.ipcRenderer) {
          const isVis = await (window as any).electron.ipcRenderer.invoke('overlay:is-visible')
          await (window as any).electron.ipcRenderer.invoke('overlay:toggle-visible', !isVis)
        }
        onOpenChange(false)
      },
    },
    {
      id: 'action-lang',
      title: `切换系统语言 (${locale === 'zh-CN' ? 'Switch to English' : '切换至简体中文'})`,
      category: '偏好设置',
      icon: Languages,
      action: () => {
        void updateSettings({ language: locale === 'zh-CN' ? 'en' : 'zh-CN' })
        onOpenChange(false)
      },
    },
  ]

  const filteredCommands = commands.filter((cmd) =>
    cmd.title.toLowerCase().includes(search.toLowerCase()) ||
    cmd.category.toLowerCase().includes(search.toLowerCase())
  )

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onOpenChange])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 max-w-xl overflow-hidden border shadow-2xl">
        <DialogHeader className="p-4 pb-0">
          <DialogTitle className="sr-only">快捷指令面板</DialogTitle>
          <div className="flex items-center gap-2 border-b pb-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="输入工作区名称、功能或指令进行搜索..."
              className="border-0 focus-visible:ring-0 px-0 text-sm shadow-none"
              autoFocus
            />
          </div>
        </DialogHeader>

        <div className="max-h-[350px] overflow-y-auto p-2 space-y-1">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              未找到匹配的指令或工作区
            </div>
          ) : (
            filteredCommands.map((cmd) => {
              const Icon = cmd.icon
              return (
                <button
                  key={cmd.id}
                  type="button"
                  onClick={cmd.action}
                  className="flex w-full items-center justify-between rounded-md px-3 py-2.5 text-sm hover:bg-accent hover:text-accent-foreground text-left transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4 text-primary" />
                    <span className="font-medium">{cmd.title}</span>
                  </div>
                  <span className="text-xs text-muted-foreground font-normal">
                    {cmd.category}
                  </span>
                </button>
              )
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <span>提示: 使用方向键导航，Enter 确认选择</span>
          <kbd className="rounded border bg-background px-1.5 py-0.5 text-[10px] font-mono">ESC 退出</kbd>
        </div>
      </DialogContent>
    </Dialog>
  )
}
