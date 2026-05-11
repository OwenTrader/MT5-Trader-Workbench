import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { SettingsPage } from '@/pages/SettingsPage'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'
import { toast } from 'sonner'

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'light',
    setTheme: vi.fn(),
  }),
}))

function TestRoot() {
  return (
    <I18nProvider language="zh-CN">
      <SettingsPage />
    </I18nProvider>
  )
}

describe('SettingsPage bot toggles', () => {
  beforeEach(() => {
    vi.resetAllMocks()

    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
      isLoading: false,
      error: null,
    })

    Object.defineProperty(window, 'electron', {
      configurable: true,
      value: {
        ipcRenderer: {
          invoke: vi.fn(async (channel: string) => {
            if (channel === 'app:get-resources-path') {
              return 'C:/resources'
            }

            return undefined
          }),
          on: vi.fn(() => () => undefined),
        },
      },
    })

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            language: 'zh-CN',
          }),
        } as Response
      }

      if (url.endsWith('/settings') && init?.method === 'POST') {
        return {
          ok: true,
          json: async () => ({ status: 'ok' }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({ status: 'ok' }),
        text: async () => 'ok',
      } as Response
    }) as typeof fetch
  })

  it('keeps DingTalk form values when enabling after typing', async () => {
    render(<TestRoot />)

    const botTab = await screen.findByRole('tab', { name: 'Bot预警' })
    fireEvent.click(botTab)
    fireEvent.keyDown(botTab, { key: 'Enter' })

    const tokenInput = await screen.findByLabelText('Access Token')
    const secretInput = await screen.findByLabelText('Secret (可选)')
    const enableSwitch = screen.getByLabelText('钉钉 (DingTalk) Bot')

    fireEvent.change(tokenInput, { target: { value: 'ding-token' } })
    fireEvent.change(secretInput, { target: { value: 'ding-secret' } })
    fireEvent.click(enableSwitch)

    await waitFor(() => {
      expect(screen.getByLabelText('Access Token')).toHaveValue('ding-token')
      expect(screen.getByLabelText('Secret (可选)')).toHaveValue('ding-secret')
    })
  })

  it('allows editing overlay symbols as comma-separated text', async () => {
    render(<TestRoot />)

    const symbolsInput = await screen.findByLabelText('在浮窗显示的品种列表 (逗号分隔)')
    fireEvent.change(symbolsInput, { target: { value: 'XAUUSD, EURUSD,' } })

    expect(symbolsInput).toHaveValue('XAUUSD, EURUSD,')
  })

  it('blocks DingTalk test requests when the token is empty', async () => {
    render(<TestRoot />)

    const botTab = await screen.findByRole('tab', { name: 'Bot预警' })
    fireEvent.click(botTab)
    fireEvent.keyDown(botTab, { key: 'Enter' })

    const testButtons = await screen.findAllByRole('button', { name: '发送测试' })
    expect(testButtons[0]).toBeDisabled()
    fireEvent.click(testButtons[0])

    expect(toast.error).not.toHaveBeenCalled()

    expect(global.fetch).not.toHaveBeenCalledWith(
      'http://127.0.0.1:8765/notifications/test_dingtalk',
      expect.anything()
    )
  })

  it('disables test buttons until each bot form is filled', async () => {
    render(<TestRoot />)

    const botTab = await screen.findByRole('tab', { name: 'Bot预警' })
    fireEvent.click(botTab)
    fireEvent.keyDown(botTab, { key: 'Enter' })

    const testButtons = await screen.findAllByRole('button', { name: '发送测试' })
    expect(testButtons[0]).toBeDisabled()
    expect(testButtons[1]).toBeDisabled()
    expect(testButtons[2]).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Access Token'), { target: { value: 'ding-token' } })
    const webhookInputs = screen.getAllByLabelText('Webhook URL')
    fireEvent.change(webhookInputs[0], { target: { value: 'https://example.test/wecom' } })

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: '发送测试' })[0]).toBeEnabled()
      expect(screen.getAllByRole('button', { name: '发送测试' })[1]).toBeEnabled()
      expect(screen.getAllByRole('button', { name: '发送测试' })[2]).toBeDisabled()
    })
  })
})
