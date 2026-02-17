import { Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import type { PostSummary } from '@/api/client'
import LabelChip from '@/components/labels/LabelChip'

interface PostCardProps {
  post: PostSummary
  index?: number
}

export default function PostCard({ post, index = 0 }: PostCardProps) {
  const postUrl = `/post/${post.file_path}`
  const staggerClass = `stagger-${Math.min(index + 1, 8)}`

  let dateStr = ''
  try {
    const parsed = parseISO(post.created_at.replace(' ', 'T').replace(/\+(\d{2})$/, '+$1:00'))
    dateStr = format(parsed, 'MMM d, yyyy')
  } catch {
    dateStr = post.created_at.split(' ')[0] ?? ''
  }

  return (
    <article
      className={`group opacity-0 animate-slide-up ${staggerClass}`}
    >
      <Link to={postUrl} className="block py-6 -mx-4 px-4 rounded-xl transition-colors hover:bg-paper-warm/60">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h2 className="font-display text-xl text-ink group-hover:text-accent transition-colors leading-snug">
              {post.title}
            </h2>

            {post.excerpt && (
              <p className="mt-2 text-sm text-muted leading-relaxed line-clamp-2">
                {post.excerpt}
              </p>
            )}

            <div className="mt-3 flex items-center gap-3 flex-wrap">
              <span className="text-xs text-muted font-mono tracking-wide uppercase">
                {dateStr}
              </span>

              {post.author && (
                <>
                  <span className="text-border-dark">·</span>
                  <span className="text-xs text-muted">{post.author}</span>
                </>
              )}

              {post.labels.length > 0 && (
                <>
                  <span className="text-border-dark">·</span>
                  <div className="flex gap-1.5 flex-wrap">
                    {post.labels.map((label) => (
                      <LabelChip key={label} labelId={label} clickable={false} />
                    ))}
                  </div>
                </>
              )}

              {post.is_draft && (
                <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium">
                  Draft
                </span>
              )}
            </div>
          </div>

          <div className="hidden sm:block w-1 h-12 rounded-full bg-border group-hover:bg-accent transition-colors shrink-0 mt-1" />
        </div>
      </Link>
    </article>
  )
}
