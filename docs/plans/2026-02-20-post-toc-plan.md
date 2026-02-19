# Post Table of Contents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a client-side table of contents to the post view, with a floating toggle button and active heading tracking.

**Architecture:** Extract heading data (H2/H3) from the rendered HTML DOM. A `useActiveHeading` hook tracks scroll position via IntersectionObserver. A `TableOfContents` component renders a floating button and dropdown panel. PostPage passes a content ref.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, lucide-react icons, IntersectionObserver API, Vitest + testing-library.

---

### Task 1: Create `useActiveHeading` hook with tests

**Files:**
- Create: `frontend/src/hooks/__tests__/useActiveHeading.test.ts`
- Create: `frontend/src/hooks/useActiveHeading.ts`

**Step 1: Write the failing tests**

Create `frontend/src/hooks/__tests__/useActiveHeading.test.ts`:

```typescript
import { renderHook } from '@testing-library/react'
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
    observerCallback([
      { target: container.querySelector('#section-one')!, isIntersecting: true },
    ])
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
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useActiveHeading.test.ts`
Expected: FAIL — module `@/hooks/useActiveHeading` not found.

**Step 3: Write minimal implementation**

Create `frontend/src/hooks/useActiveHeading.ts`:

```typescript
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
```

The `rootMargin` triggers when a heading enters the top 40% of the viewport, offset 80px from top for the site header.

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useActiveHeading.test.ts`
Expected: PASS (all 4 tests).

**Step 5: Commit**

```bash
git add frontend/src/hooks/useActiveHeading.ts frontend/src/hooks/__tests__/useActiveHeading.test.ts
git commit -m "feat: add useActiveHeading hook for scroll-based heading tracking"
```

---

### Task 2: Create `TableOfContents` component with tests

**Files:**
- Create: `frontend/src/components/posts/__tests__/TableOfContents.test.tsx`
- Create: `frontend/src/components/posts/TableOfContents.tsx`

**Step 1: Write the failing tests**

Create `frontend/src/components/posts/__tests__/TableOfContents.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TableOfContents from '../TableOfContents'

let mockActiveId: string | null = null

vi.mock('@/hooks/useActiveHeading', () => ({
  useActiveHeading: () => mockActiveId,
}))

function makeContentRef(...headings: Array<{ tag: string; id: string; text: string }>) {
  const div = document.createElement('div')
  for (const h of headings) {
    const el = document.createElement(h.tag)
    el.id = h.id
    el.textContent = h.text
    div.appendChild(el)
  }
  return { current: div }
}

beforeEach(() => {
  mockActiveId = null
})

describe('TableOfContents', () => {
  it('renders nothing when fewer than 3 headings', () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'A' },
      { tag: 'h2', id: 'b', text: 'B' },
    )
    const { container } = render(<TableOfContents contentRef={ref} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders toggle button when 3+ headings', () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'Section A' },
      { tag: 'h2', id: 'b', text: 'Section B' },
      { tag: 'h2', id: 'c', text: 'Section C' },
    )
    render(<TableOfContents contentRef={ref} />)
    expect(screen.getByRole('button', { name: /table of contents/i })).toBeInTheDocument()
  })

  it('shows TOC panel on button click', async () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'Section A' },
      { tag: 'h2', id: 'b', text: 'Section B' },
      { tag: 'h3', id: 'b1', text: 'Subsection B1' },
    )
    render(<TableOfContents contentRef={ref} />)

    await userEvent.click(screen.getByRole('button', { name: /table of contents/i }))

    expect(screen.getByText('Section A')).toBeInTheDocument()
    expect(screen.getByText('Section B')).toBeInTheDocument()
    expect(screen.getByText('Subsection B1')).toBeInTheDocument()
  })

  it('closes panel on Escape key', async () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'Section A' },
      { tag: 'h2', id: 'b', text: 'Section B' },
      { tag: 'h2', id: 'c', text: 'Section C' },
    )
    render(<TableOfContents contentRef={ref} />)

    await userEvent.click(screen.getByRole('button', { name: /table of contents/i }))
    expect(screen.getByText('Section A')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByText('Section A')).not.toBeInTheDocument()
    })
  })

  it('closes panel when a TOC link is clicked', async () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'Section A' },
      { tag: 'h2', id: 'b', text: 'Section B' },
      { tag: 'h2', id: 'c', text: 'Section C' },
    )
    render(<TableOfContents contentRef={ref} />)

    await userEvent.click(screen.getByRole('button', { name: /table of contents/i }))
    await userEvent.click(screen.getByText('Section A'))
    await waitFor(() => {
      expect(screen.queryByText('Section B')).not.toBeInTheDocument()
    })
  })

  it('indents h3 entries', async () => {
    const ref = makeContentRef(
      { tag: 'h2', id: 'a', text: 'Section A' },
      { tag: 'h3', id: 'a1', text: 'Sub A1' },
      { tag: 'h2', id: 'b', text: 'Section B' },
    )
    render(<TableOfContents contentRef={ref} />)

    await userEvent.click(screen.getByRole('button', { name: /table of contents/i }))

    const subItem = screen.getByText('Sub A1').closest('li')
    expect(subItem?.className).toContain('pl-')
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/posts/__tests__/TableOfContents.test.tsx`
Expected: FAIL — module not found.

**Step 3: Write implementation**

Create `frontend/src/components/posts/TableOfContents.tsx`. Use the `frontend-design` skill to design the UI for this component. The component must:

- Accept `contentRef: RefObject<HTMLElement | null>`
- Extract h2/h3 elements on mount via `useEffect` + `querySelectorAll`
- Return `null` if fewer than 3 headings
- Render a floating button (lucide `List` icon) with `aria-label="Table of contents"`
- On click, toggle a dropdown panel with:
  - "Table of Contents" heading
  - List of heading links (h3 indented with `pl-4`)
  - Active heading highlighted via `useActiveHeading` hook
  - Max height with overflow-y scroll
- Close on Escape (keydown listener), click outside (mousedown listener), or link click
- Clicking a link calls `document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })`
- Animations: slide-down/fade-in on open using Tailwind transitions

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/posts/__tests__/TableOfContents.test.tsx`
Expected: PASS (all 6 tests).

**Step 5: Commit**

```bash
git add frontend/src/components/posts/TableOfContents.tsx frontend/src/components/posts/__tests__/TableOfContents.test.tsx
git commit -m "feat: add TableOfContents component with floating toggle"
```

---

### Task 3: Integrate TOC into PostPage

**Files:**
- Modify: `frontend/src/pages/PostPage.tsx`
- Modify: `frontend/src/pages/__tests__/PostPage.test.tsx`

**Step 1: Write the failing test**

Add to `frontend/src/pages/__tests__/PostPage.test.tsx`:

1. Add a mock for the `TableOfContents` component:

```typescript
vi.mock('@/components/posts/TableOfContents', () => ({
  default: ({ contentRef }: { contentRef: React.RefObject<HTMLElement | null> }) => (
    <div data-testid="toc" data-has-ref={!!contentRef.current} />
  ),
}))
```

2. Add a test case:

```typescript
it('renders table of contents component', async () => {
  mockFetchPost.mockResolvedValue(postDetail)
  renderPostPage()

  await waitFor(() => {
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })
  expect(screen.getByTestId('toc')).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/PostPage.test.tsx`
Expected: FAIL — `toc` testid not found.

**Step 3: Modify PostPage**

In `frontend/src/pages/PostPage.tsx`:

1. Add `useRef` to the React import
2. Import `TableOfContents` from `@/components/posts/TableOfContents`
3. Create a ref: `const contentRef = useRef<HTMLDivElement>(null)`
4. Add `ref={contentRef}` to the prose `<div>` (line 159)
5. Render `<TableOfContents contentRef={contentRef} />` between the back link and the header, in a row with the back link. Wrap the back link and TOC button in a flex container:

```tsx
<div className="flex items-center justify-between mb-8">
  <Link
    to="/"
    className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors"
  >
    <ArrowLeft size={14} />
    Back to posts
  </Link>
  <TableOfContents contentRef={contentRef} />
</div>
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/PostPage.test.tsx`
Expected: PASS (all tests including the new one).

**Step 5: Commit**

```bash
git add frontend/src/pages/PostPage.tsx frontend/src/pages/__tests__/PostPage.test.tsx
git commit -m "feat: integrate table of contents into post page"
```

---

### Task 4: Browser testing and polish

**Files:**
- Possibly adjust: `frontend/src/components/posts/TableOfContents.tsx`
- Possibly adjust: `frontend/src/index.css`

**Step 1: Start dev server**

Run: `just start`

**Step 2: Test in browser with Playwright MCP**

Navigate to a post with 3+ headings. Verify:
- TOC button appears in the header row
- Clicking the button opens the dropdown with correct headings
- H3 entries are indented under H2s
- Clicking a heading smooth-scrolls to it and closes the panel
- Active heading highlight updates on scroll
- Escape closes the panel
- Clicking outside closes the panel
- Posts with < 3 headings do not show the TOC button

**Step 3: Adjust styling if needed**

Fix any visual issues found during browser testing.

**Step 4: Run full checks**

Run: `just check`
Expected: All type checks, linting, and tests pass.

**Step 5: Clean up and commit**

Remove any leftover screenshot files. Commit any polish changes:

```bash
git commit -m "fix: polish table of contents styling"
```

**Step 6: Stop dev server**

Run: `just stop`
