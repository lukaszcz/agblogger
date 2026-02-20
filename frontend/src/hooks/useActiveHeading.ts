import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

export function useActiveHeading(contentRef: RefObject<HTMLElement | null>): string | null {
  const [activeId, setActiveId] = useState<string | null>(null)

  useEffect(() => {
    const container = contentRef.current
    if (!container) return

    const headings = container.querySelectorAll('h2, h3')
    if (headings.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 },
    )

    headings.forEach((heading) => observer.observe(heading))

    return () => observer.disconnect()
  }, [contentRef])

  return activeId
}
