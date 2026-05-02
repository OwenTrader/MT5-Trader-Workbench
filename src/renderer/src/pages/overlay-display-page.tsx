import React, { useEffect, useState } from 'react'
import { useI18n } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'
import { Pin, X } from 'lucide-react'

export const OverlayDisplayPage: React.FC = () => {
  const { t } = useI18n()
  const [quotes, setQuotes] = useState<Record<string, { bid: number, change_pct: number, digits: number }>>({})
  const [status, setStatus] = useState('connecting')
  const [isPinned, setIsPinned] = useState(false)
  const { settings, fetchSettings } = useSettingsStore()
  const containerRef = React.useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchSettings()
    
    // Listen for settings change notifications from main process
    let removeSettingsListener: (() => void) | undefined

    if ((window as any).electron?.ipcRenderer) {
      removeSettingsListener = (window as any).electron.ipcRenderer.on('settings:changed', () => {
        console.log('Settings changed notification received, fetching...')
        fetchSettings()
      })
    }

    return () => {
      removeSettingsListener?.()
    }
  }, [])

  // Auto-resize window to fit content
  useEffect(() => {
    if (!(window as any).electron?.ipcRenderer) return

    const observeTarget = containerRef.current
    if (!observeTarget) return

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // Measure with precision
        const rect = observeTarget.getBoundingClientRect()
        const targetWidth = Math.ceil(rect.width) 
        const targetHeight = Math.ceil(rect.height)
        
        // Prevent infinite loop by checking if current window size is already close to target
        if (targetWidth > 0 && targetHeight > 0) {
          const currentWidth = window.innerWidth
          const currentHeight = window.innerHeight
          
          // Only resize if difference is significant to avoid rounding flickers
          if (Math.abs(currentWidth - targetWidth) > 1 || Math.abs(currentHeight - targetHeight) > 1) {
            (window as any).electron.ipcRenderer.invoke('overlay:set-size', targetWidth, targetHeight)
          }
        }
      }
    })

    resizeObserver.observe(observeTarget)
    return () => resizeObserver.disconnect()
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: NodeJS.Timeout

    const connect = () => {
      ws = new WebSocket('ws://127.0.0.1:8765/ws/overlay')
      
      ws.onopen = () => setStatus('connected')
      ws.onclose = () => {
        setStatus('disconnected')
        reconnectTimer = setTimeout(connect, 3000)
      }
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'quotes') {
          setQuotes(data.data)
        }
      }
    }

    connect()
    return () => {
      ws?.close()
      clearTimeout(reconnectTimer)
    }
  }, [])

  const textStyle = {
    fontSize: `${settings.overlay_font_size}px`,
    color: status === 'connected' ? settings.overlay_font_color : '#666',
    fontFamily: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
  }

  const handleClose = () => {
    if ((window as any).electron?.ipcRenderer) {
      (window as any).electron.ipcRenderer.invoke('overlay:toggle-visible', false)
    }
  }

  return (
    <div 
      ref={containerRef}
      className={`relative inline-block w-max group bg-black/85 rounded-lg border border-white/20 select-none overflow-hidden backdrop-blur-xl px-2 pt-8 pb-2 transition-shadow ${!isPinned ? 'drag-region cursor-move' : ''}`}
      style={{ 
        WebkitAppRegion: !isPinned ? 'drag' : 'no-drag'
      } as any}
    >
      {/* 悬浮操作栏 - 水平排列在右上角 */}
      <div 
        className="absolute right-1 top-1 flex flex-row gap-0.5 z-[9999]"
        style={{ WebkitAppRegion: 'no-drag' } as any}
      >
        <button
          onClick={() => setIsPinned(!isPinned)}
          className={`p-1.5 rounded-md transition-all duration-200 ${isPinned ? 'text-blue-400 bg-blue-500/10' : 'text-white/40 hover:text-white hover:bg-white/10'}`}
          title={isPinned ? t('overlay.unpin') : t('overlay.pin')}
        >
          <Pin size={13} className={isPinned ? 'fill-blue-400' : ''} />
        </button>
        <button
          onClick={handleClose}
          className="p-1.5 rounded-md text-white/40 hover:text-white hover:bg-red-500/80 transition-all duration-200"
          title={t('overlay.close')}
        >
          <X size={13} />
        </button>
      </div>

      <div 
        className="inline-grid grid-cols-[auto_auto_auto] px-2"
        style={{ 
          columnGap: '2em',
          rowGap: '4px'
        }}
      >
      {(settings.overlay_symbols || []).map((symbol) => {
        const quote = quotes[symbol]
        return (
          <React.Fragment key={symbol}>
            {/* 1. 品种 (Symbol) - 左对齐 */}
            <span className="uppercase font-bold whitespace-nowrap text-left border-b border-white/5 py-1" style={textStyle}>
              {symbol}
            </span>

            {/* 2. 价格 (Price) - 左对齐 */}
            <span className="font-bold tabular-nums whitespace-nowrap text-left border-b border-white/5 py-1" style={textStyle}>
              {quote?.bid?.toFixed(quote.digits ?? 2) || t('overlay.unavailable')}
            </span>

            {/* 3. 波动幅度 (Volatility %) - 左对齐 */}
            <span className="font-bold tabular-nums whitespace-nowrap text-left border-b border-white/5 py-1" style={textStyle}>
              {(quote?.change_pct || 0) >= 0 ? '+' : ''}
              {quote?.change_pct?.toFixed(2) || '0.00'}%
            </span>
          </React.Fragment>
        )
      })}
      </div>

      {status !== 'connected' && (
        <div className="absolute inset-0 bg-black/90 flex items-center justify-center text-[10px] text-white/40 z-50">
          {t('overlay.reconnecting')}
        </div>
      )}
    </div>
  )
}
