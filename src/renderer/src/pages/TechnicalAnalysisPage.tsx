import React, { useState } from 'react'
import { useI18n } from '@/i18n'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { BarChart3, Loader2 } from 'lucide-react'

declare global {
  interface Window {
    electron: {
      openExternal: (target: string) => Promise<void>
      ipcRenderer: {
        send: (channel: string, data: unknown) => void
        invoke: (channel: string, ...args: unknown[]) => Promise<unknown>
        on: (channel: string, func: (...args: unknown[]) => void) => () => void
        removeListener: (channel: string, func: (...args: unknown[]) => void) => void
      }
    }
  }
}

type ReportResponse = {
  html?: string
  report_path?: string
  error?: string
}

export const TechnicalAnalysisPage: React.FC = () => {
  const { t } = useI18n()
  const [generatingReport, setGeneratingReport] = useState(false)

  const handleGenerateReport = async () => {
    if (generatingReport) {
      return
    }

    setGeneratingReport(true)

    try {
      const response = await fetch('http://127.0.0.1:8765/awakening/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'XAUUSD' })
      })

      const data = (await response.json()) as ReportResponse
      if (!response.ok) {
        throw new Error(data.error || t('technicalAnalysis.generateFailed'))
      }

      if (!data.report_path) {
        throw new Error(t('technicalAnalysis.missingPath'))
      }

      const normalizedPath = data.report_path.replace(/\\/g, '/')
      const fileUrl = normalizedPath.startsWith('file:///')
        ? normalizedPath
        : `file:///${normalizedPath}`

      await window.electron.openExternal(fileUrl)
    } catch (err) {
      console.error(err)
    } finally {
      setGeneratingReport(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader title={t('nav.technicalAnalysis')} icon={BarChart3} />

      <Button onClick={handleGenerateReport} disabled={generatingReport}>
        {generatingReport ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
        {generatingReport ? t('technicalAnalysis.generating') : t('technicalAnalysis.generate')}
      </Button>
    </div>
  )
}
