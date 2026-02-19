import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { fetchPostForEdit } from '@/api/posts'
import type { UserResponse, PostEditResponse } from '@/api/client'

vi.mock('@/api/posts', () => ({
  fetchPostForEdit: vi.fn(),
  createPost: vi.fn(),
  updatePost: vi.fn(),
}))

vi.mock('@/api/client', () => {
  class HTTPError extends Error {
    response: { status: number }
    constructor(status: number) {
      super(`HTTP ${status}`)
      this.response = { status }
    }
  }
  return {
    default: { post: vi.fn() },
    HTTPError,
  }
})

vi.mock('@/api/labels', () => ({
  fetchLabels: vi.fn().mockResolvedValue([]),
  createLabel: vi.fn(),
}))

let mockUser: UserResponse | null = null

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: UserResponse | null; isInitialized: boolean }) => unknown) =>
    selector({ user: mockUser, isInitialized: true }),
}))

vi.mock('@/hooks/useKatex', () => ({
  useRenderedHtml: (html: string | null) => html ?? '',
}))

import EditorPage from '../EditorPage'

const mockFetchPostForEdit = vi.mocked(fetchPostForEdit)

// Get the mock HTTPError class for creating test errors
const { HTTPError: MockHTTPError } = await import('@/api/client')

function renderEditor(path = '/editor/new') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/editor/new" element={<EditorPage />} />
        <Route path="/editor/*" element={<EditorPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

const editResponse: PostEditResponse = {
  file_path: 'posts/existing.md',
  body: '# Existing Post\n\nContent here.',
  labels: ['swe'],
  is_draft: false,
  created_at: '2026-02-01 12:00:00+00:00',
  modified_at: '2026-02-01 13:00:00+00:00',
  author: 'Admin',
}

describe('EditorPage', () => {
  beforeEach(() => {
    mockUser = { id: 1, username: 'jane', email: 'jane@test.com', display_name: null, is_admin: true }
    mockFetchPostForEdit.mockReset()
  })

  it('author from display_name', () => {
    mockUser = { id: 1, username: 'jane', email: 'j@t.com', display_name: 'Jane Doe', is_admin: false }
    renderEditor('/editor/new')

    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
  })

  it('author fallback to username', () => {
    mockUser = { id: 1, username: 'jane', email: 'j@t.com', display_name: null, is_admin: false }
    renderEditor('/editor/new')

    expect(screen.getByText('jane')).toBeInTheDocument()
  })

  it('file path input for new post', () => {
    renderEditor('/editor/new')
    const input = screen.getByLabelText('File path')
    expect(input).toHaveValue('posts/')
  })

  it('default body for new post', () => {
    renderEditor('/editor/new')
    const textareas = document.querySelectorAll('textarea')
    const bodyTextarea = Array.from(textareas).find((t) => t.value.includes('# New Post'))
    expect(bodyTextarea).toBeTruthy()
  })

  it('loads existing post data', async () => {
    mockFetchPostForEdit.mockResolvedValue(editResponse)
    renderEditor('/editor/posts/existing.md')

    await waitFor(() => {
      expect(screen.getByText('Admin')).toBeInTheDocument()
    })
    expect(mockFetchPostForEdit).toHaveBeenCalledWith('posts/existing.md')
  })

  it('shows 404 error page without editor form', async () => {
    // MockHTTPError has our test-friendly 1-arg constructor but TS sees the real type
    mockFetchPostForEdit.mockRejectedValue(new (MockHTTPError as unknown as new (s: number) => Error)(404))
    renderEditor('/editor/posts/missing.md')

    await waitFor(() => {
      expect(screen.getByText('404')).toBeInTheDocument()
    })
    expect(screen.getByText('Post not found')).toBeInTheDocument()
    expect(screen.getByText('Go back')).toBeInTheDocument()
    // Editor form should NOT be rendered
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
    expect(screen.queryByText('Preview')).not.toBeInTheDocument()
  })

  it('shows generic error page without editor form', async () => {
    mockFetchPostForEdit.mockRejectedValue(new Error('Network error'))
    renderEditor('/editor/posts/broken.md')

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument()
    })
    expect(screen.getByText('Failed to load post')).toBeInTheDocument()
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
  })
})
