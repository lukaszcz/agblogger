import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PlatformIcon from '../PlatformIcon'

describe('PlatformIcon', () => {
  it('renders Bluesky icon', () => {
    render(<PlatformIcon platform="bluesky" />)
    expect(screen.getByLabelText('Bluesky')).toBeInTheDocument()
  })

  it('renders Mastodon icon', () => {
    render(<PlatformIcon platform="mastodon" />)
    expect(screen.getByLabelText('Mastodon')).toBeInTheDocument()
  })

  it('renders X icon', () => {
    render(<PlatformIcon platform="x" />)
    expect(screen.getByLabelText('X')).toBeInTheDocument()
  })

  it('renders Facebook icon', () => {
    render(<PlatformIcon platform="facebook" />)
    expect(screen.getByLabelText('Facebook')).toBeInTheDocument()
  })

  it('renders LinkedIn icon', () => {
    render(<PlatformIcon platform="linkedin" />)
    expect(screen.getByLabelText('LinkedIn')).toBeInTheDocument()
  })

  it('renders Reddit icon', () => {
    render(<PlatformIcon platform="reddit" />)
    expect(screen.getByLabelText('Reddit')).toBeInTheDocument()
  })

  it('renders fallback for unknown platform', () => {
    render(<PlatformIcon platform="unknown" />)
    expect(screen.getByLabelText('unknown')).toBeInTheDocument()
  })

  it('applies custom size', () => {
    render(<PlatformIcon platform="bluesky" size={24} />)
    const icon = screen.getByLabelText('Bluesky')
    expect(icon).toHaveAttribute('width', '24')
    expect(icon).toHaveAttribute('height', '24')
  })
})
