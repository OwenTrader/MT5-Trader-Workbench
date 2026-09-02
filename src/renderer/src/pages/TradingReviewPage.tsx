import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useI18n } from '@/i18n'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import {
  useTradingReviewStore,
  calculatePerformanceMetrics,
  calculateFloatingPnL,
} from '@/stores/trading-review-store'
import { apiFetch } from '@/lib/api'
import {
  PlayCircle,
  Trash2,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Clock,
  PauseCircle,
  FastForward,
  Keyboard,
  BarChart2,
  Layers,
  Sparkles,
  Percent,
  DollarSign,
  ShieldAlert,
} from 'lucide-react'
import { TradingChart } from '@/components/trading-chart'

interface CachedDataset {
  symbol: string
  timeframe: string
  count: number
  min_time: number
  max_time: number
}

export function TradingReviewPage() {
  const { t } = useI18n()
  const store = useTradingReviewStore()

  // Form states for creating new session
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M15')
  const [startDate, setStartDate] = useState('2024-01-01T00:00:00Z')
  const [endDate, setEndDate] = useState(new Date().toISOString())
  const [initialBalance, setInitialBalance] = useState(10000)

  // Trade execution inputs
  const [lots, setLots] = useState(0.1)
  const [slPrice, setSlPrice] = useState<string>('')
  const [tpPrice, setTpPrice] = useState<string>('')

  // Chart toggles
  const [showEMA, setShowEMA] = useState(true)
  const [showVolume, setShowVolume] = useState(true)

  // Local cached data summaries
  const [cachedDatasets, setCachedDatasets] = useState<CachedDataset[]>([])

  useEffect(() => {
    store.fetchSessions()
    loadCachedDatasets()
  }, [])

  const loadCachedDatasets = async () => {
    try {
      const res = await apiFetch('/data-management/summary')
      if (res.ok) {
        const data = await res.json()
        setCachedDatasets(data)
      }
    } catch {
      // ignore
    }
  }

  const handleSelectCachedDataset = (val: string) => {
    const [dsSymbol, dsTF] = val.split('__')
    const found = cachedDatasets.find((d) => d.symbol === dsSymbol && d.timeframe === dsTF)
    if (found) {
      setSymbol(found.symbol)
      setTimeframe(found.timeframe)
      setStartDate(new Date(found.min_time * 1000).toISOString())
      setEndDate(new Date(found.max_time * 1000).toISOString())
      toast.success(t('tradingReview.cachedDataHint'))
    }
  }

  // Next candle step helper
  const handleNextCandle = useCallback(async (limit = 1) => {
    try {
      const res = await store.nextCandle(limit)
      if (res.triggeredCount > 0) {
        toast.info(t('tradingReview.autoTriggered', { count: res.triggeredCount }))
      }
      if (res.finished) {
        toast.info(t('tradingReview.historyFinished'))
      }
    } catch (err: any) {
      toast.error(err.message)
    }
  }, [store, t])

  // Trade execution helper
  const handleTrade = useCallback(
    async (type: 'buy' | 'sell') => {
      if (!store.klines.length) return
      const currentCandle = store.klines[store.klines.length - 1]
      const currentPrice = currentCandle.close
      const currentTime = currentCandle.time
      const sl = slPrice ? parseFloat(slPrice) : undefined
      const tp = tpPrice ? parseFloat(tpPrice) : undefined

      try {
        await store.openTrade(type, lots, currentPrice, currentTime, sl, tp)
        toast.success(t('tradingReview.openTradeSuccess', { type }))
      } catch (err: any) {
        toast.error(err.message || t('tradingReview.openTradeFailed'))
      }
    },
    [store, lots, slPrice, tpPrice, t]
  )

  const handleCloseAllTrades = useCallback(async () => {
    if (!store.klines.length) return
    const currentCandle = store.klines[store.klines.length - 1]
    try {
      await store.closeAllTrades(currentCandle.close, currentCandle.time)
      toast.success(t('tradingReview.closeTradeSuccess'))
    } catch (err: any) {
      toast.error(err.message || t('tradingReview.closeTradeFailed'))
    }
  }, [store, t])

  // Global Replay Hotkeys
  useEffect(() => {
    if (!store.currentSession) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)

      if (e.code === 'Space') {
        if (!isInput) {
          e.preventDefault()
          store.togglePlayback()
        }
      } else if (e.code === 'ArrowRight') {
        if (!isInput) {
          e.preventDefault()
          const count = e.shiftKey ? 10 : 1
          handleNextCandle(count)
        }
      } else if (e.key === 'b' || e.key === 'B') {
        if (!isInput) {
          e.preventDefault()
          handleTrade('buy')
        }
      } else if (e.key === 's' || e.key === 'S') {
        if (!isInput) {
          e.preventDefault()
          handleTrade('sell')
        }
      } else if (e.key === 'c' || e.key === 'C') {
        if (!isInput) {
          e.preventDefault()
          handleCloseAllTrades()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [store.currentSession, handleNextCandle, handleTrade, handleCloseAllTrades])

  // Auto playback loop
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (store.isPlaying && store.currentSession) {
      interval = setInterval(async () => {
        try {
          const res = await store.nextCandle(1)
          if (res.triggeredCount > 0) {
            toast.info(t('tradingReview.autoTriggered', { count: res.triggeredCount }))
          }
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
  }, [store.isPlaying, store.playbackSpeed, store.currentSession, t])

  const handleCreateSession = async () => {
    try {
      const id = await store.createSession(symbol, timeframe, startDate, endDate, initialBalance)
      toast.success(t('tradingReview.sessionCreated'))
      await store.fetchSessions()
      await store.loadSessionState(id)
    } catch (err: any) {
      toast.error(err.message || t('tradingReview.sessionCreateFailed'))
    }
  }

  const handleDeleteSession = async (id: number) => {
    if (confirm(t('tradingReview.confirmDelete'))) {
      try {
        await store.deleteSession(id)
        toast.success(t('tradingReview.sessionDeleted'))
        store.fetchSessions()
      } catch {
        toast.error(t('tradingReview.deleteFailed'))
      }
    }
  }

  const formatTime = (ts: number) => new Date(ts * 1000).toLocaleString()

  const handleCloseTrade = async (tradeId: number) => {
    if (!store.klines.length) return
    const currentCandle = store.klines[store.klines.length - 1]
    try {
      await store.closeTrade(tradeId, currentCandle.close, currentCandle.time)
      toast.success(t('tradingReview.closeTradeSuccess'))
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  // Active Workspace Calculations
  const activeTrades = useMemo(
    () => store.trades.filter((t) => t.close_time === null),
    [store.trades]
  )
  const closedTrades = useMemo(
    () => store.trades.filter((t) => t.close_time !== null),
    [store.trades]
  )
  const lastCandle = store.klines[store.klines.length - 1]

  const floatingPnL = useMemo(() => {
    if (!store.currentSession || !lastCandle) return 0
    return calculateFloatingPnL(store.currentSession.symbol, activeTrades, lastCandle.close)
  }, [store.currentSession, lastCandle, activeTrades])

  const metrics = useMemo(() => {
    if (!store.currentSession) return null
    return calculatePerformanceMetrics(store.trades, store.currentSession.initial_balance)
  }, [store.trades, store.currentSession])

  // Calculated R:R preview
  const rrRatioPreview = useMemo(() => {
    if (!lastCandle || !slPrice || !tpPrice) return null
    const entry = lastCandle.close
    const sl = parseFloat(slPrice)
    const tp = parseFloat(tpPrice)
    if (isNaN(sl) || isNaN(tp)) return null

    // If buy
    if (tp > entry && sl < entry) {
      const risk = entry - sl
      const reward = tp - entry
      const ratio = risk > 0 ? (reward / risk).toFixed(2) : 'N/A'
      return `Buy 1 : ${ratio}`
    }
    // If sell
    if (tp < entry && sl > entry) {
      const risk = sl - entry
      const reward = entry - tp
      const ratio = risk > 0 ? (reward / risk).toFixed(2) : 'N/A'
      return `Sell 1 : ${ratio}`
    }
    return null
  }, [lastCandle, slPrice, tpPrice])

  // ----------------------------------------------------
  // Replay Workspace View
  // ----------------------------------------------------
  if (store.currentSession) {
    return (
      <div className="space-y-4 flex flex-col h-[calc(100vh-7.5rem)]">
        {/* Top Header */}
        <div className="flex justify-between items-center shrink-0">
          <div className="flex items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight">{t('tradingReview.workspaceTitle')}</h1>
                <Badge variant="secondary" className="font-mono text-xs">
                  {store.currentSession.symbol} · {store.currentSession.timeframe}
                </Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden lg:flex items-center gap-1.5 px-3 py-1 bg-muted/60 rounded-md border text-xs text-muted-foreground">
              <Keyboard className="w-3.5 h-3.5 text-primary" />
              <span>{t('tradingReview.hotkeyGuide')}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => useTradingReviewStore.setState({ currentSession: null, klines: [], trades: [] })}
            >
              {t('tradingReview.backToSessions')}
            </Button>
          </div>
        </div>

        {/* Top Metric & Playback Cards */}
        <div className="grid grid-cols-4 gap-4 shrink-0">
          <Card className="py-2">
            <CardHeader className="py-1 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                {t('tradingReview.currentBalance')}
              </CardTitle>
            </CardHeader>
            <CardContent className="py-1 px-4">
              <div className="text-xl font-bold font-mono">
                ${store.currentSession.current_balance.toFixed(2)}
              </div>
            </CardContent>
          </Card>

          <Card className="py-2">
            <CardHeader className="py-1 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                {t('tradingReview.floatingPnL')}
              </CardTitle>
            </CardHeader>
            <CardContent className="py-1 px-4">
              <div
                className={`text-xl font-bold font-mono ${
                  floatingPnL >= 0 ? 'text-emerald-500' : 'text-rose-500'
                }`}
              >
                {floatingPnL >= 0 ? `+$${floatingPnL.toFixed(2)}` : `-$${Math.abs(floatingPnL).toFixed(2)}`}
              </div>
            </CardContent>
          </Card>

          <Card className="col-span-2 py-2">
            <CardHeader className="py-1 px-4">
              <div className="flex justify-between items-center">
                <CardTitle className="text-xs font-medium flex items-center gap-1.5 text-muted-foreground">
                  <Clock className="w-3.5 h-3.5 text-primary" />
                  <span>{t('tradingReview.timeProgress', { time: '' })}</span>
                </CardTitle>
                <div className="text-xs font-mono font-medium">
                  {lastCandle ? formatTime(lastCandle.time) : formatTime(store.currentSession.current_time)}
                </div>
              </div>
            </CardHeader>
            <CardContent className="py-1 px-4">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant={store.isPlaying ? 'default' : 'outline'}
                  className={store.isPlaying ? 'bg-amber-600 hover:bg-amber-700 text-white h-8' : 'h-8'}
                  onClick={store.togglePlayback}
                >
                  {store.isPlaying ? (
                    <>
                      <PauseCircle className="mr-1.5 h-4 w-4" /> {t('tradingReview.pause')}
                    </>
                  ) : (
                    <>
                      <PlayCircle className="mr-1.5 h-4 w-4" /> {t('tradingReview.autoPlay')}
                    </>
                  )}
                </Button>

                <div className="flex items-center gap-1">
                  <FastForward className="h-3.5 w-3.5 text-muted-foreground" />
                  <Select
                    value={store.playbackSpeed.toString()}
                    onValueChange={(v) => store.setPlaybackSpeed(parseFloat(v))}
                  >
                    <SelectTrigger className="w-[85px] h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">{t('tradingReview.speed1x')}</SelectItem>
                      <SelectItem value="5">{t('tradingReview.speed5x')}</SelectItem>
                      <SelectItem value="10">{t('tradingReview.speed10x')}</SelectItem>
                      <SelectItem value="20">{t('tradingReview.speed20x')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() => handleNextCandle(1)}
                  disabled={store.isPlaying}
                >
                  <ArrowRight className="mr-1 h-3.5 w-3.5" /> {t('tradingReview.stepForward')}
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs"
                  onClick={() => handleNextCandle(10)}
                  disabled={store.isPlaying}
                >
                  +10
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Chart + Trading Cockpit Area */}
        <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
          {/* Left Chart Area (8 cols) */}
          <Card className="col-span-8 flex flex-col min-h-0 overflow-hidden border">
            <CardHeader className="py-2.5 px-4 shrink-0 flex flex-row items-center justify-between border-b bg-muted/20">
              <div className="flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-primary" />
                <CardTitle className="text-sm font-semibold">{t('tradingReview.chartView')}</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={showEMA ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-7 text-xs px-2.5"
                  onClick={() => setShowEMA(!showEMA)}
                >
                  <Layers className="w-3 h-3 mr-1" />
                  {t('tradingReview.showEMA')}
                </Button>
                <Button
                  variant={showVolume ? 'secondary' : 'ghost'}
                  size="sm"
                  className="h-7 text-xs px-2.5"
                  onClick={() => setShowVolume(!showVolume)}
                >
                  {t('tradingReview.showVolume')}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden p-0 relative">
              <TradingChart
                klines={store.klines}
                trades={store.trades}
                showEMA={showEMA}
                showVolume={showVolume}
              />
            </CardContent>
          </Card>

          {/* Right Trading Cockpit & Analytics (4 cols) */}
          <div className="col-span-4 flex flex-col gap-4 min-h-0 overflow-hidden">
            {/* Quick Order Panel */}
            <Card className="shrink-0 border shadow-sm">
              <CardHeader className="py-2.5 px-4 border-b bg-muted/20">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-primary" />
                    {t('tradingReview.tradePanel')}
                  </CardTitle>
                  {rrRatioPreview && (
                    <Badge variant="outline" className="text-xs font-mono border-primary/40 text-primary">
                      {rrRatioPreview}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="p-3.5 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">{t('tradingReview.lots')}</Label>
                    <Input
                      type="number"
                      step="0.01"
                      className="h-8 text-xs font-mono"
                      value={lots}
                      onChange={(e) => setLots(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">{t('tradingReview.sl')}</Label>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder="SL"
                      className="h-8 text-xs font-mono"
                      value={slPrice}
                      onChange={(e) => setSlPrice(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">{t('tradingReview.tp')}</Label>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder="TP"
                      className="h-8 text-xs font-mono"
                      value={tpPrice}
                      onChange={(e) => setTpPrice(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white h-9 text-xs font-semibold"
                    onClick={() => handleTrade('buy')}
                  >
                    <TrendingUp className="mr-1.5 h-3.5 w-3.5" /> {t('tradingReview.buy')}
                  </Button>
                  <Button
                    className="flex-1 bg-rose-600 hover:bg-rose-700 text-white h-9 text-xs font-semibold"
                    onClick={() => handleTrade('sell')}
                  >
                    <TrendingDown className="mr-1.5 h-3.5 w-3.5" /> {t('tradingReview.sell')}
                  </Button>
                </div>

                {activeTrades.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full h-7 text-xs text-destructive hover:bg-destructive/10"
                    onClick={handleCloseAllTrades}
                  >
                    <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                    {t('tradingReview.closeAll')} ({activeTrades.length})
                  </Button>
                )}
              </CardContent>
            </Card>

            {/* Trades & Analytics Tabs */}
            <Card className="flex-1 flex flex-col min-h-0 border shadow-sm">
              <Tabs defaultValue="active" className="flex-1 flex flex-col min-h-0">
                <div className="px-3 pt-2 border-b bg-muted/10 shrink-0">
                  <TabsList className="grid w-full grid-cols-3 h-8">
                    <TabsTrigger value="active" className="text-xs">
                      {t('tradingReview.activeTrades')} ({activeTrades.length})
                    </TabsTrigger>
                    <TabsTrigger value="closed" className="text-xs">
                      {t('tradingReview.closedTrades')} ({closedTrades.length})
                    </TabsTrigger>
                    <TabsTrigger value="analytics" className="text-xs">
                      {t('tradingReview.analytics')}
                    </TabsTrigger>
                  </TabsList>
                </div>

                {/* Active Trades Tab */}
                <TabsContent value="active" className="flex-1 overflow-auto p-3 m-0">
                  {activeTrades.length === 0 ? (
                    <div className="text-center py-8 text-xs text-muted-foreground">
                      {t('tradingReview.noActiveTrades')}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {activeTrades.map((tr) => (
                        <div
                          key={tr.id}
                          className="flex justify-between items-center p-2.5 border rounded-md text-xs bg-card/60"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`font-bold uppercase ${
                                  tr.type === 'buy' ? 'text-emerald-500' : 'text-rose-500'
                                }`}
                              >
                                {tr.type}
                              </span>
                              <span className="font-mono">{tr.lots} lots</span>
                              <span className="text-muted-foreground font-mono">@{tr.open_price}</span>
                            </div>
                            {(tr.sl || tr.tp) && (
                              <div className="flex gap-2 text-[10px] text-muted-foreground font-mono">
                                {tr.sl && <span className="text-rose-400">SL: {tr.sl}</span>}
                                {tr.tp && <span className="text-emerald-400">TP: {tr.tp}</span>}
                              </div>
                            )}
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            onClick={() => handleCloseTrade(tr.id)}
                          >
                            {t('tradingReview.closePosition')}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                {/* Closed Trades Tab */}
                <TabsContent value="closed" className="flex-1 overflow-auto p-3 m-0">
                  {closedTrades.length === 0 ? (
                    <div className="text-center py-8 text-xs text-muted-foreground">
                      暂无平仓记录
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {closedTrades.map((tr) => (
                        <div
                          key={tr.id}
                          className="flex justify-between items-center p-2 border rounded-md text-xs bg-muted/30"
                        >
                          <div>
                            <span
                              className={`font-bold mr-1.5 uppercase ${
                                tr.type === 'buy' ? 'text-emerald-500' : 'text-rose-500'
                              }`}
                            >
                              {tr.type}
                            </span>
                            <span className="font-mono text-muted-foreground">{tr.lots} lots</span>
                          </div>
                          <div
                            className={`font-mono font-bold ${
                              (tr.profit ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'
                            }`}
                          >
                            {(tr.profit ?? 0) >= 0 ? `+$${tr.profit?.toFixed(2)}` : `-$${Math.abs(tr.profit || 0).toFixed(2)}`}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                {/* Analytics Tab */}
                <TabsContent value="analytics" className="flex-1 overflow-auto p-3 m-0">
                  {metrics ? (
                    <div className="space-y-3 text-xs">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="p-2.5 rounded-md border bg-muted/20">
                          <div className="text-muted-foreground flex items-center gap-1">
                            <Percent className="w-3.5 h-3.5 text-primary" />
                            {t('tradingReview.winRate')}
                          </div>
                          <div className="text-lg font-bold font-mono mt-0.5 text-primary">
                            {metrics.winRate.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            {metrics.winTrades} 胜 / {metrics.lossTrades} 负
                          </div>
                        </div>

                        <div className="p-2.5 rounded-md border bg-muted/20">
                          <div className="text-muted-foreground flex items-center gap-1">
                            <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                            {t('tradingReview.profitFactor')}
                          </div>
                          <div className="text-lg font-bold font-mono mt-0.5 text-emerald-500">
                            {metrics.profitFactor.toFixed(2)}
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            总交易 {metrics.totalTrades} 笔
                          </div>
                        </div>
                      </div>

                      <div className="space-y-1.5 p-2.5 rounded-md border bg-muted/10 font-mono">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">{t('tradingReview.netProfit')}:</span>
                          <span
                            className={`font-bold ${
                              metrics.netProfit >= 0 ? 'text-emerald-500' : 'text-rose-500'
                            }`}
                          >
                            {metrics.netProfit >= 0
                              ? `+$${metrics.netProfit.toFixed(2)}`
                              : `-$${Math.abs(metrics.netProfit).toFixed(2)}`}
                            {' '}({metrics.returnPercent.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">{t('tradingReview.maxDrawdown')}:</span>
                          <span className="text-rose-500">
                            ${metrics.maxDrawdown.toFixed(2)} ({metrics.maxDrawdownPercent.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">平均盈利:</span>
                          <span className="text-emerald-500">${metrics.avgWin.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">平均亏损:</span>
                          <span className="text-rose-500">${metrics.avgLoss.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-xs text-muted-foreground">无战绩数据</div>
                  )}
                </TabsContent>
              </Tabs>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  // ----------------------------------------------------
  // Sessions List & Creation View
  // ----------------------------------------------------
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('tradingReview.title')}</h1>
        <p className="text-muted-foreground">{t('tradingReview.description')}</p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Creation Form */}
        <Card className="md:col-span-1 h-fit">
          <CardHeader>
            <CardTitle>{t('tradingReview.newSession')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {cachedDatasets.length > 0 && (
              <div className="space-y-1.5 p-3 rounded-lg border bg-primary/5">
                <Label className="text-xs font-semibold text-primary">
                  {t('tradingReview.cachedDataSelect')}
                </Label>
                <Select onValueChange={handleSelectCachedDataset}>
                  <SelectTrigger className="text-xs">
                    <SelectValue placeholder={t('tradingReview.cachedDataHint')} />
                  </SelectTrigger>
                  <SelectContent>
                    {cachedDatasets.map((ds) => (
                      <SelectItem key={`${ds.symbol}__${ds.timeframe}`} value={`${ds.symbol}__${ds.timeframe}`}>
                        {ds.symbol} · {ds.timeframe} ({ds.count} 根)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

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
              <Input
                type="number"
                value={initialBalance}
                onChange={(e) => setInitialBalance(parseFloat(e.target.value) || 0)}
              />
            </div>
            <Button onClick={handleCreateSession} className="w-full">
              {t('tradingReview.startReview')}
            </Button>
          </CardContent>
        </Card>

        {/* Sessions List */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>{t('tradingReview.sessionList')}</CardTitle>
          </CardHeader>
          <CardContent>
            {store.loading && !store.sessions.length ? (
              <div className="text-center py-8 text-muted-foreground">加载复盘记录中...</div>
            ) : store.sessions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">{t('tradingReview.emptySessions')}</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('tradingReview.symbol')}</TableHead>
                    <TableHead>{t('tradingReview.timeframe')}</TableHead>
                    <TableHead>{t('tradingReview.tableStartTime')}</TableHead>
                    <TableHead>{t('tradingReview.tableBalance')}</TableHead>
                    <TableHead className="text-right">{t('tradingReview.tableActions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {store.sessions.map((s) => (
                    <TableRow key={s.id}>
                      <TableCell className="font-medium">{s.symbol}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{s.timeframe}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatTime(s.start_time)}</TableCell>
                      <TableCell className="font-mono font-medium">${s.current_balance.toFixed(2)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => store.loadSessionState(s.id)}
                          className="mr-2"
                        >
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
