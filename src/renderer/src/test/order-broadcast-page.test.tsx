import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { I18nProvider } from '@/i18n'
import { OrderBroadcastPage } from '@/pages/OrderBroadcastPage'
import { useAlertsStore } from '@/stores/alerts-store'

function renderOrderBroadcastPage(overrides?: Partial<ReturnType<typeof useAlertsStore.getState>>) {
  const storeState = {
    ...useAlertsStore.getInitialState(),
    orderBroadcastRules: [],
    isLoading: false,
    fetchOrderBroadcastRules: vi.fn().mockResolvedValue(undefined),
    addOrderBroadcastRule: vi.fn().mockResolvedValue({ ok: true }),
    updateOrderBroadcastRule: vi.fn().mockResolvedValue({ ok: true }),
    deleteOrderBroadcastRule: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }

  useAlertsStore.setState(storeState)

  render(
    <I18nProvider language="zh-CN">
      <OrderBroadcastPage />
    </I18nProvider>
  )

  return storeState
}

describe('OrderBroadcastPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    useAlertsStore.setState(useAlertsStore.getInitialState())
  })

  it('prevents creating a duplicate broadcast symbol', async () => {
    const addOrderBroadcastRule = vi.fn().mockResolvedValue({ ok: true })
    renderOrderBroadcastPage({
      orderBroadcastRules: [{ id: 'rule-1', symbol: 'XAUUSD', is_active: true }],
      addOrderBroadcastRule,
    })

    fireEvent.click(screen.getByRole('button', { name: '立即添加' }))

    expect(addOrderBroadcastRule).not.toHaveBeenCalled()
    expect(await screen.findByText('XAUUSD 已在广播列表中，无需重复添加')).toBeInTheDocument()
  })

  it('prevents editing a symbol into another existing symbol', async () => {
    const updateOrderBroadcastRule = vi.fn().mockResolvedValue({ ok: true })
    renderOrderBroadcastPage({
      orderBroadcastRules: [
        { id: 'rule-1', symbol: 'XAUUSD', is_active: true },
        { id: 'rule-2', symbol: 'EURUSD', is_active: false },
      ],
      updateOrderBroadcastRule,
    })

    fireEvent.click(screen.getAllByTitle('编辑')[1])
    fireEvent.change(screen.getByLabelText('交易品种'), { target: { value: ' xauusd ' } })
    fireEvent.click(screen.getByRole('button', { name: '确认修改' }))

    expect(updateOrderBroadcastRule).not.toHaveBeenCalled()
    expect(await screen.findByText('XAUUSD 已在广播列表中，无需重复添加')).toBeInTheDocument()
  })
})
