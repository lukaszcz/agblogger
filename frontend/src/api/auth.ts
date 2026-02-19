import api from './client'
import type { TokenResponse, UserResponse } from './client'

export async function login(username: string, password: string): Promise<TokenResponse> {
  return api.post('auth/login', { json: { username, password } }).json<TokenResponse>()
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

export async function logout(): Promise<void> {
  await api.post('auth/logout', { json: {} })
}
