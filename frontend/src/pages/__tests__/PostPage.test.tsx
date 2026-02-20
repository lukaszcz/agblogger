import type React from 'react'

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { fetchPost, deletePost } from '@/api/posts'
import type { UserResponse, PostDetail } from '@/api/client'

vi.mock('@/api/posts', () => ({
  fetchPost: vi.fn(),
  deletePost: vi.fn(),
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
    default: {},
    HTTPError,
  }
})

let mockUser: UserResponse | null = null

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { user: UserResponse | null }) => unknown) =>
    selector({ user: mockUser }),
}))

vi.mock('@/hooks/useKatex', () => ({
  useRenderedHtml: (html: string | null | undefined) => html ?? '',
}))

vi.mock('@/components/labels/LabelChip', () => ({
  default: ({ labelId }: { labelId: string }) => <span data-testid="label">{labelId}</span>,
}))

vi.mock('@/components/posts/TableOfContents', () => ({
  default: ({ contentRef }: { contentRef: React.RefObject<HTMLElement | null> }) => (
    <div data-testid="toc" data-has-ref={!!contentRef.current} />
  ),
}))

import PostPage from '../PostPage'

const mockFetchPost = vi.mocked(fetchPost)
const mockDeletePost = vi.mocked(deletePost)
const { HTTPError: MockHTTPError } = await import('@/api/client')

const postDetail: PostDetail = {
  id: 1,
  file_path: 'posts/hello.md',
  title: 'Hello World',
  author: 'Admin',
  created_at: '2026-02-01 12:00:00+00:00',
  modified_at: '2026-02-01 12:00:00+00:00',
  is_draft: false,
  rendered_excerpt: '<p>First post</p>',
  labels: [],
  rendered_html: '<p>Content here</p>',
  content: 'Content here',
}

let navigatedTo: string | number | null = null

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => (to: string | number, opts?: { replace?: boolean }) => {
      navigatedTo = to
      void opts
    },
  }
})

function renderPostPage(path = '/post/posts/hello.md') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/post/*" element={<PostPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PostPage', () => {
  beforeEach(() => {
    mockUser = null
    navigatedTo = null
    mockFetchPost.mockReset()
    mockDeletePost.mockReset()
  })

  it('renders table of contents component', async () => {
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })
    expect(screen.getByTestId('toc')).toBeInTheDocument()
  })

  it('renders post content', async () => {
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })
    expect(screen.getByText('Content here')).toBeInTheDocument()
  })

  it('shows 404 for missing post', async () => {
    mockFetchPost.mockRejectedValue(new (MockHTTPError as unknown as new (s: number) => Error)(404))
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('404')).toBeInTheDocument()
    })
    expect(screen.getByText('Post not found')).toBeInTheDocument()
  })

  it('hides delete button when not authenticated', async () => {
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })
    expect(screen.queryByText('Delete')).not.toBeInTheDocument()
  })

  it('shows delete button when authenticated', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
  })

  it('shows confirmation dialog on delete click', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Delete'))

    expect(screen.getByText('Delete post?')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
    expect(screen.getByText(/This will permanently delete/)).toBeInTheDocument()
  })

  it('cancel closes confirmation dialog', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockFetchPost.mockResolvedValue(postDetail)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Delete'))
    expect(screen.getByText('Delete post?')).toBeInTheDocument()

    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Delete post?')).not.toBeInTheDocument()
  })

  it('confirming delete navigates to home', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockFetchPost.mockResolvedValue(postDetail)
    mockDeletePost.mockResolvedValue(undefined)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Delete'))

    // Click the Delete button inside the dialog (not the one in the header)
    const dialogButtons = screen.getAllByRole('button')
    const confirmButton = dialogButtons.find(
      (btn) => btn.textContent === 'Delete' && btn.className.includes('bg-red'),
    )!
    await userEvent.click(confirmButton)

    await waitFor(() => {
      expect(mockDeletePost).toHaveBeenCalledWith('posts/hello.md')
    })
    expect(navigatedTo).toBe('/')
  })

  it('renders title from metadata not from rendered HTML', async () => {
    const postWithNoH1 = {
      ...postDetail,
      rendered_html: '<p>Just body content</p>',
    }
    mockFetchPost.mockResolvedValue(postWithNoH1)
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Hello World')
    })
    expect(screen.getByText('Just body content')).toBeInTheDocument()
  })

  it('shows error on delete failure', async () => {
    mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: null, is_admin: true }
    mockFetchPost.mockResolvedValue(postDetail)
    mockDeletePost.mockRejectedValue(new Error('Network error'))
    renderPostPage()

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByText('Delete'))

    const dialogButtons = screen.getAllByRole('button')
    const confirmButton = dialogButtons.find(
      (btn) => btn.textContent === 'Delete' && btn.className.includes('bg-red'),
    )!
    await userEvent.click(confirmButton)

    await waitFor(() => {
      expect(screen.getByText('Failed to delete post. Please try again.')).toBeInTheDocument()
    })
    // Dialog should be closed after error
    expect(screen.queryByText('Delete post?')).not.toBeInTheDocument()
  })
})
