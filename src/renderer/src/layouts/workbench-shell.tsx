import React from 'react'
import { BookOpen } from 'lucide-react'
import { useI18n } from '@/i18n'
import { ModuleNav } from '@/components/module-nav'
import { Button } from '@/components/ui/button'
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
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar Navigation */}
      <ModuleNav activeModule={activeModule} onModuleChange={onModuleChange} />
      
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-14 border-b flex items-center justify-between px-6 bg-background/50 backdrop-blur-md z-10 shrink-0">
            <h2 className="font-semibold text-lg tracking-tight">{t('app.title')}</h2>
            <Button variant="outline" size="sm" onClick={() => void handleOpenUserGuide()} title={t('help.userGuideHint')}>
              <BookOpen className="mr-2 h-4 w-4" />
              {t('help.userGuide')}
            </Button>
          </header>
        
        <main className="flex-1 p-6 overflow-y-auto overflow-x-hidden relative">
          {children}
        </main>
      </div>
    </div>
  )
}
