import api from './client'
import type { TokenResponse, UserResponse } from './client'

export async function login(username: string, password: string): Promise<TokenResponse> {
  const response = await api.post('auth/login', { json: { username, password } }).json<TokenResponse>()
  localStorage.setItem('access_token', response.access_token)
  localStorage.setItem('refresh_token', response.refresh_token)
  return response
}

export async function register(
  username: string,
  email: string,
  password: string,
  displayName?: string,
): Promise<UserResponse> {
  return api
    .post('auth/register', {
      json: { username, email, password, display_name: displayName },
    })
    .json<UserResponse>()
}

export async function fetchMe(): Promise<UserResponse> {
  return api.get('auth/me').json<UserResponse>()
}

export function logout(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('access_token')
}
