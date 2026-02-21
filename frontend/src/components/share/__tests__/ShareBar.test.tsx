import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import ShareBar from '../ShareBar'

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

describe('ShareBar', () => {
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

  it('renders all platform share buttons', () => {
    render(<ShareBar {...defaultProps} />)
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Mastodon')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on X')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Facebook')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on LinkedIn')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Reddit')).toBeInTheDocument()
    expect(screen.getByLabelText('Share via email')).toBeInTheDocument()
    expect(screen.getByLabelText('Copy link')).toBeInTheDocument()
  })

  it('opens share URL in new tab when platform button is clicked', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Bluesky'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://bsky.app/intent/compose?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('shows mastodon instance prompt when mastodon button clicked and no saved instance', async () => {
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(screen.getByPlaceholderText('mastodon.social')).toBeInTheDocument()
  })

  it('shares to mastodon directly when instance is saved in localStorage', async () => {
    storage.set('agblogger:mastodon-instance', 'hachyderm.io')
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://hachyderm.io/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('copies link and shows feedback on copy button click', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Copy link'))

    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument()
    })
  })

  it('shows native share button when navigator.share is available', () => {
    Object.defineProperty(navigator, 'share', {
      value: vi.fn(),
      writable: true,
      configurable: true,
    })
    render(<ShareBar {...defaultProps} />)
    expect(screen.getByLabelText('Share via device')).toBeInTheDocument()
  })

  it('hides native share button when navigator.share is unavailable', () => {
    Object.defineProperty(navigator, 'share', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    render(<ShareBar {...defaultProps} />)
    expect(screen.queryByLabelText('Share via device')).not.toBeInTheDocument()
  })
})
