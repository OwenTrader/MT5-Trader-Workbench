import React from 'react'
import { BookOpen } from 'lucide-react'
import { useI18n } from '@/i18n'
import { ModuleNav } from '@/components/module-nav'
import { Button } from '@/components/ui/button'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { toast } from 'sonner'

interface WorkbenchShellProps {
  activeModule: string
  onModuleChange: (module: string) => void
  children: React.ReactNode
}

export function WorkbenchShell({ activeModule, onModuleChange, children }: WorkbenchShellProps) {
  const { t, locale } = useI18n()

  const handleOpenUserGuide = async () => {
    try {
      await (window as any).electron?.openUserGuide?.(locale)
    } catch (error) {
      console.error('Failed to open user guide:', error)
      toast.error(t('help.openFailed'))
    }
  }

  return (
    <SidebarProvider>
      <div className="flex h-screen w-full overflow-hidden bg-background">
        <ModuleNav activeModule={activeModule} onModuleChange={onModuleChange} />

        <SidebarInset className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between border-b bg-background/50 px-6 backdrop-blur-md">
            <div className="flex min-w-0 items-center gap-3">
              <SidebarTrigger />
              <h2 className="truncate text-lg font-semibold tracking-tight">{t('app.title')}</h2>
            </div>
            <Button variant="outline" size="sm" onClick={() => void handleOpenUserGuide()} title={t('help.userGuideHint')}>
              <BookOpen className="mr-2 h-4 w-4" />
              {t('help.userGuide')}
            </Button>
          </header>

          <main className="relative flex-1 overflow-y-auto overflow-x-hidden p-6">
            {children}
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}
