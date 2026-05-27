import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { I18nProvider } from '@/i18n'
import { RiskControlPage } from '@/pages/RiskControlPage'
import { toast } from 'sonner'

describe('RiskControlPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('loads saved risk settings and posts updates', async () => {
    const user = userEvent.setup()
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/risk-control') && (!init || init.method === undefined)) {
        return { ok: true, json: async () => ({ margin_alert: 200, equity_alert: 1000 }) } as Response
      }
      if (url.endsWith('/risk-control') && init?.method === 'POST') {
        return { ok: true, json: async () => ({ status: 'ok' }) } as Response
      }
      throw new Error(`Unexpected request: ${url}`)
    }) as any

    render(
      <I18nProvider language="en">
        <RiskControlPage />
      </I18nProvider>
    )

    expect(screen.getByText('Loading current risk settings...')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('200')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save Risk Settings' }))

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('Risk settings saved')
    })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/risk-control'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ margin_alert: 200, equity_alert: 1000 }),
      })
    )
  })

  it('shows inline validation for invalid numbers', async () => {
    const user = userEvent.setup()
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/risk-control') && (!init || init.method === undefined)) {
        return { ok: true, json: async () => ({ margin_alert: 200, equity_alert: 1000 }) } as Response
      }

      throw new Error(`Unexpected request: ${url}`)
    }) as any

    render(
      <I18nProvider language="en">
        <RiskControlPage />
      </I18nProvider>
    )

    const marginInput = await screen.findByDisplayValue('200')
    await user.clear(marginInput)
    await user.click(screen.getByRole('button', { name: 'Save Risk Settings' }))

    expect(await screen.findByText('Please enter valid non-negative numbers.')).toBeInTheDocument()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('does not allow saving defaults after risk settings fail to load', async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/risk-control') && (!init || init.method === undefined)) {
        return { ok: false, status: 500, json: async () => ({}) } as Response
      }

      throw new Error(`Unexpected request: ${url}`)
    }) as any

    render(
      <I18nProvider language="en">
        <RiskControlPage />
      </I18nProvider>
    )

    expect(await screen.findAllByText('Failed to load risk settings. Please try again later.')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Save Risk Settings' })).toBeDisabled()
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
