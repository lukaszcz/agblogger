import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, ArrowLeft } from 'lucide-react'
import { format, parseISO } from 'date-fns'

import { fetchPostForEdit, createPost, updatePost } from '@/api/posts'
import { HTTPError } from '@/api/client'
import api from '@/api/client'
import { useEditorAutoSave } from '@/hooks/useEditorAutoSave'
import type { DraftData } from '@/hooks/useEditorAutoSave'
import { useRenderedHtml } from '@/hooks/useKatex'
import { useAuthStore } from '@/stores/authStore'
import LabelInput from '@/components/editor/LabelInput'

export default function EditorPage() {
  const { '*': filePath } = useParams()
  const navigate = useNavigate()
  const isNew = !filePath || filePath === 'new'
  const user = useAuthStore((s) => s.user)
  const isInitialized = useAuthStore((s) => s.isInitialized)

  const [body, setBody] = useState(isNew ? '# New Post\n\nStart writing here...\n' : '')
  const [labels, setLabels] = useState<string[]>([])
  const [isDraft, setIsDraft] = useState(false)
  const [newPath, setNewPath] = useState('posts/')
  const [author, setAuthor] = useState<string | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [modifiedAt, setModifiedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const renderedPreview = useRenderedHtml(preview)
  const previewRequestRef = useRef(0)

  const autoSaveKey = isNew ? 'agblogger:draft:new' : `agblogger:draft:${filePath}`
  const currentState = useMemo<DraftData>(
    () => ({ body, labels, isDraft, ...(isNew ? { newPath } : {}) }),
    [body, labels, isDraft, isNew, newPath],
  )

  const handleRestore = useCallback((draft: DraftData) => {
    setBody(draft.body)
    setLabels(draft.labels)
    setIsDraft(draft.isDraft)
    if (draft.newPath) setNewPath(draft.newPath)
  }, [])

  const { isDirty, draftAvailable, draftSavedAt, restoreDraft, discardDraft, markSaved } =
    useEditorAutoSave({
      key: autoSaveKey,
      currentState,
      onRestore: handleRestore,
      enabled: isNew || !loading,
    })

  useEffect(() => {
    if (isInitialized && !user) {
      void navigate('/login', { replace: true })
    }
  }, [user, isInitialized, navigate])

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
    }
  }, [filePath, isNew])

  useEffect(() => {
    if (isNew) {
      setAuthor(user?.display_name || user?.username || null)
    }
  }, [isNew, user?.display_name, user?.username])

  useEffect(() => {
    if (!body) return
    const requestId = ++previewRequestRef.current
    const timer = setTimeout(async () => {
      try {
        const resp = await api
          .post('render/preview', { json: { markdown: body } })
          .json<{ html: string }>()
        if (previewRequestRef.current === requestId) {
          setPreview(resp.html)
        }
      } catch {
        // Silently ignore preview failures — editor remains usable
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [body])

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
      markSaved()
      void navigate(`/post/${path}`)
    } catch (err) {
      if (err instanceof HTTPError) {
        const status = err.response.status
        if (status === 401) {
          setError('Session expired. Please log in again.')
        } else if (status === 409) {
          setError(
            isNew
              ? 'A post with this file path already exists.'
              : 'Conflict: this post was modified elsewhere.',
          )
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

  function formatDate(iso: string): string {
    try {
      const parsed = parseISO(iso.replace(' ', 'T').replace(/\+(\d{2})$/, '+$1:00'))
      return format(parsed, 'MMM d, yyyy, HH:mm')
    } catch {
      return iso.split('.')[0] ?? iso
    }
  }

  if (!isInitialized || !user) {
    return null
  }

  if (loading) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-muted text-sm">Loading...</span>
      </div>
    )
  }

  if (!isNew && error) {
    return (
      <div className="animate-fade-in text-center py-24">
        <p className="font-display text-3xl text-muted italic">
          {error === 'Post not found' ? '404' : 'Error'}
        </p>
        <p className="text-sm text-muted mt-2">{error}</p>
        <button
          onClick={() => void navigate(-1)}
          className="text-accent text-sm hover:underline mt-4 inline-block"
        >
          Go back
        </button>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => void navigate(-1)}
            className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          {isDirty && <span className="text-muted text-sm">*</span>}
        </div>

        <button
          onClick={() => void handleSave()}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium
                   bg-accent text-white rounded-lg hover:bg-accent-light disabled:opacity-50 transition-colors"
        >
          <Save size={14} />
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {draftAvailable && draftSavedAt && (
        <div className="mb-4 flex items-center justify-between text-sm bg-sky-50 border border-sky-200 rounded-lg px-4 py-3">
          <span className="text-sky-800">
            You have unsaved changes from{' '}
            {format(parseISO(draftSavedAt), 'MMM d, h:mm a')}
          </span>
          <span className="flex gap-2">
            <button
              onClick={restoreDraft}
              className="font-medium text-sky-700 hover:text-sky-900 hover:underline"
            >
              Restore
            </button>
            <button
              onClick={discardDraft}
              className="font-medium text-sky-500 hover:text-sky-700 hover:underline"
            >
              Discard
            </button>
          </span>
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
              disabled={saving}
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
          <LabelInput value={labels} onChange={setLabels} disabled={saving} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isDraft}
                onChange={(e) => setIsDraft(e.target.checked)}
                disabled={saving}
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
            onChange={(e) => setBody(e.target.value)}
            disabled={saving}
            className="w-full h-full min-h-[60vh] p-4 bg-paper-warm border border-border rounded-lg
                     font-mono text-sm leading-relaxed text-ink resize-none
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                     disabled:opacity-50"
            spellCheck={false}
          />
        </div>

        <div className="p-6 bg-paper border border-border rounded-lg overflow-y-auto">
          {preview ? (
            <div
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: renderedPreview }}
            />
          ) : (
            <p className="text-sm text-muted italic">Preview will appear here...</p>
          )}
        </div>
      </div>
    </div>
  )
}
