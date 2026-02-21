import ky, { HTTPError } from 'ky'

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const CSRF_STORAGE_KEY = 'agb_csrf_token'

function hasBrowserDom(): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return false
  }
  return document.defaultView === window
}

function readPersistedCsrfToken(): string | null {
  if (!hasBrowserDom()) {
    return null
  }
  try {
    return window.localStorage.getItem(CSRF_STORAGE_KEY)
  } catch {
    return null
  }
}

function persistCsrfToken(token: string): void {
  if (!hasBrowserDom()) {
    return
  }
  try {
    window.localStorage.setItem(CSRF_STORAGE_KEY, token)
  } catch {
    // Ignore storage failures; keep in-memory token only.
  }
}

function clearPersistedCsrfToken(): void {
  if (!hasBrowserDom()) {
    return
  }
  try {
    window.localStorage.removeItem(CSRF_STORAGE_KEY)
  } catch {
    // Ignore storage failures.
  }
}

let csrfToken: string | null = null
let csrfTokenLoaded = false

function ensureCsrfTokenLoaded(): void {
  if (csrfTokenLoaded) {
    return
  }
  csrfToken = readPersistedCsrfToken()
  csrfTokenLoaded = true
}

function setCsrfHeader(headers: Headers): void {
  ensureCsrfTokenLoaded()
  if (csrfToken !== null) {
    headers.set(CSRF_HEADER_NAME, csrfToken)
  }
}

function updateCsrfTokenFromResponse(response: Response): void {
  const token = response.headers.get(CSRF_HEADER_NAME)
  if (token === null) {
    return
  }
  const normalizedToken = token.trim()
  if (normalizedToken === '') {
    csrfToken = null
    csrfTokenLoaded = true
    clearPersistedCsrfToken()
    return
  }
  csrfToken = normalizedToken
  csrfTokenLoaded = true
  persistCsrfToken(normalizedToken)
}

async function refreshAccessToken(): Promise<boolean> {
  const headers = new Headers()
  setCsrfHeader(headers)

  try {
    const response = await ky.post('auth/refresh', {
      prefixUrl: '/api',
      credentials: 'include',
      headers,
      json: {},
    })
    updateCsrfTokenFromResponse(response)
    return true
  } catch (err) {
    console.error('Token refresh failed:', err)
    return false
  }
}

const api = ky.create({
  prefixUrl: '/api',
  credentials: 'include',
  hooks: {
    beforeRequest: [
      (request) => {
        if (UNSAFE_METHODS.has(request.method)) {
          setCsrfHeader(request.headers)
        }
      },
    ],
    afterResponse: [
      async (request, _options, response) => {
        updateCsrfTokenFromResponse(response)
        const alreadyRetried = request.headers.get('X-Auth-Retry') === '1'
        if (response.status === 401 && !request.url.includes('/auth/refresh') && !alreadyRetried) {
          const refreshed = await refreshAccessToken()
          if (!refreshed) {
            return response
          }

          try {
            const headers = new Headers(request.headers)
            headers.set('X-Auth-Retry', '1')
            if (UNSAFE_METHODS.has(request.method)) {
              setCsrfHeader(headers)
            }
            const retryRequest = new Request(request, { headers })
            return await ky(retryRequest, {
              credentials: 'include',
              retry: 0,
            })
          } catch (retryErr) {
            console.error('Request retry after refresh failed:', retryErr)
            return response
          }
        }
        return response
      },
    ],
  },
})

export default api

export { HTTPError }

// Type definitions
export interface PostSummary {
  id: number
  file_path: string
  title: string
  author: string | null
  created_at: string
  modified_at: string
  is_draft: boolean
  rendered_excerpt: string | null
  labels: string[]
}

export interface PostDetail extends PostSummary {
  rendered_html: string
  content: string | null
}

export interface PostListResponse {
  posts: PostSummary[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface LabelResponse {
  id: string
  names: string[]
  is_implicit: boolean
  parents: string[]
  children: string[]
  post_count: number
}

export interface LabelGraphNode {
  id: string
  names: string[]
  post_count: number
}

export interface LabelGraphEdge {
  source: string
  target: string
}

export interface LabelGraphResponse {
  nodes: LabelGraphNode[]
  edges: LabelGraphEdge[]
}

export interface LabelCreateRequest {
  id: string
  names?: string[]
  parents?: string[]
}

export interface LabelUpdateRequest {
  names: string[]
  parents: string[]
}

export interface LabelDeleteResponse {
  id: string
  deleted: boolean
}

export interface PageConfig {
  id: string
  title: string
  file: string | null
}

export interface SiteConfigResponse {
  title: string
  description: string
  pages: PageConfig[]
}

export interface PageResponse {
  id: string
  title: string
  rendered_html: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserResponse {
  id: number
  username: string
  email: string
  display_name: string | null
  is_admin: boolean
}

export interface SearchResult {
  id: number
  file_path: string
  title: string
  rendered_excerpt: string | null
  created_at: string
  rank: number
}

export interface PostEditResponse {
  file_path: string
  title: string
  body: string
  labels: string[]
  is_draft: boolean
  created_at: string
  modified_at: string
  author: string | null
}

export interface AdminSiteSettings {
  title: string
  description: string
  default_author: string
  timezone: string
}

export interface AdminPageConfig {
  id: string
  title: string
  file: string | null
  is_builtin: boolean
  content: string | null
}

export interface AdminPagesResponse {
  pages: AdminPageConfig[]
}
