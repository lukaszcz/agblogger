# Editor Auto-Save & Unsaved Changes Warning

## Problem

Users can lose work when they navigate away from the editor without saving. There is no warning on navigation and no automatic draft persistence.

## Solution

A `useEditorAutoSave` hook that provides:
1. Dirty-tracking by comparing current form state to the initial/loaded state
2. Debounced auto-save to localStorage (3s after last change)
3. Native browser `beforeunload` dialog when dirty (covers tab close/refresh)
4. react-router `useBlocker` with `window.confirm()` for in-app navigation
5. Recovery banner when returning to a post with a stale auto-saved draft

## Storage

**localStorage key**: `agblogger:draft:<filePath>` for existing posts, `agblogger:draft:new` for new posts.

**Stored value**:
```ts
interface DraftData {
  body: string;
  labels: string[];
  isDraft: boolean;
  newPath?: string;
  savedAt: string;  // ISO timestamp
}
```

Draft lifecycle:
- Written to localStorage 3s after last form change
- Cleared on successful server save
- Cleared when user clicks "Discard" on recovery banner

## Hook Interface

```ts
function useEditorAutoSave(params: {
  key: string;
  currentState: DraftData;
  onRestore: (draft: DraftData) => void;
}) => {
  isDirty: boolean;
  draftAvailable: boolean;
  draftSavedAt: string | null;
  restoreDraft: () => void;
  discardDraft: () => void;
  markSaved: () => void;
}
```

### Behavior

1. On mount, check localStorage for existing draft; set `draftAvailable` and `draftSavedAt`
2. Capture `currentState` as `initialState` ref on first render
3. Compute `isDirty` by deep-comparing `currentState` to `initialState`
4. When dirty, debounce (3s) writes to localStorage
5. When dirty, register `beforeunload` listener
6. When dirty, activate react-router `useBlocker`
7. `restoreDraft()`: calls `onRestore(draft)`, updates `initialState`, clears `draftAvailable`
8. `discardDraft()`: removes localStorage entry, clears `draftAvailable`
9. `markSaved()`: removes localStorage entry, updates `initialState`, resets `isDirty`

## UI Changes

**Recovery banner**: Info bar at top of editor form:
> "You have unsaved changes from Feb 20 at 3:45 PM. Restore | Discard"

**Dirty indicator**: Asterisk in page title (e.g., "Edit Post *") when form has unsaved changes.

**Navigation blocking**: Native browser dialog for both tab close and in-app navigation.

## Testing

### Hook tests
- `isDirty` computed correctly on form state changes
- Debounced localStorage writes (mock timers)
- Draft detection on mount
- `restoreDraft()` calls `onRestore` and resets dirty state
- `discardDraft()` clears localStorage
- `markSaved()` clears localStorage and resets dirty
- `beforeunload` registered when dirty, unregistered when clean

### EditorPage integration tests
- Recovery banner renders and responds to Restore/Discard
- Dirty indicator appears on form modification
