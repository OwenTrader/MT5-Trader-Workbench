import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { I18nProvider, useI18n } from '@/i18n'

function Probe() {
  const { locale, t } = useI18n()

  return (
    <div>
      <span>{locale}</span>
      <span>{t('nav.settings')}</span>
    </div>
  )
}

describe('I18nProvider', () => {
  it('uses zh-CN by default and can switch to English', () => {
    const { rerender } = render(
      <I18nProvider language="zh-CN">
        <Probe />
      </I18nProvider>
    )

    expect(screen.getByText('zh-CN')).toBeInTheDocument()
    expect(screen.getByText('设置')).toBeInTheDocument()

    rerender(
      <I18nProvider language="en">
        <Probe />
      </I18nProvider>
    )

    expect(screen.getByText('en')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })
})
