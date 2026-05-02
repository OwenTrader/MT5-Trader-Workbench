import React, { createContext, useContext, useMemo } from 'react'
import { Locale, messages } from './messages'

type I18nContextValue = {
  locale: Locale
  t: (key: string, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function getMessage(source: unknown, key: string): string | undefined {
  return key.split('.').reduce<unknown>((current, part) => {
    if (current && typeof current === 'object' && part in current) {
      return (current as Record<string, unknown>)[part]
    }

    return undefined
  }, source) as string | undefined
}

function formatMessage(template: string, params?: Record<string, string | number>): string {
  if (!params) {
    return template
  }

  return template.replace(/\{(\w+)\}/g, (_match, token: string) => {
    const value = params[token]
    return value === undefined ? `{${token}}` : String(value)
  })
}

export function I18nProvider({ language, children }: { language: Locale; children: React.ReactNode }) {
  const value = useMemo<I18nContextValue>(() => ({
    locale: language,
    t: (key: string, params?: Record<string, string | number>) => {
      const template = getMessage(messages[language], key) ?? getMessage(messages['zh-CN'], key) ?? key
      return formatMessage(template, params)
    },
  }), [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }

  return context
}

export type { Locale }
