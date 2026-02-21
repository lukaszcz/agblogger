import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { SocialAccount } from '@/api/crosspost'
import CrossPostDialog from '../CrossPostDialog'

const mockCrossPost = vi.fn()

vi.mock('@/api/crosspost', () => ({
  crossPost: (...args: unknown[]) => mockCrossPost(...args) as unknown,
}))

const blueskyAccount: SocialAccount = {
  id: 1,
  platform: 'bluesky',
  account_name: 'alice.bsky.social',
  created_at: '2026-01-15T10:00:00Z',
}

const mastodonAccount: SocialAccount = {
  id: 2,
  platform: 'mastodon',
  account_name: '@alice@mastodon.social',
  created_at: '2026-01-16T10:00:00Z',
}

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  accounts: [blueskyAccount, mastodonAccount],
  postPath: 'posts/2026-02-20-hello-world/index.md',
  postTitle: 'Hello World',
  postExcerpt: 'This is a test post excerpt.',
  postLabels: ['swe', 'typescript'],
}

function renderDialog(
  overrides: Partial<typeof defaultProps> & { initialPlatforms?: string[] } = {},
) {
  const props = { ...defaultProps, ...overrides }
  return render(<CrossPostDialog {...props} />)
}

describe('CrossPostDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('does not render when open is false', () => {
    renderDialog({ open: false })
    expect(screen.queryByText('Cross-Post')).not.toBeInTheDocument()
  })

  it('renders platform checkboxes for connected accounts', () => {
    renderDialog()
    expect(screen.getByText('alice.bsky.social')).toBeInTheDocument()
    expect(screen.getByText('@alice@mastodon.social')).toBeInTheDocument()
    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes).toHaveLength(2)
    expect(checkboxes[0]).toBeChecked()
    expect(checkboxes[1]).toBeChecked()
  })

  it('shows character count per selected platform', () => {
    renderDialog()
    // Both platforms should show character counts since both are checked by default
    expect(screen.getByText(/\/300/)).toBeInTheDocument()
    expect(screen.getByText(/\/500/)).toBeInTheDocument()
  })

  it('disables post button when over character limit', async () => {
    const user = userEvent.setup()
    renderDialog({ accounts: [blueskyAccount] })

    const textarea = screen.getByLabelText('Cross-post text')
    // Clear existing text and type text over 300 characters
    await user.clear(textarea)
    const longText = 'a'.repeat(301)
    await user.type(textarea, longText)

    const postButton = screen.getByRole('button', { name: 'Post' })
    expect(postButton).toBeDisabled()

    // Counter's parent container should be red
    const counter = screen.getByText(`${longText.length}/300`)
    expect(counter.closest('div')).toHaveClass('text-red-600')
  })

  it('disables post button when no platforms selected', async () => {
    const user = userEvent.setup()
    renderDialog()

    // Uncheck all platforms
    const checkboxes = screen.getAllByRole('checkbox')
    for (const checkbox of checkboxes) {
      await user.click(checkbox)
    }

    const postButton = screen.getByRole('button', { name: 'Post' })
    expect(postButton).toBeDisabled()
  })

  it('calls crossPost with selected platforms and custom text on submit', async () => {
    mockCrossPost.mockResolvedValue([
      {
        id: 1,
        post_path: defaultProps.postPath,
        platform: 'bluesky',
        platform_id: '123',
        status: 'posted',
        posted_at: '2026-02-20T10:00:00Z',
        error: null,
      },
    ])

    const user = userEvent.setup()
    renderDialog({ accounts: [blueskyAccount] })

    const textarea = screen.getByLabelText('Cross-post text')
    await user.clear(textarea)
    await user.type(textarea, 'Custom post text')

    await user.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(mockCrossPost).toHaveBeenCalledWith(
        defaultProps.postPath,
        ['bluesky'],
        'Custom post text',
      )
    })
  })

  it('shows results after successful posting', async () => {
    mockCrossPost.mockResolvedValue([
      {
        id: 1,
        post_path: defaultProps.postPath,
        platform: 'bluesky',
        platform_id: '123',
        status: 'posted',
        posted_at: '2026-02-20T10:00:00Z',
        error: null,
      },
      {
        id: 2,
        post_path: defaultProps.postPath,
        platform: 'mastodon',
        platform_id: null,
        status: 'failed',
        posted_at: null,
        error: 'Rate limited',
      },
    ])

    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(screen.getByText('Cross-Post Results')).toBeInTheDocument()
    })

    expect(screen.getByText('Posted')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('Rate limited')).toBeInTheDocument()

    // Should have Close button in results view
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('shows error banner when API call fails', async () => {
    mockCrossPost.mockRejectedValue(new Error('Network error'))

    const user = userEvent.setup()
    renderDialog()

    await user.click(screen.getByRole('button', { name: 'Post' }))

    await waitFor(() => {
      expect(screen.getByText('Failed to cross-post. Please try again.')).toBeInTheDocument()
    })
  })

  it('pre-checks only initialPlatforms when provided', () => {
    renderDialog({ initialPlatforms: ['bluesky'] })

    const checkboxes = screen.getAllByRole('checkbox')
    expect(checkboxes[0]).toBeChecked() // bluesky
    expect(checkboxes[1]).not.toBeChecked() // mastodon
  })

  it('generates default text with excerpt, hashtags, and URL', () => {
    renderDialog()

    const textarea = screen.getByLabelText('Cross-post text')
    const value = (textarea as HTMLTextAreaElement).value
    expect(value).toContain('This is a test post excerpt.')
    expect(value).toContain('#swe')
    expect(value).toContain('#typescript')
    expect(value).toContain('/post/2026-02-20-hello-world')
  })

  it('uses postTitle when postExcerpt is empty', () => {
    renderDialog({ postExcerpt: '' })

    const textarea = screen.getByLabelText('Cross-post text')
    const value = (textarea as HTMLTextAreaElement).value
    expect(value).toContain('Hello World')
    expect(value).not.toContain('This is a test post excerpt.')
  })

  it('hides character counter when platform is unchecked', async () => {
    const user = userEvent.setup()
    renderDialog({ accounts: [blueskyAccount] })

    expect(screen.getByText(/\/300/)).toBeInTheDocument()

    // Uncheck bluesky
    await user.click(screen.getByRole('checkbox'))

    expect(screen.queryByText(/\/300/)).not.toBeInTheDocument()
  })

  it('calls onClose when Cancel button is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderDialog({ onClose })

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('disables controls while posting', async () => {
    let resolvePost: (value: unknown) => void
    mockCrossPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve
      }),
    )

    const user = userEvent.setup()
    renderDialog({ accounts: [blueskyAccount] })

    await user.click(screen.getByRole('button', { name: 'Post' }))

    // While posting, controls should be disabled
    expect(screen.getByLabelText('Cross-post text')).toBeDisabled()
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Posting...' })).toBeDisabled()

    // Resolve to clean up
    resolvePost!([])
    await waitFor(() => {
      expect(screen.getByText('Cross-Post Results')).toBeInTheDocument()
    })
  })
})
