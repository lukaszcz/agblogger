import { create } from 'zustand'
import type { UserResponse } from '@/api/client'
import { fetchMe, login as apiLogin, logout as apiLogout } from '@/api/auth'

interface AuthState {
  user: UserResponse | null
  isLoading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      await apiLogin(username, password)
      const user = await fetchMe()
      set({ user, isLoading: false })
    } catch {
      set({ error: 'Invalid username or password', isLoading: false })
      throw new Error('Login failed')
    }
  },

  logout: () => {
    apiLogout()
    set({ user: null })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ user: null })
      return
    }
    try {
      const user = await fetchMe()
      set({ user })
    } catch {
      set({ user: null })
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  },
}))
