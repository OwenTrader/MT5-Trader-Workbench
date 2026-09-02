import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QuantLabPage } from '@/pages/quant/QuantLabPage'
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

describe('QuantLabPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders tabs for python quant, backtest, data management, trading review, and tech analysis', () => {
    renderWithRouter(<QuantLabPage defaultTab="python-quant" />)

    expect(screen.getByRole('tab', { name: /Python 量化|Python Quant/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /量化回测|Quant Backtest/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /数据管理|Data Management/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /复盘|Trading Review/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /技术分析|Technical Analysis/i })).toBeInTheDocument()
  })

  it('switches to backtest tab when clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<QuantLabPage defaultTab="python-quant" />)

    const backtestTab = screen.getByRole('tab', { name: /量化回测|Quant Backtest/i })
    await user.click(backtestTab)

    expect(backtestTab).toHaveAttribute('data-state', 'active')
  })
})
