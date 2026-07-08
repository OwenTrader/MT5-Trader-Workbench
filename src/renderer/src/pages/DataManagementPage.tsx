import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from 'sonner'
import { useDataManagementStore } from '@/stores/data-management-store'
import { Database, Trash2, RefreshCw } from 'lucide-react'

export function DataManagementPage() {
  const { t } = useI18n()
  const { summary, loading, fetchSummary, syncData, deleteData } = useDataManagementStore()
  
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [startDate, setStartDate] = useState('2024-01-01T00:00:00Z')
  const [endDate, setEndDate] = useState(new Date().toISOString())
  const [isSyncing, setIsSyncing] = useState(false)

  useEffect(() => {
    fetchSummary()
  }, [])

  const handleSync = async () => {
    if (!symbol || !startDate || !endDate) {
      toast.error(t('dataManagement.syncFailed'))
      return
    }
    setIsSyncing(true)
    try {
      const result = await syncData(symbol, timeframe, startDate, endDate)
      toast.success(t('dataManagement.syncSuccess', { count: result.count }))
      fetchSummary()
    } catch (err: any) {
      toast.error(err.message || t('dataManagement.syncFailed'))
    } finally {
      setIsSyncing(false)
    }
  }

  const handleDelete = async (s: string, tf: string) => {
    if (confirm(t('dataManagement.confirmDelete', { symbol: s, timeframe: tf }))) {
      try {
        await deleteData(s, tf)
        toast.success('Deleted successfully')
        fetchSummary()
      } catch (err: any) {
        toast.error('Failed to delete')
      }
    }
  }

  const formatTime = (ts: number) => {
    return new Date(ts * 1000).toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('dataManagement.title')}</h1>
        <p className="text-muted-foreground">{t('dataManagement.description')}</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              {t('dataManagement.syncTitle')}
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">Fetch history data from MT5</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t('dataManagement.symbol')}</Label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="e.g. XAUUSD" />
            </div>
            <div className="space-y-2">
              <Label>{t('dataManagement.timeframe')}</Label>
              <Select value={timeframe} onValueChange={setTimeframe}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="M1">M1</SelectItem>
                  <SelectItem value="M5">M5</SelectItem>
                  <SelectItem value="M15">M15</SelectItem>
                  <SelectItem value="M30">M30</SelectItem>
                  <SelectItem value="H1">H1</SelectItem>
                  <SelectItem value="H4">H4</SelectItem>
                  <SelectItem value="D1">D1</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('dataManagement.startDate')} (ISO)</Label>
              <Input value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('dataManagement.endDate')} (ISO)</Label>
              <Input value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <Button onClick={handleSync} disabled={isSyncing} className="w-full">
              {isSyncing ? t('dataManagement.syncing') : t('dataManagement.syncNow')}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              {t('dataManagement.listTitle')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading && !summary.length ? (
              <div className="text-center py-4">Loading...</div>
            ) : summary.length === 0 ? (
              <div className="text-center py-4 text-muted-foreground">{t('dataManagement.empty')}</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>TF</TableHead>
                    <TableHead>Count</TableHead>
                    <TableHead>Range</TableHead>
                    <TableHead className="w-[80px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {summary.map((row, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{row.symbol}</TableCell>
                      <TableCell>{row.timeframe}</TableCell>
                      <TableCell>{row.count}</TableCell>
                      <TableCell className="text-xs">
                        {formatTime(row.min_time)}<br/>
                        {formatTime(row.max_time)}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(row.symbol, row.timeframe)} title={t('dataManagement.delete')}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
