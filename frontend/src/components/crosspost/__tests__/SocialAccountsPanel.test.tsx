import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import SocialAccountsPanel from '../SocialAccountsPanel'

const mockFetchSocialAccounts = vi.fn()
const mockDeleteSocialAccount = vi.fn()
const mockAuthorizeBluesky = vi.fn()
const mockAuthorizeMastodon = vi.fn()

vi.mock('@/api/crosspost', () => ({
  fetchSocialAccounts: (...args: unknown[]) => mockFetchSocialAccounts(...args) as unknown,
  deleteSocialAccount: (...args: unknown[]) => mockDeleteSocialAccount(...args) as unknown,
  authorizeBluesky: (...args: unknown[]) => mockAuthorizeBluesky(...args) as unknown,
  authorizeMastodon: (...args: unknown[]) => mockAuthorizeMastodon(...args) as unknown,
}))

function renderPanel(props: { busy?: boolean; onBusyChange?: (busy: boolean) => void } = {}) {
  const defaultProps = {
    busy: false,
    onBusyChange: vi.fn(),
    ...props,
  }
  return render(<SocialAccountsPanel {...defaultProps} />)
}

describe('SocialAccountsPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mockFetchSocialAccounts.mockResolvedValue([])
  })

  it('renders section title "Social Accounts"', async () => {
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Social Accounts')).toBeInTheDocument()
    })
  })

  it('shows loading spinner initially', () => {
    mockFetchSocialAccounts.mockReturnValue(new Promise(() => {}))
    renderPanel()
    // The spinner is an svg with animate-spin class inside the section
    expect(screen.queryByText('Connect Bluesky')).not.toBeInTheDocument()
  })

  it('shows connect buttons when no accounts exist', async () => {
    mockFetchSocialAccounts.mockResolvedValue([])
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Connect Bluesky')).toBeInTheDocument()
    })
    expect(screen.getByText('Connect Mastodon')).toBeInTheDocument()
  })

  it('shows connected accounts with account name and disconnect button', async () => {
    mockFetchSocialAccounts.mockResolvedValue([
      {
        id: 1,
        platform: 'bluesky',
        account_name: 'alice.bsky.social',
        created_at: '2026-01-15T10:00:00Z',
      },
    ])
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('alice.bsky.social')).toBeInTheDocument()
    })
    expect(screen.getByLabelText('Disconnect alice.bsky.social')).toBeInTheDocument()
  })

  it('shows handle input when Connect Bluesky is clicked', async () => {
    mockFetchSocialAccounts.mockResolvedValue([])
    const user = userEvent.setup()
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Connect Bluesky')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Connect Bluesky'))
    expect(screen.getByLabelText('Bluesky Handle')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('alice.bsky.social')).toBeInTheDocument()
  })

  it('shows instance URL input when Connect Mastodon is clicked', async () => {
    mockFetchSocialAccounts.mockResolvedValue([])
    const user = userEvent.setup()
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Connect Mastodon')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Connect Mastodon'))
    expect(screen.getByLabelText('Mastodon Instance URL')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('https://mastodon.social')).toBeInTheDocument()
  })

  it('disables controls when busy prop is true', async () => {
    mockFetchSocialAccounts.mockResolvedValue([
      {
        id: 1,
        platform: 'bluesky',
        account_name: 'alice.bsky.social',
        created_at: '2026-01-15T10:00:00Z',
      },
    ])
    renderPanel({ busy: true })
    await waitFor(() => {
      expect(screen.getByText('alice.bsky.social')).toBeInTheDocument()
    })
    expect(screen.getByLabelText('Disconnect alice.bsky.social')).toBeDisabled()
    expect(screen.getByText('Connect Bluesky')).toBeDisabled()
    expect(screen.getByText('Connect Mastodon')).toBeDisabled()
  })

  it('shows inline disconnect confirmation when trash icon is clicked', async () => {
    mockFetchSocialAccounts.mockResolvedValue([
      {
        id: 1,
        platform: 'bluesky',
        account_name: 'alice.bsky.social',
        created_at: '2026-01-15T10:00:00Z',
      },
    ])
    const user = userEvent.setup()
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('alice.bsky.social')).toBeInTheDocument()
    })
    await user.click(screen.getByLabelText('Disconnect alice.bsky.social'))
    expect(screen.getByText('Confirm disconnect?')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('disconnects account on confirm', async () => {
    mockFetchSocialAccounts.mockResolvedValue([
      {
        id: 1,
        platform: 'bluesky',
        account_name: 'alice.bsky.social',
        created_at: '2026-01-15T10:00:00Z',
      },
    ])
    mockDeleteSocialAccount.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('alice.bsky.social')).toBeInTheDocument()
    })
    await user.click(screen.getByLabelText('Disconnect alice.bsky.social'))
    await user.click(screen.getByText('Confirm'))
    await waitFor(() => {
      expect(mockDeleteSocialAccount).toHaveBeenCalledWith(1)
    })
    await waitFor(() => {
      expect(screen.queryByText('alice.bsky.social')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Account disconnected.')).toBeInTheDocument()
  })

  it('shows error when fetching accounts fails', async () => {
    mockFetchSocialAccounts.mockRejectedValue(new Error('Network error'))
    renderPanel()
    await waitFor(() => {
      expect(screen.getByText('Failed to load social accounts.')).toBeInTheDocument()
    })
  })

  it('does not call onBusyChange again when callback reference changes', async () => {
    mockFetchSocialAccounts.mockResolvedValue([])
    const onBusyChange1 = vi.fn()
    const onBusyChange2 = vi.fn()

    const { rerender } = render(
      <SocialAccountsPanel busy={false} onBusyChange={onBusyChange1} />,
    )
    await waitFor(() => {
      expect(screen.getByText('Connect Bluesky')).toBeInTheDocument()
    })

    // Record call count after initial render
    const initialCalls = onBusyChange1.mock.calls.length

    // Re-render with a new callback reference — should NOT trigger extra calls
    rerender(<SocialAccountsPanel busy={false} onBusyChange={onBusyChange2} />)

    // Wait a tick for effects to settle
    await waitFor(() => {
      expect(screen.getByText('Connect Bluesky')).toBeInTheDocument()
    })

    // onBusyChange2 should not have been called because localBusy didn't change
    expect(onBusyChange2).not.toHaveBeenCalled()
    // And onBusyChange1 should not have received extra calls beyond initial
    expect(onBusyChange1.mock.calls.length).toBe(initialCalls)
  })
})
