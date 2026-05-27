import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import { I18nProvider } from '@/i18n'
import { OrderCenterPage } from '@/pages/OrderCenterPage'
import { useOrderStore } from '@/stores/order-store'

describe('OrderCenterPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useOrderStore.setState(useOrderStore.getInitialState())
  })

  it('computes review metrics from daily statistics only', async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)

      if (url.endsWith('/history/overview')) {
        return { ok: true, json: async () => ({ today: 0, week: 0, month: 0 }) } as Response
      }

      if (url.includes('/history/daily?')) {
        return {
          ok: true,
          json: async () => ([
            { date: '2026-05-17', total_lots: 1, min_lot: 0.1, max_lot: 0.5, trades_count: 2, profit: 120, profit_pct: 1.2, balance: 10120 },
            { date: '2026-05-18', total_lots: 2, min_lot: 0.1, max_lot: 1, trades_count: 3, profit: -30, profit_pct: -0.3, balance: 10090 },
            { date: '2026-05-19', total_lots: 0.5, min_lot: 0.1, max_lot: 0.4, trades_count: 1, profit: 0, profit_pct: 0, balance: 10090 },
          ]),
        } as Response
      }

      throw new Error(`Unexpected request: ${url}`)
    }) as any

    render(
      <I18nProvider language="en">
        <OrderCenterPage />
      </I18nProvider>
    )

    expect(await screen.findByText('Review Metrics')).toBeInTheDocument()
    expect(screen.getByText('+90.00')).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText('33.3%')).toBeInTheDocument()
    expect(screen.getByText('+15.00')).toBeInTheDocument()
    expect(screen.getByText('+30.00')).toBeInTheDocument()
    expect(screen.getByText('2026-05-17 +120.00')).toBeInTheDocument()
    expect(screen.getByText('2026-05-18 -30.00')).toBeInTheDocument()
  })
})
