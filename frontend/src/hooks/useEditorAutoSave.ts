import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useBlocker } from 'react-router-dom'

const AUTO_SAVE_DEBOUNCE_MS = 3000

export interface DraftData {
  title: string
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
  enabled?: boolean
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
  if (a.title !== b.title) return false
  if (a.body !== b.body) return false
  if (a.isDraft !== b.isDraft) return false
  if (a.labels.length !== b.labels.length) return false
  for (let i = 0; i < a.labels.length; i++) {
    if (a.labels[i] !== b.labels[i]) return false
  }
  if (a.newPath !== b.newPath) return false
  return true
}

function readDraft(key: string): DraftData | null {
  try {
    const stored = localStorage.getItem(key)
    if (stored) {
      const parsed = JSON.parse(stored) as DraftData
      // Ensure title exists for drafts saved before the title field was added
      parsed.title = parsed.title ?? ''
      return parsed
    }
  } catch {
    // Ignore invalid JSON
  }
  return null
}

export function useEditorAutoSave({
  key,
  currentState,
  onRestore,
  enabled = true,
}: UseEditorAutoSaveParams): UseEditorAutoSaveReturn {
  // Use state (not ref) so changes trigger isDirty recalculation
  const [savedState, setSavedState] = useState<DraftData>(currentState)

  const onRestoreRef = useRef(onRestore)
  useEffect(() => {
    onRestoreRef.current = onRestore
  }, [onRestore])

  // Keep a ref to currentState so markSaved always has the latest value
  const currentStateRef = useRef(currentState)
  useEffect(() => {
    currentStateRef.current = currentState
  }, [currentState])

  // Track enabled transitions: when enabled becomes true, capture current state as baseline
  const prevEnabledRef = useRef(enabled)
  useEffect(() => {
    if (enabled && !prevEnabledRef.current) {
      setSavedState(currentStateRef.current)
    }
    prevEnabledRef.current = enabled
  }, [enabled])

  // Draft recovery: read from localStorage synchronously on init
  const [initialDraft] = useState(() => readDraft(key))
  const draftDataRef = useRef<DraftData | null>(initialDraft)
  const [draftAvailable, setDraftAvailable] = useState(initialDraft !== null)
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(
    initialDraft?.savedAt ?? null,
  )

  const isDirty = useMemo(
    () => enabled && !statesEqual(currentState, savedState),
    [enabled, currentState, savedState],
  )

  // Debounced auto-save to localStorage
  useEffect(() => {
    if (!isDirty) return

    const timer = setTimeout(() => {
      const toSave: DraftData = {
        ...currentState,
        savedAt: new Date().toISOString(),
      }
      localStorage.setItem(key, JSON.stringify(toSave))
    }, AUTO_SAVE_DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [isDirty, currentState, key])

  // beforeunload handler
  useEffect(() => {
    if (!isDirty) return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isDirty])

  // react-router navigation blocking
  const blocker = useBlocker(isDirty)

  useEffect(() => {
    if (blocker.state === 'blocked') {
      const leave = window.confirm('You have unsaved changes. Are you sure you want to leave?')
      if (leave) {
        blocker.proceed()
      } else {
        blocker.reset()
      }
    }
  }, [blocker])

  const restoreDraft = useCallback(() => {
    if (draftDataRef.current) {
      onRestoreRef.current(draftDataRef.current)
      setSavedState(draftDataRef.current)
    }
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [])

  const discardDraft = useCallback(() => {
    localStorage.removeItem(key)
    draftDataRef.current = null
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [key])

  const markSaved = useCallback(() => {
    localStorage.removeItem(key)
    setSavedState(currentStateRef.current)
    draftDataRef.current = null
    setDraftAvailable(false)
    setDraftSavedAt(null)
  }, [key])

  return {
    isDirty,
    draftAvailable,
    draftSavedAt,
    restoreDraft,
    discardDraft,
    markSaved,
  }
}
