# CodeRabbit Code Review

**Date:** 2026-02-20
**Scope:** Last 5 commits (editor auto-save feature) + full codebase scan
**Tool:** CodeRabbit CLI v0.3.5

## Critical — Security & Bugs (5)

### 1. Path traversal in sync download URL — ALREADY FIXED

**File:** `cli/sync_client.py:162-167`

`_download_file()` already validates via `_is_safe_local_path()` which resolves the path and checks `is_relative_to()`. Merge-result downloads (line 295) also validate. No action needed.

### 2. Hardcoded default credentials — ALREADY FIXED

**File:** `cli/sync_client.py:435-439`

Credentials are fetched from args/config with no hardcoded defaults. Missing credentials produce a clear error and `sys.exit(1)`. No action needed.

### 3. Cross-post history endpoint lacks authentication — ALREADY FIXED

**File:** `backend/api/crosspost.py:141`

The endpoint already has `user: Annotated[User, Depends(require_auth)]`. No action needed.

### 4. Unhandled ValueError in user_id parsing — ALREADY FIXED

**File:** `backend/api/deps.py:64-67`

The code already validates `user_id` with `isinstance` and `isdigit()` checks before calling `int()`. No action needed.

### 5. Incorrect ky retry pattern in token refresh — ALREADY FIXED

**File:** `frontend/src/api/client.ts:56-76`

The code already uses `X-Auth-Retry` header guard, `new Headers(request.headers)`, `new Request(request, { headers })`, and `retry: 0`. No action needed.

## Important — Code Quality (12)

### 6. TypeError if body.parents is None in label endpoints — NOT A BUG

**File:** `backend/api/labels.py:89, 135`

`body.parents` has `default_factory=list` in the Pydantic schema, so it is always a list, never None. No action needed.

### 7. Blocking subprocess in async context — ALREADY FIXED

**File:** `backend/pandoc/renderer.py:14-20`

`render_markdown()` is already async and delegates to `_render_markdown_sync()` via `asyncio.to_thread()`. No action needed.

### 8. Unused _fallback_render function — NEEDS FIX

**File:** `backend/pandoc/renderer.py:81-169`

`_fallback_render` and `_inline_format` are defined but never called. Dead code should be removed.

### 9. Confusing label source logic with inner import — ALREADY FIXED

**File:** `backend/services/cache_service.py:11, 126-127`

`get_directory_labels` is imported at module level (line 11). Source logic is clean: `"directory" if label_id in dir_labels else "frontmatter"`. No action needed.

### 10. LabelCreate.names accepts empty list — BY DESIGN

**File:** `backend/schemas/label.py:52`

When `names` is empty, the create endpoint uses the label ID as the default display name (`body.names if body.names else [body.id]` at `labels.py:106`). This is intentional — labels always get a display name. No action needed.

### 11. SyncClient never closes httpx.Client — ALREADY FIXED

**File:** `cli/sync_client.py:97-105`

`SyncClient` already has `close()`, `__enter__`, and `__exit__`. The `main()` function uses `with SyncClient(...) as client:`. No action needed.

### 12. Search results persist when query is cleared — ALREADY FIXED

**File:** `frontend/src/pages/SearchPage.tsx:29-32`

The effect already calls `setResults([])` and `setError(null)` when query is empty. No action needed.

### 13. loadError cannot be cleared on success — NEEDS FIX

**File:** `frontend/src/components/editor/LabelInput.tsx:24-28`

Once `loadError` is set to true, successful fetches or label creates don't clear it. The error message persists incorrectly.

### 14. Missing null check in LabelGraphPage onConnect — ALREADY FIXED

**File:** `frontend/src/pages/LabelGraphPage.tsx:272`

`onConnect` already checks `if (!connection.source || !connection.target) return`. No action needed.

### 15. Missing initialAuthor in useEffect dependencies — ALREADY FIXED

**File:** `frontend/src/pages/EditorPage.tsx:87-91`

Author is set in a separate `useEffect` with proper deps `[isNew, user?.display_name, user?.username]`. No eslint-disable comment present. No action needed.

### 16. Filesystem write before session.commit() — BY DESIGN

**File:** `backend/api/labels.py:37-57`

The filesystem is the source of truth; the DB is a regenerable cache. Writing TOML first then committing DB is correct — if DB commit fails, the rollback is handled, and the next cache rebuild regenerates from filesystem. No action needed.

### 17. Edge case in Mastodon excerpt truncation — ALREADY FIXED

**File:** `backend/crosspost/mastodon.py:33-34`

The code already guards `if available <= 3:` with `excerpt[:max(available, 0)]`. No action needed.

## Suggestions — Minor (4)

### 18. Documentation inaccuracy: pypandoc vs subprocess — NEEDS FIX

**File:** `docs/ARCHITECTURE.md:48`

States "Pandoc (via pypandoc)" but the implementation uses `subprocess.run` directly.

### 19. Overlay Link missing accessible name — ALREADY FIXED

**File:** `frontend/src/pages/LabelsPage.tsx:112`

The overlay `<Link>` already has `aria-label={...}`. No action needed.

### 20. Catch blocks discard error details — ALREADY FIXED

**Files:** `frontend/src/pages/TimelinePage.tsx:63-64`, `frontend/src/pages/SearchPage.tsx:40-41`

Both already capture the error and call `console.error()`. No action needed.

### 21. List numbering gap in history.md — NEEDS FIX

**File:** `docs/history.md:23-25`

Numbered list jumps from 8 to 10, skipping 9.

## Summary

| Status | Count |
|--------|-------|
| Already fixed | 15 |
| By design | 2 |
| Needs fix | 4 |

**Remaining fixes:** Issues 8, 13, 18, 21.
