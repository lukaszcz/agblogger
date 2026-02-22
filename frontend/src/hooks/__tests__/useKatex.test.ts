import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

vi.mock('katex', () => ({
  default: {
    renderToString: (tex: string, opts: { displayMode?: boolean; throwOnError?: boolean }) => {
      const mode = opts.displayMode ? 'display' : 'inline'
      return `<rendered-${mode}>${tex}</rendered-${mode}>`
    },
  },
}))

// Must import after mock
const { useRenderedHtml } = await import('@/hooks/useKatex')

describe('useRenderedHtml', () => {
  it('returns empty string for null', () => {
    const { result } = renderHook(() => useRenderedHtml(null))
    expect(result.current).toBe('')
  })

  it('returns empty string for undefined', () => {
    const { result } = renderHook(() => useRenderedHtml(undefined))
    expect(result.current).toBe('')
  })

  it('passes through HTML without math spans', () => {
    const html = '<p>Hello world</p>'
    const { result } = renderHook(() => useRenderedHtml(html))
    expect(result.current).toBe('<p>Hello world</p>')
  })

  it('renders inline math spans', () => {
    const html = '<p>The value <span class="math inline">x^2</span> is positive.</p>'
    const { result } = renderHook(() => useRenderedHtml(html))
    expect(result.current).toBe(
      '<p>The value <span class="math inline"><rendered-inline>x^2</rendered-inline></span> is positive.</p>',
    )
  })

  it('renders display math spans with displayMode', () => {
    const html = '<span class="math display">\\sum_{i=0}^n i</span>'
    const { result } = renderHook(() => useRenderedHtml(html))
    expect(result.current).toBe(
      '<span class="math display"><rendered-display>\\sum_{i=0}^n i</rendered-display></span>',
    )
  })

  it('handles multiple math spans', () => {
    const html = '<span class="math inline">a</span> and <span class="math display">b</span>'
    const { result } = renderHook(() => useRenderedHtml(html))
    expect(result.current).toContain('<rendered-inline>a</rendered-inline>')
    expect(result.current).toContain('<rendered-display>b</rendered-display>')
  })

  it('trims whitespace from tex content', () => {
    const html = '<span class="math inline"> x + 1 </span>'
    const { result } = renderHook(() => useRenderedHtml(html))
    expect(result.current).toContain('<rendered-inline>x + 1</rendered-inline>')
  })
})
