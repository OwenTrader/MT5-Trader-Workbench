import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AutomationCenterPage } from '@/pages/automation/AutomationCenterPage'
import { I18nProvider } from '@/i18n'

import { MemoryRouter } from 'react-router-dom'

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn().mockImplementation((url: string) => {
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve([]),
    })
  }),
}))

function renderWithRouter(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <I18nProvider language="zh-CN">
        {ui}
      </I18nProvider>
    </MemoryRouter>
  )
}

describe('AutomationCenterPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders tabs for copy trading, accounts, order sync, and risk control', () => {
    renderWithRouter(<AutomationCenterPage defaultTab="copy-trading" />)

    expect(screen.getByRole('tab', { name: /本地跟单|Local Copy Trading/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /账户列表|Account List/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /订单同步|Order Sync/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /风控与账户|Risk & Account/i })).toBeInTheDocument()
  })

  it('switches to accounts tab when clicking accounts tab trigger', async () => {
    const user = userEvent.setup()
    renderWithRouter(<AutomationCenterPage defaultTab="copy-trading" />)

    const accountsTab = screen.getByRole('tab', { name: /账户列表|Account List/i })
    await user.click(accountsTab)

    expect(accountsTab).toHaveAttribute('data-state', 'active')
  })
})
