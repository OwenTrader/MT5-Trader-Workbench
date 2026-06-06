import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'
import { AccountListPage } from '@/pages/AccountListPage'

function renderPage() {
  return render(
    <I18nProvider language="en">
      <AccountListPage />
    </I18nProvider>,
  )
}

describe('Account List Page', () => {
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
          { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
        ],
        relationships: [],
        events: [],
      }),
    })) as any
  })

  it('renders the account-list heading and account actions', async () => {
    renderPage()

    expect(await screen.findByRole('heading', { name: 'Account List' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add Account' })).toBeInTheDocument()
    expect(screen.getByText('Accounts: 2')).toBeInTheDocument()
    expect(screen.getByText('This page no longer separates source and follower accounts. Maintain the account pool here, then assign source and target roles freely on the Local Copy Trading page.')).toBeInTheDocument()
  })

  it('allows closing the account dialog without completing the form and resets partial input', async () => {
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Account' }))
    await user.type(screen.getByLabelText('Account Name'), 'Draft Account')
    expect(screen.getByLabelText('Account Name')).toHaveValue('Draft Account')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => {
      expect(screen.queryByLabelText('Account Name')).not.toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: 'Add Account' }))
    expect(await screen.findByLabelText('Account Name')).toHaveValue('')
  })

  it('edits an existing account from the table', async () => {
    const user = userEvent.setup()
    let updatedPayload: Record<string, unknown> | null = null

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/accounts/src-1') {
        updatedPayload = JSON.parse(String(init?.body ?? '{}'))
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [
              { id: 'src-1', name: 'Main A Updated', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a-updated/terminal64.exe', login: '10011', server: 'Broker-A2', password: 'secret-1', is_active: true },
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
          accounts: [
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: 'secret-0', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    expect(await screen.findByText('Main A')).toBeInTheDocument()
    const buttons = screen.getAllByRole('button')
    await user.click(buttons.find((button) => button.getAttribute('aria-label') === 'Edit Account') as HTMLButtonElement)

    expect(await screen.findByRole('heading', { name: 'Edit Account' })).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Account Name'))
    await user.type(screen.getByLabelText('Account Name'), 'Main A Updated')
    await user.clear(screen.getByLabelText('MT5 Terminal Path'))
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:/MT5/source-a-updated/terminal64.exe')
    await user.clear(screen.getByLabelText('Login'))
    await user.type(screen.getByLabelText('Login'), '10011')
    await user.clear(screen.getByLabelText('Password'))
    await user.type(screen.getByLabelText('Password'), 'secret-1')
    await user.clear(screen.getByLabelText('Server'))
    await user.type(screen.getByLabelText('Server'), 'Broker-A2')
    await user.click(screen.getByRole('button', { name: 'Update Account' }))

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

  it('submits the account dialog', async () => {
    const user = userEvent.setup()
    let created = false

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/accounts') {
        created = true
        expect(init?.body).toContain('Main A')
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [{ id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: '', login: '', server: '', password: '', is_active: true }],
            relationships: [],
            events: [],
          }),
        } as Response
      }

      return {
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: '2026-05-11T00:00:00+00:00' },
          accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Account' }))
    await user.type(screen.getByLabelText('Account Name'), 'Main A')
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:\\MT5\\source\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '10001')
    await user.type(screen.getByLabelText('Password'), 'secret-1')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-A')
    await user.click(screen.getByRole('button', { name: 'Save Account' }))

    await waitFor(() => {
      expect(created).toBe(true)
    })
  })

  it('shows an inline error when account verification fails', async () => {
    const user = userEvent.setup()
    let resolveRequest: ((value: Response) => void) | null = null

    global.fetch = vi.fn((input: RequestInfo | URL) => {
      if (String(input) === 'http://127.0.0.1:8765/local-copy-trading/accounts') {
        return new Promise<Response>((resolve) => {
          resolveRequest = resolve
        })
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
          accounts: [],
          relationships: [],
          events: [],
        }),
      } as Response)
    }) as any

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Add Account' }))
    await user.type(screen.getByLabelText('Account Name'), 'Broken')
    await user.type(screen.getByLabelText('MT5 Terminal Path'), 'C:\\MT5\\broken\\terminal64.exe')
    await user.type(screen.getByLabelText('Login'), '30003')
    await user.type(screen.getByLabelText('Password'), 'secret-3')
    await user.type(screen.getByLabelText('Server'), 'Broker-Server-C')
    await user.click(screen.getByRole('button', { name: 'Save Account' }))

    expect(screen.getByRole('button', { name: 'Verifying and saving...' })).toBeDisabled()

    resolveRequest?.({
      ok: false,
      json: async () => ({ detail: 'MT5 credential verification failed' }),
    } as Response)

    expect(await screen.findByText('MT5 credential verification failed')).toBeInTheDocument()
  })

  it('deletes an account after confirmation', async () => {
    const user = userEvent.setup()
    let deleteCalled = false

    global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)

      if (url === 'http://127.0.0.1:8765/local-copy-trading/accounts/src-1') {
        deleteCalled = true
        expect(init?.method).toBe('DELETE')
        return {
          ok: true,
          json: async () => ({
            runtime: { enabled: true, poll_interval_seconds: 2, last_error: null, last_checked_at: null },
            accounts: [{ id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true }],
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
            { id: 'src-1', name: 'Main A', connection_type: 'mt5_terminal', terminal_path: 'C:/MT5/source-a/terminal64.exe', login: '10001', server: 'Broker-A', password: '', is_active: true },
            { id: 'fol-1', name: 'Follower A', connection_type: 'mt5_terminal', terminal_path: 'D:/MT5/follower-a/terminal64.exe', login: '20001', server: 'Broker-C', password: '', is_active: true },
          ],
          relationships: [],
          events: [],
        }),
      } as Response
    }) as any

    renderPage()

    expect(await screen.findByText('Main A')).toBeInTheDocument()
    const buttons = screen.getAllByRole('button')
    const deleteButtons = buttons.filter((button) => button.getAttribute('aria-label') === 'Confirm Deletion')
    await user.click(deleteButtons[0] as HTMLButtonElement)
    expect(await screen.findByText('Delete account Main A (10001)? Related relationships and events will also be removed.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(deleteCalled).toBe(true)
    })
  })
})
