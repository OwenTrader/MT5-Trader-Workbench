export type MainLocale = 'zh-CN' | 'en'

const messages = {
  'zh-CN': {
    'tray.showWindow': '显示窗口',
    'tray.showOverlay': '开启浮窗',
    'tray.hideOverlay': '关闭浮窗',
    'tray.quit': '退出',
    'tray.tooltip': 'MT5 Trader Workbench',
    'window.title': 'Trader Workbench',
  },
  en: {
    'tray.showWindow': 'Show Window',
    'tray.showOverlay': 'Show Overlay',
    'tray.hideOverlay': 'Hide Overlay',
    'tray.quit': 'Quit',
    'tray.tooltip': 'MT5 Trader Workbench',
    'window.title': 'Trader Workbench',
  },
} as const

type MainMessageKey = keyof (typeof messages)['zh-CN']

export function tMain(locale: MainLocale, key: MainMessageKey): string {
  return messages[locale][key]
}
