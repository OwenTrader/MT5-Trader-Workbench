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

describe('PriceAlertsPage', () => {
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

  it('does not default a new alert target price to zero', () => {
    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    expect(screen.getByLabelText('Target Price')).toHaveValue(null)
    expect(screen.getByText('Before saving, MT5 validates the symbol, target price, and break above/below direction.')).toBeInTheDocument()
  })

  it('requires a symbol before verifying with the backend', async () => {
    const user = userEvent.setup()

    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    await user.clear(screen.getByLabelText('Symbol'))
    await user.type(screen.getByLabelText('Target Price'), '3330')
    await user.click(screen.getByRole('button', { name: 'Add Alert' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a symbol.')
    expect(global.fetch).not.toHaveBeenCalledWith('http://127.0.0.1:8765/mt5/verify_alert', expect.anything())
  })

  it('requires a target price greater than zero before verifying with the backend', async () => {
    const user = userEvent.setup()

    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    await user.click(screen.getByRole('button', { name: 'Add Alert' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a target price greater than 0.')
    expect(global.fetch).not.toHaveBeenCalledWith('http://127.0.0.1:8765/mt5/verify_alert', expect.anything())
  })

  it('keeps the backend verification flow for valid input', async () => {
    const user = userEvent.setup()
    const addPriceAlert = useAlertsStore.getState().addPriceAlert

    global.fetch = vi.fn(async (input) => {
      if (String(input).endsWith('/mt5/verify_alert')) {
        return { ok: true, json: async () => ({ status: 'ok', current_price: 3320 }) } as Response
      }

      return { ok: true, json: async () => ({}) } as Response
    }) as typeof fetch

    render(
      <I18nProvider language="en">
        <PriceAlertsPage />
      </I18nProvider>
    )

    await user.clear(screen.getByLabelText('Target Price'))
    await user.type(screen.getByLabelText('Target Price'), '3330')
    await user.click(screen.getByRole('button', { name: 'Add Alert' }))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/mt5/verify_alert', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ symbol: 'XAUUSD', price: 3330, condition: 'above' }),
      }))
      expect(addPriceAlert).toHaveBeenCalledWith({ symbol: 'XAUUSD', price: 3330, condition: 'above', comment: '', is_active: true })
    })
  })
})
