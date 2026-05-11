import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { ShieldCheck } from 'lucide-react'

export const RiskControlPage: React.FC = () => {
  const { t } = useI18n()
  const [formData, setFormData] = useState({ margin_alert: 200, equity_alert: 1000 })

  useEffect(() => {
    fetch('http://127.0.0.1:8765/risk-control')
      .then((response) => response.json())
      .then((data) => setFormData(data))
      .catch(console.error)
  }, [])

  const handleSave = async () => {
    await fetch('http://127.0.0.1:8765/risk-control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    })
  }

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      <PageHeader title={t('riskControl.title')} icon={ShieldCheck} />
      
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t('riskControl.cardTitle')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-sm">{t('riskControl.marginAlert')}</Label>
            <Input
              type="number"
              value={formData.margin_alert}
              onChange={(event) => setFormData({ ...formData, margin_alert: parseFloat(event.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm">{t('riskControl.equityAlert')}</Label>
            <Input
              type="number"
              value={formData.equity_alert}
              onChange={(event) => setFormData({ ...formData, equity_alert: parseFloat(event.target.value) })}
            />
          </div>
          <Button variant="default" className="w-full" onClick={() => void handleSave()}>{t('riskControl.save')}</Button>
        </CardContent>
      </Card>
    </div>
  )
}
