import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockLogin = vi.fn()
let mockError: string | null = null
let mockIsLoading = false

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: {
    login: typeof mockLogin
    error: string | null
    isLoading: boolean
  }) => unknown) =>
    selector({ login: mockLogin, error: mockError, isLoading: mockIsLoading }),
}))

import LoginPage from '../LoginPage'

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    mockLogin.mockReset()
    mockError = null
    mockIsLoading = false
  })

  it('renders sign in form', () => {
    renderLogin()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('calls login with credentials', async () => {
    mockLogin.mockResolvedValue(undefined)
    renderLogin()

    await userEvent.type(screen.getByLabelText('Username'), 'admin')
    await userEvent.type(screen.getByLabelText('Password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(mockLogin).toHaveBeenCalledWith('admin', 'secret')
  })

  it('displays error from store', () => {
    mockError = 'Invalid username or password'
    renderLogin()
    expect(screen.getByText('Invalid username or password')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    mockIsLoading = true
    renderLogin()
    const button = screen.getByRole('button', { name: 'Signing in...' })
    expect(button).toBeDisabled()
  })
})
