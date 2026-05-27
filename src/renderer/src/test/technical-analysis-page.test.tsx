import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TechnicalAnalysisPage } from '@/pages/TechnicalAnalysisPage'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'

function TestRoot() {
  return (
    <I18nProvider language="en">
      <TechnicalAnalysisPage />
    </I18nProvider>
  )
}

describe('TechnicalAnalysisPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()

    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
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
            language: 'en',
          }),
        } as Response
      }

      if (url.endsWith('/awakening/report')) {
        return {
          ok: true,
          json: async () => ({
            symbol: 'XAUUSD',
            timeframe: 'M15',
            candles_count: 100,
            prompt_version: 'v1',
            analysis_markdown: '## Market Structure\nBullish continuation',
            used_model: 'gpt-4.1-mini',
            generated_at: '2026-05-27T00:00:00+00:00',
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({ status: 'ok' }),
      } as Response
    }) as typeof fetch
  })

  it('blocks AI analysis when base URL or API key is missing', async () => {
    render(<TestRoot />)

    expect(await screen.findByText('Fill AI Base URL and AI API Key in Settings first.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate AI Analysis' })).toBeDisabled()
  })

  it('renders AI analysis after successful request', async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url.endsWith('/settings') && (!init || init.method === undefined)) {
        return {
          ok: true,
          json: async () => ({
            ...useSettingsStore.getInitialState().settings,
            language: 'en',
            ai_base_url: 'https://example.test/v1',
            ai_api_key: 'sk-test',
          }),
        } as Response
      }

      if (url.endsWith('/awakening/report')) {
        return {
          ok: true,
          json: async () => ({
            symbol: 'XAUUSD',
            timeframe: 'M15',
            candles_count: 100,
            prompt_version: 'v1',
            analysis_markdown: '## Market Structure\nBullish continuation',
            used_model: 'gpt-4.1-mini',
            generated_at: '2026-05-27T00:00:00+00:00',
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({ status: 'ok' }),
      } as Response
    }) as typeof fetch

    render(<TestRoot />)

    const button = await screen.findByRole('button', { name: 'Generate AI Analysis' })
    await waitFor(() => {
      expect(button).toBeEnabled()
    })

    fireEvent.click(button)

    expect(await screen.findByText(/## Market Structure/)).toBeInTheDocument()
    expect(screen.getByText(/Bullish continuation/)).toBeInTheDocument()
  })
})
