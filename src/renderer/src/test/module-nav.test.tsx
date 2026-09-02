import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ModuleNav } from '@/components/module-nav'
import { I18nProvider } from '@/i18n'
import { SidebarProvider } from '@/components/ui/sidebar'

function renderModuleNav(activeModule: string, onModuleChange = vi.fn()) {
  return render(
    <I18nProvider language="zh-CN">
      <SidebarProvider>
        <ModuleNav activeModule={activeModule} onModuleChange={onModuleChange} />
      </SidebarProvider>
    </I18nProvider>
  )
}

describe('ModuleNav Component', () => {
  it('renders all core workspace and system items correctly', () => {
    renderModuleNav('dashboard')

    expect(screen.getByTestId('sidebar-icon-dashboard')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-alerts')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-automation')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-quant')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-event-log')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-sponsor')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-icon-settings')).toBeInTheDocument()
  })

  it('correctly maps sub-modules to their corresponding parent hub active states', () => {
    const { rerender } = render(
      <I18nProvider language="zh-CN">
        <SidebarProvider>
          <ModuleNav activeModule="risk-control" onModuleChange={vi.fn()} />
        </SidebarProvider>
      </I18nProvider>
    )

    const autoBtn = screen.getByTestId('sidebar-icon-automation').closest('button')
    expect(autoBtn).toHaveAttribute('data-active', 'true')

    rerender(
      <I18nProvider language="zh-CN">
        <SidebarProvider>
          <ModuleNav activeModule="price-alerts" onModuleChange={vi.fn()} />
        </SidebarProvider>
      </I18nProvider>
    )

    const alertsBtn = screen.getByTestId('sidebar-icon-alerts').closest('button')
    expect(alertsBtn).toHaveAttribute('data-active', 'true')
    expect(autoBtn).toHaveAttribute('data-active', 'false')
  })

  it('triggers onModuleChange with workspace id on click', () => {
    const handleModuleChange = vi.fn()
    renderModuleNav('dashboard', handleModuleChange)

    const alertsBtn = screen.getByTestId('sidebar-icon-alerts').closest('button')
    fireEvent.click(alertsBtn!)

    expect(handleModuleChange).toHaveBeenCalledWith('alerts')
  })
})
