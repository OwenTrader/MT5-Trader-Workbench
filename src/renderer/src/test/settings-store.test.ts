import { renderHook, waitFor } from '@testing-library/react'
import { useSettingsStore } from '@/stores/settings-store'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch
global.fetch = vi.fn()

const mockGetBackendStartupDiagnostics = vi.fn()

Object.defineProperty(window, 'electron', {
  configurable: true,
  value: {
    getBackendStartupDiagnostics: mockGetBackendStartupDiagnostics,
    ipcRenderer: {
      invoke: vi.fn(),
    },
  },
})

describe('Settings Store', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockGetBackendStartupDiagnostics.mockResolvedValue(undefined)
    useSettingsStore.setState({
      settings: useSettingsStore.getInitialState().settings,
      isLoading: false,
      error: null,
    })
  })

  it('initializes with default settings', () => {
    const { result } = renderHook(() => useSettingsStore())
    expect(result.current.settings.mt5_path).toBe('')
  })

  it('initializes with zh-CN as the default language', () => {
    const { result } = renderHook(() => useSettingsStore())
    expect(result.current.settings.language).toBe('zh-CN')
  })

  it('enables alert sound with built-in sound 2 by default', () => {
    const { result } = renderHook(() => useSettingsStore())
    expect(result.current.settings.alert_sound_enabled).toBe(true)
    expect(result.current.settings.alert_sound_path).toBe('02.mp3')
  })

  it('fetches settings from backend', async () => {
    const mockSettings = { mt5_path: 'C:/MT5', auto_connect: true, language: 'en' }
    ;(fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockSettings,
    })

    const { result } = renderHook(() => useSettingsStore())
    await result.current.fetchSettings()

    expect(result.current.settings.mt5_path).toBe('C:/MT5')
    expect(result.current.settings.auto_connect).toBe(true)
    expect(result.current.settings.language).toBe('en')
  })

  it('includes backend diagnostics when fetching settings fails', async () => {
    ;(fetch as any).mockRejectedValue(new Error('fetch failed'))
    mockGetBackendStartupDiagnostics.mockResolvedValue({
      healthUrl: 'http://127.0.0.1:8765/health',
      executablePath: 'C:/app/resources/mt5_service/mt5_service.exe',
      workingDirectory: 'C:/app/resources/mt5_service',
      settingsPath: 'C:/Users/test/AppData/Roaming/app/storage/settings.json',
      defaultSettingsPath: 'C:/app/resources/storage/settings.json',
      startedAt: '2026-04-30T10:00:00.000Z',
      lastError: 'Backend health check timed out after 15000ms',
      recentLogs: ['line 1', 'line 2'],
    })

    const { result } = renderHook(() => useSettingsStore())
    await result.current.fetchSettings('无法连接到后台服务，请检查程序是否完全启动')

    await waitFor(() => {
      expect(result.current.error).toContain('无法连接到后台服务，请检查程序是否完全启动')
      expect(result.current.error).toContain('Request error: fetch failed')
      expect(result.current.error).toContain('Health URL: http://127.0.0.1:8765/health')
      expect(result.current.error).toContain('Last backend error: Backend health check timed out after 15000ms')
      expect(result.current.error).toContain('Recent backend logs:\nline 1\nline 2')
    })
  })

  it('saves settings to backend', async () => {
    ;(fetch as any).mockResolvedValue({ ok: true })

    const { result } = renderHook(() => useSettingsStore())
    await result.current.updateSettings({ mt5_path: 'D:/MT5', language: 'en' })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/settings'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('D:/MT5'),
      })
    )

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/settings'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"language":"en"'),
      })
    )
  })
})
