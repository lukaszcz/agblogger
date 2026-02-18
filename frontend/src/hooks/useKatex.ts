import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const MATH_SPAN_RE =
  /<span class="math (inline|display)">([\s\S]*?)<\/span>/g

/**
 * Pre-renders KaTeX math in an HTML string. Replaces Pandoc's
 * `<span class="math inline">` and `<span class="math display">`
 * with KaTeX-rendered HTML so React can manage the final DOM.
 */
export function useRenderedHtml(html: string | null | undefined): string {
  return useMemo(() => {
    if (!html) return ''
    return html.replace(MATH_SPAN_RE, (_match, mode: string, tex: string) => {
      const displayMode = mode === 'display'
      const rendered = katex.renderToString(tex.trim(), {
        throwOnError: false,
        displayMode,
      })
      return `<span class="math ${mode}">${rendered}</span>`
    })
  }, [html])
}
