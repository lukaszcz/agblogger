import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Calendar, User, PenLine } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { fetchPost } from '@/api/posts'
import { useAuthStore } from '@/stores/authStore'
import LabelChip from '@/components/labels/LabelChip'
import type { PostDetail } from '@/api/client'

export default function PostPage() {
  const { '*': filePath } = useParams()
  const [post, setPost] = useState<PostDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const user = useAuthStore((s) => s.user)

  useEffect(() => {
    if (!filePath) return
    void (async () => {
      setLoading(true)
      try {
        const p = await fetchPost(filePath)
        setPost(p)
      } catch {
        setError('Post not found')
      } finally {
        setLoading(false)
      }
    })()
  }, [filePath])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !post) {
    return (
      <div className="text-center py-24">
        <p className="font-display text-3xl text-muted italic">404</p>
        <p className="text-sm text-muted mt-2">{error ?? 'Post not found'}</p>
        <Link to="/" className="text-accent text-sm hover:underline mt-4 inline-block">
          Back to timeline
        </Link>
      </div>
    )
  }

  let dateStr = ''
  try {
    const parsed = parseISO(post.created_at.replace(' ', 'T').replace(/\+(\d{2})$/, '+$1:00'))
    dateStr = format(parsed, 'MMMM d, yyyy')
  } catch {
    dateStr = post.created_at.split(' ')[0] ?? ''
  }

  return (
    <article className="animate-fade-in">
      {/* Back link */}
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors mb-8"
      >
        <ArrowLeft size={14} />
        Back to posts
      </Link>

      {/* Post header */}
      <header className="mb-10">
        <h1 className="font-display text-4xl md:text-5xl text-ink leading-tight tracking-tight">
          {post.title}
        </h1>

        <div className="mt-5 flex items-center gap-4 flex-wrap text-sm text-muted">
          <div className="flex items-center gap-1.5">
            <Calendar size={14} />
            <time>{dateStr}</time>
          </div>

          {post.author && (
            <div className="flex items-center gap-1.5">
              <User size={14} />
              <span>{post.author}</span>
            </div>
          )}

          {post.labels.length > 0 && (
            <div className="flex gap-1.5 flex-wrap">
              {post.labels.map((label) => (
                <LabelChip key={label} labelId={label} />
              ))}
            </div>
          )}

          {user && (
            <Link
              to={`/editor/${post.file_path}`}
              className="flex items-center gap-1 text-accent hover:underline ml-auto"
            >
              <PenLine size={14} />
              Edit
            </Link>
          )}
        </div>

        <div className="mt-6 h-px bg-gradient-to-r from-accent/40 via-border to-transparent" />
      </header>

      {/* Post content — strip the first h1 since we show it in the header */}
      <div
        className="prose max-w-none"
        dangerouslySetInnerHTML={{
          __html: post.rendered_html.replace(/<h1[^>]*>.*?<\/h1>\s*/i, ''),
        }}
      />

      {/* Footer */}
      <footer className="mt-16 pt-8 border-t border-border">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft size={14} />
          Back to posts
        </Link>
      </footer>
    </article>
  )
}
