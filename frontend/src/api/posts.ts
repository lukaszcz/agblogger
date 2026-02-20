import api from './client'
import type { PostDetail, PostEditResponse, PostListResponse, SearchResult } from './client'

export interface PostListParams {
  page?: number
  per_page?: number
  label?: string
  labels?: string
  labelMode?: string
  author?: string
  from?: string
  to?: string
  sort?: string
  order?: string
}

export async function fetchPosts(params: PostListParams = {}): Promise<PostListResponse> {
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value))
    }
  }
  return api.get('posts', { searchParams }).json<PostListResponse>()
}

export async function fetchPost(filePath: string): Promise<PostDetail> {
  return api.get(`posts/${filePath}`).json<PostDetail>()
}

export async function fetchPostForEdit(filePath: string): Promise<PostEditResponse> {
  return api.get(`posts/${filePath}/edit`).json<PostEditResponse>()
}

export async function searchPosts(query: string, limit = 20): Promise<SearchResult[]> {
  return api
    .get('posts/search', { searchParams: { q: query, limit: String(limit) } })
    .json<SearchResult[]>()
}

export async function createPost(params: {
  title: string
  body: string
  labels: string[]
  is_draft: boolean
}): Promise<PostDetail> {
  return api.post('posts', { json: params }).json<PostDetail>()
}

export async function updatePost(
  filePath: string,
  params: { title: string; body: string; labels: string[]; is_draft: boolean },
): Promise<PostDetail> {
  return api.put(`posts/${filePath}`, { json: params }).json<PostDetail>()
}

export async function deletePost(filePath: string, deleteAssets = false): Promise<void> {
  const searchParams = deleteAssets ? { delete_assets: 'true' } : undefined
  await api.delete(`posts/${filePath}`, { searchParams })
}

export async function uploadAssets(
  filePath: string,
  files: File[],
): Promise<{ uploaded: string[] }> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  return api.post(`posts/${filePath}/assets`, { body: form }).json<{ uploaded: string[] }>()
}
