import ky, { HTTPError } from 'ky'

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') {
    return null
  }
  const prefix = `${encodeURIComponent(name)}=`
  const part = document.cookie
    .split('; ')
    .find((cookiePart) => cookiePart.startsWith(prefix))
  if (!part) {
    return null
  }
  return decodeURIComponent(part.slice(prefix.length))
}

async function refreshAccessToken(): Promise<boolean> {
  const csrfToken = readCookie('csrf_token')
  const headers = new Headers()
  if (csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  try {
    await ky.post('auth/refresh', {
      prefixUrl: '/api',
      credentials: 'include',
      headers,
      json: {},
    })
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
          const csrfToken = readCookie('csrf_token')
          if (csrfToken) {
            request.headers.set('X-CSRF-Token', csrfToken)
          }
        }
      },
    ],
    afterResponse: [
      async (request, _options, response) => {
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
              const csrfToken = readCookie('csrf_token')
              if (csrfToken) {
                headers.set('X-CSRF-Token', csrfToken)
              }
            }
            const retryRequest = new Request(request, { headers })
            return ky(retryRequest, {
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
  body: string
  labels: string[]
  is_draft: boolean
  created_at: string
  modified_at: string
  author: string | null
}
