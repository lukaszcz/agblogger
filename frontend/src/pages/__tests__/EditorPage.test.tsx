import { createElement } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { fetchPostForEdit } from '@/api/posts'
import type { UserResponse, PostEditResponse } from '@/api/client'

// Mock localStorage since jsdom doesn't always provide full implementation
const storage = new Map<string, string>()
const mockLocalStorage = {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
  get length() {
    return storage.size
  },
  key: (index: number) => [...storage.keys()][index] ?? null,
}

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
})

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
  const router = createMemoryRouter(
    [
      { path: '/editor/new', element: createElement(EditorPage) },
      { path: '/editor/*', element: createElement(EditorPage) },
    ],
    { initialEntries: [path] },
  )
  return render(createElement(RouterProvider, { router }))
}

const editResponse: PostEditResponse = {
  file_path: 'posts/existing.md',
  title: 'Existing Post',
  body: 'Content here.',
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
    localStorage.clear()
  })

  it('author from display_name', async () => {
    mockUser = { id: 1, username: 'jane', email: 'j@t.com', display_name: 'Jane Doe', is_admin: false }
    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
  })

  it('author fallback to username', async () => {
    mockUser = { id: 1, username: 'jane', email: 'j@t.com', display_name: null, is_admin: false }
    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByText('jane')).toBeInTheDocument()
    })
  })

  it('default body for new post is empty', async () => {
    renderEditor('/editor/new')
    await waitFor(() => {
      const textareas = document.querySelectorAll('textarea')
      expect(textareas.length).toBeGreaterThan(0)
      expect(textareas[0]).toHaveValue('')
    })
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

  it('shows recovery banner when draft exists', async () => {
    const draft = {
      title: 'Draft Title',
      body: 'Draft content',
      labels: ['swe'],
      isDraft: false,
      savedAt: '2026-02-20T15:45:00.000Z',
    }
    localStorage.setItem('agblogger:draft:new', JSON.stringify(draft))

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument()
  })

  it('restores draft content when Restore is clicked', async () => {
    const user = userEvent.setup()
    const draft = {
      title: 'Restored Title',
      body: 'Restored draft',
      labels: ['cs'],
      isDraft: true,
      savedAt: '2026-02-20T15:45:00.000Z',
    }
    localStorage.setItem('agblogger:draft:new', JSON.stringify(draft))

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /restore/i }))

    // Banner should disappear
    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument()

    // Body should be restored
    const textareas = document.querySelectorAll('textarea')
    const bodyTextarea = Array.from(textareas).find((t) => t.value.includes('Restored draft'))
    expect(bodyTextarea).toBeTruthy()

    // Title should be restored
    expect(screen.getByLabelText('Title')).toHaveValue('Restored Title')
  })

  it('dismisses banner and clears draft when Discard is clicked', async () => {
    const user = userEvent.setup()
    localStorage.setItem(
      'agblogger:draft:new',
      JSON.stringify({ title: 'Old', body: 'Old body', labels: [], isDraft: false, savedAt: '2026-02-20T15:45:00.000Z' }),
    )

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /discard/i }))

    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument()
    expect(localStorage.getItem('agblogger:draft:new')).toBeNull()
  })

  it('renders title input for new post', async () => {
    renderEditor('/editor/new')
    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toBeInTheDocument()
    })
  })

  it('save disabled when title is empty', async () => {
    renderEditor('/editor/new')
    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toBeInTheDocument()
    })
    // Title is initially empty for new posts
    const saveButton = screen.getByRole('button', { name: /save/i })
    expect(saveButton).toBeDisabled()
  })

  it('loads title for existing post', async () => {
    mockFetchPostForEdit.mockResolvedValue(editResponse)
    renderEditor('/editor/posts/existing.md')
    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toHaveValue('Existing Post')
    })
  })

  it('no file path input for new post', async () => {
    renderEditor('/editor/new')
    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('File path')).not.toBeInTheDocument()
  })

  it('enables save button when title is provided', async () => {
    const user = userEvent.setup()
    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toBeInTheDocument()
    })

    const saveButton = screen.getByRole('button', { name: /save/i })
    expect(saveButton).toBeDisabled()

    await user.type(screen.getByLabelText('Title'), 'A Title')
    expect(saveButton).toBeEnabled()
  })
})
