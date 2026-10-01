import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles/globals.css'
import { App } from './App'
import { I18nProvider } from '@/i18n'
import { ErrorBoundary } from '@/components/error-boundary'
import { useSettingsStore } from '@/stores/settings-store'

function Root() {
  const language = useSettingsStore((state) => state.settings.language || 'zh-CN')

  return (
    <ErrorBoundary>
      <I18nProvider language={language}>
        <App />
      </I18nProvider>
    </ErrorBoundary>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
