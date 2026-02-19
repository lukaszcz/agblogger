import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { searchPosts } from '@/api/posts'
import type { SearchResult } from '@/api/client'

export default function SearchPage() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      setError(null)
      return
    }
    void (async () => {
      setLoading(true)
      setError(null)
      try {
        const r = await searchPosts(query)
        setResults(r)
      } catch (err) {
        console.error('Search failed:', err)
        setError('Search failed. Please try again.')
      } finally {
        setLoading(false)
      }
    })()
  }, [query])

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-3 mb-8">
        <Search size={20} className="text-muted" />
        <h1 className="font-display text-3xl text-ink">
          {query ? (
            <>
              Results for <span className="italic text-accent">"{query}"</span>
            </>
          ) : (
            'Search'
          )}
        </h1>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <p className="text-red-600 text-center py-16">{error}</p>
      ) : results.length === 0 ? (
        <p className="text-muted text-center py-16">
          {query ? 'No results found.' : 'Enter a search query above.'}
        </p>
      ) : (
        <div className="space-y-1">
          {results.map((result, i) => (
            <Link
              key={result.id}
              to={`/post/${result.file_path}`}
              className={`block py-4 px-4 -mx-4 rounded-xl hover:bg-paper-warm/60 transition-colors
                        opacity-0 animate-slide-up stagger-${Math.min(i + 1, 8)}`}
            >
              <h3 className="font-display text-lg text-ink">{result.title}</h3>
              {result.rendered_excerpt && (
                <div
                  className="text-sm text-muted mt-1 line-clamp-2 prose-excerpt"
                  dangerouslySetInnerHTML={{ __html: result.rendered_excerpt }}
                />
              )}
              <span className="text-xs text-muted font-mono mt-2 block">
                {result.created_at.split(' ')[0]}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
