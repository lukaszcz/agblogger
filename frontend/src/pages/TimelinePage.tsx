import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import PostCard from '@/components/posts/PostCard'
import { fetchPosts } from '@/api/posts'
import type { PostListResponse } from '@/api/client'

export default function TimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<PostListResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const page = Number(searchParams.get('page') ?? '1')
  const label = searchParams.get('label') ?? undefined
  const author = searchParams.get('author') ?? undefined

  useEffect(() => {
    setLoading(true)
    fetchPosts({ page, per_page: 10, label, author })
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page, label, author])

  function goToPage(p: number) {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(p))
    setSearchParams(params)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (!data || data.posts.length === 0) {
    return (
      <div className="text-center py-24">
        <p className="font-display text-2xl text-muted italic">No posts yet</p>
        <p className="text-sm text-muted mt-2">Check back soon.</p>
      </div>
    )
  }

  return (
    <div>
      {/* Active filters */}
      {(label || author) && (
        <div className="mb-6 flex items-center gap-2 text-sm text-muted">
          <span>Filtering by:</span>
          {label && (
            <span className="px-2 py-0.5 bg-tag-bg text-tag-text rounded-md">
              #{label}
            </span>
          )}
          {author && (
            <span className="px-2 py-0.5 bg-tag-bg text-tag-text rounded-md">
              {author}
            </span>
          )}
          <button
            onClick={() => setSearchParams({})}
            className="text-accent hover:underline ml-1"
          >
            Clear
          </button>
        </div>
      )}

      {/* Post list */}
      <div className="divide-y divide-border/60">
        {data.posts.map((post, i) => (
          <PostCard key={post.id} post={post} index={i} />
        ))}
      </div>

      {/* Pagination */}
      {data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-10 pt-6 border-t border-border">
          <button
            onClick={() => goToPage(page - 1)}
            disabled={page <= 1}
            className="p-2 rounded-lg text-muted hover:text-ink hover:bg-paper-warm
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={18} />
          </button>

          <span className="text-sm font-mono text-muted px-3">
            {page} / {data.total_pages}
          </span>

          <button
            onClick={() => goToPage(page + 1)}
            disabled={page >= data.total_pages}
            className="p-2 rounded-lg text-muted hover:text-ink hover:bg-paper-warm
                     disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}
    </div>
  )
}
