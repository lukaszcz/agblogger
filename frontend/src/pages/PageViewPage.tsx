import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '@/api/client'
import type { PageResponse } from '@/api/client'

export default function PageViewPage() {
  const { pageId } = useParams()
  const [page, setPage] = useState<PageResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!pageId) return
    void (async () => {
      setLoading(true)
      try {
        const p = await api.get(`pages/${pageId}`).json<PageResponse>()
        setPage(p)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    })()
  }, [pageId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  if (!page) {
    return (
      <div className="text-center py-24">
        <p className="font-display text-2xl text-muted italic">Page not found</p>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
      <h1 className="font-display text-4xl text-ink mb-8">{page.title}</h1>
      <div
        className="prose max-w-none"
        dangerouslySetInnerHTML={{ __html: page.rendered_html }}
      />
    </div>
  )
}
