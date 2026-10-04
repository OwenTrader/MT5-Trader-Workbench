import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Eye, TrendingUp, Sparkles } from 'lucide-react'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'

interface WatchlistCardProps {
  selectedSymbol: string
  onSelectSymbol: (symbol: string) => void
  isOverlayVisible: boolean
  onToggleOverlay: () => void
}

interface DefaultSymbol {
  symbol: string
  name: string
  category: 'Forex' | 'Metals' | 'Crypto' | 'Indices'
  typicalSpread: string
}

const DEFAULT_SYMBOLS: DefaultSymbol[] = [
  { symbol: 'XAUUSD', name: 'Spot Gold / US Dollar', category: 'Metals', typicalSpread: '15-25' },
  { symbol: 'EURUSD', name: 'Euro / US Dollar', category: 'Forex', typicalSpread: '0.8-1.5' },
  { symbol: 'GBPUSD', name: 'British Pound / US Dollar', category: 'Forex', typicalSpread: '1.2-2.0' },
  { symbol: 'USDJPY', name: 'US Dollar / Japanese Yen', category: 'Forex', typicalSpread: '0.9-1.6' },
  { symbol: 'BTCUSD', name: 'Bitcoin / US Dollar', category: 'Crypto', typicalSpread: '20-40' },
  { symbol: 'US30', name: 'Dow Jones Industrial 30', category: 'Indices', typicalSpread: '1.5-3.0' },
]

export const WatchlistCard: React.FC<WatchlistCardProps> = ({
  selectedSymbol,
  onSelectSymbol,
  isOverlayVisible,
  onToggleOverlay,
}) => {
  const { t } = useI18n()
  return (
    <Card className="shadow-sm border h-full flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between py-3.5 px-5 border-b bg-card/50">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm font-semibold">{t('dashboard.watchlist.title')}</CardTitle>
        </div>

        <Button
          variant={isOverlayVisible ? "default" : "outline"}
          size="sm"
          onClick={onToggleOverlay}
          className="h-8 gap-1.5 text-xs font-medium"
        >
          <Eye className="h-3.5 w-3.5" />
          <span>{isOverlayVisible ? t('dashboard.watchlist.hideOverlay') : t('dashboard.watchlist.showOverlay')}</span>
        </Button>
      </CardHeader>

      <CardContent className="p-3 flex-1 flex flex-col justify-between">
        <div className="space-y-1.5">
          {DEFAULT_SYMBOLS.map((item) => {
            const isSelected = selectedSymbol === item.symbol

            return (
              <div
                key={item.symbol}
                onClick={() => onSelectSymbol(item.symbol)}
                className={cn(
                  "flex items-center justify-between p-2.5 rounded-lg border text-sm cursor-pointer transition-all",
                  isSelected
                    ? "bg-primary/10 border-primary/40 shadow-sm"
                    : "hover:bg-muted/50 border-transparent"
                )}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    isSelected ? "bg-primary" : "bg-muted-foreground/30"
                  )} />
                  <div>
                    <div className="font-bold font-mono leading-none">{item.symbol}</div>
                    <div className="text-xs text-muted-foreground mt-1">{item.name}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[11px] font-normal px-1.5 py-0.5">
                    {item.category}
                  </Badge>
                  {isSelected && (
                    <Badge variant="default" className="text-[11px] px-1.5 py-0.5 bg-primary text-primary-foreground">
                      {t('dashboard.watchlist.active')}
                    </Badge>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-3 pt-2.5 border-t text-xs text-muted-foreground flex items-center justify-between px-1">
          <span className="flex items-center gap-1">
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            <span>{t('dashboard.watchlist.syncHint')}</span>
          </span>
          <span className="font-mono text-[11px]">{t('dashboard.watchlist.count')}</span>
        </div>
      </CardContent>
    </Card>
  )
}
