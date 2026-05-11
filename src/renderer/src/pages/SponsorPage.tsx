import React from 'react'
import { HeartHandshake } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { developerContact } from '@/config/developer'
import { useI18n } from '@/i18n'

const tradingViewPlans = [
  { nameKey: 'sponsor.tradingViewPlans.essential.name', priceKey: 'sponsor.tradingViewPlans.essential.price' },
  { nameKey: 'sponsor.tradingViewPlans.plus.name', priceKey: 'sponsor.tradingViewPlans.plus.price' },
  { nameKey: 'sponsor.tradingViewPlans.premium.name', priceKey: 'sponsor.tradingViewPlans.premium.price' },
  { nameKey: 'sponsor.tradingViewPlans.expert.name', priceKey: 'sponsor.tradingViewPlans.expert.price' },
] as const

export const SponsorPage: React.FC = () => {
  const { t } = useI18n()

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader title={t('sponsor.title')} icon={HeartHandshake} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="border-primary/20 bg-gradient-to-br from-card via-card to-primary/5 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">{t('sponsor.buyMembership.title')}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">{t('sponsor.buyMembership.description')}</p>
            <div className="flex flex-col gap-3">
              {tradingViewPlans.map((plan) => (
                <div
                  key={plan.nameKey}
                  className="flex items-center justify-between rounded-xl border bg-background/70 px-4 py-3"
                >
                  <span className="font-medium">{t(plan.nameKey)}</span>
                  <span className="text-sm font-semibold text-primary">{t(plan.priceKey)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">{t('sponsor.customSupport.title')}</CardTitle>
          </CardHeader>
          <CardContent className="flex h-full flex-col gap-4">
            <p className="text-sm text-muted-foreground">{t('sponsor.customSupport.description')}</p>
            <div className="flex-1 rounded-xl border border-dashed bg-muted/30 p-4">
              {developerContact.length > 0 ? (
                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-foreground">
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
