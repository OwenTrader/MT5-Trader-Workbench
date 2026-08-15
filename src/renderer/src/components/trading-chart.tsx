import React, { useEffect, useRef } from 'react'
import {
  createChart,
  IChartApi,
  ISeriesApi,
  IPriceLine,
  SeriesMarker,
  Time,
  LineStyle,
} from 'lightweight-charts'
import { Kline, ReviewTrade } from '@/stores/trading-review-store'

interface TradingChartProps {
  klines: Kline[]
  trades: ReviewTrade[]
  showEMA?: boolean
  showVolume?: boolean
}

function calculateEMA(data: { time: Time; close: number }[], period: number) {
  if (data.length < period) return []
  const k = 2 / (period + 1)
  const result: { time: Time; value: number }[] = []

  let sum = 0
  for (let i = 0; i < period; i++) {
    sum += data[i].close
  }
  let prevEMA = sum / period
  result.push({ time: data[period - 1].time, value: prevEMA })

  for (let i = period; i < data.length; i++) {
    const currentEMA = data[i].close * k + prevEMA * (1 - k)
    result.push({ time: data[i].time, value: currentEMA })
    prevEMA = currentEMA
  }
  return result
}

export function TradingChart({
  klines,
  trades,
  showEMA = true,
  showVolume = true,
}: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const ema20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ema50SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const priceLinesRef = useRef<IPriceLine[]>([])

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.85)',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: 1, // Magnet mode
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      autoSize: true,
    })
    chartRef.current = chart

    // 1. Candlestick Series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })
    seriesRef.current = candlestickSeries

    // 2. Volume Histogram Series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    })
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.82,
        bottom: 0,
      },
    })
    volumeSeriesRef.current = volumeSeries

    // 3. EMA 20 & EMA 50
    const ema20 = chart.addLineSeries({
      color: '#eab308',
      lineWidth: 2,
      title: 'EMA 20',
    })
    ema20SeriesRef.current = ema20

    const ema50 = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      title: 'EMA 50',
    })
    ema50SeriesRef.current = ema50

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      volumeSeriesRef.current = null
      ema20SeriesRef.current = null
      ema50SeriesRef.current = null
      priceLinesRef.current = []
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current) return

    // Format candlestick data
    const sorted = [...klines].sort((a, b) => a.time - b.time)
    const unique = sorted.filter((v, i, a) => a.findIndex((t) => t.time === v.time) === i)

    const formattedCandles = unique.map((k) => ({
      time: k.time as Time,
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    }))

    seriesRef.current.setData(formattedCandles)

    // Volume Series Data
    if (volumeSeriesRef.current) {
      if (showVolume) {
        const volumeData = unique.map((k) => ({
          time: k.time as Time,
          value: k.tick_volume || 0,
          color: k.close >= k.open ? 'rgba(34, 197, 94, 0.35)' : 'rgba(239, 68, 68, 0.35)',
        }))
        volumeSeriesRef.current.setData(volumeData)
      } else {
        volumeSeriesRef.current.setData([])
      }
    }

    // EMA Series Data
    if (ema20SeriesRef.current && ema50SeriesRef.current) {
      if (showEMA) {
        const ema20Data = calculateEMA(formattedCandles, 20)
        const ema50Data = calculateEMA(formattedCandles, 50)
        ema20SeriesRef.current.setData(ema20Data)
        ema50SeriesRef.current.setData(ema50Data)
      } else {
        ema20SeriesRef.current.setData([])
        ema50SeriesRef.current.setData([])
      }
    }

    // Setup Price Lines for active trades
    priceLinesRef.current.forEach((pl) => {
      try {
        seriesRef.current?.removePriceLine(pl)
      } catch {
        // ignore
      }
    })
    priceLinesRef.current = []

    const activeTrades = trades.filter((t) => t.close_time === null)
    activeTrades.forEach((t) => {
      if (!seriesRef.current) return
      // Entry price line
      const entryLine = seriesRef.current.createPriceLine({
        price: t.open_price,
        color: t.type === 'buy' ? '#3b82f6' : '#f97316',
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `${t.type.toUpperCase()} ${t.lots} @ ${t.open_price}`,
      })
      priceLinesRef.current.push(entryLine)

      // SL price line
      if (t.sl) {
        const slLine = seriesRef.current.createPriceLine({
          price: t.sl,
          color: '#ef4444',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `SL ${t.sl}`,
        })
        priceLinesRef.current.push(slLine)
      }

      // TP price line
      if (t.tp) {
        const tpLine = seriesRef.current.createPriceLine({
          price: t.tp,
          color: '#22c55e',
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `TP ${t.tp}`,
        })
        priceLinesRef.current.push(tpLine)
      }
    })

    // Setup markers for trade executions
    const markers: SeriesMarker<Time>[] = []

    trades.forEach((trade) => {
      // Open trade marker
      markers.push({
        time: trade.open_time as Time,
        position: trade.type === 'buy' ? 'belowBar' : 'aboveBar',
        color: trade.type === 'buy' ? '#3b82f6' : '#f97316',
        shape: trade.type === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `Open ${trade.type.toUpperCase()} ${trade.lots} @ ${trade.open_price}`,
      })

      // Close trade marker
      if (trade.close_time && trade.close_price) {
        const isWin = (trade.profit ?? 0) >= 0
        markers.push({
          time: trade.close_time as Time,
          position: trade.type === 'buy' ? 'aboveBar' : 'belowBar',
          color: isWin ? '#22c55e' : '#ef4444',
          shape: 'circle',
          text: `Close ${trade.type.toUpperCase()} @ ${trade.close_price}\nPnL: $${trade.profit?.toFixed(2)}`,
        })
      }
    })

    markers.sort((a, b) => (a.time as number) - (b.time as number))
    seriesRef.current.setMarkers(markers)
  }, [klines, trades, showEMA, showVolume])

  return <div ref={chartContainerRef} className="w-full h-full min-h-[420px]" />
}
