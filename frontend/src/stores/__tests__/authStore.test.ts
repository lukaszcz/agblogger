import { describe, it, expect, vi, beforeEach } from 'vitest'

// Stub localStorage before any module imports
const storage = new Map<string, string>()
const localStorageMock = {
  getItem: vi.fn((key: string) => storage.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
  removeItem: vi.fn((key: string) => storage.delete(key)),
  clear: vi.fn(() => storage.clear()),
  get length() { return storage.size },
  key: vi.fn((i: number) => [...storage.keys()][i] ?? null),
}
vi.stubGlobal('localStorage', localStorageMock)

const mockFetchMe = vi.fn()
const mockApiLogin = vi.fn()
const mockApiLogout = vi.fn()

vi.mock('@/api/auth', () => ({
  fetchMe: (...args: unknown[]) => mockFetchMe(...args) as unknown,
  login: (...args: unknown[]) => mockApiLogin(...args) as unknown,
  logout: (...args: unknown[]) => mockApiLogout(...args) as unknown,
}))

class MockHTTPError extends Error {
  response: { status: number }
  constructor(status: number) {
    super(`HTTP ${status}`)
    this.response = { status }
  }
}

vi.mock('@/api/client', () => ({
  HTTPError: MockHTTPError,
}))

// Import after mocks are set up
const { useAuthStore } = await import('@/stores/authStore')

const testUser = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  display_name: 'Admin',
  is_admin: true,
}

describe('authStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    storage.clear()
    useAuthStore.setState({ user: null, isLoading: false, error: null })
  })

  describe('checkAuth', () => {
    it('no token sets user to null', async () => {
      await useAuthStore.getState().checkAuth()
      expect(useAuthStore.getState().user).toBeNull()
      expect(mockFetchMe).not.toHaveBeenCalled()
    })

    it('success sets user', async () => {
      storage.set('access_token', 'valid-token')
      mockFetchMe.mockResolvedValue(testUser)

      await useAuthStore.getState().checkAuth()
      expect(useAuthStore.getState().user).toEqual(testUser)
    })

    it('401 clears tokens from localStorage', async () => {
      storage.set('access_token', 'expired')
      storage.set('refresh_token', 'expired-refresh')
      mockFetchMe.mockRejectedValue(new MockHTTPError(401))

      await useAuthStore.getState().checkAuth()
      expect(useAuthStore.getState().user).toBeNull()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token')
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token')
      expect(storage.has('access_token')).toBe(false)
      expect(storage.has('refresh_token')).toBe(false)
    })

    it('non-401 error clears user and logs error', async () => {
      storage.set('access_token', 'valid')
      const error = new Error('Network failure')
      mockFetchMe.mockRejectedValue(error)
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      await useAuthStore.getState().checkAuth()
      expect(useAuthStore.getState().user).toBeNull()
      expect(consoleSpy).toHaveBeenCalledWith('Auth check failed:', error)
      consoleSpy.mockRestore()
    })
  })

  describe('login', () => {
    it('success sets user', async () => {
      mockApiLogin.mockResolvedValue({ access_token: 'tok', refresh_token: 'ref', token_type: 'bearer' })
      mockFetchMe.mockResolvedValue(testUser)

      await useAuthStore.getState().login('admin', 'password')
      expect(useAuthStore.getState().user).toEqual(testUser)
      expect(useAuthStore.getState().isLoading).toBe(false)
    })

    it('401 shows invalid credentials message', async () => {
      mockApiLogin.mockRejectedValue(new MockHTTPError(401))

      await expect(useAuthStore.getState().login('bad', 'creds')).rejects.toThrow('Login failed')
      expect(useAuthStore.getState().error).toBe('Invalid username or password')
    })

    it('generic error shows generic message', async () => {
      mockApiLogin.mockRejectedValue(new Error('Network'))

      await expect(useAuthStore.getState().login('admin', 'pass')).rejects.toThrow('Login failed')
      expect(useAuthStore.getState().error).toBe('Login failed. Please try again.')
    })
  })

  describe('logout', () => {
    it('clears user and calls apiLogout', () => {
      useAuthStore.setState({ user: testUser })

      useAuthStore.getState().logout()
      expect(useAuthStore.getState().user).toBeNull()
      expect(mockApiLogout).toHaveBeenCalled()
    })
  })
})
