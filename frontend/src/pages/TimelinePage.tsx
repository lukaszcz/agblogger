import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import PostCard from '@/components/posts/PostCard'
import FilterPanel, { EMPTY_FILTER, type FilterState } from '@/components/filters/FilterPanel'
import { fetchPosts } from '@/api/posts'
import type { PostListResponse } from '@/api/client'

export default function TimelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<PostListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Parse filter state from URL
  const page = Number(searchParams.get('page') ?? '1')
  const filterState: FilterState = {
    labels: searchParams.get('labels')?.split(',').filter(Boolean) ?? [],
    labelMode: (searchParams.get('labelMode') as 'or' | 'and') ?? 'or',
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
    const currentPage = Number(searchParams.get('page') ?? '1')
    const labels = searchParams.get('labels')?.split(',').filter(Boolean) ?? []
    const labelMode = (searchParams.get('labelMode') as 'or' | 'and') ?? 'or'
    const author = searchParams.get('author') ?? ''
    const fromDate = searchParams.get('from') ?? ''
    const toDate = searchParams.get('to') ?? ''

    void (async () => {
      setLoading(true)
      setError(null)
      try {
        const d = await fetchPosts({
          page: currentPage,
          per_page: 10,
          labels: labels.length > 0 ? labels.join(',') : undefined,
          labelMode: labelMode !== 'or' ? labelMode : undefined,
          author: author || undefined,
          from: fromDate || undefined,
          to: toDate || undefined,
        })
        setData(d)
      } catch {
        setError('Failed to load posts. Please try again.')
      } finally {
        setLoading(false)
      }
    })()
  }, [searchParams])

  function goToPage(p: number) {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(p))
    setSearchParams(params)
  }

  return (
    <div>
      <FilterPanel value={filterState} onChange={setFilter} />

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <div className="text-center py-24">
          <p className="font-display text-2xl text-red-600">{error}</p>
          <button
            onClick={() => setSearchParams(searchParams)}
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
