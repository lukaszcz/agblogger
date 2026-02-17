import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Tag } from 'lucide-react'
import { fetchLabels } from '@/api/labels'
import type { LabelResponse } from '@/api/client'

export default function LabelListPage() {
  const [labels, setLabels] = useState<LabelResponse[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchLabels()
      .then(setLabels)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
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
            <Link
              key={label.id}
              to={`/labels/${label.id}`}
              className={`group p-5 rounded-xl border border-border bg-paper
                        hover:border-accent/40 hover:shadow-sm transition-all
                        opacity-0 animate-slide-up stagger-${Math.min(i + 1, 8)}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-display text-lg text-ink group-hover:text-accent transition-colors">
                    #{label.id}
                  </h3>
                  {label.names.length > 0 && (
                    <p className="text-sm text-muted mt-1">
                      {label.names.join(', ')}
                    </p>
                  )}
                </div>
                <span className="text-xs font-mono text-muted bg-paper-warm px-2 py-1 rounded-md">
                  {label.post_count} {label.post_count === 1 ? 'post' : 'posts'}
                </span>
              </div>

              {label.parents.length > 0 && (
                <div className="mt-3 flex items-center gap-1 text-xs text-muted">
                  <span>Parent:</span>
                  {label.parents.map((p) => (
                    <span key={p} className="text-tag-text bg-tag-bg px-1.5 py-0.5 rounded">
                      #{p}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
