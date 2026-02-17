import ky from 'ky'

const api = ky.create({
  prefixUrl: '/api',
  hooks: {
    beforeRequest: [
      (request) => {
        const token = localStorage.getItem('access_token')
        if (token) {
          request.headers.set('Authorization', `Bearer ${token}`)
        }
      },
    ],
    afterResponse: [
      async (_request, _options, response) => {
        if (response.status === 401) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        }
      },
    ],
  },
})

export default api

// Type definitions
export interface PostSummary {
  id: number
  file_path: string
  title: string
  author: string | null
  created_at: string
  modified_at: string
  is_draft: boolean
  excerpt: string | null
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
  excerpt: string | null
  created_at: string
  rank: number
}
