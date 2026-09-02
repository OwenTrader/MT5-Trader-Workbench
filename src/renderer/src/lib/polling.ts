import { useEffect, useRef } from 'react'

interface UsePollingOptions {
  enabled?: boolean
  immediate?: boolean
  pauseWhenHidden?: boolean
}

/**
 * Replaces ad-hoc `setInterval` polling with a version that:
 *  - cleans up on unmount (no leaked timers when navigating between pages)
 *  - pauses while the tab is hidden (saves CPU / network)
 *  - re-creates itself when the interval changes
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  options: UsePollingOptions = {},
): void {
  const { enabled = true, immediate = true, pauseWhenHidden = true } = options
  const savedCallback = useRef(callback)
  savedCallback.current = callback

  useEffect(() => {
    if (!enabled || !intervalMs || intervalMs <= 0) return

    let timer: ReturnType<typeof setInterval> | null = null
    let stopped = false

    const isHidden = () =>
      pauseWhenHidden &&
      typeof document !== 'undefined' &&
      document.visibilityState === 'hidden'

    const tick = () => {
      if (stopped || isHidden()) return
      void savedCallback.current()
    }

    const start = () => {
      if (timer || stopped) return
      timer = setInterval(tick, intervalMs)
    }

    const stop = () => {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    }

    const onVisibility = () => {
      if (document.visibilityState === 'visible') start()
      else stop()
    }

    if (immediate) tick()
    if (!isHidden()) start()
    if (pauseWhenHidden && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility)
    }

    return () => {
      stopped = true
      stop()
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility)
      }
    }
  }, [enabled, intervalMs, immediate, pauseWhenHidden])
}

/** Store-level interval registry: de-duplicates and guarantees cleanup. */
const registry = new Map<string, ReturnType<typeof setInterval>>()

export function registerPollingJob(
  key: string,
  fn: () => void | Promise<void>,
  intervalMs: number,
): () => void {
  const existing = registry.get(key)
  if (existing) clearInterval(existing)

  if (!intervalMs || intervalMs <= 0) {
    registry.delete(key)
    return () => {}
  }

  const run = () => {
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
    void fn()
  }

  const timer = setInterval(run, intervalMs)
  registry.set(key, timer)
  void run()
  return () => {
    const current = registry.get(key)
    if (current === timer) {
      clearInterval(timer)
      registry.delete(key)
    }
  }
}

export function stopPollingJob(key: string): void {
  const timer = registry.get(key)
  if (timer) {
    clearInterval(timer)
    registry.delete(key)
  }
}
