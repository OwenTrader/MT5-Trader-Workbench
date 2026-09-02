import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AlertsCenterPage } from '@/pages/alerts/AlertsCenterPage'
import { I18nProvider } from '@/i18n'

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    if (typeof url === 'string' && url.includes('/settings')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          api_refresh_interval: 2000,
          dingtalk_enabled: false,
          wecom_enabled: false,
          feishu_enabled: false,
        }),
      })
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve([]),
    })
  }),
}))

describe('AlertsCenterPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders tabs for price, volatility, indicator, and broadcast', () => {
    render(
      <I18nProvider language="zh-CN">
        <AlertsCenterPage defaultTab="price" />
      </I18nProvider>
    )

    expect(screen.getByRole('tab', { name: /价格预警|Price Alerts/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /波动检测|Volatility/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /指标预警|Indicator Alerts/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /订单广播|Order Broadcast/i })).toBeInTheDocument()
  })


  it('switches tab when clicking tab triggers', async () => {
    const user = userEvent.setup()
    render(
      <I18nProvider language="zh-CN">
        <AlertsCenterPage defaultTab="price" />
      </I18nProvider>
    )

    const volTab = screen.getByRole('tab', { name: /波动检测|Volatility/i })
    await user.click(volTab)

    expect(volTab).toHaveAttribute('data-state', 'active')
  })
})
