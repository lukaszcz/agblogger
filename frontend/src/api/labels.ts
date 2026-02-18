import api from './client'
import type {
  LabelDeleteResponse,
  LabelGraphResponse,
  LabelResponse,
  PostListResponse,
} from './client'

export async function fetchLabels(): Promise<LabelResponse[]> {
  return api.get('labels').json<LabelResponse[]>()
}

export async function fetchLabel(labelId: string): Promise<LabelResponse> {
  return api.get(`labels/${labelId}`).json<LabelResponse>()
}

export async function fetchLabelGraph(): Promise<LabelGraphResponse> {
  return api.get('labels/graph').json<LabelGraphResponse>()
}

export async function fetchLabelPosts(
  labelId: string,
  page = 1,
  perPage = 20,
): Promise<PostListResponse> {
  return api
    .get(`labels/${labelId}/posts`, {
      searchParams: { page: String(page), per_page: String(perPage) },
    })
    .json<PostListResponse>()
}

export async function createLabel(
  id: string,
  names?: string[],
  parents?: string[],
): Promise<LabelResponse> {
  return api
    .post('labels', {
      json: { id, ...(names && { names }), ...(parents && { parents }) },
    })
    .json<LabelResponse>()
}

export async function updateLabel(
  labelId: string,
  data: { names: string[]; parents: string[] },
): Promise<LabelResponse> {
  return api.put(`labels/${labelId}`, { json: data }).json<LabelResponse>()
}

export async function deleteLabel(labelId: string): Promise<LabelDeleteResponse> {
  return api.delete(`labels/${labelId}`).json<LabelDeleteResponse>()
}
