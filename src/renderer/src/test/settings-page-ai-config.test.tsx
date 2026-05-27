import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SettingsPage } from '@/pages/SettingsPage'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'

vi.mock('next-themes', () => ({
  useTheme: () => ({
    theme: 'light',
    setTheme: vi.fn(),
  }),
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

function TestRoot() {
  return (
    <I18nProvider language="en">
      <SettingsPage />
    </I18nProvider>
  )
}

describe('SettingsPage AI config', () => {
  beforeEach(() => {
    vi.resetAllMocks()

    const savedSettings = {
      ...useSettingsStore.getInitialState().settings,
      language: 'en',
      ai_base_url: 'https://saved.example/v1',
      ai_api_key: 'sk-saved',
      ai_model: 'gpt-4o-mini',
      ai_timeframe: 'H1',
      ai_candles_count: 120,
      ai_temperature: 0.4,
      ai_system_prompt: 'Focus on trend continuation.',
    }

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
          json: async () => savedSettings,
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
      } as Response
    }) as typeof fetch
  })

  it('renders and saves AI base URL and API key settings', async () => {
    render(<TestRoot />)

    const baseUrlInput = await screen.findByLabelText('AI Base URL')
    const apiKeyInput = screen.getByLabelText('AI API Key')
    const modelInput = screen.getByLabelText('AI Model Name')
    const timeframeInput = screen.getByLabelText('AI Analysis Timeframe')
    const candlesCountInput = screen.getByLabelText('Candles Count')
    const temperatureInput = screen.getByLabelText('Temperature')
    const systemPromptInput = screen.getByLabelText('AI System Prompt')

    expect(baseUrlInput).toHaveValue('https://saved.example/v1')
    expect(apiKeyInput).toHaveValue('sk-saved')
    expect(modelInput).toHaveValue('gpt-4o-mini')
    expect(timeframeInput).toHaveValue('H1')
    expect(candlesCountInput).toHaveValue(120)
    expect(temperatureInput).toHaveValue(0.4)
    expect(systemPromptInput).toHaveValue('Focus on trend continuation.')

    fireEvent.change(baseUrlInput, { target: { value: 'https://example.test/v1' } })
    fireEvent.change(apiKeyInput, { target: { value: 'sk-test' } })
    fireEvent.change(modelInput, { target: { value: 'gpt-4.1-mini' } })
    fireEvent.change(timeframeInput, { target: { value: 'M30' } })
    fireEvent.change(candlesCountInput, { target: { value: '150' } })
    fireEvent.change(temperatureInput, { target: { value: '0.3' } })
    fireEvent.change(systemPromptInput, { target: { value: 'Prefer conservative setups.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Settings' }))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8765/settings',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('https://example.test/v1'),
        })
      )
    })

    const postCall = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.find((call) =>
      String(call[0]).endsWith('/settings') && call[1]?.method === 'POST'
    )
    expect(postCall).toBeTruthy()
    const payload = JSON.parse(String(postCall?.[1]?.body ?? '{}'))
    expect(payload.ai_base_url).toBe('https://example.test/v1')
    expect(payload.ai_api_key).toBe('sk-test')
    expect(payload.ai_model).toBe('gpt-4.1-mini')
    expect(payload.ai_timeframe).toBe('M30')
    expect(payload.ai_candles_count).toBe(150)
    expect(payload.ai_temperature).toBe(0.3)
    expect(payload.ai_system_prompt).toBe('Prefer conservative setups.')
  })
})
