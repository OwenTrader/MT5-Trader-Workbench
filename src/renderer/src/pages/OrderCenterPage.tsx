import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { useOrderStore } from '@/stores/order-store'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/page-header'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ShoppingBag, Calendar, TrendingUp, TrendingDown, DollarSign, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'

export const OrderCenterPage: React.FC = () => {
  const { t } = useI18n()
  const { 
    overview, 
    dailyStats, 
    fetchOverview, 
    fetchDailyStats, 
    dateRange, 
    setDateRange, 
    isOverviewLoading, 
    isDailyLoading 
  } = useOrderStore()
  
  const [localFrom, setLocalFrom] = useState(dateRange.from)
  const [localTo, setLocalTo] = useState(dateRange.to)

  useEffect(() => {
    fetchOverview()
    fetchDailyStats()
  }, [])

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault()
    setDateRange({ from: localFrom, to: localTo })
    fetchDailyStats(localFrom, localTo)
  }

  return (
    <div className="h-full flex flex-col gap-6">
      <PageHeader
        title={t('orderCenter.title')}
        icon={ShoppingBag}
        actions={isDailyLoading ? <Loader2 className="w-4 h-4 animate-spin text-primary" /> : null}
      />

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Left Panel: Overview & Filters */}
        <div className="md:col-span-4 flex min-h-0 flex-col">
          <ScrollArea className="flex-1">
            <div className="flex flex-col gap-6 pr-3">
              {/* Performance Overview */}
              <div className="grid grid-cols-1 gap-4">
                <StatCard 
                  title={t('orderCenter.today')} 
                  value={overview.today} 
                  icon={<DollarSign className="w-4 h-4" />} 
                  loading={isOverviewLoading}
                />
                <StatCard 
                  title={t('orderCenter.week')} 
                  value={overview.week} 
                  icon={<TrendingUp className="w-4 h-4" />} 
                  loading={isOverviewLoading}
                />
                <StatCard 
                  title={t('orderCenter.month')} 
                  value={overview.month} 
                  icon={<TrendingDown className="w-4 h-4" />} 
                  loading={isOverviewLoading}
                />
              </div>

              {/* Filters */}
              <Card>
                <CardContent className="p-6">
                  <h3 className="font-semibold mb-4 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-primary" />
                    {t('orderCenter.dateQuery')}
                  </h3>
                  <form onSubmit={handleFilter} className="space-y-4">
                    <div className="space-y-2">
                      <Label>{t('orderCenter.startDate')}</Label>
                      <Input type="date" value={localFrom} onChange={(e) => setLocalFrom(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('orderCenter.endDate')}</Label>
                      <Input type="date" value={localTo} onChange={(e) => setLocalTo(e.target.value)} />
                    </div>
                    <Button type="submit" className="w-full" disabled={isDailyLoading}>
                      {isDailyLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                      {t('orderCenter.query')}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>
          </ScrollArea>
        </div>

        {/* Right Panel: Daily Table */}
        <Card className="md:col-span-8 flex flex-col overflow-hidden">
          <div className="p-4 border-b bg-muted/20 flex justify-between items-center">
            <h3 className="font-semibold text-sm">{t('orderCenter.detailsTitle')}</h3>
            <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium tracking-wider">
              {t('orderCenter.entries', { count: dailyStats.length })}
            </span>
          </div>
          <ScrollArea className="flex-1">
            <div className="relative min-h-full p-4">
              {isDailyLoading && (
                <div className="absolute inset-x-0 top-0 h-1 z-20">
                  <div className="h-full bg-primary/10 overflow-hidden">
                    <div className="h-full bg-primary animate-progress-indeterminate w-full origin-left" />
                  </div>
                </div>
              )}
              
              <Table>
                <TableHeader className="bg-muted/40 sticky top-0 z-10">
                  <TableRow>
                    <TableHead className="w-[120px]">{t('orderCenter.date')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.totalLots')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.minMax')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.trades')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.profit')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.profitPct')}</TableHead>
                    <TableHead className="text-right">{t('orderCenter.balance')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dailyStats.length === 0 && !isDailyLoading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-[400px] text-center text-muted-foreground">
                        <div className="flex flex-col items-center gap-2 opacity-40">
                          <ShoppingBag className="w-12 h-12" />
                          <p className="text-sm">{t('orderCenter.empty')}</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    dailyStats.map((stat) => (
                      <TableRow key={stat.date} className="group hover:bg-muted/30">
                        <TableCell className="font-medium whitespace-nowrap">{stat.date}</TableCell>
                        <TableCell className="text-right font-mono">{stat.total_lots.toFixed(2)}</TableCell>
                        <TableCell className="text-right text-[10px] text-muted-foreground font-mono">
                          {stat.min_lot.toFixed(2)} / {stat.max_lot.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-right font-mono">{stat.trades_count}</TableCell>
                        <TableCell className={cn(
                          "text-right font-bold font-mono",
                          stat.profit >= 0 ? "text-green-500" : "text-red-500"
                        )}>
                          {stat.profit > 0 ? '+' : ''}{stat.profit.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </TableCell>
                        <TableCell className={cn(
                          "text-right font-mono",
                          stat.profit_pct >= 0 ? "text-green-500/80" : "text-red-500/80"
                        )}>
                          {stat.profit_pct.toFixed(2)}%
                        </TableCell>
                        <TableCell className="text-right font-mono text-muted-foreground">
                          {stat.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </ScrollArea>
        </Card>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number
  icon: React.ReactNode
  loading?: boolean
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, loading }) => (
  <Card className="overflow-hidden relative group">
    <CardContent className="p-6">
      <div className="flex justify-between items-start">
        <div className="relative z-10">
          <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">{title}</p>
          {loading ? (
             <div className="h-8 w-24 bg-muted animate-pulse rounded mt-1" />
          ) : (
            <h3 className={cn(
              "text-2xl font-bold tracking-tight",
              value >= 0 ? "text-green-500" : "text-red-500"
            )}>
              {value > 0 ? '+' : ''}{value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </h3>
          )}
        </div>
        <div className="p-2.5 rounded-xl bg-primary/10 text-primary group-hover:scale-110 transition-transform">
          {icon}
        </div>
      </div>
    </CardContent>
    <div className={cn(
      "absolute bottom-0 left-0 h-1 bg-current transition-all duration-500 opacity-20",
      value >= 0 ? "text-green-500 w-full" : "text-red-500 w-full"
    )} />
  </Card>
)
