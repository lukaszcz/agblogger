import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import MastodonSharePrompt from '../MastodonSharePrompt'

import { storage } from './testUtils'

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

  // Issue #5: label should be associated with input
  it('has label associated with input via htmlFor', () => {
    render(<MastodonSharePrompt {...defaultProps} />)
    const label = screen.getByText('Mastodon instance')
    const input = screen.getByPlaceholderText('mastodon.social')
    expect(label).toHaveAttribute('for', input.getAttribute('id'))
  })

  // Issue #12: Enter key should submit
  it('submits on Enter key press', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), 'mastodon.social{Enter}')

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://mastodon.social/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    expect(defaultProps.onClose).toHaveBeenCalled()
    windowOpen.mockRestore()
  })

  // Issue #1: invalid hostnames should show validation error
  it('shows validation error for invalid hostname', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), 'evil.com/phishing')
    await user.click(screen.getByRole('button', { name: 'Share' }))

    expect(windowOpen).not.toHaveBeenCalled()
    expect(screen.getByText(/invalid instance/i)).toBeInTheDocument()
    windowOpen.mockRestore()
  })

  // Issue #1: protocol prefix should be stripped
  it('strips https:// prefix and shares correctly', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), 'https://mastodon.social')
    await user.click(screen.getByRole('button', { name: 'Share' }))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://mastodon.social/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    expect(storage.get('agblogger:mastodon-instance')).toBe('mastodon.social')
    windowOpen.mockRestore()
  })

  it('does not submit when input contains only whitespace', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), '   ')
    expect(screen.getByRole('button', { name: 'Share' })).toBeDisabled()
    windowOpen.mockRestore()
  })
})
