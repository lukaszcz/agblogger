import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import PostCard from '@/components/posts/PostCard'
import FilterPanel, { EMPTY_FILTER, type FilterState } from '@/components/filters/FilterPanel'
import { fetchPosts, type PostListParams } from '@/api/posts'
import type { PostListResponse } from '@/api/client'

export default function TimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<PostListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Parse filter state from URL
  const page = Number(searchParams.get('page') ?? '1')
  const urlLabelMode = searchParams.get('labelMode')
  const parsedLabelMode: 'or' | 'and' = urlLabelMode === 'and' ? 'and' : 'or'
  const filterState: FilterState = {
    labels: searchParams.get('labels')?.split(',').filter(Boolean) ?? [],
    labelMode: parsedLabelMode,
    author: searchParams.get('author') ?? '',
    fromDate: searchParams.get('from') ?? '',
    toDate: searchParams.get('to') ?? '',
  }

  // Sync filters to URL
  const setFilter = useCallback(
    (f: FilterState) => {
      const params = new URLSearchParams()
      if (f.labels.length > 0) params.set('labels', f.labels.join(','))
      if (f.labelMode !== 'or') params.set('labelMode', f.labelMode)
      if (f.author) params.set('author', f.author)
      if (f.fromDate) params.set('from', f.fromDate)
      if (f.toDate) params.set('to', f.toDate)
      // Reset page when filters change
      setSearchParams(params)
    },
    [setSearchParams],
  )

  useEffect(() => {
    const p = Number(searchParams.get('page') ?? '1')
    const labels = searchParams.get('labels')?.split(',').filter(Boolean) ?? []
    const labelModeParam = searchParams.get('labelMode')
    const labelMode: 'or' | 'and' = labelModeParam === 'and' ? 'and' : 'or'
    const author = searchParams.get('author') ?? ''
    const fromDate = searchParams.get('from') ?? ''
    const toDate = searchParams.get('to') ?? ''

    void (async () => {
      setLoading(true)
      setError(null)
      try {
        const params: PostListParams = {
          page: p,
          per_page: 10,
        }
        if (labels.length > 0) params.labels = labels.join(',')
        if (labelMode !== 'or') params.labelMode = labelMode
        if (author) params.author = author
        if (fromDate) params.from = fromDate
        if (toDate) params.to = toDate
        const d = await fetchPosts(params)
        setData(d)
      } catch (err) {
        console.error('Failed to fetch posts:', err)
        setError('Failed to load posts. Please try again.')
      } finally {
        setLoading(false)
      }
    })()
  }, [searchParams, retryCount])

  function goToPage(p: number) {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(p))
    setSearchParams(params)
  }

  return (
    <div>
      <FilterPanel value={filterState} onChange={setFilter} />

      {loading ? (
        <div className="divide-y divide-border/60">
          {[0, 1, 2].map((i) => (
            <div key={i} className="py-6 animate-pulse">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0 space-y-3">
                  <div className="h-5 bg-border/50 rounded w-3/5" />
                  <div className="space-y-2">
                    <div className="h-3.5 bg-border/40 rounded w-full" />
                    <div className="h-3.5 bg-border/40 rounded w-4/5" />
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-3 bg-border/30 rounded w-20" />
                    <div className="h-3 bg-border/30 rounded w-16" />
                  </div>
                </div>
                <div className="hidden sm:block w-1 h-12 rounded-full bg-border/30 shrink-0 mt-1" />
              </div>
            </div>
          ))}
        </div>
      ) : error !== null ? (
        <div className="text-center py-24">
          <p className="font-display text-2xl text-red-600">{error}</p>
          <button
            onClick={() => setRetryCount((c) => c + 1)}
            className="text-accent text-sm hover:underline mt-4"
          >
            Retry
          </button>
        </div>
      ) : !data || data.posts.length === 0 ? (
        <div className="text-center py-24">
          <p className="font-display text-2xl text-muted italic">No posts found</p>
          <p className="text-sm text-muted mt-2">
            {filterState.labels.length > 0 || filterState.author || filterState.fromDate
              ? 'Try adjusting your filters.'
              : 'Check back soon.'}
          </p>
          {(filterState.labels.length > 0 || filterState.author || filterState.fromDate || filterState.toDate) && (
            <button
              onClick={() => setFilter(EMPTY_FILTER)}
              className="text-accent text-sm hover:underline mt-4"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="divide-y divide-border/60">
            {data.posts.map((post, i) => (
              <PostCard key={post.id} post={post} index={i} />
            ))}
          </div>

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
        </>
      )}
    </div>
  )
}
