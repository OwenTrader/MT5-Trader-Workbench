import React, { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, SeriesMarker, Time } from 'lightweight-charts'
import { Kline, ReviewTrade } from '@/stores/trading-review-store'

interface TradingChartProps {
  klines: Kline[]
  trades: ReviewTrade[]
}

export function TradingChart({ klines, trades }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.9)',
      },
      grid: {
        vertLines: { color: 'rgba(197, 203, 206, 0.1)' },
        horzLines: { color: 'rgba(197, 203, 206, 0.1)' },
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

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })
    seriesRef.current = candlestickSeries

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current) return

    // Format data for lightweight-charts
    // time needs to be converted to lightweight-charts Time type
    // Ensure data is sorted by time and unique
    const formattedData = klines.map((k) => ({
      time: k.time as Time,
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    })).sort((a, b) => (a.time as number) - (b.time as number))
    
    // Deduplicate
    const uniqueData = formattedData.filter((v, i, a) => a.findIndex(t => t.time === v.time) === i)
    
    seriesRef.current.setData(uniqueData)

    // Setup markers for trades
    const markers: SeriesMarker<Time>[] = []
    
    trades.forEach((trade) => {
      // Open trade marker
      markers.push({
        time: trade.open_time as Time,
        position: trade.type === 'buy' ? 'belowBar' : 'aboveBar',
        color: trade.type === 'buy' ? '#2196F3' : '#FF9800',
        shape: trade.type === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `Open ${trade.type.toUpperCase()} @ ${trade.open_price}`,
      })

      // Close trade marker
      if (trade.close_time && trade.close_price) {
        markers.push({
          time: trade.close_time as Time,
          position: trade.type === 'buy' ? 'aboveBar' : 'belowBar',
          color: '#9C27B0',
          shape: 'circle',
          text: `Close ${trade.type.toUpperCase()} @ ${trade.close_price}\nPnL: $${trade.profit?.toFixed(2)}`,
        })
      }
    })

    // Sort markers by time
    markers.sort((a, b) => (a.time as number) - (b.time as number))
    
    seriesRef.current.setMarkers(markers)

  }, [klines, trades])

  return (
    <div 
      ref={chartContainerRef} 
      className="w-full h-full min-h-[400px]" 
    />
  )
}
