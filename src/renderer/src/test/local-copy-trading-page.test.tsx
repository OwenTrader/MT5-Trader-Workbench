import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/components/ui/select', () => {
  const SelectContext = React.createContext<{
    value?: string
    onValueChange?: (value: string) => void
    options: Array<{ value: string; label: string }>
    registerOption: (option: { value: string; label: string }) => void
  } | null>(null)

  function Select({ value, onValueChange, children }: { value?: string; onValueChange?: (value: string) => void; children: React.ReactNode }) {
    const [options, setOptions] = React.useState<Array<{ value: string; label: string }>>([])

    const registerOption = React.useCallback((option: { value: string; label: string }) => {
      setOptions((current) => (current.some((item) => item.value === option.value) ? current : [...current, option]))
    }, [])

    return <SelectContext.Provider value={{ value, onValueChange, options, registerOption }}>{children}</SelectContext.Provider>
  }

  function SelectTrigger({ 'aria-label': ariaLabel }: { children: React.ReactNode; 'aria-label'?: string }) {
    const context = React.useContext(SelectContext)
    if (!context) {
      return null
    }

    return (
      <select aria-label={ariaLabel} value={context.value ?? ''} onChange={(event) => context.onValueChange?.(event.target.value)}>
        <option value=""></option>
        {context.options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    )
  }

  function SelectValue() {
    return null
  }

  function SelectContent({ children }: { children: React.ReactNode }) {
    return <>{children}</>
  }

  function SelectGroup({ children }: { children: React.ReactNode }) {
    return <>{children}</>
  }

  function SelectItem({ value, children }: { value: string; children: React.ReactNode }) {
    const context = React.useContext(SelectContext)

    React.useEffect(() => {
      const label = typeof children === 'string' ? children : String(value)
      context?.registerOption({ value, label })
    }, [children, context, value])

    return <>{children}</>
  }

  SelectItem.displayName = 'SelectItem'

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectGroup,
    SelectItem,
  }
})

import { I18nProvider } from '@/i18n'
import { LocalCopyTradingPage } from '@/pages/LocalCopyTradingPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <I18nProvider language="en">
        <LocalCopyTradingPage />
      </I18nProvider>
    </MemoryRouter>,
  )
}

describe('Local Copy Trading Page', () => {
  beforeEach(() => {
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = () => false
    }
    if (!Element.prototype.setPointerCapture) {
      Element.prototype.setPointerCapture = () => {}
    }
    if (!Element.prototype.releasePointerCapture) {
      Element.prototype.releasePointerCapture = () => {}
    }

    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
        accounts: [
          { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
          { id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true },
          { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
          { id: 'fol-2', name: 'Follower B', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-b/terminal64.exe', login: '20002', server: 'Broker-D', password: '', is_active: true },
        ],
        relationships: [
          { id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', source_symbol: 'XAUUSD', follower_symbol: 'XAUUSD.m', lot_multiplier: 1, is_active: true },
        ],
        events: [
          { id: 'evt-1', relationship_id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', position_id: 'ticket-1', symbol: 'XAUUSD', status: 'copied', message: 'Copied successfully', created_at: '2026-05-11T00:00:00+00:00' },
        ],
      }),
    })) as any
  })

  it('renders the local copy trading heading, tabs, and account-list action', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Local Copy Trading' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Relationships' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Events' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Account List' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add Source Account' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add Follower Account' })).not.toBeInTheDocument()
  })

  it('renders account summary, relationship data, and events', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Manage account assignment, relationships, runtime state, and sync events.')).toBeInTheDocument()
    expect(screen.getByText('Accounts: 4')).toBeInTheDocument()
    expect(screen.getByText('Maintain accounts in Account List, then assign them here as source or follower accounts.')).toBeInTheDocument()

    expect(await screen.findByText('Main A (10001)')).toBeInTheDocument()
    expect(screen.getByText('Follower A (20001)')).toBeInTheDocument()
    expect(screen.getByText('XAUUSD.m')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Events' }))
    expect(await screen.findByText('ticket-1')).toBeInTheDocument()
    expect(screen.getByText('Copied successfully')).toBeInTheDocument()
  })

  it('updates runtime enabled state from the page', async () => {
    const user = userEvent.setup()
    let runtimeUpdated = false

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === 'http://127.0.0.1:8765/local-copy-trading/runtime') {
        runtimeUpdated = true
        expect(init?.method).toBe('POST')
        expect(init?.body).toContain('"enabled":true')
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [
              { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: 'Broker-A', password: '', is_active: true },
              { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: 'Broker-C', password: '', is_active: true },
            ],
            relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true }],
            events: [],
          }),
        } as Response
      }
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: 'Broker-A', password: '', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: 'Broker-C', password: '', is_active: true },
          ],
          relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true }],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    await user.click(await screen.findByRole('switch'))
    expect(await screen.findByText('Enable Local Copy Trading?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Enable' }))

    await waitFor(() => {
      expect(runtimeUpdated).toBe(true)
    })
  })

  it('blocks enabling runtime without required local copy trading configuration', async () => {
    const user = userEvent.setup()

    global.fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        runtime: { enabled: false, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
        accounts: [],
        relationships: [],
        events: [],
      }),
    })) as any

    renderPage()

    await user.click(await screen.findByRole('switch'))

    expect(await screen.findByText('Add at least 2 accounts and 1 relationship before enabling.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Relationship' })).toBeDisabled()
  })

  it('allows closing the relationship dialog without completing the form and resets partial input', async () => {
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Relationship' }))
    await user.clear(screen.getByLabelText('Follower Symbol'))
    await user.type(screen.getByLabelText('Follower Symbol'), 'XAUUSD.PRO')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByLabelText('Follower Symbol')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Add Relationship' }))
    expect(await screen.findByLabelText('Follower Symbol')).toHaveValue('XAUUSD')
  })

  it('submits the relationship dialog and refreshes the page', async () => {
    const user = userEvent.setup()
    let relationshipCreated = false
    let relationshipPayload: Record<string, unknown> | null = null

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === 'http://127.0.0.1:8765/local-copy-trading/relationships') {
        relationshipCreated = true
        relationshipPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [
              { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: '', password: '', is_active: true },
              { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: '', password: '', is_active: true },
            ],
            relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', source_symbol: 'XAUUSD', follower_symbol: 'XAUUSD.m', lot_multiplier: 0.5, is_active: true }],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: '', password: '', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: '', password: '', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Relationship' }))
    await user.selectOptions(await screen.findByLabelText('Source Account'), 'src-1')
    await user.selectOptions(screen.getByLabelText('Follower Account'), 'fol-1')
    await user.clear(screen.getByLabelText('Lot Multiplier'))
    await user.type(screen.getByLabelText('Lot Multiplier'), '0.5')
    await user.click(screen.getByRole('button', { name: 'Save Relationship' }))

    await waitFor(() => {
      expect(relationshipCreated).toBe(true)
    })

    expect(relationshipPayload).toMatchObject({
      source_account_id: 'src-1',
      follower_account_id: 'fol-1',
      symbol: 'XAUUSD',
      source_symbol: 'XAUUSD',
      follower_symbol: 'XAUUSD',
      lot_multiplier: 0.5,
    })
  })

  it('deletes a relationship after confirmation', async () => {
    const user = userEvent.setup()
    let deleteCalled = false

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/relationships/rel-1') {
        deleteCalled = true
        expect(init?.method).toBe('DELETE')
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [
              { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: '', password: '', is_active: true },
              { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: '', password: '', is_active: true },
            ],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '10001', server: '', password: '', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '20001', server: '', password: '', is_active: true },
          ],
          relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', source_symbol: 'XAUUSD', follower_symbol: 'XAUUSD.m', lot_multiplier: 1, is_active: true }],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    await user.click(screen.getByRole('tab', { name: 'Relationships' }))
    await screen.findByText('Main A (10001)')
    const relationshipPanel = screen.getByRole('tabpanel', { name: 'Relationships' })
    const deleteButtons = relationshipPanel.querySelectorAll('button')
    await user.click(deleteButtons[0] as HTMLButtonElement)
    expect(await screen.findByText('Delete relationship rel-1? Related events will also be removed.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(deleteCalled).toBe(true)
    })
  })
})
