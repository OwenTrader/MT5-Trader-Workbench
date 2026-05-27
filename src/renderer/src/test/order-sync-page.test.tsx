import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'
import { OrderSyncPage } from '@/pages/OrderSyncPage'
import { useOrderSyncStore } from '@/stores/order-sync-store'

describe('OrderSyncPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useOrderSyncStore.setState(useOrderSyncStore.getInitialState())

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/order-sync') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            enabled: false,
            poll_interval_seconds: 1,
            block_high_frequency_orders: false,
            high_frequency_window_seconds: 5,
            credentials: [],
            mappings: [],
            synced_orders: [],
            last_error: null,
            last_checked_at: null,
          }),
        } as Response
      }

      if (url.endsWith('/order-sync') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({
            enabled: true,
            poll_interval_seconds: 1,
            block_high_frequency_orders: false,
            high_frequency_window_seconds: 5,
            credentials: [],
            mappings: [],
            synced_orders: [],
            last_error: null,
            last_checked_at: null,
          }),
        } as Response
      }

      throw new Error(`Unexpected request: ${url}`)
    }) as any
  })

  it('requires confirmation before enabling order sync', async () => {
    const user = userEvent.setup()

    render(
      <I18nProvider language="en">
        <OrderSyncPage />
      </I18nProvider>
    )

    await screen.findByText('Order Sync is a high-risk experimental feature: when enabled, it attempts to mirror MT5 instant market opens and closes to TopStep using the configured credentials and mappings. Validate with small scope first.')
    await user.click(screen.getByRole('switch', { name: 'Enable order sync' }))

    expect(await screen.findByRole('heading', { name: 'Enable Order Sync?' })).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalledWith(expect.stringContaining('/order-sync'), expect.objectContaining({ method: 'POST' }))

    await user.click(screen.getByRole('button', { name: 'Enable Sync' }))

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/order-sync'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"enabled":true'),
        })
      )
    })
  })
})
