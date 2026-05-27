import React from 'react'
import { HeartHandshake } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { developerContact } from '@/config/developer'
import { useI18n } from '@/i18n'

export const SponsorPage: React.FC = () => {
  const { t } = useI18n()

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader title={t('sponsor.title')} icon={HeartHandshake} />

      <div className="max-w-3xl">
        <Card className="border-border/80 bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">{t('sponsor.customSupport.title')}</CardTitle>
          </CardHeader>
          <CardContent className="flex min-w-0 flex-col gap-4">
            <p className="text-sm text-muted-foreground">{t('sponsor.customSupport.description')}</p>
            <div className="min-w-0 overflow-hidden rounded-xl border border-dashed bg-muted/30 p-4">
              {developerContact.length > 0 ? (
                <pre className="min-w-0 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
                  {developerContact}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">{t('sponsor.customSupport.empty')}</p>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{t('sponsor.customSupport.configHint')}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
