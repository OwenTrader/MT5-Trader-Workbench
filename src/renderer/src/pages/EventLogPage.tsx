import React, { useEffect } from 'react'
import { Activity, RefreshCw } from 'lucide-react'

import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useI18n } from '@/i18n'
import { cn } from '@/lib/utils'
import { useLocalCopyTradingStore } from '@/stores/local-copy-trading-store'
import { useOrderSyncStore } from '@/stores/order-sync-store'
import type { SyncedOrder } from '@/stores/order-sync-store'

type EventLogItem = {
  id: string
  source: string
  status: string
  summary: string
  detail: string
  timestamp: string | null
}

function formatDateTime(value: string | null) {
  if (!value) {
    return '-'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

function getSyncedOrderTimestamp(order: SyncedOrder) {
  return order.closed_at || order.opened_at || null
}

function getSyncedOrderDetail(order: SyncedOrder, fallback: string) {
  if (order.last_error) {
    return order.last_error
  }
  if (order.blocked_reason) {
    return order.blocked_reason
  }
  if (order.topstep_order_id) {
    return `TopStep #${order.topstep_order_id}`
  }
  return fallback
}

export function EventLogPage() {
  const { t } = useI18n()
  const { overview, fetchOverview, isLoading: copyTradingLoading } = useLocalCopyTradingStore()
  const { config, fetchConfig, isLoading: orderSyncLoading } = useOrderSyncStore()
  const isLoading = copyTradingLoading || orderSyncLoading

  useEffect(() => {
    void fetchOverview()
    void fetchConfig({ silent: true })
  }, [fetchConfig, fetchOverview])

  const items = React.useMemo<EventLogItem[]>(() => {
    const copyEvents = overview.events.map((event) => ({
      id: `copy-${event.id}`,
      source: t('eventLog.sources.localCopyTrading'),
      status: event.status,
      summary: `${event.symbol} #${event.position_id}`,
      detail: event.message,
      timestamp: event.created_at,
    }))

    const syncedOrders = config.synced_orders.map((order) => ({
      id: `sync-${order.mt5_ticket}-${order.status}`,
      source: t('eventLog.sources.orderSync'),
      status: order.status,
      summary: `${order.mt5_symbol} ${order.side.toUpperCase()} #${order.mt5_ticket}`,
      detail: getSyncedOrderDetail(order, t('eventLog.orderSynced')),
      timestamp: getSyncedOrderTimestamp(order),
    }))

    const orderSyncError = config.last_error
      ? [{
          id: 'order-sync-last-error',
          source: t('eventLog.sources.orderSync'),
          status: t('eventLog.status.error'),
          summary: t('eventLog.orderSyncRuntime'),
          detail: config.last_error,
          timestamp: config.last_checked_at,
        }]
      : []

    return [...copyEvents, ...syncedOrders, ...orderSyncError]
      .sort((left, right) => new Date(right.timestamp || 0).getTime() - new Date(left.timestamp || 0).getTime())
  }, [config.last_checked_at, config.last_error, config.synced_orders, overview.events, t])

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <PageHeader
        title={t('eventLog.title')}
        icon={Activity}
        actions={(
          <Button variant="outline" size="sm" onClick={() => { void fetchOverview(); void fetchConfig({ silent: true }) }} disabled={isLoading}>
            <RefreshCw data-icon="inline-start" className={cn(isLoading && 'animate-spin')} />
            {t('eventLog.refresh')}
          </Button>
        )}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t('eventLog.recentTitle')}</CardTitle>
          <div className="text-sm text-muted-foreground">{t('eventLog.description')}</div>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {t('eventLog.empty')}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('eventLog.columns.time')}</TableHead>
                  <TableHead>{t('eventLog.columns.source')}</TableHead>
                  <TableHead>{t('eventLog.columns.status')}</TableHead>
                  <TableHead>{t('eventLog.columns.event')}</TableHead>
                  <TableHead>{t('eventLog.columns.detail')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{formatDateTime(item.timestamp)}</TableCell>
                    <TableCell>{item.source}</TableCell>
                    <TableCell><Badge variant={item.status.toLowerCase() === 'error' ? 'destructive' : 'secondary'}>{item.status}</Badge></TableCell>
                    <TableCell className="font-medium">{item.summary}</TableCell>
                    <TableCell className="max-w-md text-muted-foreground">{item.detail}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
