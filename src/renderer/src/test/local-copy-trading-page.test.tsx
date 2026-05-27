import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import React from 'react'

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
    <I18nProvider language="en">
      <LocalCopyTradingPage />
    </I18nProvider>
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
        source_accounts: [
          { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
          { id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true },
        ],
        follower_accounts: [
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

  it('renders the local copy trading heading and tabs', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Local Copy Trading' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Source Accounts' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Follower Accounts' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Relationships' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Events' })).toBeInTheDocument()
  })

  it('renders multiple source rows, follower rows, and a relationship row', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Main A')).toBeInTheDocument()
    expect(screen.getByText('Main B')).toBeInTheDocument()
    expect(screen.getByText('Live Copy Trading')).toBeInTheDocument()
    expect(screen.getByText('When enabled, local copy trading reads source positions and sends MT5 market orders to follower accounts using the configured mappings. Validate accounts, symbols, and lot multipliers with small size first.')).toBeInTheDocument()
    expect(screen.getByText('10001')).toBeInTheDocument()
    expect(screen.getByText('Broker-A')).toBeInTheDocument()
    expect(screen.getByText('C:/MT5/source-a/terminal64.exe')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Follower Accounts' }))
    expect(await screen.findByText('Follower A')).toBeInTheDocument()
    expect(screen.getByText('Follower B')).toBeInTheDocument()
    expect(screen.getByText('20001')).toBeInTheDocument()
    expect(screen.getByText('Broker-C')).toBeInTheDocument()
    expect(screen.getByText('D:/MT5/follower-a/terminal64.exe')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Relationships' }))
    expect(await screen.findByText('XAUUSD')).toBeInTheDocument()
    expect(screen.getByText('XAUUSD.m')).toBeInTheDocument()
    expect(screen.getByText('Main A (10001)')).toBeInTheDocument()
    expect(screen.getByText('Follower A (20001)')).toBeInTheDocument()
    expect(screen.getByText('Lot Multiplier')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Events' }))
    expect(await screen.findByText('ticket-1')).toBeInTheDocument()
    expect(screen.getByText('Copied successfully')).toBeInTheDocument()
  })

  it('renders runtime configuration values', async () => {
    renderPage()

    expect((await screen.findAllByText('Enabled')).length).toBeGreaterThan(0)
    expect(screen.getByText('Poll: 2s')).toBeInTheDocument()
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
            source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true }],
            follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true }],
            relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true }],
            events: [],
          }),
        } as Response
      }
      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: false, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true }],
          follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true }],
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
        source_accounts: [],
        follower_accounts: [],
        relationships: [],
        events: [],
      }),
    })) as any

    renderPage()

    await user.click(await screen.findByRole('switch'))

    expect(await screen.findByText('Add at least 1 source account, 1 follower account, and 1 relationship before enabling.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Relationship' })).toBeDisabled()
  })

  it('allows closing the source dialog without completing the form and resets partial input', async () => {
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Source Account' }))
    expect(screen.getByText('Enter the MT5 terminal path for this source account along with the login, password, and server details required to sign in.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Source Account Name'), 'Draft Source')
    expect(screen.getByLabelText('Source Account Name')).toHaveValue('Draft Source')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByLabelText('Source Account Name')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Add Source Account' }))
    expect(await screen.findByLabelText('Source Account Name')).toHaveValue('')
  })

  it('allows closing the follower dialog without completing the form and resets partial input', async () => {
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Follower Account' }))
    expect(screen.getByText('Enter the MT5 terminal path for this follower account along with the login, password, and server details required to sign in.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Follower Account Name'), 'Draft Follower')
    expect(screen.getByLabelText('Follower Account Name')).toHaveValue('Draft Follower')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByLabelText('Follower Account Name')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Add Follower Account' }))
    expect(await screen.findByLabelText('Follower Account Name')).toHaveValue('')
  })

  it('edits an existing source account from the table', async () => {
    const user = userEvent.setup()
    let updatedPayload: Record<string, unknown> | null = null

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/source-accounts/src-1') {
        updatedPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [
              { id: 'src-1', name: 'Main A Updated', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a-updated/terminal64.exe', login: '10011', server: 'Broker-A2', password: 'secret-1', is_active: true },
              { id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true },
            ],
            follower_accounts: [
              { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
            ],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
          source_accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: 'secret-0', is_active: true },
            { id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true },
          ],
          follower_accounts: [
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    expect(await screen.findByText('Main A')).toBeInTheDocument()
    const sourcePanel = screen.getByRole('tabpanel', { name: 'Source Accounts' })
    const buttons = sourcePanel.querySelectorAll('button')
    await user.click(buttons[0] as HTMLButtonElement)

    expect(await screen.findByRole('heading', { name: 'Edit Source Account' })).toBeInTheDocument()
    expect(screen.getByLabelText('Source Account Name')).toHaveValue('Main A')
    await user.clear(screen.getByLabelText('Source Account Name'))
    await user.type(screen.getByLabelText('Source Account Name'), 'Main A Updated')
    await user.clear(screen.getByLabelText('MT5 Terminal Path'))
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:/MT5/source-a-updated/terminal64.exe')
    await user.clear(screen.getByLabelText('Login'))
    await user.type(screen.getByLabelText('Login'), '10011')
    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'secret-1')
    await user.clear(screen.getByLabelText('Server'))
    await user.type(screen.getByLabelText('Server'), 'Broker-A2')
    await user.click(screen.getByRole('button', { name: 'Update Source Account' }))

    await waitFor(() => {
      expect(updatedPayload).toMatchObject({
        name: 'Main A Updated',
        terminal_path: 'C:/MT5/source-a-updated/terminal64.exe',
        login: '10011',
        password: 'secret-1',
        server: 'Broker-A2',
      })
    })
  })

  it('edits an existing follower account from the table', async () => {
    const user = userEvent.setup()
    let updatedPayload: Record<string, unknown> | null = null

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/follower-accounts/fol-1') {
        updatedPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [
              { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
            ],
            follower_accounts: [
              { id: 'fol-1', name: 'Follower A Updated', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a-updated/terminal64.exe', login: '20011', server: 'Broker-C2', password: 'secret-2', is_active: true },
            ],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
          source_accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
          ],
          follower_accounts: [
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: 'secret-0', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()
    await user.click(screen.getByRole('tab', { name: 'Follower Accounts' }))
    expect(await screen.findByText('Follower A')).toBeInTheDocument()

    const followerPanel = screen.getByRole('tabpanel', { name: 'Follower Accounts' })
    const buttons = followerPanel.querySelectorAll('button')
    await user.click(buttons[0] as HTMLButtonElement)

    expect(await screen.findByRole('heading', { name: 'Edit Follower Account' })).toBeInTheDocument()
    expect(screen.getByLabelText('Follower Account Name')).toHaveValue('Follower A')
    await user.clear(screen.getByLabelText('Follower Account Name'))
    await user.type(screen.getByLabelText('Follower Account Name'), 'Follower A Updated')
    await user.clear(screen.getByLabelText('MT5 Terminal Path'))
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'D:/MT5/follower-a-updated/terminal64.exe')
    await user.clear(screen.getByLabelText('Login'))
    await user.type(screen.getByLabelText('Login'), '20011')
    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'secret-2')
    await user.clear(screen.getByLabelText('Server'))
    await user.type(screen.getByLabelText('Server'), 'Broker-C2')
    await user.click(screen.getByRole('button', { name: 'Update Follower Account' }))

    await waitFor(() => {
      expect(updatedPayload).toMatchObject({
        name: 'Follower A Updated',
        terminal_path: 'D:/MT5/follower-a-updated/terminal64.exe',
        login: '20011',
        password: 'secret-2',
        server: 'Broker-C2',
      })
    })
  })

  it('allows closing the relationship dialog without completing the form and resets partial input', async () => {
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Relationship' }))
    await user.clear(screen.getByLabelText('Follower Symbol'))
    await user.type(screen.getByLabelText('Follower Symbol'), 'XAUUSD.PRO')
    expect(screen.getByLabelText('Follower Symbol')).toHaveValue('XAUUSD.PRO')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByLabelText('Follower Symbol')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Add Relationship' }))
    expect(await screen.findByLabelText('Follower Symbol')).toHaveValue('XAUUSD')
  })

  it('submits source-account, follower-account, and relationship dialogs and refreshes the page', async () => {
    const user = userEvent.setup()
    let sourceCreated = false
    let followerCreated = false
    let relationshipCreated = false
    let sourcePayload: Record<string, unknown> | null = null
    let followerPayload: Record<string, unknown> | null = null
    let relationshipPayload: Record<string, unknown> | null = null

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/source-accounts') {
        sourceCreated = true
        sourcePayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            follower_accounts: [],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      if (url === 'http://127.0.0.1:8765/local-copy-trading/follower-accounts') {
        followerCreated = true
        followerPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      if (url === 'http://127.0.0.1:8765/local-copy-trading/relationships') {
        relationshipCreated = true
        relationshipPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            follower_accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            relationships: [{ id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 0.5, is_active: true }],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          source_accounts: [],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Source Account' }))
    await user.type(screen.getByLabelText('Source Account Name'), 'Main A')
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:\\MT5\\source\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '10001')
    await user.type(screen.getByLabelText('Password'), 'secret-1')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-A')
    await user.click(screen.getByRole('button', { name: 'Save Source Account' }))

    await user.click(screen.getByRole('button', { name: 'Add Follower Account' }))
    await user.type(screen.getByLabelText('Follower Account Name'), 'Follower A')
    await user.type(screen.getAllByLabelText('MT5 Terminal Path')[0], 'D:\\MT5\\follower\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '20002')
    await user.type(screen.getByLabelText('Password'), 'secret-2')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-B')
    await user.click(screen.getByRole('button', { name: 'Save Follower Account' }))

    await user.click(screen.getByRole('button', { name: 'Add Relationship' }))
    expect(screen.getByText('Choose the source account and follower account, then map the source symbol to the follower symbol. Different broker suffixes are supported.')).toBeInTheDocument()
    await user.selectOptions(await screen.findByLabelText('Source Account'), 'src-1')
    await user.selectOptions(screen.getByLabelText('Follower Account'), 'fol-1')
    await user.clear(screen.getByLabelText('Source Symbol'))
    await user.type(screen.getByLabelText('Source Symbol'), 'XAUUSD')
    await user.clear(screen.getByLabelText('Follower Symbol'))
    await user.type(screen.getByLabelText('Follower Symbol'), 'XAUUSD.m')
    await user.clear(screen.getByLabelText('Lot Multiplier'))
    await user.type(screen.getByLabelText('Lot Multiplier'), '0.5')
    await user.click(screen.getByRole('button', { name: 'Save Relationship' }))

    await waitFor(() => {
      expect(sourceCreated).toBe(true)
      expect(followerCreated).toBe(true)
      expect(relationshipCreated).toBe(true)
    })

    expect(sourcePayload).toMatchObject({
      name: 'Main A',
      connection_type: 'mt5_terminal',
      terminal_path: 'C:\\MT5\\source\\terminal64.exe',
      login: '10001',
      password: 'secret-1',
      server: 'Broker-Server-A',
    })
    expect(followerPayload).toMatchObject({
      name: 'Follower A',
      connection_type: 'mt5_terminal',
      terminal_path: 'D:\\MT5\\follower\\terminal64.exe',
      login: '20002',
      password: 'secret-2',
      server: 'Broker-Server-B',
    })
    expect(relationshipPayload).toMatchObject({
      source_account_id: 'src-1',
      follower_account_id: 'fol-1',
      symbol: 'XAUUSD',
      source_symbol: 'XAUUSD',
      follower_symbol: 'XAUUSD.m',
      lot_multiplier: 0.5,
    })
  })

  it('shows an error when a post fails', async () => {
    const user = userEvent.setup()
    let resolveSourceRequest: ((value: Response) => void) | null = null

    global.fetch = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === 'http://127.0.0.1:8765/local-copy-trading/source-accounts') {
        return new Promise<Response>((resolve) => {
          resolveSourceRequest = resolve
        })
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response)
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Source Account' }))
    await user.type(screen.getByLabelText('Source Account Name'), 'Broken')
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:\\MT5\\broken\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '30003')
    await user.type(screen.getByLabelText('Password'), 'secret-3')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-C')
    const saveButton = screen.getByRole('button', { name: 'Save Source Account' })
    await user.click(saveButton)

    expect(screen.getByRole('button', { name: 'Verifying and saving...' })).toBeDisabled()

    resolveSourceRequest?.({
      ok: false,
      json: async () => ({ detail: 'MT5 credential verification failed' }),
    } as Response)

    expect(await screen.findByText('MT5 credential verification failed')).toBeInTheDocument()
    expect(screen.getByLabelText('Source Account Name')).toBeInTheDocument()
  })

  it('shows an inline error when follower account verification fails', async () => {
    const user = userEvent.setup()
    let resolveFollowerRequest: ((value: Response) => void) | null = null

    global.fetch = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === 'http://127.0.0.1:8765/local-copy-trading/follower-accounts') {
        return new Promise<Response>((resolve) => {
          resolveFollowerRequest = resolve
        })
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
          source_accounts: [],
          follower_accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response)
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Follower Account' }))
    await user.type(screen.getByLabelText('Follower Account Name'), 'Broken Follower')
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'D:\\MT5\\broken\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '40004')
    await user.type(screen.getByLabelText('Password'), 'secret-4')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-D')
    await user.click(screen.getByRole('button', { name: 'Save Follower Account' }))

    expect(screen.getByRole('button', { name: 'Verifying and saving...' })).toBeDisabled()

    resolveFollowerRequest?.({
      ok: false,
      json: async () => ({ detail: 'Follower MT5 login failed' }),
    } as Response)

    expect(await screen.findByText('Follower MT5 login failed')).toBeInTheDocument()
    expect(screen.getByLabelText('Follower Account Name')).toBeInTheDocument()
  })

  it('deletes a source account after confirmation', async () => {
    const user = userEvent.setup()
    let deleteCalled = false

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/source-accounts/src-1') {
        deleteCalled = true
        expect(init?.method).toBe('DELETE')
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            source_accounts: [{ id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true }],
            follower_accounts: [
              { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
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
          source_accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
            { id: 'src-2', name: 'Main B', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-b/terminal64.exe', login: '10002', server: 'Broker-B', password: '', is_active: true },
          ],
          follower_accounts: [
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
          ],
          relationships: [
            { id: 'rel-1', source_account_id: 'src-1', follower_account_id: 'fol-1', symbol: 'XAUUSD', lot_multiplier: 1, is_active: true },
          ],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    expect(await screen.findByText('Main A')).toBeInTheDocument()
    const sourcePanel = screen.getByRole('tabpanel', { name: 'Source Accounts' })
    const deleteButtons = sourcePanel.querySelectorAll('button')
    await user.click(deleteButtons[1] as HTMLButtonElement)
    expect(await screen.findByText('Delete source account Main A (10001)? Related relationships and events will also be removed.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(deleteCalled).toBe(true)
    })
  })
})
