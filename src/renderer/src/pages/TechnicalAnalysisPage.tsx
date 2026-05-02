import React, { useMemo, useState } from 'react'
import { useI18n } from '@/i18n'
import { Button } from '@/components/ui/button'
import { Loader2, Orbit, Sparkles } from 'lucide-react'

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
  const [phaseIndex, setPhaseIndex] = useState(0)
  const [message, setMessage] = useState<string | null>(null)

  const phases = useMemo(
    () => [
      t('technicalAnalysis.phaseSync'),
      t('technicalAnalysis.phaseCompose'),
      t('technicalAnalysis.phaseWrap'),
      t('technicalAnalysis.phaseOpen'),
    ],
    [t]
  )

  const phase = useMemo(() => phases[phaseIndex] ?? phases[0], [phaseIndex, phases])

  const handleGenerateReport = async () => {
    if (generatingReport) {
      return
    }

    setGeneratingReport(true)
    setPhaseIndex(0)
    setMessage(null)

    const timer = window.setInterval(() => {
      setPhaseIndex((current) => (current + 1) % phases.length)
    }, 900)

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

      setPhaseIndex(phases.length - 1)
      setMessage(t('technicalAnalysis.opening'))
      await window.electron.openExternal(fileUrl)
    } catch (err) {
      console.error(err)
      setMessage(err instanceof Error ? err.message : t('technicalAnalysis.networkError'))
    } finally {
      window.clearInterval(timer)
      setGeneratingReport(false)
    }
  }

  return (
    <div className="relative flex h-full w-full items-center justify-center overflow-hidden bg-[#04111f] text-slate-100">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(34,211,238,0.18),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(250,204,21,0.12),transparent_24%)]" />
      <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.08)_1px,transparent_1px)] [background-size:36px_36px]" />

      <div className="relative z-10 flex w-full max-w-3xl flex-col items-center px-6 text-center">
        <div className="mb-6 inline-flex items-center gap-3 rounded-full border border-cyan-400/20 bg-slate-950/40 px-4 py-2 text-xs uppercase tracking-[0.35em] text-cyan-200/80 backdrop-blur-sm">
          <Sparkles className="h-4 w-4" />
          {t('technicalAnalysis.portal')}
        </div>

        <h1 className="max-w-4xl font-serif text-5xl font-semibold tracking-tight text-white md:text-7xl">
          {t('technicalAnalysis.title')}
        </h1>

        <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 md:text-lg">
          {t('technicalAnalysis.subtitle')}
        </p>

        <div className="mt-12 w-full rounded-[32px] border border-white/10 bg-slate-950/45 p-8 shadow-[0_30px_120px_rgba(2,6,23,0.65)] backdrop-blur-xl md:p-10">
          <div className="mx-auto flex max-w-xl flex-col items-center">
            <div className="relative mb-8 flex h-32 w-32 items-center justify-center">
              <div className={`absolute inset-0 rounded-full border border-cyan-400/25 ${generatingReport ? 'animate-ping' : ''}`} />
              <div className={`absolute inset-3 rounded-full border border-cyan-300/35 ${generatingReport ? 'animate-spin' : ''}`} style={{ animationDuration: '5s' }} />
              <div className="absolute inset-7 rounded-full bg-cyan-400/10 blur-xl" />
              <Orbit className={`relative z-10 h-14 w-14 text-cyan-300 ${generatingReport ? 'animate-spin' : ''}`} style={{ animationDuration: '3s' }} />
            </div>

            <Button
              size="lg"
              onClick={handleGenerateReport}
              disabled={generatingReport}
              className="h-16 w-full rounded-2xl border border-cyan-300/30 bg-cyan-300/90 text-lg font-semibold text-slate-950 shadow-[0_18px_50px_rgba(103,232,249,0.32)] transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-90"
            >
              {generatingReport ? <Loader2 className="mr-3 h-5 w-5 animate-spin" /> : null}
              {generatingReport ? t('technicalAnalysis.generating') : t('technicalAnalysis.generate')}
            </Button>

            <div className="mt-6 min-h-14 text-sm tracking-[0.2em] text-slate-300/85 uppercase">
              {generatingReport ? phase : t('technicalAnalysis.standby')}
            </div>

            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className={`h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-amber-300 transition-all duration-700 ${generatingReport ? 'w-full animate-pulse' : 'w-0'}`}
              />
            </div>

            <p className="mt-6 min-h-6 text-sm text-slate-400">
              {message || t('technicalAnalysis.footer')}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
