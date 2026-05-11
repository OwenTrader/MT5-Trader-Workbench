import { useEffect, useRef } from 'react'

export function useAlertTriggerEffects<T extends { id: string; is_triggered: boolean }>({
  alerts,
  isSoundEnabled,
  soundPath,
  soundVolume,
  notificationTitle,
  buildBody,
}: {
  alerts: T[]
  isSoundEnabled: boolean
  soundPath?: string
  soundVolume?: number
  notificationTitle?: string
  buildBody: (alert: T) => string
}) {
  const prevTriggeredRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    const newlyTriggered = alerts.filter((alert) => alert.is_triggered && !prevTriggeredRef.current.has(alert.id))

    if (newlyTriggered.length > 0 && isSoundEnabled && soundPath) {
      const audio = new Audio(`local-file://${soundPath}`)
      audio.volume = soundVolume || 0.5
      void audio.play().catch(console.error)
    }

    if (typeof Notification !== 'undefined' && Notification.permission === 'granted' && notificationTitle) {
      for (const alert of newlyTriggered) {
        new Notification(notificationTitle, { body: buildBody(alert), silent: true })
      }
    }

    prevTriggeredRef.current = new Set(alerts.filter((alert) => alert.is_triggered).map((alert) => alert.id))
  }, [alerts, isSoundEnabled, soundPath, soundVolume, notificationTitle, buildBody])
}
