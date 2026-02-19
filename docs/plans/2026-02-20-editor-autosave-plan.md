# Editor Auto-Save & Unsaved Changes Warning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Warn users about unsaved editor changes and auto-save drafts to localStorage for crash recovery.

**Architecture:** A `useEditorAutoSave` custom hook encapsulates dirty-tracking, debounced localStorage persistence, `beforeunload`, and react-router `useBlocker`. EditorPage consumes the hook and renders a recovery banner when a stale draft is found.

**Tech Stack:** React 19, react-router-dom v7 (`useBlocker`), localStorage, Vitest + testing-library

---

### Task 1: Create `useEditorAutoSave` hook with dirty-tracking

**Files:**
- Create: `frontend/src/hooks/useEditorAutoSave.ts`
- Test: `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`

**Step 1: Write failing tests for dirty-tracking**

Create `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`:

```ts
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'

import { useEditorAutoSave } from '@/hooks/useEditorAutoSave'
import type { DraftData } from '@/hooks/useEditorAutoSave'

function wrapper({ children }: { children: React.ReactNode }) {
  // useBlocker requires a router context
  const { MemoryRouter } = require('react-router-dom')
  return <MemoryRouter>{children}</MemoryRouter>
}

const initial: DraftData = {
  body: '# Hello',
  labels: ['swe'],
  isDraft: false,
}

describe('useEditorAutoSave', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('is not dirty when state matches initial', () => {
    const onRestore = vi.fn()
    const { result } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: initial, onRestore }),
      { wrapper },
    )
    expect(result.current.isDirty).toBe(false)
  })

  it('is dirty when body changes', () => {
    const onRestore = vi.fn()
    let state = { ...initial }
    const { result, rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )
    expect(result.current.isDirty).toBe(false)

    state = { ...initial, body: '# Changed' }
    rerender()
    expect(result.current.isDirty).toBe(true)
  })

  it('is dirty when labels change', () => {
    const onRestore = vi.fn()
    let state = { ...initial }
    const { result, rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    state = { ...initial, labels: ['swe', 'cs'] }
    rerender()
    expect(result.current.isDirty).toBe(true)
  })

  it('is dirty when isDraft changes', () => {
    const onRestore = vi.fn()
    let state = { ...initial }
    const { result, rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    state = { ...initial, isDraft: true }
    rerender()
    expect(result.current.isDirty).toBe(true)
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: FAIL — module not found

**Step 3: Write minimal `useEditorAutoSave` hook**

Create `frontend/src/hooks/useEditorAutoSave.ts`:

```ts
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useBlocker } from 'react-router-dom'

export interface DraftData {
  body: string
  labels: string[]
  isDraft: boolean
  newPath?: string
  savedAt?: string
}

interface UseEditorAutoSaveParams {
  key: string
  currentState: DraftData
  onRestore: (draft: DraftData) => void
}

interface UseEditorAutoSaveReturn {
  isDirty: boolean
  draftAvailable: boolean
  draftSavedAt: string | null
  restoreDraft: () => void
  discardDraft: () => void
  markSaved: () => void
}

function statesEqual(a: DraftData, b: DraftData): boolean {
  return (
    a.body === b.body &&
    a.isDraft === b.isDraft &&
    a.labels.length === b.labels.length &&
    a.labels.every((l, i) => l === b.labels[i])
  )
}

export function useEditorAutoSave({
  key,
  currentState,
  onRestore,
}: UseEditorAutoSaveParams): UseEditorAutoSaveReturn {
  const initialStateRef = useRef<DraftData>(currentState)
  const [draftAvailable, setDraftAvailable] = useState(false)
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null)
  const onRestoreRef = useRef(onRestore)
  onRestoreRef.current = onRestore

  // Check for existing draft on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(key)
      if (stored) {
        const draft: DraftData = JSON.parse(stored)
        if (draft.savedAt) {
          setDraftAvailable(true)
          setDraftSavedAt(draft.savedAt)
        }
      }
    } catch {
      // Ignore corrupt localStorage data
    }
  }, [key])

  const isDirty = useMemo(
    () => !statesEqual(currentState, initialStateRef.current),
    [currentState],
  )

  // Debounced auto-save to localStorage
  useEffect(() => {
    if (!isDirty) return
    const timer = setTimeout(() => {
      const draft: DraftData = { ...currentState, savedAt: new Date().toISOString() }
      localStorage.setItem(key, JSON.stringify(draft))
    }, 3000)
    return () => clearTimeout(timer)
  }, [isDirty, currentState, key])

  // beforeunload warning
  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // react-router navigation blocker
  useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname &&
      !window.confirm('You have unsaved changes. Leave anyway?'),
  )

  const restoreDraft = useCallback(() => {
    try {
      const stored = localStorage.getItem(key)
      if (stored) {
        const draft: DraftData = JSON.parse(stored)
        onRestoreRef.current(draft)
        initialStateRef.current = draft
      }
    } catch {
      // Ignore
    }
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [key])

  const discardDraft = useCallback(() => {
    localStorage.removeItem(key)
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [key])

  const markSaved = useCallback(() => {
    localStorage.removeItem(key)
    initialStateRef.current = currentState
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [key, currentState])

  return { isDirty, draftAvailable, draftSavedAt, restoreDraft, discardDraft, markSaved }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add frontend/src/hooks/useEditorAutoSave.ts frontend/src/hooks/__tests__/useEditorAutoSave.test.ts
git commit -m "feat: add useEditorAutoSave hook with dirty-tracking"
```

---

### Task 2: Add localStorage auto-save and recovery tests

**Files:**
- Modify: `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`

**Step 1: Add failing tests for localStorage auto-save and draft recovery**

Append to the `describe` block in the test file:

```ts
  it('auto-saves to localStorage after debounce', async () => {
    vi.useFakeTimers()
    const onRestore = vi.fn()
    let state = { ...initial }
    const { rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    state = { ...initial, body: '# Changed' }
    rerender()

    // Not saved yet (before debounce)
    expect(localStorage.getItem('test')).toBeNull()

    // Advance past debounce
    await act(async () => { vi.advanceTimersByTime(3000) })

    const stored = JSON.parse(localStorage.getItem('test')!)
    expect(stored.body).toBe('# Changed')
    expect(stored.savedAt).toBeTruthy()
    vi.useRealTimers()
  })

  it('detects existing draft on mount', () => {
    const draft = { ...initial, body: '# Draft', savedAt: '2026-02-20T12:00:00Z' }
    localStorage.setItem('test', JSON.stringify(draft))

    const onRestore = vi.fn()
    const { result } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: initial, onRestore }),
      { wrapper },
    )

    expect(result.current.draftAvailable).toBe(true)
    expect(result.current.draftSavedAt).toBe('2026-02-20T12:00:00Z')
  })

  it('restoreDraft calls onRestore and clears draftAvailable', () => {
    const draft = { ...initial, body: '# Draft', savedAt: '2026-02-20T12:00:00Z' }
    localStorage.setItem('test', JSON.stringify(draft))

    const onRestore = vi.fn()
    const { result } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: initial, onRestore }),
      { wrapper },
    )

    act(() => { result.current.restoreDraft() })

    expect(onRestore).toHaveBeenCalledWith(draft)
    expect(result.current.draftAvailable).toBe(false)
  })

  it('discardDraft removes localStorage entry', () => {
    localStorage.setItem('test', JSON.stringify({ ...initial, savedAt: '2026-02-20T12:00:00Z' }))

    const onRestore = vi.fn()
    const { result } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: initial, onRestore }),
      { wrapper },
    )

    act(() => { result.current.discardDraft() })

    expect(localStorage.getItem('test')).toBeNull()
    expect(result.current.draftAvailable).toBe(false)
  })

  it('markSaved clears localStorage and resets dirty', async () => {
    vi.useFakeTimers()
    const onRestore = vi.fn()
    let state = { ...initial }
    const { result, rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    // Make dirty
    state = { ...initial, body: '# Changed' }
    rerender()
    await act(async () => { vi.advanceTimersByTime(3000) })
    expect(localStorage.getItem('test')).not.toBeNull()

    // Mark saved
    act(() => { result.current.markSaved() })

    expect(localStorage.getItem('test')).toBeNull()
    expect(result.current.isDirty).toBe(false)
    vi.useRealTimers()
  })
```

**Step 2: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: PASS (all 9 tests)

**Step 3: Commit**

```bash
git add frontend/src/hooks/__tests__/useEditorAutoSave.test.ts
git commit -m "test: add localStorage auto-save and recovery tests"
```

---

### Task 3: Add beforeunload tests

**Files:**
- Modify: `frontend/src/hooks/__tests__/useEditorAutoSave.test.ts`

**Step 1: Add failing tests for beforeunload behavior**

```ts
  it('registers beforeunload when dirty', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const onRestore = vi.fn()
    let state = { ...initial }
    const { rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    // Not dirty — no beforeunload
    expect(addSpy).not.toHaveBeenCalledWith('beforeunload', expect.any(Function))

    // Make dirty
    state = { ...initial, body: '# Changed' }
    rerender()

    expect(addSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))
    addSpy.mockRestore()
  })

  it('unregisters beforeunload when no longer dirty', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const onRestore = vi.fn()
    let state: DraftData = { ...initial, body: '# Changed' }
    const { rerender } = renderHook(
      () => useEditorAutoSave({ key: 'test', currentState: state, onRestore }),
      { wrapper },
    )

    // Revert to initial
    state = { ...initial }
    rerender()

    expect(removeSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))
    removeSpy.mockRestore()
  })
```

**Step 2: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEditorAutoSave.test.ts`
Expected: PASS (all 11 tests)

**Step 3: Commit**

```bash
git add frontend/src/hooks/__tests__/useEditorAutoSave.test.ts
git commit -m "test: add beforeunload listener tests"
```

---

### Task 4: Integrate hook into EditorPage

**Files:**
- Modify: `frontend/src/pages/EditorPage.tsx`

**Step 1: Write failing integration tests**

Add to `frontend/src/pages/__tests__/EditorPage.test.tsx`:

```ts
import userEvent from '@testing-library/user-event'

  // ... inside existing describe('EditorPage', () => { ... })

  it('shows recovery banner when draft exists', async () => {
    const draft = {
      body: '# Draft content',
      labels: ['swe'],
      isDraft: false,
      savedAt: '2026-02-20T15:45:00Z',
    }
    localStorage.setItem('agblogger:draft:new', JSON.stringify(draft))

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument()
  })

  it('restores draft content when Restore is clicked', async () => {
    const user = userEvent.setup()
    const draft = {
      body: '# Restored draft',
      labels: ['cs'],
      isDraft: true,
      savedAt: '2026-02-20T15:45:00Z',
    }
    localStorage.setItem('agblogger:draft:new', JSON.stringify(draft))

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /restore/i }))

    // Banner should disappear
    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument()

    // Body should be restored
    const textareas = document.querySelectorAll('textarea')
    const bodyTextarea = Array.from(textareas).find((t) => t.value.includes('# Restored draft'))
    expect(bodyTextarea).toBeTruthy()
  })

  it('dismisses banner and clears draft when Discard is clicked', async () => {
    const user = userEvent.setup()
    localStorage.setItem(
      'agblogger:draft:new',
      JSON.stringify({ body: '# Old', labels: [], isDraft: false, savedAt: '2026-02-20T15:45:00Z' }),
    )

    renderEditor('/editor/new')

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /discard/i })).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /discard/i }))

    expect(screen.queryByText(/unsaved changes/i)).not.toBeInTheDocument()
    expect(localStorage.getItem('agblogger:draft:new')).toBeNull()
  })

  it('shows dirty indicator when body is modified', async () => {
    const user = userEvent.setup()
    renderEditor('/editor/new')

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText('Save')).toBeInTheDocument()
    })

    // Type in textarea to make dirty
    const textareas = document.querySelectorAll('textarea')
    const bodyTextarea = textareas[0]!
    await user.type(bodyTextarea, ' extra text')

    await waitFor(() => {
      expect(screen.getByText(/\*/)).toBeInTheDocument()
    })
  })
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.tsx`
Expected: FAIL — recovery banner not rendered, dirty indicator not present

**Step 3: Integrate hook into EditorPage**

Modify `frontend/src/pages/EditorPage.tsx`:

1. Import the hook:
```ts
import { useEditorAutoSave } from '@/hooks/useEditorAutoSave'
import type { DraftData } from '@/hooks/useEditorAutoSave'
import { format, parseISO } from 'date-fns'
```

2. Inside `EditorPage()`, after the state declarations, add:
```ts
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
    useEditorAutoSave({ key: autoSaveKey, currentState, onRestore: handleRestore })
```

3. Add `useMemo` and `useCallback` to the import:
```ts
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
```

4. In `handleSave()`, after the navigate call on success, add `markSaved()`:
```ts
      markSaved()
      void navigate(`/post/${path}`)
```

5. Add the recovery banner JSX after the error banner and before the metadata panel:
```tsx
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
```

6. Add dirty indicator in the header — modify the title area between Back and Save:
```tsx
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
        {/* Save button unchanged */}
      </div>
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/pages/EditorPage.tsx frontend/src/pages/__tests__/EditorPage.test.tsx
git commit -m "feat: integrate auto-save hook into editor with recovery banner"
```

---

### Task 5: Verify full test suite and clean up

**Files:**
- No new files

**Step 1: Run full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS

**Step 2: Run type checking**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Run linting**

Run: `cd frontend && npx eslint src/`
Expected: No errors

**Step 4: Run `just check`**

Run: `just check`
Expected: All checks pass

**Step 5: Commit any fixes if needed, then final commit**

```bash
git add -A
git commit -m "chore: clean up editor auto-save implementation"
```

---

### Task 6: Browser test

**Files:**
- No file changes

**Step 1: Start dev server**

Run: `just start`

**Step 2: Browser test the following scenarios**

Use Playwright MCP to verify:

1. **New post editor**: Navigate to `/editor/new`, type some text, verify the dirty indicator (`*`) appears
2. **Auto-save**: Wait 3+ seconds after typing, verify localStorage has a `agblogger:draft:new` entry
3. **Recovery banner**: Refresh the page, verify the "You have unsaved changes" banner appears with Restore/Discard buttons
4. **Restore**: Click Restore, verify the draft content is loaded into the editor
5. **Discard**: Trigger the banner again, click Discard, verify the banner disappears and localStorage is cleared
6. **Save clears draft**: Make changes, wait for auto-save, click Save, verify localStorage is cleared
7. **Existing post**: Edit an existing post, verify auto-save uses the correct key (`agblogger:draft:posts/...`)

**Step 3: Stop dev server**

Run: `just stop`

**Step 4: Clean up screenshots**

Run: `rm -f *.png`
