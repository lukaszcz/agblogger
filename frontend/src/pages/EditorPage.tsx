import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, Eye, ArrowLeft } from 'lucide-react'

import { fetchPostForEdit, createPost, updatePost } from '@/api/posts'
import { HTTPError } from '@/api/client'
import api from '@/api/client'
import { useRenderedHtml } from '@/hooks/useKatex'
import { useAuthStore } from '@/stores/authStore'
import LabelInput from '@/components/editor/LabelInput'

export default function EditorPage() {
  const { '*': filePath } = useParams()
  const navigate = useNavigate()
  const isNew = !filePath || filePath === 'new'
  const user = useAuthStore((s) => s.user)
  const initialAuthor = user?.display_name || user?.username || null

  const [body, setBody] = useState('')
  const [labels, setLabels] = useState<string[]>([])
  const [isDraft, setIsDraft] = useState(false)
  const [newPath, setNewPath] = useState('posts/')
  const [author, setAuthor] = useState<string | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [modifiedAt, setModifiedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const renderedPreview = useRenderedHtml(preview)
  const busy = saving || previewing

  useEffect(() => {
    if (!isNew && filePath) {
      setLoading(true)
      fetchPostForEdit(filePath)
        .then((data) => {
          setBody(data.body)
          setLabels(data.labels)
          setIsDraft(data.is_draft)
          setNewPath(data.file_path)
          setAuthor(data.author)
          setCreatedAt(data.created_at)
          setModifiedAt(data.modified_at)
        })
        .catch((err) => {
          if (err instanceof HTTPError && err.response.status === 404) {
            setError('Post not found')
          } else {
            setError('Failed to load post')
          }
        })
        .finally(() => setLoading(false))
    } else {
      setBody('# New Post\n\nStart writing here...\n')
      setAuthor(initialAuthor)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filePath, isNew])

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const path = isNew ? newPath : filePath
      if (isNew) {
        await createPost({ file_path: path, body, labels, is_draft: isDraft })
      } else {
        await updatePost(path, { body, labels, is_draft: isDraft })
      }
      void navigate(`/post/${path}`)
    } catch (err) {
      if (err instanceof HTTPError) {
        const status = err.response.status
        if (status === 401) {
          setError('Session expired. Please log in again.')
        } else if (status === 409) {
          setError('Conflict: this post was modified elsewhere.')
        } else if (status === 404) {
          setError('Post not found. It may have been deleted.')
        } else if (status === 422) {
          try {
            const text = await err.response.text()
            const parsed: unknown = JSON.parse(text)
            const detail =
              parsed && typeof parsed === 'object' && 'detail' in parsed
                ? (parsed as { detail: unknown }).detail
                : undefined
            if (Array.isArray(detail)) {
              setError(
                detail
                  .map((d: unknown) => {
                    const item = d as { msg?: string }
                    return item.msg ?? 'Unknown error'
                  })
                  .join(', '),
              )
            } else if (typeof detail === 'string') {
              setError(detail || 'Validation error. Check your input.')
            } else {
              setError('Validation error. Check your input.')
            }
          } catch {
            setError('Validation error. Check your input.')
          }
        } else {
          setError('Failed to save post. Please try again.')
        }
      } else {
        setError('Failed to save post. The server may be unavailable.')
      }
    } finally {
      setSaving(false)
    }
  }

  async function handlePreview() {
    setPreviewing(true)
    try {
      const resp = await api
        .post('render/preview', { json: { markdown: body } })
        .json<{ html: string }>()
      setPreview(resp.html)
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Preview failed. The server may be unavailable.')
      }
    } finally {
      setPreviewing(false)
    }
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString()
  }

  if (loading) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-muted text-sm">Loading...</span>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => void navigate(-1)}
          className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void handlePreview()}
            disabled={busy}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                     border border-border rounded-lg hover:bg-paper-warm disabled:opacity-50 transition-colors"
          >
            <Eye size={14} />
            {previewing ? 'Loading...' : 'Preview'}
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={busy}
            className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium
                     bg-accent text-white rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="mb-4 space-y-3 p-4 bg-paper border border-border rounded-lg">
        {isNew && (
          <div>
            <label htmlFor="filepath" className="block text-xs font-medium text-muted mb-1">
              File path
            </label>
            <input
              id="filepath"
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              disabled={busy}
              placeholder="posts/my-new-post.md"
              className="w-full px-3 py-2 bg-paper-warm border border-border rounded-lg
                       text-ink font-mono text-sm
                       focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                       disabled:opacity-50"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-muted mb-1">Labels</label>
          <LabelInput value={labels} onChange={setLabels} disabled={busy} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isDraft}
                onChange={(e) => setIsDraft(e.target.checked)}
                disabled={busy}
                className="rounded border-border text-accent focus:ring-accent/20"
              />
              <span className="text-sm text-ink">Draft</span>
            </label>

            {author && (
              <span className="text-sm text-muted">
                Author: <span className="text-ink">{author}</span>
              </span>
            )}
          </div>

          {!isNew && (createdAt || modifiedAt) && (
            <div className="flex items-center gap-4 text-xs text-muted">
              {createdAt && <span>Created {formatDate(createdAt)}</span>}
              {modifiedAt && <span>Modified {formatDate(modifiedAt)}</span>}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: '60vh' }}>
        <div>
          <textarea
            value={body}
            onChange={(e) => {
              setBody(e.target.value)
              setPreview(null)
            }}
            disabled={busy}
            className="w-full h-full min-h-[60vh] p-4 bg-paper-warm border border-border rounded-lg
                     font-mono text-sm leading-relaxed text-ink resize-none
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                     disabled:opacity-50"
            spellCheck={false}
          />
        </div>

        {preview && (
          <div className="p-6 bg-paper border border-border rounded-lg overflow-y-auto">
            <div
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: renderedPreview }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
