# Review: Structured Front Matter Editor

**Date:** 2026-02-18
**Commits:** 291118f..76dcb20 (8 commits)
**Reviewers:** code-reviewer, pr-test-analyzer, silent-failure-hunter, comment-analyzer

## Files Changed

**Backend:**
- `backend/api/labels.py` — POST /api/labels endpoint
- `backend/api/posts.py` — GET /edit endpoint, rewritten create/update
- `backend/schemas/label.py` — LabelCreate with pattern validation
- `backend/schemas/post.py` — PostEditResponse, restructured PostCreate/PostUpdate
- `backend/services/label_service.py` — create_label function

**Frontend:**
- `frontend/src/api/client.ts` — PostEditResponse type
- `frontend/src/api/labels.ts` — createLabel function
- `frontend/src/api/posts.ts` — fetchPostForEdit, structured createPost/updatePost
- `frontend/src/components/editor/LabelInput.tsx` — new component
- `frontend/src/pages/EditorPage.tsx` — complete rewrite

**Tests:**
- `tests/test_api/test_api_integration.py` — 8 new tests, 5 updated
- `tests/test_services/test_config.py` — fixed pre-existing failure

**Docs:**
- `docs/ARCHITECTURE.md` — updated routes, data flows

---

## Critical Issues (3)

### 1. `create_label_endpoint` — unprotected filesystem write

**File:** `backend/api/labels.py:55-62`

`write_labels_config()` has no error handling. If it fails, the in-memory `content_manager.labels` dict is already mutated but the session is never committed. If it succeeds but `session.commit()` fails, `labels.toml` is out of sync with the database.

The post create/update endpoints already demonstrate the correct pattern (try/except with rollback). The label endpoint should follow the same pattern.

```python
# Current (no error handling):
labels[body.id] = LabelDef(id=body.id, names=[body.id])
write_labels_config(content_manager.content_dir, labels)
content_manager.reload_config()
await session.commit()

# Fix: wrap in try/except, work on a copy, rollback on failure
labels = dict(content_manager.labels)
if body.id not in labels:
    labels[body.id] = LabelDef(id=body.id, names=[body.id])
    try:
        write_labels_config(content_manager.content_dir, labels)
        content_manager.reload_config()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to persist label to filesystem")
await session.commit()
```

### 2. `LabelInput.fetchLabels` — empty catch block

**File:** `frontend/src/components/editor/LabelInput.tsx:23`

```typescript
fetchLabels().then(setAllLabels).catch(() => {})
```

Silently discards all errors. User sees an empty dropdown with no indication that labels failed to load. Should surface an error state.

### 3. `LabelInput.handleCreate` — catch-all treats every error as 409

**File:** `frontend/src/components/editor/LabelInput.tsx:69-71`

```typescript
} catch {
    // 409 = already exists, just add it
    addLabel(trimmed)
}
```

Network failures, 422 validation errors, and 500s are all treated as "label already exists". The label appears locally but may not exist on the server. Should check for `HTTPError` with status 409 specifically and handle other errors differently.

---

## Important Issues (6)

### 4. `LabelCreate` schema — unused `names` and `parents` fields

**File:** `backend/schemas/label.py:45-46`

The schema accepts `names` and `parents` fields but the endpoint and service ignore them. A client sending `{"id": "cooking", "names": ["Cooking"], "parents": ["food"]}` gets a 201 with none of those values applied. Either wire them through or remove them.

### 5. `EditorPage` useEffect — `user` dependency can reset body

**File:** `frontend/src/pages/EditorPage.tsx:33-58`

The `user` object is in the useEffect dependency array. If the auth store's user reference changes (e.g., token refresh), the effect re-fires and resets `body` to the template string, erasing the user's draft content. Remove `user` from the dependency array and compute `author` once at initialization.

```typescript
// Fix: compute author outside the effect
const initialAuthor = user?.display_name || user?.username || null

useEffect(() => {
    if (!isNew && filePath) {
      // ...fetch existing post...
    } else {
      setBody('# New Post\n\nStart writing here...\n')
      setAuthor(initialAuthor)
    }
  }, [filePath, isNew]) // remove user dependency
```

### 6. `update_post_endpoint` — silent fallback to `now_utc()`

**File:** `backend/api/posts.py:194-198`

If `content_manager.read_post(file_path)` returns `None`, `created_at` silently becomes "now" and author changes to the current user. This masks a data integrity issue (DB says post exists but filesystem disagrees). Should use DB cache values as fallback or log a warning.

### 7. `LabelCreate` docstring says "create or update"

**File:** `backend/schemas/label.py:42`

No update endpoint exists. Docstring should say `"""Request to create a new label."""`.

### 8. ARCHITECTURE.md lists `@uiw/react-md-editor`

**File:** `docs/ARCHITECTURE.md:68`

The editor now uses a plain `<textarea>`. The dependency reference is stale. Either update the row or remove it (and uninstall the unused dependency).

### 9. `serialize_post` has zero test coverage

**File:** `backend/filesystem/frontmatter.py:112-126`

This function is invoked on every create/update. No tests verify:
- Labels serialize with `#` prefix
- `draft: true` appears when `is_draft=True`
- Author is included when present, omitted when `None`
- Timestamps round-trip correctly through format/parse

---

## Suggestions (6)

### 10. No create-then-edit round-trip test

The test creates a structured post but never retrieves it via `/edit` to verify labels, draft status, author, and body survive the write-to-disk-then-read-back pipeline.

### 11. No test creates a post with `is_draft: True`

Every test sends `is_draft: False`. If the `serialize_post` conditional for `draft: true` breaks, draft posts become published.

### 12. No test for invalid label ID rejection

`LabelCreate.id` has pattern `^[a-z0-9][a-z0-9-]*$` but no test sends uppercase, special characters, or leading hyphens to verify 422 rejection.

### 13. `handlePreview` bare catch discards error context

**File:** `frontend/src/pages/EditorPage.tsx:95`

Should distinguish 401 (session expired) from other errors. Currently shows generic "Preview failed" for everything.

### 14. `handleSave` hides 422 validation details

**File:** `frontend/src/pages/EditorPage.tsx:77`

Pydantic validation errors return field-level details in the response body, but the catch block never reads them. User sees "Failed to save post" with no indication of what's wrong with their input.

### 15. ARCHITECTURE.md data flow conflates create vs update author handling

The "Creating/Updating a Post" flow says "Backend sets author from authenticated user" but updates preserve the original author from the filesystem. Should distinguish the two cases.

---

## Strengths

- Clean separation: backend owns all YAML serialization, frontend never touches front matter
- Full ARIA accessibility on LabelInput with combobox pattern and keyboard navigation
- All interactive controls properly disabled during async operations via `busy` state
- Post endpoints follow correct try/except + rollback pattern for filesystem writes
- Good test coverage of happy paths and auth requirements for new endpoints
- Pydantic schema docstrings and Field constraints are well-applied
- ARCHITECTURE.md properly updated with new endpoints and data flow sections
- `test_config.py` fix prevents `.env` from polluting test assertions
