import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const MATH_SPAN_RE =
  /<span class="math (inline|display)">([\s\S]*?)<\/span>/g

const HTML_ENTITY_RE = /&(?:amp|lt|gt|quot|#39);/g
const HTML_ENTITY_MAP: Record<string, string> = {
  '&amp;': '&',
  '&lt;': '<',
  '&gt;': '>',
  '&quot;': '"',
  '&#39;': "'",
}

function decodeHtmlEntities(s: string): string {
  return s.replace(HTML_ENTITY_RE, (entity) => HTML_ENTITY_MAP[entity] ?? entity)
}

/**
 * Pre-renders KaTeX math in an HTML string. Replaces Pandoc's
 * `<span class="math inline">` and `<span class="math display">`
 * with KaTeX-rendered HTML so React can manage the final DOM.
 *
 * Used for both full post HTML and rendered excerpts.
 */
export function useRenderedHtml(html: string | null | undefined): string {
  return useMemo(() => {
    if (html == null) return ''
    return html.replace(MATH_SPAN_RE, (_match, mode: string, tex: string) => {
      const displayMode = mode === 'display'
      const rendered = katex.renderToString(decodeHtmlEntities(tex.trim()), {
        throwOnError: false,
        displayMode,
      })
      return `<span class="math ${mode}">${rendered}</span>`
    })
  }, [html])
}
