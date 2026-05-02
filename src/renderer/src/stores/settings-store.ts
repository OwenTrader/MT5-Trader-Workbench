import { create } from 'zustand'

type BackendStartupDiagnostics = {
  host: string
  port: number
  healthUrl: string
  workingDirectory: string
  executablePath: string
  settingsPath: string
  defaultSettingsPath: string
  isPackaged: boolean
  startedAt: string | null
  lastError: string | null
  recentLogs: string[]
}

type ElectronBridge = {
  getBackendStartupDiagnostics?: () => Promise<BackendStartupDiagnostics>
  ipcRenderer?: {
    invoke: (channel: string, ...args: any[]) => Promise<unknown>
  }
}

function getElectronBridge(): ElectronBridge | undefined {
  return (window as unknown as { electron?: ElectronBridge }).electron
}

async function buildBackendUnavailableMessage(defaultMessage: string, error: unknown): Promise<string> {
  const details: string[] = []

  if (error instanceof Error && error.message) {
    details.push(`Request error: ${error.message}`)
  }

  try {
    const diagnostics = await getElectronBridge()?.getBackendStartupDiagnostics?.()
    if (diagnostics) {
      details.push(`Health URL: ${diagnostics.healthUrl}`)
      details.push(`Backend executable: ${diagnostics.executablePath}`)
      details.push(`Working directory: ${diagnostics.workingDirectory}`)
      details.push(`Settings file: ${diagnostics.settingsPath}`)
      details.push(`Default settings: ${diagnostics.defaultSettingsPath}`)

      if (diagnostics.startedAt) {
        details.push(`Last startup attempt: ${diagnostics.startedAt}`)
      }

      if (diagnostics.lastError) {
        details.push(`Last backend error: ${diagnostics.lastError}`)
      }

      if (diagnostics.recentLogs.length > 0) {
        details.push(`Recent backend logs:\n${diagnostics.recentLogs.join('\n')}`)
      }
    }
  } catch (diagnosticError) {
    if (diagnosticError instanceof Error && diagnosticError.message) {
      details.push(`Failed to read backend diagnostics: ${diagnosticError.message}`)
    }
  }

  if (details.length === 0) {
    return defaultMessage
  }

  return `${defaultMessage}\n\n${details.join('\n')}`
}

export interface Settings {
  mt5_path: string
  auto_connect: boolean
  price_alerts_path: string
  account_monitoring_interval: number
  volatility_check_interval: number
  overlay_font_size: number
  overlay_font_color: string
  overlay_symbols: string[]
  overlay_width: number
  overlay_height: number
  api_refresh_interval: number
  dingtalk_enabled: boolean
  dingtalk_token: string
  dingtalk_secret: string
  wecom_enabled: boolean
  wecom_webhook_url: string
  feishu_enabled: boolean
  feishu_webhook_url: string
  push_price_alerts: boolean
  push_volatility_alerts: boolean
  push_indicator_alerts: boolean
  theme: string
  language: 'zh-CN' | 'en'
  alert_sound_enabled: boolean
  alert_sound_path: string
  alert_sound_volume: number
}

interface SettingsState {
  settings: Settings
  isLoading: boolean
  error: string | null
  fetchSettings: (backendUnavailableMessage?: string) => Promise<void>
  updateSettings: (newSettings: Partial<Settings>) => Promise<void>
}

const DEFAULT_SETTINGS: Settings = {
  mt5_path: '',
  auto_connect: false,
  price_alerts_path: '',
  account_monitoring_interval: 5,
  volatility_check_interval: 60,
  overlay_font_size: 24,
  overlay_font_color: '#4ade80',
  overlay_symbols: ['XAUUSD', 'USDJPY'],
  overlay_width: 320,
  overlay_height: 250,
  api_refresh_interval: 1000,
  dingtalk_enabled: false,
  dingtalk_token: '',
  dingtalk_secret: '',
  wecom_enabled: false,
  wecom_webhook_url: '',
  feishu_enabled: false,
  feishu_webhook_url: '',
  push_price_alerts: true,
  push_volatility_alerts: true,
  push_indicator_alerts: true,
  theme: 'light',
  language: 'zh-CN',
  alert_sound_enabled: true,
  alert_sound_path: '02.mp3',
  alert_sound_volume: 0.5,
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: DEFAULT_SETTINGS,
  isLoading: false,
  error: null,
  fetchSettings: async (backendUnavailableMessage = 'Unable to connect to the backend service.') => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('http://127.0.0.1:8765/settings')
      if (!response.ok) throw new Error('Failed to fetch settings')
      const settings = await response.json()
      set({
        settings: {
          ...DEFAULT_SETTINGS,
          ...settings,
          language: settings.language === 'en' ? 'en' : 'zh-CN',
        },
        isLoading: false,
      })
    } catch (err: any) {
      const errorMessage = await buildBackendUnavailableMessage(backendUnavailableMessage, err)
      set({ error: errorMessage, isLoading: false })
    }
  },
  updateSettings: async (newSettings) => {
    const updated = { ...get().settings, ...newSettings }
    set({ settings: updated, isLoading: true, error: null })
    try {
      const response = await fetch('http://127.0.0.1:8765/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      })
      if (!response.ok) throw new Error('Failed to save settings')
      
      // Notify main process to broadcast change to other windows
      if ((window as any).electron?.ipcRenderer) {
        await (window as any).electron.ipcRenderer.invoke('settings:notify-update')
      }
      
      set({ isLoading: false })
    } catch (err: any) {
      set({ error: err.message, isLoading: false })
    }
  },
}))
