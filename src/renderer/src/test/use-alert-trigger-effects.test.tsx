import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi, afterEach } from 'vitest'

import { useAlertTriggerEffects } from '@/hooks/use-alert-trigger-effects'

describe('useAlertTriggerEffects', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a notification only for newly triggered alerts', () => {
    const notify = vi.fn()

    vi.stubGlobal('Notification', class {
      static permission = 'granted'
      constructor(_title: string, options: NotificationOptions) {
        notify(options.body)
      }
    } as any)

    const { rerender } = renderHook(
      ({ alerts }) => useAlertTriggerEffects({
        alerts,
        isSoundEnabled: false,
        notificationTitle: 'Alert',
        buildBody: (alert) => alert.body,
      }),
      { initialProps: { alerts: [{ id: '1', is_triggered: false, body: 'first' }] } }
    )

    rerender({ alerts: [{ id: '1', is_triggered: true, body: 'first' }] })
    rerender({ alerts: [{ id: '1', is_triggered: true, body: 'first' }] })

    expect(notify).toHaveBeenCalledTimes(1)
    expect(notify).toHaveBeenCalledWith('first')
  })
})
