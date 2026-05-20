import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

const RISK_CONTROL_URL = 'http://127.0.0.1:8765/risk-control'

function parsePositiveNumber(value: string) {
  if (value.trim() === '') {
    return null
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null
  }

  return parsed
}

export const RiskControlPage: React.FC = () => {
  const { t } = useI18n()
  const [formData, setFormData] = useState({ margin_alert: '200', equity_alert: '1000' })
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [hasLoadedSettings, setHasLoadedSettings] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    const loadRiskControl = async () => {
      setIsLoading(true)
      setHasLoadedSettings(false)
      setError(null)

      try {
        const response = await fetch(RISK_CONTROL_URL)
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`)
        }

        const data = await response.json()
        if (active) {
          setFormData({
            margin_alert: String(data.margin_alert ?? ''),
            equity_alert: String(data.equity_alert ?? ''),
          })
          setHasLoadedSettings(true)
        }
      } catch (loadError) {
        const message = t('riskControl.loadFailed')
        if (active) {
          setError(message)
        }
        toast.error(message)
        console.error('Failed to load risk control settings:', loadError)
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }

    void loadRiskControl()

    return () => {
      active = false
    }
  }, [])

  const handleSave = async () => {
    const marginAlert = parsePositiveNumber(formData.margin_alert)
    const equityAlert = parsePositiveNumber(formData.equity_alert)

    if (marginAlert === null || equityAlert === null) {
      setError(t('riskControl.invalidInput'))
      return
    }

    setIsSaving(true)
    setError(null)

    try {
      const response = await fetch(RISK_CONTROL_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          margin_alert: marginAlert,
          equity_alert: equityAlert,
        }),
      })

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      toast.success(t('riskControl.saveSuccess'))
    } catch (saveError) {
      const message = t('riskControl.saveFailed')
      setError(message)
      toast.error(message)
      console.error('Failed to save risk control settings:', saveError)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      <PageHeader title={t('riskControl.title')} icon={ShieldCheck} />
      
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('riskControl.cardTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground leading-6">
            {t('riskControl.description')}
          </p>
          <div className="rounded-lg border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {isLoading ? t('riskControl.loading') : hasLoadedSettings ? t('riskControl.ready') : t('riskControl.loadFailed')}
          </div>
          <div className="space-y-2">
            <Label className="text-sm">{t('riskControl.marginAlert')}</Label>
            <Input
              type="number"
              min={0}
              step="0.01"
              inputMode="decimal"
              disabled={isLoading || isSaving || !hasLoadedSettings}
              value={formData.margin_alert}
              onChange={(event) => {
                setFormData({ ...formData, margin_alert: event.target.value })
                setError(null)
              }}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm">{t('riskControl.equityAlert')}</Label>
            <Input
              type="number"
              min={0}
              step="0.01"
              inputMode="decimal"
              disabled={isLoading || isSaving || !hasLoadedSettings}
              value={formData.equity_alert}
              onChange={(event) => {
                setFormData({ ...formData, equity_alert: event.target.value })
                setError(null)
              }}
            />
          </div>
          {error && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive">
              {error}
            </div>
          )}
          <Button
            variant="default"
            className="w-full"
            onClick={() => void handleSave()}
            disabled={isLoading || isSaving || !hasLoadedSettings}
          >
            {isSaving ? t('riskControl.saving') : t('riskControl.save')}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
