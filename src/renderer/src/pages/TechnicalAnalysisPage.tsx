import { apiFetch } from '@/lib/api'
import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { BarChart3, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useSettingsStore } from '@/stores/settings-store'

type ReportResponse = {
  analysis_markdown?: string
  detail?: string
}

export const TechnicalAnalysisPage: React.FC = () => {
  const { t } = useI18n()
  const { settings, fetchSettings } = useSettingsStore()
  const [generatingReport, setGeneratingReport] = useState(false)
  const [analysis, setAnalysis] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void fetchSettings()
  }, [fetchSettings])

  const aiConfigured = Boolean(settings.ai_base_url.trim() && settings.ai_api_key.trim())

  const handleGenerateReport = async () => {
    if (generatingReport || !aiConfigured) {
      return
    }

    setGeneratingReport(true)
    setError(null)

    try {
      const response = await apiFetch('/awakening/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'XAUUSD' })
      })

      const data = (await response.json()) as ReportResponse
      if (!response.ok) {
        throw new Error(data.detail || t('technicalAnalysis.generateFailed'))
      }

      if (!data.analysis_markdown) {
        throw new Error(t('technicalAnalysis.generateFailed'))
      }

      setAnalysis(data.analysis_markdown)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : t('technicalAnalysis.networkError'))
    } finally {
      setGeneratingReport(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <PageHeader title={t('nav.technicalAnalysis')} icon={BarChart3} />

      <div className="max-w-4xl space-y-4">
        <p className="text-sm text-muted-foreground">{t('technicalAnalysis.subtitle')}</p>

        {!aiConfigured ? (
          <p className="text-sm font-medium text-destructive">{t('technicalAnalysis.missingAiConfig')}</p>
        ) : null}

        <Button onClick={handleGenerateReport} disabled={generatingReport || !aiConfigured}>
          {generatingReport ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {generatingReport ? t('technicalAnalysis.generating') : t('technicalAnalysis.generate')}
        </Button>

        <Card>
          <CardHeader>
            <CardTitle>{t('technicalAnalysis.resultTitle')}</CardTitle>
          </CardHeader>
          <CardContent>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            {!error && analysis ? (
              <pre className="whitespace-pre-wrap break-words text-sm leading-6">{analysis}</pre>
            ) : null}
            {!error && !analysis ? (
              <p className="text-sm text-muted-foreground">{t('technicalAnalysis.empty')}</p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
