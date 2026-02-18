import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { fetchPosts } from '@/api/posts'
import type { PostListResponse } from '@/api/client'

vi.mock('@/api/posts', () => ({
  fetchPosts: vi.fn(),
}))

vi.mock('@/api/labels', () => ({
  fetchLabels: vi.fn().mockResolvedValue([]),
}))

import TimelinePage from '../TimelinePage'

const mockFetchPosts = vi.mocked(fetchPosts)

const postsResponse: PostListResponse = {
  posts: [
    {
      id: 1,
      file_path: 'posts/hello.md',
      title: 'Hello World',
      author: 'Admin',
      created_at: '2026-02-01 12:00:00+00:00',
      modified_at: '2026-02-01 12:00:00+00:00',
      is_draft: false,
      excerpt: 'First post',
      labels: [],
    },
    {
      id: 2,
      file_path: 'posts/second.md',
      title: 'Second Post',
      author: 'Admin',
      created_at: '2026-02-02 12:00:00+00:00',
      modified_at: '2026-02-02 12:00:00+00:00',
      is_draft: false,
      excerpt: 'Another post',
      labels: [],
    },
  ],
  total: 2,
  page: 1,
  per_page: 10,
  total_pages: 1,
}

function renderTimeline() {
  return render(
    <MemoryRouter>
      <TimelinePage />
    </MemoryRouter>,
  )
}

describe('TimelinePage', () => {
  beforeEach(() => {
    mockFetchPosts.mockReset()
  })

  it('renders posts', async () => {
    mockFetchPosts.mockResolvedValue(postsResponse)
    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })
    expect(screen.getByText('Second Post')).toBeInTheDocument()
  })

  it('error shows retry button', async () => {
    mockFetchPosts.mockRejectedValue(new Error('Network error'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('Failed to load posts. Please try again.')).toBeInTheDocument()
    })
    expect(screen.getByText('Retry')).toBeInTheDocument()
    consoleSpy.mockRestore()
  })

  it('retry re-fetches posts', async () => {
    mockFetchPosts.mockRejectedValueOnce(new Error('Network error'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeInTheDocument()
    })

    mockFetchPosts.mockResolvedValue(postsResponse)
    await userEvent.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })
    expect(mockFetchPosts).toHaveBeenCalledTimes(2)
    consoleSpy.mockRestore()
  })

  it('logs error to console on failure', async () => {
    const error = new Error('Network error')
    mockFetchPosts.mockRejectedValue(error)
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderTimeline()

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to fetch posts:', error)
    })
    consoleSpy.mockRestore()
  })

  it('shows empty results message', async () => {
    mockFetchPosts.mockResolvedValue({ ...postsResponse, posts: [], total: 0 })
    renderTimeline()

    await waitFor(() => {
      expect(screen.getByText('No posts found')).toBeInTheDocument()
    })
  })
})
