import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { StatusBar } from '@/components/status-bar'
import { I18nProvider } from '@/i18n'

describe('StatusBar Component', () => {
  it('renders MT5 status and stream server info', () => {
    render(
      <I18nProvider language="zh-CN">
        <StatusBar />
      </I18nProvider>
    )

    expect(screen.getByText(/MT5:/i)).toBeInTheDocument()
    expect(screen.getByText(/推流服务:/i)).toBeInTheDocument()
  })

  it('triggers onOpenCommandPalette on clicking shortcut button', () => {
    const handleOpen = vi.fn()
    render(
      <I18nProvider language="zh-CN">
        <StatusBar onOpenCommandPalette={handleOpen} />
      </I18nProvider>
    )

    const cmdBtn = screen.getByRole('button', { name: /Ctrl \+ K 快捷指令/i })
    fireEvent.click(cmdBtn)

    expect(handleOpen).toHaveBeenCalledTimes(1)
  })
})
