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
      title: t('commandPalette.commands.dashboard'),
      category: t('commandPalette.categories.workspace'),
      icon: LayoutDashboard,
      action: () => {
        navigate('/dashboard')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-alerts',
      title: t('commandPalette.commands.alerts'),
      category: t('commandPalette.categories.workspace'),
      icon: Bell,
      action: () => {
        navigate('/alerts')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-automation',
      title: t('commandPalette.commands.automation'),
      category: t('commandPalette.categories.workspace'),
      icon: Link2,
      action: () => {
        navigate('/automation')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-quant',
      title: t('commandPalette.commands.quant'),
      category: t('commandPalette.categories.workspace'),
      icon: LineChart,
      action: () => {
        navigate('/quant')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-settings',
      title: t('commandPalette.commands.settings'),
      category: t('commandPalette.categories.workspace'),
      icon: Settings,
      action: () => {
        navigate('/settings')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-event-log',
      title: t('commandPalette.commands.eventLog'),
      category: t('commandPalette.categories.tools'),
      icon: Activity,
      action: () => {
        navigate('/event-log')
        onOpenChange(false)
      },
    },
    {
      id: 'nav-sponsor',
      title: t('commandPalette.commands.sponsor'),
      category: t('commandPalette.categories.tools'),
      icon: HeartHandshake,
      action: () => {
        navigate('/sponsor')
        onOpenChange(false)
      },
    },
    {
      id: 'action-overlay',
      title: t('commandPalette.commands.overlay'),
      category: t('commandPalette.categories.actions'),
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
      title: t('commandPalette.commands.switchLanguage', { target: locale === 'zh-CN' ? 'English' : '简体中文' }),
      category: t('commandPalette.categories.preferences'),
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
          <DialogTitle className="sr-only">{t('commandPalette.title')}</DialogTitle>
          <div className="flex items-center gap-2 border-b pb-3">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('commandPalette.placeholder')}
              className="border-0 focus-visible:ring-0 px-0 text-sm shadow-none"
              autoFocus
            />
          </div>
        </DialogHeader>

        <div className="max-h-[350px] overflow-y-auto p-2 space-y-1">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t('commandPalette.empty')}
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
          <span>{t('commandPalette.hint')}</span>
          <kbd className="rounded border bg-background px-1.5 py-0.5 text-[10px] font-mono">{t('commandPalette.esc')}</kbd>
        </div>
      </DialogContent>
    </Dialog>
  )
}
