import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Save, Eye, ArrowLeft } from 'lucide-react'
import { fetchPost, createPost, updatePost } from '@/api/posts'
import { HTTPError } from '@/api/client'
import api from '@/api/client'

export default function EditorPage() {
  const { '*': filePath } = useParams()
  const navigate = useNavigate()
  const isNew = !filePath || filePath === 'new'

  const [content, setContent] = useState('')
  const [newPath, setNewPath] = useState('posts/')
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isNew && filePath) {
      fetchPost(filePath)
        .then((post) => {
          // We need to fetch raw content - for now use a simple reconstruction
          setContent(post.content ?? `# ${post.title}\n\n`)
          setNewPath(post.file_path)
        })
        .catch((err) => {
          if (err instanceof HTTPError && err.response.status === 404) {
            setError('Post not found')
          } else {
            setError('Failed to load post')
          }
        })
    } else {
      const now = new Date().toISOString().split('T')[0]
      setContent(
        `---\ncreated_at: ${now}\nauthor: \nlabels: []\n---\n# New Post\n\nStart writing here...\n`,
      )
    }
  }, [filePath, isNew])

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const path = isNew ? newPath : filePath
      if (isNew) {
        await createPost(path, content)
      } else {
        await updatePost(path, content)
      }
      void navigate(`/post/${path}`)
    } catch (err) {
      if (err instanceof HTTPError) {
        if (err.response.status === 401) {
          setError('Session expired. Please log in again.')
        } else if (err.response.status === 409) {
          setError('Conflict: this post was modified elsewhere.')
        } else {
          setError('Failed to save post')
        }
      } else {
        setError('Failed to save post')
      }
    } finally {
      setSaving(false)
    }
  }

  async function handlePreview() {
    // Strip frontmatter for preview
    const bodyMatch = content.match(/^---[\s\S]*?---\n([\s\S]*)$/)
    const body = bodyMatch ? bodyMatch[1] : content
    setPreviewing(true)
    try {
      const resp = await api
        .post('render/preview', { json: { markdown: body } })
        .json<{ html: string }>()
      setPreview(resp.html)
    } catch {
      setError('Preview failed')
    } finally {
      setPreviewing(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
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
            disabled={previewing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                     border border-border rounded-lg hover:bg-paper-warm disabled:opacity-50 transition-colors"
          >
            <Eye size={14} />
            {previewing ? 'Loading...' : 'Preview'}
          </button>
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
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {isNew && (
        <div className="mb-4">
          <label htmlFor="filepath" className="block text-sm font-medium text-ink mb-1.5">
            File path
          </label>
          <input
            id="filepath"
            type="text"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="posts/my-new-post.md"
            className="w-full px-4 py-2.5 bg-paper-warm border border-border rounded-lg
                     text-ink font-mono text-sm
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ minHeight: '60vh' }}>
        <div>
          <textarea
            value={content}
            onChange={(e) => {
              setContent(e.target.value)
              setPreview(null)
            }}
            className="w-full h-full min-h-[60vh] p-4 bg-paper-warm border border-border rounded-lg
                     font-mono text-sm leading-relaxed text-ink resize-none
                     focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
            spellCheck={false}
          />
        </div>

        {preview && (
          <div className="p-6 bg-white border border-border rounded-lg overflow-y-auto">
            <div
              className="prose max-w-none"
              dangerouslySetInnerHTML={{ __html: preview }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
