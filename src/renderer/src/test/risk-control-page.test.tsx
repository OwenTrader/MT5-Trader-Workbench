import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { I18nProvider } from '@/i18n'
import { RiskControlPage } from '@/pages/RiskControlPage'

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

    expect(await screen.findByDisplayValue('200')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save Risk Settings' }))

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/risk-control'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ margin_alert: 200, equity_alert: 1000 }),
      })
    )
  })
})
