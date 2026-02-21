import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import ShareButton from '../ShareButton'

// Mock localStorage since jsdom doesn't always provide full implementation
const storage = new Map<string, string>()
const mockLocalStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
  get length() {
    return storage.size
  },
  key: (index: number) => [...storage.keys()][index] ?? null,
}

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
})

describe('ShareButton', () => {
  const defaultProps = {
    title: 'Hello World',
    author: 'Alice' as string | null,
    url: 'https://blog.example.com/post/hello',
  }

  beforeEach(() => {
    storage.clear()
    vi.resetAllMocks()
  })

  afterEach(() => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
  })

  it('renders a share button', () => {
    render(<ShareButton {...defaultProps} />)
    expect(screen.getByLabelText('Share this post')).toBeInTheDocument()
  })

  it('calls native share directly when available', async () => {
    const mockShare = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', {
      value: mockShare,
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))

    expect(mockShare).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Hello World',
        url: 'https://blog.example.com/post/hello',
      }),
    )
  })

  it('does not open dropdown when native share is available', async () => {
    Object.defineProperty(navigator, 'share', {
      value: vi.fn().mockResolvedValue(undefined),
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))

    expect(screen.queryByLabelText('Share on Bluesky')).not.toBeInTheDocument()
  })

  it('opens dropdown when native share is unavailable', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))

    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Mastodon')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on X')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Facebook')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on LinkedIn')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Reddit')).toBeInTheDocument()
    expect(screen.getByLabelText('Share via email')).toBeInTheDocument()
    expect(screen.getByLabelText('Copy link')).toBeInTheDocument()
  })

  it('closes dropdown when clicking outside', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(
      <div>
        <ShareButton {...defaultProps} />
        <span>outside</span>
      </div>,
    )

    await user.click(screen.getByLabelText('Share this post'))
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()

    await user.click(screen.getByText('outside'))
    expect(screen.queryByLabelText('Share on Bluesky')).not.toBeInTheDocument()
  })

  it('opens platform share URL from dropdown', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))
    await user.click(screen.getByLabelText('Share on Bluesky'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://bsky.app/intent/compose?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('closes dropdown after clicking a platform', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))
    await user.click(screen.getByLabelText('Share on X'))

    expect(screen.queryByLabelText('Share on Bluesky')).not.toBeInTheDocument()
  })

  it('shows mastodon prompt when no saved instance', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))
    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(screen.getByPlaceholderText('mastodon.social')).toBeInTheDocument()
  })

  it('shares to mastodon directly when instance is saved', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    storage.set('agblogger:mastodon-instance', 'hachyderm.io')
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))
    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://hachyderm.io/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('toggles dropdown open and closed', async () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Share this post'))
    expect(screen.queryByLabelText('Share on Bluesky')).not.toBeInTheDocument()
  })
})
