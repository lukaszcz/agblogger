import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useActiveHeading } from '@/hooks/useActiveHeading'

type IntersectionCallback = (entries: Partial<IntersectionObserverEntry>[]) => void

let observerCallback: IntersectionCallback
let observedElements: Element[] = []

const mockDisconnect = vi.fn()

class MockIntersectionObserver {
  constructor(callback: IntersectionCallback) {
    observerCallback = callback
  }
  observe(el: Element) {
    observedElements.push(el)
  }
  unobserve() {}
  disconnect() {
    mockDisconnect()
  }
}

beforeEach(() => {
  observedElements = []
  mockDisconnect.mockClear()
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
})

function makeContainer(...headings: Array<{ tag: string; id: string; text: string }>) {
  const div = document.createElement('div')
  for (const h of headings) {
    const el = document.createElement(h.tag)
    el.id = h.id
    el.textContent = h.text
    div.appendChild(el)
  }
  return div
}

describe('useActiveHeading', () => {
  it('returns null when ref is null', () => {
    const ref = { current: null }
    const { result } = renderHook(() => useActiveHeading(ref))
    expect(result.current).toBeNull()
  })

  it('observes h2 and h3 elements in the container', () => {
    const container = makeContainer(
      { tag: 'h2', id: 'intro', text: 'Intro' },
      { tag: 'h3', id: 'details', text: 'Details' },
      { tag: 'p', id: 'not-heading', text: 'paragraph' },
    )
    const ref = { current: container }
    renderHook(() => useActiveHeading(ref))
    expect(observedElements).toHaveLength(2)
  })

  it('returns the id of the intersecting heading', () => {
    const container = makeContainer(
      { tag: 'h2', id: 'section-one', text: 'Section One' },
      { tag: 'h2', id: 'section-two', text: 'Section Two' },
    )
    const ref = { current: container }
    const { result } = renderHook(() => useActiveHeading(ref))

    // Simulate section-one becoming visible
    act(() => {
      observerCallback([
        { target: container.querySelector('#section-one')!, isIntersecting: true },
      ])
    })
    expect(result.current).toBe('section-one')
  })

  it('disconnects observer on unmount', () => {
    const container = makeContainer({ tag: 'h2', id: 'a', text: 'A' })
    const ref = { current: container }
    const { unmount } = renderHook(() => useActiveHeading(ref))
    unmount()
    expect(mockDisconnect).toHaveBeenCalled()
  })
})
