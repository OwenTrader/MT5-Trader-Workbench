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

    const botTab = await screen.findByRole('tab', { name: '通知' })
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

    const botTab = await screen.findByRole('tab', { name: '通知' })
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

    const botTab = await screen.findByRole('tab', { name: '通知' })
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

  it('shows configured and enabled bot transport statuses', async () => {
    useSettingsStore.setState({
      settings: {
        ...useSettingsStore.getInitialState().settings,
        dingtalk_enabled: true,
        dingtalk_token: 'ding-token',
        wecom_enabled: false,
        wecom_webhook_url: 'https://example.test/wecom',
        feishu_enabled: false,
        feishu_webhook_url: '',
      },
      isLoading: false,
      error: null,
    })

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            language: 'zh-CN',
            dingtalk_enabled: true,
            dingtalk_token: 'ding-token',
            wecom_enabled: false,
            wecom_webhook_url: 'https://example.test/wecom',
            feishu_enabled: false,
            feishu_webhook_url: '',
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({ status: 'ok' }),
        text: async () => 'ok',
      } as Response
    }) as typeof fetch

    render(<TestRoot />)

    const botTab = await screen.findByRole('tab', { name: '通知' })
    fireEvent.click(botTab)
    fireEvent.keyDown(botTab, { key: 'Enter' })

    expect(await screen.findByText('通知通道状态')).toBeInTheDocument()
    expect(screen.getByText('已存在可用通道，开启的推送类别会通过可用 Bot 发送。')).toBeInTheDocument()
    expect(screen.getByText('钉钉')).toBeInTheDocument()
    expect(screen.getByText('已启用')).toBeInTheDocument()
    expect(screen.getByText('企业微信')).toBeInTheDocument()
    expect(screen.getByText('已配置未启用')).toBeInTheDocument()
    expect(screen.getByText('飞书')).toBeInTheDocument()
    expect(screen.getByText('未配置')).toBeInTheDocument()
    expect(screen.getByText('开启任一推送类别前，请至少配置并启用一个 Bot 通道；否则预警不会发出远程推送。')).toBeInTheDocument()
  })
})
