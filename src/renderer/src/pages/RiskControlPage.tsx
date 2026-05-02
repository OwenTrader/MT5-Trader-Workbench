import React from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { ShieldCheck } from 'lucide-react'

export const RiskControlPage: React.FC = () => {
  const { t } = useI18n()

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
            <Input type="number" defaultValue="200" />
          </div>
          <div className="space-y-2">
            <Label className="text-sm">{t('riskControl.equityAlert')}</Label>
            <Input type="number" defaultValue="1000" />
          </div>
          <Button variant="default" className="w-full">{t('riskControl.save')}</Button>
        </CardContent>
      </Card>
    </div>
  )
}
