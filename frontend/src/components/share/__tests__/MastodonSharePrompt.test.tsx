import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import MastodonSharePrompt from '../MastodonSharePrompt'

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

describe('MastodonSharePrompt', () => {
  const defaultProps = {
    shareText: '\u201cHello World\u201d by Alice https://example.com/post/hello',
    onClose: vi.fn(),
  }

  beforeEach(() => {
    storage.clear()
    vi.resetAllMocks()
  })

  it('renders instance input and share button', () => {
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByPlaceholderText('mastodon.social')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Share' })).toBeInTheDocument()
  })

  it('pre-fills input with saved instance from localStorage', () => {
    storage.set('agblogger:mastodon-instance', 'hachyderm.io')
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByPlaceholderText('mastodon.social')).toHaveValue('hachyderm.io')
  })

  it('disables share button when input is empty', () => {
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Share' })).toBeDisabled()
  })

  it('opens share URL and saves instance on submit', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), 'mastodon.social')
    await user.click(screen.getByRole('button', { name: 'Share' }))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://mastodon.social/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    expect(storage.get('agblogger:mastodon-instance')).toBe('mastodon.social')
    expect(defaultProps.onClose).toHaveBeenCalled()
    windowOpen.mockRestore()
  })

  it('calls onClose when cancel button is clicked', async () => {
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(defaultProps.onClose).toHaveBeenCalled()
  })
})
