import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles/globals.css'
import { App } from './App'
import { I18nProvider } from '@/i18n'
import { useSettingsStore } from '@/stores/settings-store'

function Root() {
  const language = useSettingsStore((state) => state.settings.language || 'zh-CN')

  return (
    <I18nProvider language={language}>
      <App />
    </I18nProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
