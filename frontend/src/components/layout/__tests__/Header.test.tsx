import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import type { UserResponse, SiteConfigResponse } from '@/api/client'

const siteConfig: SiteConfigResponse = {
  title: 'My Blog',
  description: 'A test blog',
  pages: [
    { id: 'timeline', title: 'Posts', file: null },
    { id: 'labels', title: 'Labels', file: null },
  ],
}

let mockUser: UserResponse | null = null
let mockIsLoggingOut = false
const mockLogout = vi.fn()

vi.mock('@/stores/siteStore', () => ({
  useSiteStore: (selector: (s: { config: SiteConfigResponse | null }) => unknown) =>
    selector({ config: siteConfig }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: {
    user: UserResponse | null
    logout: () => Promise<void>
    isLoggingOut: boolean
  }) => unknown) =>
    selector({ user: mockUser, logout: mockLogout, isLoggingOut: mockIsLoggingOut }),
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
    mockIsLoggingOut = false
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

  it('shows login when unauthenticated', () => {
    renderHeader()
    expect(screen.getByLabelText('Login')).toBeInTheDocument()
  })

  it('shows write and logout when authenticated', () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    renderHeader()
    expect(screen.getAllByText('Write').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByLabelText('Logout').length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByLabelText('Login')).not.toBeInTheDocument()
  })

  it('disables logout button while logout is in progress', () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockIsLoggingOut = true
    renderHeader()
    const logoutButtons = screen.getAllByLabelText('Logout')
    logoutButtons.forEach((btn) => expect(btn).toBeDisabled())
  })

  it('logout button has tooltip', () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    renderHeader()
    const logoutButtons = screen.getAllByLabelText('Logout')
    // Desktop logout button has tooltip
    expect(logoutButtons.some((btn) => btn.getAttribute('title') === 'Log out')).toBe(true)
  })

  it('shows hamburger menu button', () => {
    renderHeader()
    expect(screen.getByLabelText('Menu')).toBeInTheDocument()
  })

  it('toggles mobile menu on hamburger click', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    renderHeader()

    const menuButton = screen.getByLabelText('Menu')
    await userEvent.click(menuButton)

    // Mobile menu should show nav links
    const postLinks = screen.getAllByText('Posts')
    expect(postLinks.length).toBeGreaterThanOrEqual(2) // desktop + mobile
  })

  it('opens search on click', async () => {
    renderHeader()
    await userEvent.click(screen.getByLabelText('Search'))
    expect(screen.getByPlaceholderText('Search posts...')).toBeInTheDocument()
  })
})
