import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Tag, Settings } from 'lucide-react'

import { useAuthStore } from '@/stores/authStore'
import { fetchLabels } from '@/api/labels'
import type { LabelResponse } from '@/api/client'

export default function LabelListPage() {
  const user = useAuthStore((s) => s.user)
  const [labels, setLabels] = useState<LabelResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchLabels()
      .then(setLabels)
      .catch(() => setError('Failed to load labels.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-24">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-3 mb-8">
        <Tag size={20} className="text-accent" />
        <h1 className="font-display text-3xl text-ink">Labels</h1>
      </div>

      {labels.length === 0 ? (
        <p className="text-muted text-center py-16">No labels defined yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {labels.map((label, i) => (
            <div
              key={label.id}
              className={`group relative p-5 rounded-xl border border-border bg-paper
                        hover:border-accent/40 hover:shadow-sm transition-all
                        opacity-0 animate-slide-up stagger-${Math.min(i + 1, 8)}`}
            >
              <Link to={`/labels/${label.id}`} className="absolute inset-0 rounded-xl" />
              <div className="relative pointer-events-none">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-display text-lg text-ink group-hover:text-accent transition-colors">
                      #{label.id}
                    </h3>
                    {label.names.length > 0 && (
                      <p className="text-sm text-muted mt-1">{label.names.join(', ')}</p>
                    )}
                  </div>
                  <span className="text-xs font-mono text-muted bg-paper-warm px-2 py-1 rounded-md">
                    {label.post_count} {label.post_count === 1 ? 'post' : 'posts'}
                  </span>
                </div>

                {label.parents.length > 0 && (
                  <div className="mt-3 flex items-center gap-1 text-xs text-muted">
                    <span>{label.parents.length === 1 ? 'Parent:' : 'Parents:'}</span>
                    {label.parents.map((p) => (
                      <span key={p} className="text-tag-text bg-tag-bg px-1.5 py-0.5 rounded">
                        #{p}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {user && (
                <Link
                  to={`/labels/${label.id}/settings`}
                  className="relative z-10 pointer-events-auto mt-3 inline-flex items-center
                           gap-1 text-xs text-muted hover:text-ink transition-colors
                           rounded-lg hover:bg-paper-warm p-1 -ml-1"
                  aria-label={`Settings for ${label.id}`}
                >
                  <Settings size={12} />
                  <span>Settings</span>
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
