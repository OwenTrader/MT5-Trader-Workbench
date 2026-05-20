import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
  },
}))

import { I18nProvider } from '@/i18n'
import { PriceAlertsPage } from '@/pages/PriceAlertsPage'
import { useAlertsStore } from '@/stores/alerts-store'
import { useSettingsStore } from '@/stores/settings-store'

describe('PriceAlertsPage delete flow', () => {
  beforeEach(() => {
    vi.resetAllMocks()

    useAlertsStore.setState({
      priceAlerts: [
        {
          id: 'alert-1',
          symbol: 'XAUUSD',
          price: 3330,
          condition: 'above',
          comment: '',
          is_active: true,
          is_triggered: false,
        },
      ],
      isLoading: false,
      error: null,
      fetchAlerts: vi.fn(),
      addPriceAlert: vi.fn(),
      updatePriceAlert: vi.fn(),
      deletePriceAlert: vi.fn(),
    })

    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
      isLoading: false,
      error: null,
      fetchSettings: vi.fn(),
      updateSettings: vi.fn(),
    })

    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({}),
    })) as typeof fetch
  })

  it('asks for confirmation before deleting an alert', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))

    expect(confirmSpy).toHaveBeenCalledWith('Delete the price alert for XAUUSD (3330)?')
    expect(useAlertsStore.getState().deletePriceAlert).not.toHaveBeenCalled()
  })

  it('deletes an alert after confirmation', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(useAlertsStore.getState().deletePriceAlert).toHaveBeenCalledWith('alert-1')
    })
  })
})
