import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from 'sonner'
import { useTradingReviewStore } from '@/stores/trading-review-store'
import { PlayCircle, Trash2, ArrowRight, TrendingUp, TrendingDown, Clock, PauseCircle, FastForward } from 'lucide-react'
import { TradingChart } from '@/components/trading-chart'

export function TradingReviewPage() {
  const { t } = useI18n()
  const store = useTradingReviewStore()

  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [startDate, setStartDate] = useState('2024-01-01T00:00:00Z')
  const [endDate, setEndDate] = useState(new Date().toISOString())
  const [initialBalance, setInitialBalance] = useState(10000)
  
  const [lots, setLots] = useState(0.1)

  useEffect(() => {
    store.fetchSessions()
  }, [])

  // Auto playback loop
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (store.isPlaying && store.currentSession) {
      interval = setInterval(async () => {
        try {
          const res = await store.nextCandle(1)
          if (res.finished) {
            store.togglePlayback()
            toast.info(t('tradingReview.historyFinished'))
          }
        } catch (err: any) {
          toast.error(err.message)
          store.togglePlayback()
        }
      }, 1000 / store.playbackSpeed)
    }
    return () => clearInterval(interval)
  }, [store.isPlaying, store.playbackSpeed, store.currentSession])

  const handleCreateSession = async () => {
    try {
      const id = await store.createSession(symbol, timeframe, startDate, endDate, initialBalance)
      toast.success('Session created')
      store.fetchSessions()
      store.loadSessionState(id)
    } catch (err: any) {
      toast.error(err.message || 'Failed to create session')
    }
  }

  const handleDeleteSession = async (id: number) => {
    if (confirm(t('tradingReview.confirmDelete'))) {
      try {
        await store.deleteSession(id)
        toast.success('Session deleted')
        store.fetchSessions()
      } catch (err: any) {
        toast.error('Failed to delete')
      }
    }
  }

  const formatTime = (ts: number) => new Date(ts * 1000).toLocaleString()

  const handleNextCandle = async () => {
    try {
      const res = await store.nextCandle(1)
      if (res.finished) {
        toast.info(t('tradingReview.historyFinished'))
      }
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  const handleTrade = async (type: 'buy' | 'sell') => {
    if (!store.klines.length) return
    const currentPrice = type === 'buy' ? store.klines[store.klines.length - 1].close : store.klines[store.klines.length - 1].close
    const currentTime = store.klines[store.klines.length - 1].time
    try {
      await store.openTrade(type, lots, currentPrice, currentTime)
      toast.success(`Opened ${type} trade`)
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  const handleCloseTrade = async (tradeId: number) => {
    if (!store.klines.length) return
    const currentPrice = store.klines[store.klines.length - 1].close
    const currentTime = store.klines[store.klines.length - 1].time
    try {
      await store.closeTrade(tradeId, currentPrice, currentTime)
      toast.success('Trade closed')
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  // Workspace View
  if (store.currentSession) {
    const activeTrades = store.trades.filter(t => t.close_time === null)
    const closedTrades = store.trades.filter(t => t.close_time !== null)
    const lastCandle = store.klines[store.klines.length - 1]

    let floatingPnL = 0
    if (lastCandle) {
      activeTrades.forEach(t => {
        const diff = t.type === 'buy' ? lastCandle.close - t.open_price : t.open_price - lastCandle.close
        floatingPnL += diff * t.lots * 100000 // Simplified estimation
      })
    }

    return (
      <div className="space-y-6 flex flex-col h-[calc(100vh-8rem)]">
        <div className="flex justify-between items-center shrink-0">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('tradingReview.workspaceTitle')}</h1>
            <p className="text-muted-foreground">{store.currentSession.symbol} - {store.currentSession.timeframe}</p>
          </div>
          <Button variant="outline" onClick={() => useTradingReviewStore.setState({ currentSession: null, klines: [], trades: [] })}>
            Back to Sessions
          </Button>
        </div>

        <div className="grid grid-cols-4 gap-4 shrink-0">
          <Card>
            <CardHeader className="py-4"><CardTitle className="text-sm font-medium">{t('tradingReview.currentBalance')}</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">${store.currentSession.current_balance.toFixed(2)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="py-4"><CardTitle className="text-sm font-medium">{t('tradingReview.floatingPnL')}</CardTitle></CardHeader>
            <CardContent><div className={`text-2xl font-bold ${floatingPnL >= 0 ? 'text-green-500' : 'text-red-500'}`}>${floatingPnL.toFixed(2)}</div></CardContent>
          </Card>
          <Card className="col-span-2">
            <CardHeader className="py-4">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><Clock className="w-4 h-4"/> Time</CardTitle>
                <div className="text-lg">{lastCandle ? formatTime(lastCandle.time) : formatTime(store.currentSession.current_time)}</div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Button 
                  variant={store.isPlaying ? "default" : "outline"} 
                  className={store.isPlaying ? "bg-amber-600 hover:bg-amber-700 text-white" : ""}
                  onClick={store.togglePlayback}
                >
                  {store.isPlaying ? <><PauseCircle className="mr-2 h-4 w-4" /> Pause</> : <><PlayCircle className="mr-2 h-4 w-4" /> Auto Play</>}
                </Button>
                
                <div className="flex items-center gap-2 flex-1">
                  <FastForward className="h-4 w-4 text-muted-foreground" />
                  <Select value={store.playbackSpeed.toString()} onValueChange={(v) => store.setPlaybackSpeed(parseFloat(v))}>
                    <SelectTrigger className="w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1x Speed</SelectItem>
                      <SelectItem value="5">5x Speed</SelectItem>
                      <SelectItem value="10">10x Speed</SelectItem>
                      <SelectItem value="20">20x Speed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button onClick={handleNextCandle} disabled={store.isPlaying}>
                  <ArrowRight className="mr-2 h-4 w-4" /> Step Forward
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-3 gap-6 flex-1 min-h-0">
          <Card className="col-span-2 flex flex-col min-h-0">
            <CardHeader className="shrink-0"><CardTitle>Chart View</CardTitle></CardHeader>
            <CardContent className="flex-1 overflow-hidden p-0 rounded-b-lg border-t">
              <TradingChart klines={store.klines} trades={closedTrades} />
            </CardContent>
          </Card>

          <div className="space-y-6 flex flex-col min-h-0">
            <Card className="shrink-0">
              <CardHeader><CardTitle>{t('tradingReview.tradePanel')}</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('tradingReview.lots')}</Label>
                  <Input type="number" step="0.01" value={lots} onChange={e => setLots(parseFloat(e.target.value) || 0)} />
                </div>
                <div className="flex gap-2">
                  <Button className="flex-1 bg-green-600 hover:bg-green-700 text-white" onClick={() => handleTrade('buy')}>
                    <TrendingUp className="mr-2 h-4 w-4" /> {t('tradingReview.buy')}
                  </Button>
                  <Button className="flex-1 bg-red-600 hover:bg-red-700 text-white" onClick={() => handleTrade('sell')}>
                    <TrendingDown className="mr-2 h-4 w-4" /> {t('tradingReview.sell')}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="flex-1 flex flex-col min-h-0">
              <CardHeader className="shrink-0"><CardTitle>{t('tradingReview.tradesListTitle')}</CardTitle></CardHeader>
              <CardContent className="flex-1 overflow-auto">
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold mb-2">Active Trades</h3>
                    {activeTrades.length === 0 ? <p className="text-sm text-muted-foreground">{t('tradingReview.noActiveTrades')}</p> : (
                      <div className="space-y-2">
                        {activeTrades.map(t => (
                          <div key={t.id} className="flex justify-between items-center p-2 border rounded text-sm">
                            <div>
                              <span className={t.type === 'buy' ? 'text-green-500 font-bold' : 'text-red-500 font-bold'}>{t.type.toUpperCase()}</span> {t.lots} @ {t.open_price}
                            </div>
                            <Button size="sm" variant="outline" onClick={() => handleCloseTrade(t.id)}>{t('tradingReview.closePosition')}</Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">Closed Trades ({closedTrades.length})</h3>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {closedTrades.map(t => (
                        <div key={t.id} className="flex justify-between items-center p-2 border rounded text-sm bg-muted/50">
                          <div><span className={t.type === 'buy' ? 'text-green-500' : 'text-red-500'}>{t.type.toUpperCase()}</span> {t.lots}</div>
                          <div className={t.profit! >= 0 ? 'text-green-500' : 'text-red-500'}>${t.profit!.toFixed(2)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  // Sessions List View
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('tradingReview.title')}</h1>
        <p className="text-muted-foreground">{t('tradingReview.description')}</p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-1 h-fit">
          <CardHeader>
            <CardTitle>{t('tradingReview.newSession')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t('tradingReview.symbol')}</Label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('tradingReview.timeframe')}</Label>
              <Input value={timeframe} onChange={(e) => setTimeframe(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('dataManagement.startDate')} (ISO)</Label>
              <Input value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('dataManagement.endDate')} (ISO)</Label>
              <Input value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{t('tradingReview.initialBalance')}</Label>
              <Input type="number" value={initialBalance} onChange={(e) => setInitialBalance(parseFloat(e.target.value) || 0)} />
            </div>
            <Button onClick={handleCreateSession} className="w-full">
              {t('tradingReview.startReview')}
            </Button>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>{t('tradingReview.sessionList')}</CardTitle>
          </CardHeader>
          <CardContent>
            {store.loading && !store.sessions.length ? (
              <div className="text-center py-4">Loading...</div>
            ) : store.sessions.length === 0 ? (
              <div className="text-center py-4 text-muted-foreground">{t('tradingReview.emptySessions')}</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Timeframe</TableHead>
                    <TableHead>Start Time</TableHead>
                    <TableHead>Balance</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {store.sessions.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-medium">{s.symbol}</TableCell>
                      <TableCell>{s.timeframe}</TableCell>
                      <TableCell className="text-xs">{formatTime(s.start_time)}</TableCell>
                      <TableCell>${s.current_balance.toFixed(2)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" onClick={() => store.loadSessionState(s.id)} className="mr-2">
                          {t('tradingReview.resume')}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDeleteSession(s.id)}>
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
