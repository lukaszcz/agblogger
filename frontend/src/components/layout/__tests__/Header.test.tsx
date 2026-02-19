import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { UserResponse, SiteConfigResponse } from '@/api/client'

const siteConfig: SiteConfigResponse = {
  title: 'My Blog',
  description: 'A test blog',
  pages: [{ id: 'timeline', title: 'Posts', file: null }],
}

let mockUser: UserResponse | null = null
const mockLogout = vi.fn()

vi.mock('@/stores/siteStore', () => ({
  useSiteStore: (selector: (s: { config: SiteConfigResponse | null }) => unknown) =>
    selector({ config: siteConfig }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: UserResponse | null; logout: () => void }) => unknown) =>
    selector({ user: mockUser, logout: mockLogout }),
}))

import Header from '../Header'

function renderHeader(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Header />
    </MemoryRouter>,
  )
}

describe('Header', () => {
  beforeEach(() => {
    mockUser = null
    vi.clearAllMocks()
  })

  it('renders site title', () => {
    renderHeader()
    expect(screen.getByText('My Blog')).toBeInTheDocument()
  })

  it('Labels active at /labels', () => {
    renderHeader('/labels')
    const labelsLink = screen.getByRole('link', { name: 'Labels' })
    expect(labelsLink.className).toContain('border-accent')
  })

  it('Labels active at /labels/swe', () => {
    renderHeader('/labels/swe')
    const labelsLink = screen.getByRole('link', { name: 'Labels' })
    expect(labelsLink.className).toContain('border-accent')
  })

  it('Labels NOT active at /labels/graph', () => {
    renderHeader('/labels/graph')
    const labelsLink = screen.getByRole('link', { name: 'Labels' })
    expect(labelsLink.className).not.toContain('border-accent')
  })

  it('Graph active at /labels/graph', () => {
    renderHeader('/labels/graph')
    const graphLink = screen.getByRole('link', { name: 'Graph' })
    expect(graphLink.className).toContain('border-accent')
  })

  it('shows login when unauthenticated', () => {
    renderHeader()
    expect(screen.getByLabelText('Login')).toBeInTheDocument()
  })

  it('shows write and logout when authenticated', () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    renderHeader()
    expect(screen.getByText('Write')).toBeInTheDocument()
    expect(screen.getByLabelText('Logout')).toBeInTheDocument()
    expect(screen.queryByLabelText('Login')).not.toBeInTheDocument()
  })

  it('logout button has tooltip', () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    renderHeader()
    const logoutButton = screen.getByLabelText('Logout')
    expect(logoutButton).toHaveAttribute('title', 'Log out')
  })

  it('opens search on click', async () => {
    renderHeader()
    await userEvent.click(screen.getByLabelText('Search'))
    expect(screen.getByPlaceholderText('Search posts...')).toBeInTheDocument()
  })
})
